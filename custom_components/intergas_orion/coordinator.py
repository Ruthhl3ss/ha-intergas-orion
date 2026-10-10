"""Data update coordinator for Intergas Orion."""
from __future__ import annotations

from datetime import timedelta
import logging
from time import monotonic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IntergasApiError, IntergasAuthError, IntergasOrionClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Statistics, weather, presets and week schemes change slowly, so they are
# fetched less often than the heater and zone state.
SLOW_INTERVAL = 300  # seconds


class IntergasCoordinator(DataUpdateCoordinator):
    """Fetches all heaters + their zones once per interval.

    data shape: {heater_id: {
        "heater": <dict>, "zones": [<dict>, ...],
        "statistics": <dict>, "weather": <dict>, "presets": [<dict>, ...],
        "schemes": {zone_number: <dict>}, "parameters": {title: <dict>},
    }}
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: IntergasOrionClient
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.entry = entry
        self._slow_due = 0.0

    def schedule_slow_refresh(self) -> None:
        """Re-read the slow-changing data on the next update (after a write)."""
        self._slow_due = 0.0

    async def _optional(self, coro, default):
        """Fetch data that not every installation has; keep going if it fails."""
        try:
            return await coro
        except IntergasApiError as err:
            _LOGGER.debug("Optional fetch failed: %s", err)
            return default

    async def _async_update_data(self) -> dict:
        previous = self.data or {}
        fetch_slow = monotonic() >= self._slow_due
        try:
            heaters = await self.client.get_heaters()
            result: dict[str, dict] = {}
            for heater in heaters:
                hid = heater.get("heater_id")
                if not hid:
                    continue
                zones = await self.client.get_zones(hid)
                bundle = {
                    "heater": heater,
                    "zones": zones,
                    "statistics": {},
                    "weather": {},
                    "presets": [],
                    "schemes": {},
                    "parameters": {},
                }
                old = previous.get(hid, {})
                if fetch_slow:
                    c = self.client
                    bundle["statistics"] = await self._optional(c.get_statistics(hid), {})
                    bundle["weather"] = await self._optional(c.get_weather(hid), {})
                    bundle["presets"] = await self._optional(c.get_presets(hid), [])
                    bundle["parameters"] = {
                        p["title"]: p
                        for p in await self._optional(c.get_parameters(hid), [])
                        if isinstance(p, dict) and p.get("title")
                    }
                    for zone in zones:
                        n = zone.get("zone_number")
                        if n is not None:
                            bundle["schemes"][n] = await self._optional(
                                c.get_week_scheme(hid, n), {}
                            )
                else:
                    for key in ("statistics", "weather", "presets", "schemes", "parameters"):
                        if key in old:
                            bundle[key] = old[key]
                result[hid] = bundle
        except IntergasAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except IntergasApiError as err:
            raise UpdateFailed(str(err)) from err
        if fetch_slow:
            self._slow_due = monotonic() + SLOW_INTERVAL
        return result

"""Data update coordinator for Intergas Orion."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IntergasApiError, IntergasAuthError, IntergasOrionClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IntergasCoordinator(DataUpdateCoordinator):
    """Fetches all heaters + their zones once per interval.

    data shape: {heater_id: {"heater": <dict>, "zones": [<dict>, ...]}}
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: IntergasOrionClient
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict:
        try:
            heaters = await self.client.get_heaters()
            result: dict[str, dict] = {}
            for heater in heaters:
                hid = heater.get("heater_id")
                if not hid:
                    continue
                zones = await self.client.get_zones(hid)
                result[hid] = {"heater": heater, "zones": zones}
            return result
        except IntergasAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except IntergasApiError as err:
            raise UpdateFailed(str(err)) from err

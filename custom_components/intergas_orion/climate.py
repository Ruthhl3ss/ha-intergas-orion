"""Climate platform for Intergas Orion — one entity per zone."""
from __future__ import annotations

from time import monotonic

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import IntergasApiError
from .const import (
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    MODE_HOLIDAY,
    MODE_STANDBY,
    MODE_WEEK,
)
from .coordinator import IntergasCoordinator

# Seconds to wait before re-reading after a write, and to keep showing the
# requested setpoint if the cloud has not reported it yet.
CONFIRM_DELAY = 15
PENDING_TIMEOUT = 120


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: IntergasCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for hid, bundle in coordinator.data.items():
        for zone in bundle["zones"]:
            if "zone_number" in zone:
                entities.append(
                    IntergasZoneClimate(coordinator, hid, zone["zone_number"])
                )
    async_add_entities(entities)


class IntergasZoneClimate(CoordinatorEntity[IntergasCoordinator], ClimateEntity):
    """A heating zone exposed as a climate entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: IntergasCoordinator, heater_id: str, zone_number: int):
        super().__init__(coordinator)
        self._heater_id = heater_id
        self._zone_number = zone_number
        self._attr_unique_id = f"{heater_id}_zone{zone_number}"
        # The API accepts a setpoint with 202 and applies it asynchronously via the
        # gateway, so show the requested value until the cloud reports it.
        self._pending_target: float | None = None
        self._pending_until = 0.0

    # --- data accessors ---------------------------------------------------
    @property
    def _heater(self) -> dict:
        return self.coordinator.data.get(self._heater_id, {}).get("heater", {})

    @property
    def _zone(self) -> dict:
        for z in self.coordinator.data.get(self._heater_id, {}).get("zones", []):
            if z["zone_number"] == self._zone_number:
                return z
        return {}

    @property
    def name(self) -> str | None:
        return self._zone.get("name") or f"Zone {self._zone_number}"

    @property
    def device_info(self) -> DeviceInfo:
        hw = self._heater.get("hardware", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._heater_id)},
            manufacturer="Intergas",
            name=self._heater.get("name", "Intergas boiler"),
            model=hw.get("type"),
            serial_number=hw.get("serial_number"),
            sw_version=hw.get("firmware_version"),
        )

    @property
    def available(self) -> bool:
        return super().available and bool(self._zone)

    @property
    def current_temperature(self) -> float | None:
        return self._zone.get("temperature_room")

    @property
    def target_temperature(self) -> float | None:
        reported = self._zone.get("temperature_heater_setpoint")
        if self._pending_target is not None:
            if reported == self._pending_target or monotonic() > self._pending_until:
                self._pending_target = None
            else:
                return self._pending_target
        return reported

    @property
    def hvac_mode(self) -> HVACMode:
        mode = self._heater.get("state", {}).get("mode")
        if mode == MODE_STANDBY:
            return HVACMode.OFF
        if mode in (MODE_WEEK, MODE_HOLIDAY):
            return HVACMode.AUTO
        return HVACMode.HEAT  # RUNNING_MANUAL_TEMPERATURE

    @property
    def hvac_modes(self) -> list[HVACMode]:
        # Changing the mode is not implemented yet, so only offer the current one.
        return [self.hvac_mode]

    @property
    def hvac_action(self) -> HVACAction:
        if self._heater.get("state", {}).get("mode") == MODE_STANDBY:
            return HVACAction.OFF
        if self._heater.get("state", {}).get("is_heating"):
            return HVACAction.HEATING
        return HVACAction.IDLE

    # --- commands ---------------------------------------------------------
    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        try:
            await self.coordinator.client.set_zone_temperature(
                self._heater_id, self._zone_number, temperature
            )
        except IntergasApiError as err:
            raise HomeAssistantError(f"Setting the temperature failed: {err}") from err
        self._pending_target = round(float(temperature), 1)
        self._pending_until = monotonic() + PENDING_TIMEOUT
        self.async_write_ha_state()
        self.async_on_remove(
            async_call_later(self.hass, CONFIRM_DELAY, self._confirm_refresh)
        )

    async def _confirm_refresh(self, _now) -> None:
        await self.coordinator.async_request_refresh()

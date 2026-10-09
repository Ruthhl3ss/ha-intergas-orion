"""Number entities for Intergas Orion: the temperature of each preset."""
from __future__ import annotations

from time import monotonic

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import IntergasApiError
from .climate import preset_label
from .const import DOMAIN, MAX_TEMP, MIN_TEMP
from .coordinator import IntergasCoordinator
from .entity import IntergasEntity

PENDING_TIMEOUT = 180


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: IntergasCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntergasPresetTemperature(coordinator, hid, preset["preset_id"])
        for hid, bundle in coordinator.data.items()
        for preset in bundle.get("presets", [])
        if preset.get("preset_id")
    )


class IntergasPresetTemperature(IntergasEntity, NumberEntity):
    """The temperature of one preset (used by the week schedule)."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: IntergasCoordinator, heater_id: str, preset_id: str):
        super().__init__(coordinator, heater_id)
        self._preset_id = preset_id
        self._attr_unique_id = f"{heater_id}_preset_{preset_id}"
        self._pending: float | None = None
        self._pending_until = 0.0

    @property
    def _preset(self) -> dict:
        return next(
            (p for p in self._bundle.get("presets", []) if p.get("preset_id") == self._preset_id),
            {},
        )

    @property
    def name(self) -> str:
        return f"{preset_label(self._preset)} preset temperature"

    @property
    def available(self) -> bool:
        return super().available and bool(self._preset)

    @property
    def native_value(self) -> float | None:
        reported = self._preset.get("temperature")
        if self._pending is not None:
            if reported == self._pending or monotonic() > self._pending_until:
                self._pending = None
            else:
                return self._pending
        return reported

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.client.set_preset_temperature(
                self._heater_id, self._preset_id, value
            )
        except IntergasApiError as err:
            raise HomeAssistantError(f"Changing the preset failed: {err}") from err
        self._pending = round(float(value), 1)
        self._pending_until = monotonic() + PENDING_TIMEOUT
        self.coordinator.schedule_slow_refresh()
        self.async_write_ha_state()

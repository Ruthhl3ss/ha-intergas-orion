"""Diagnostic sensors for Intergas Orion."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntergasCoordinator


@dataclass(frozen=True, kw_only=True)
class IntergasSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], float | int | str | None]


# Each reads from the heater dict. Sensors are only created when the field is
# present, since not every boiler model reports pressure or CH temperature.
SENSORS: tuple[IntergasSensorDescription, ...] = (
    IntergasSensorDescription(
        key="heater_rssi",
        translation_key="heater_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda h: h.get("radio_frequency_performance", {}).get("heater_rssi"),
    ),
    IntergasSensorDescription(
        key="gateway_rssi",
        translation_key="gateway_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda h: h.get("radio_frequency_performance", {}).get("gateway_rssi"),
    ),
    IntergasSensorDescription(
        key="ch_water_pressure",
        translation_key="ch_water_pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda h: h.get("ch_water_pressure"),
    ),
    IntergasSensorDescription(
        key="ch_temperature",
        translation_key="ch_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda h: h.get("ch_temperature"),
    ),
    IntergasSensorDescription(
        key="lockout_code",
        translation_key="lockout_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda h: h.get("state", {}).get("current_lockout_code"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: IntergasCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for hid, bundle in coordinator.data.items():
        for desc in SENSORS:
            if desc.value_fn(bundle["heater"]) is not None:
                entities.append(IntergasSensor(coordinator, hid, desc))
    async_add_entities(entities)


class IntergasSensor(CoordinatorEntity[IntergasCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: IntergasSensorDescription

    def __init__(self, coordinator, heater_id: str, desc: IntergasSensorDescription):
        super().__init__(coordinator)
        self._heater_id = heater_id
        self.entity_description = desc
        self._attr_unique_id = f"{heater_id}_{desc.key}"

    @property
    def _heater(self) -> dict:
        return self.coordinator.data.get(self._heater_id, {}).get("heater", {})

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._heater_id)})

    @property
    def native_value(self):
        return self.entity_description.value_fn(self._heater)

"""Diagnostics for Intergas Orion: a redacted snapshot to attach to issues."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import redact
from .coordinator import IntergasCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return everything the integration read from the cloud, minus identifiers.

    Heater ids are replaced by "heater_1", "heater_2", ...; ids, serial numbers,
    names, the email address and the password are removed.
    """
    coordinator: IntergasCoordinator = entry.runtime_data
    return {
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "heaters": {
            f"heater_{n}": redact(bundle)
            for n, bundle in enumerate((coordinator.data or {}).values(), start=1)
        },
    }

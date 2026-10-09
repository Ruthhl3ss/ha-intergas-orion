"""Shared fixtures for the Intergas Orion tests."""
from aioresponses import aioresponses
import pytest

API = "https://app-api.orion.intergas.nl"
AID = "acc-1"
HID = "heater-1"

HEATER = {
    "heater_id": HID,
    "name": "Boiler",
    "state": {"mode": "RUNNING_MANUAL_TEMPERATURE", "is_heating": True, "current_lockout_code": 0},
    "hardware": {"type": "Xtreme", "serial_number": "SN-TEST", "firmware_version": "2.00"},
    "number_of_zones": 1,
    "radio_frequency_performance": {"gateway_rssi": -60, "heater_rssi": -55},
}
ZONE = {"zone_number": 1, "name": "Zone A", "temperature_room": 19.8, "temperature_heater_setpoint": 20.0}
STATISTICS = {"ch_gas_consumption": 2.5, "dhw_gas_consumption": 80.25, "ch_gas_operational_hours": 2,
              "dhw_gas_operational_hours": 35, "device_poweron_hours": 2584, "ch_water_pressure": 1.57}
WEATHER = {"conditions": "BROKEN_CLOUDS", "nighttime": False, "temperature": 16.9}
PRESETS = [
    {"name": "DEFAULT_STANDBY", "temperature": 17.5, "color": "COLOR_STANDBY", "type": "STANDBY", "preset_id": "p-away"},
    {"name": "Comfort", "temperature": 21.5, "color": "COLOR_YELLOW", "type": "COMFORT", "preset_id": "p-comfort"},
    {"name": "Home", "temperature": 20.0, "color": "COLOR_WHITE", "type": "CUSTOM", "preset_id": "p-home"},
]
DAY = [{"time": "07:00", "linked_preset_id": "p-home"}, {"time": "22:30", "linked_preset_id": "p-away"}]
SCHEME = {
    "schedule_enabled": False,
    "adaptive_schedule_enabled": True,
    "timetable": {d: DAY for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")},
    "adaptive_time": 15,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def api():
    with aioresponses() as mock:
        yield mock


def mock_cloud(mock, *, jwt="jwt-1", repeat=True, heater=None, extras=True):
    mock.post(f"{API}/v1/accounts/platform_check", payload={"platform": "ARCH_2_0"}, repeat=repeat)
    mock.post(f"{API}/v1/accounts/authenticate", payload={"jwt": jwt, "account_id": AID}, repeat=repeat)
    base = f"{API}/v1/accounts/{AID}/heaters/{HID}"
    mock.get(f"{API}/v1/accounts/{AID}/heaters", payload=[heater or HEATER], repeat=repeat)
    mock.get(f"{base}/zones", payload=[ZONE], repeat=repeat)
    if extras:
        mock.get(f"{base}/statistics", payload=STATISTICS, repeat=repeat)
        mock.get(f"{base}/weather", payload=WEATHER, repeat=repeat)
        mock.get(f"{base}/presets", payload=PRESETS, repeat=repeat)
        mock.get(f"{base}/zones/1/scheme/week", payload=SCHEME, repeat=repeat)
    else:
        for path in ("statistics", "weather", "presets", "zones/1/scheme/week"):
            mock.get(f"{base}/{path}", status=404, repeat=repeat)

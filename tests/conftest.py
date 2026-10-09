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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def api():
    with aioresponses() as mock:
        yield mock


def mock_cloud(mock, *, jwt="jwt-1", repeat=True):
    mock.post(f"{API}/v1/accounts/platform_check", payload={"platform": "ARCH_2_0"}, repeat=repeat)
    mock.post(f"{API}/v1/accounts/authenticate", payload={"jwt": jwt, "account_id": AID}, repeat=repeat)
    mock.get(f"{API}/v1/accounts/{AID}/heaters", payload=[HEATER], repeat=repeat)
    mock.get(f"{API}/v1/accounts/{AID}/heaters/{HID}/zones", payload=[ZONE], repeat=repeat)

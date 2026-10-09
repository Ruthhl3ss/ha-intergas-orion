"""Tests for the Intergas Orion integration against a mocked cloud API."""
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.intergas_orion.const import DOMAIN

from .conftest import AID, API, HID, mock_cloud

CREDS = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=CREDS, unique_id=AID)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_success(hass: HomeAssistant, api) -> None:
    mock_cloud(api)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == AID


async def test_config_flow_wrong_platform(hass: HomeAssistant, api) -> None:
    api.post(f"{API}/v1/accounts/platform_check", payload={"platform": "ARCH_1_0"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["errors"] == {"base": "wrong_platform"}


async def test_config_flow_invalid_auth(hass: HomeAssistant, api) -> None:
    api.post(f"{API}/v1/accounts/platform_check", payload={"platform": "ARCH_2_0"})
    api.post(f"{API}/v1/accounts/authenticate", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_cannot_connect(hass: HomeAssistant, api) -> None:
    api.post(f"{API}/v1/accounts/platform_check", status=500)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDS)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_entities(hass: HomeAssistant, api) -> None:
    mock_cloud(api)
    await _setup(hass)
    climates = hass.states.async_all("climate")
    assert len(climates) == 1
    state = climates[0]
    assert state.state == "heat"
    assert state.attributes["current_temperature"] == 19.8
    assert state.attributes["temperature"] == 20.0
    assert state.attributes["hvac_action"] == "heating"
    assert state.attributes["hvac_modes"] == ["heat"]
    # No request may ever go to an un-substituted account path.
    assert not any("None" in str(url) or "{aid}" in str(url) for _, url in api.requests)


async def test_set_temperature(hass: HomeAssistant, api) -> None:
    mock_cloud(api)
    zone_url = f"{API}/v1/accounts/{AID}/heaters/{HID}/zones/1"
    api.patch(zone_url, status=202, body=b"")
    await _setup(hass)
    entity_id = hass.states.async_all("climate")[0].entity_id
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": entity_id, "temperature": 21.5}, blocking=True
    )
    calls = api.requests[("PATCH", URL(zone_url))]
    assert calls[0].kwargs["json"] == {"target_temperature": 21.5}
    assert calls[0].kwargs["headers"]["Authorization"] == "Bearer jwt-1"
    # The cloud applies it asynchronously (202): keep showing the requested value.
    assert hass.states.get(entity_id).attributes["temperature"] == 21.5


async def test_pending_setpoint_expires(hass: HomeAssistant, api, freezer) -> None:
    """If the cloud never reports the new setpoint, fall back to the reported one."""
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from custom_components.intergas_orion import climate

    mock_cloud(api)
    api.patch(f"{API}/v1/accounts/{AID}/heaters/{HID}/zones/1", status=202, body=b"")
    await _setup(hass)
    entity_id = hass.states.async_all("climate")[0].entity_id
    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": entity_id, "temperature": 23}, blocking=True
    )
    assert hass.states.get(entity_id).attributes["temperature"] == 23
    # freezegun swaps monotonic for a date-based clock, so use inf for "past the timeout".
    climate.monotonic = lambda: float("inf")
    try:
        freezer.tick(timedelta(seconds=climate.CONFIRM_DELAY + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).attributes["temperature"] == 20.0
    finally:
        from time import monotonic

        climate.monotonic = monotonic


async def test_token_expiry_reauths(hass: HomeAssistant, api) -> None:
    """A 401 on a data call triggers one fresh login and a retry."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from custom_components.intergas_orion.api import IntergasOrionClient

    api.post(f"{API}/v1/accounts/authenticate", payload={"jwt": "old", "account_id": AID})
    api.post(f"{API}/v1/accounts/authenticate", payload={"jwt": "new", "account_id": AID})
    heaters = f"{API}/v1/accounts/{AID}/heaters"
    api.get(heaters, status=401)
    api.get(heaters, payload=[{"heater_id": HID}])
    client = IntergasOrionClient(async_get_clientsession(hass), "u@example.com", "pw")
    assert await client.get_heaters() == [{"heater_id": HID}]
    calls = api.requests[("GET", URL(heaters))]
    assert [c.kwargs["headers"]["Authorization"] for c in calls] == ["Bearer old", "Bearer new"]


async def test_bad_password_starts_reauth(hass: HomeAssistant, api) -> None:
    api.post(f"{API}/v1/accounts/authenticate", status=401, repeat=True)
    entry = MockConfigEntry(domain=DOMAIN, data=CREDS, unique_id=AID)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == config_entries.SOURCE_REAUTH for f in flows)


async def test_unload(hass: HomeAssistant, api) -> None:
    mock_cloud(api)
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_options_scan_interval(hass: HomeAssistant, api) -> None:
    from datetime import timedelta

    mock_cloud(api)
    entry = await _setup(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.update_interval == timedelta(seconds=30)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 20}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.update_interval == timedelta(seconds=20)

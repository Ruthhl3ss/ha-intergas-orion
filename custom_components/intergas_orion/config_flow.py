"""Config flow for Intergas Orion."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import IntergasApiError, IntergasAuthError, IntergasOrionClient
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class IntergasOrionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Intergas Orion."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return IntergasOrionOptionsFlow()

    async def _validate(
        self, email: str, password: str
    ) -> tuple[IntergasOrionClient, dict[str, str]]:
        session = async_get_clientsession(self.hass)
        client = IntergasOrionClient(session, email, password)
        errors: dict[str, str] = {}
        try:
            if await client.platform() != "ARCH_2_0":
                errors["base"] = "wrong_platform"
            else:
                await client.authenticate()
        except IntergasAuthError:
            errors["base"] = "invalid_auth"
        except IntergasApiError:
            errors["base"] = "cannot_connect"
        return client, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            client, errors = await self._validate(email, user_input[CONF_PASSWORD])
            if not errors:
                await self.async_set_unique_id(client.account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Intergas ({email})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            email = entry.data[CONF_EMAIL]
            _, errors = await self._validate(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
        )


class IntergasOrionOptionsFlow(OptionsFlow):
    """Options: how often to poll the cloud."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )

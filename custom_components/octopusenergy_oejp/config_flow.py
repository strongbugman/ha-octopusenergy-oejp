"""Config flow skeleton for Octopus Energy OEJP."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_AUTH_PATH, CONF_BASE_URL, CONF_EMAIL, DEFAULT_BASE_URL, DEFAULT_NAME, DOMAIN


class OctopusOejpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Collect credentials for a later full Home Assistant implementation."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Optional(CONF_AUTH_PATH): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

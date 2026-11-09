"""Config flow for the EVO-START integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .coordinator import AuthenticationError, EvoStartCoordinator

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)


class EvoStartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            for entry in self._async_current_entries(include_ignore=False):
                if entry.data.get(CONF_EMAIL, "").strip().lower() == email.lower():
                    return self.async_abort(reason="already_configured")

            try:
                await EvoStartCoordinator(self.hass, None, email, user_input[CONF_PASSWORD]).login()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except UpdateFailed:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during EVO-START login")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="EVO-START",
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

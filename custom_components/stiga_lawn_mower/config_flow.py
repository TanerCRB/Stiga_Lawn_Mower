"""Config flow for Stiga integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import StigaAuth, StigaAuthError, StigaRestClient
from .const import CONF_BASE_LATITUDE, CONF_BASE_LONGITUDE, CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _opt_float(val: object) -> float | None:
    """Accept a float, numeric string, or blank/None — return None for empty."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        return float(val)
    raise vol.Invalid("Expected a number or blank")


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_BASE_LATITUDE): _opt_float,
        vol.Optional(CONF_BASE_LONGITUDE): _opt_float,
    }
)


class StigaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                auth = StigaAuth(email, password)
                rest = StigaRestClient(auth)
                await rest.get_user()
            except StigaAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during Stiga setup")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(email.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Stiga ({email})",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_BASE_LATITUDE: user_input.get(CONF_BASE_LATITUDE),
                        CONF_BASE_LONGITUDE: user_input.get(CONF_BASE_LONGITUDE),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

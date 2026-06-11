"""Config flow for Stiga integration."""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import StigaAuth, StigaAuthError, StigaRestClient
from .const import CONF_BASE_LATITUDE, CONF_BASE_LONGITUDE, CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_BASE_LATITUDE): str,
        vol.Optional(CONF_BASE_LONGITUDE): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

_DMS_RE = re.compile(
    r"""^(\d+)[°d\s]+(\d+)['\s]+([0-9.]+)["\s]*([NSEWnsew]?)$"""
)


def _parse_coord(val: str | None) -> float | None:
    """Convert a coordinate string to decimal degrees float.

    Accepts decimal degrees (dot or comma) and DMS format from Google Maps.
    Returns None for blank or unparseable input.
    """
    if not val:
        return None
    val = val.strip()

    dms = _DMS_RE.match(val.replace(",", "."))
    if dms:
        deg, minutes, seconds, hemi = dms.groups()
        result = float(deg) + float(minutes) / 60 + float(seconds) / 3600
        if hemi.upper() in ("S", "W"):
            result = -result
        return result

    try:
        return float(val.replace(",", "."))
    except (ValueError, TypeError):
        return None


def _coord_schema(existing_lat: float | None, existing_lon: float | None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_BASE_LATITUDE,
                default=str(existing_lat) if existing_lat is not None else "",
            ): str,
            vol.Optional(
                CONF_BASE_LONGITUDE,
                default=str(existing_lon) if existing_lon is not None else "",
            ): str,
        }
    )


def _validate_coords(
    raw_lat: str, raw_lon: str
) -> tuple[float | None, float | None, dict[str, str]]:
    """Parse and validate coordinate strings. Returns (lat, lon, errors)."""
    errors: dict[str, str] = {}
    base_lat = _parse_coord(raw_lat)
    base_lon = _parse_coord(raw_lon)

    if raw_lat and base_lat is None:
        errors[CONF_BASE_LATITUDE] = "invalid_coordinate"
    if raw_lon and base_lon is None:
        errors[CONF_BASE_LONGITUDE] = "invalid_coordinate"
    if not errors and bool(raw_lat) != bool(raw_lon):
        errors["base"] = "coords_incomplete"

    return base_lat, base_lon, errors


class StigaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            raw_lat = user_input.get(CONF_BASE_LATITUDE, "").strip()
            raw_lon = user_input.get(CONF_BASE_LONGITUDE, "").strip()

            base_lat, base_lon, errors = _validate_coords(raw_lat, raw_lon)

            if not errors:
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
                            CONF_BASE_LATITUDE: base_lat,
                            CONF_BASE_LONGITUDE: base_lon,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Triggered by HA when credentials are rejected (ConfigEntryAuthFailed)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-authentication form — only email + password, coordinates are preserved."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

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
                _LOGGER.exception("Unexpected error during Stiga reauth")
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        existing_email = entry.data.get(CONF_EMAIL, "") if entry else ""
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=existing_email): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow updating base station coordinates without reinstalling."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        existing_lat = entry.data.get(CONF_BASE_LATITUDE)
        existing_lon = entry.data.get(CONF_BASE_LONGITUDE)
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_lat = user_input.get(CONF_BASE_LATITUDE, "").strip()
            raw_lon = user_input.get(CONF_BASE_LONGITUDE, "").strip()
            base_lat, base_lon, errors = _validate_coords(raw_lat, raw_lon)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_BASE_LATITUDE: base_lat,
                        CONF_BASE_LONGITUDE: base_lon,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_coord_schema(existing_lat, existing_lon),
            errors=errors,
        )

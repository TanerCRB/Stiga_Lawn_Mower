"""Stiga Lawn Mower integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import StigaAuth, StigaAuthError, StigaRestClient
from .const import CONF_BASE_LATITUDE, CONF_BASE_LONGITUDE, CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .coordinator import StigaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    auth = StigaAuth(email, password)
    rest = StigaRestClient(auth)

    try:
        devices = await rest.get_devices()
    except StigaAuthError as exc:
        raise ConfigEntryAuthFailed(f"Stiga authentication failed: {exc}") from exc

    if not devices:
        _LOGGER.warning("No Stiga devices found for account %s", email)
        return False

    for device in devices:
        _LOGGER.debug(
            "Found device: name=%s mac=%s broker_id=%s product=%s",
            device.name,
            device.mac_address,
            device.broker_id,
            device.product_code,
        )

    base_lat = entry.data.get(CONF_BASE_LATITUDE)
    base_lon = entry.data.get(CONF_BASE_LONGITUDE)

    coordinators: list[StigaCoordinator] = []
    for device in devices:
        coord = StigaCoordinator(hass, auth, device, base_lat, base_lon)
        await coord.async_setup()
        coordinators.append(coord)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinators: list[StigaCoordinator] = hass.data[DOMAIN].pop(entry.entry_id, [])
        for coord in coordinators:
            await coord.async_shutdown()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

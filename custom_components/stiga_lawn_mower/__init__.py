"""Stiga Lawn Mower integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import StigaAuth, StigaRestClient
from .const import CONF_BASE_LATITUDE, CONF_BASE_LONGITUDE, CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .coordinator import StigaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["lawn_mower", "sensor", "binary_sensor", "button", "calendar", "device_tracker", "number", "select", "switch"]



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    auth = StigaAuth(email, password)
    rest = StigaRestClient(auth)

    devices = await rest.get_devices()
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

"""Stiga diagnostics — downloadable status dump from HA developer tools."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import StigaCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    result = []
    for coord in coordinators:
        device = coord.device
        status = coord.data
        settings = coord.settings
        result.append(
            {
                "device": {
                    "name": device.name,
                    "mac_address": device.mac_address,
                    "product_code": device.product_code,
                    "serial_number": device.serial_number,
                    "firmware_version": device.firmware_version,
                    "broker_id": device.broker_id,
                    "total_work_time_s": device.total_work_time,
                },
                "mqtt_connected": coord.mqtt_connected,
                "status": asdict(status) if status else None,
                "settings": asdict(settings) if settings else None,
            }
        )
    return {"devices": result}

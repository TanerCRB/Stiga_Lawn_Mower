"""Stiga select entities: rain delay."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    SETTINGS_FIELD_RAIN,
)
from .coordinator import StigaCoordinator

RAIN_DELAY_OPTIONS = ["4 h", "8 h", "12 h"]
_OPTION_TO_IDX = {"4 h": 0, "8 h": 1, "12 h": 2}
_IDX_TO_OPTION = {0: "4 h", 1: "8 h", 2: "12 h"}

RAIN_DELAY_DESCRIPTION = SelectEntityDescription(
    key="rain_delay",
    name="Rain Delay",
    icon="mdi:weather-rainy",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(StigaRainDelay(coord) for coord in coordinators)


class StigaRainDelay(CoordinatorEntity[StigaCoordinator], SelectEntity):
    _attr_has_entity_name = True
    entity_description = RAIN_DELAY_DESCRIPTION

    def __init__(self, coordinator: StigaCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.unique_id}_rain_delay"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )
        self._attr_options = RAIN_DELAY_OPTIONS

    @property
    def current_option(self) -> str:
        hours = self.coordinator.settings.rain_sensor_delay
        return f"{hours} h"

    async def async_select_option(self, option: str) -> None:
        idx = _OPTION_TO_IDX.get(option)
        if idx is None:
            return
        await self.coordinator.async_update_setting(
            {SETTINGS_FIELD_RAIN: {2: idx}}
        )

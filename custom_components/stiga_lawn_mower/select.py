"""Stiga select entities: rain delay, cutting mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import StigaZoneInfo
from .const import (
    DOMAIN,
    MANUFACTURER,
    SETTINGS_FIELD_RAIN,
)
from .coordinator import StigaCoordinator

RAIN_DELAY_OPTIONS = ["4 h", "8 h", "12 h"]
_OPTION_TO_IDX = {"4 h": 0, "8 h": 1, "12 h": 2}
_IDX_TO_OPTION = {0: "4 h", 1: "8 h", 2: "12 h"}

CUTTING_MODE_OPTIONS = ["Dense Grid", "Chess Board", "North-South", "East-West"]
_MODE_TO_INT = {"Dense Grid": 0, "Chess Board": 1, "North-South": 5, "East-West": 6}
_INT_TO_MODE = {0: "Dense Grid", 1: "Chess Board", 5: "North-South", 6: "East-West"}

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
    entities: list[SelectEntity] = []
    for coord in coordinators:
        entities.append(StigaRainDelay(coord))
        zones = coord.garden_info.zones if coord.garden_info else []
        for zone in zones:
            entities.append(StigaCuttingMode(coord, zone, len(zones)))
    async_add_entities(entities)


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


class StigaCuttingMode(CoordinatorEntity[StigaCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_options = CUTTING_MODE_OPTIONS
    _attr_icon = "mdi:grid"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: StigaCoordinator,
        zone: StigaZoneInfo,
        total_zones: int,
    ) -> None:
        super().__init__(coordinator)
        self._zone_id = zone.id
        self._attr_unique_id = f"{coordinator.device.unique_id}_cutting_mode_z{zone.id}"
        self._attr_name = (
            "Cutting Mode" if total_zones == 1 else f"Zone {zone.id} Cutting Mode"
        )
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )

    @property
    def current_option(self) -> str | None:
        if self.coordinator.garden_info:
            for zone in self.coordinator.garden_info.zones:
                if zone.id == self._zone_id:
                    return _INT_TO_MODE.get(zone.cutting_mode)
        return None

    async def async_select_option(self, option: str) -> None:
        mode_value = _MODE_TO_INT.get(option)
        if mode_value is None:
            return
        await self.coordinator.async_set_cutting_mode(self._zone_id, mode_value)

"""Stiga number entity: cutting height."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CUTTING_HEIGHT_MAP,
    DOMAIN,
    MANUFACTURER,
    SETTINGS_FIELD_ZONE_HEIGHT,
)
from .coordinator import StigaCoordinator

CUTTING_HEIGHT_DESCRIPTION = NumberEntityDescription(
    key="cutting_height",
    name="Cutting Height",
    icon="mdi:scissors-cutting",
    native_min_value=20,
    native_max_value=60,
    native_step=5,
    native_unit_of_measurement="mm",
    mode=NumberMode.BOX,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        StigaCuttingHeight(coord) for coord in coordinators
    )


class StigaCuttingHeight(CoordinatorEntity[StigaCoordinator], NumberEntity):
    _attr_has_entity_name = True
    entity_description = CUTTING_HEIGHT_DESCRIPTION

    def __init__(self, coordinator: StigaCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.unique_id}_cutting_height_ctrl"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )

    @property
    def native_value(self) -> float:
        return float(self.coordinator.settings.cutting_height)

    async def async_set_native_value(self, value: float) -> None:
        mm = int(value)
        # Round to nearest valid step (20,25,...,60)
        valid = sorted(CUTTING_HEIGHT_MAP.keys())
        mm = min(valid, key=lambda x: abs(x - mm))
        height_idx = CUTTING_HEIGHT_MAP[mm]
        await self.coordinator.async_update_setting(
            {SETTINGS_FIELD_ZONE_HEIGHT: {2: height_idx}}
        )

"""Stiga button entities: calibrate blades, refresh status."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, ROBOT_CMD_CALIBRATE_BLADES
from .coordinator import StigaCoordinator


@dataclass(frozen=True)
class StigaButtonDescription(ButtonEntityDescription):
    pass


BUTTON_DESCRIPTIONS: tuple[StigaButtonDescription, ...] = (
    StigaButtonDescription(
        key="calibrate_blades",
        name="Calibrate Blades",
        icon="mdi:cog-refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaButtonDescription(
        key="refresh_status",
        name="Refresh Status",
        icon="mdi:refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities = [
        StigaButton(coord, description)
        for coord in coordinators
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)


class StigaButton(CoordinatorEntity[StigaCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    entity_description: StigaButtonDescription

    def __init__(
        self,
        coordinator: StigaCoordinator,
        description: StigaButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device = coordinator.device
        self._attr_unique_id = f"{device.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )

    async def async_press(self) -> None:
        key = self.entity_description.key
        if key == "calibrate_blades":
            await self.coordinator.async_send_command(ROBOT_CMD_CALIBRATE_BLADES)
        elif key == "refresh_status":
            await self.coordinator.async_request_status()

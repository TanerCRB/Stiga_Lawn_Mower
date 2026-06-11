"""Stiga switch entities: rain sensor, anti-theft, keyboard lock, notifications, etc."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    SETTINGS_FIELD_ANTI_THEFT,
    SETTINGS_FIELD_KEYBOARD_LOCK,
    SETTINGS_FIELD_LONG_EXIT,
    SETTINGS_FIELD_OBSTACLE_NOTIFICATIONS,
    SETTINGS_FIELD_PUSH_NOTIFICATIONS,
    SETTINGS_FIELD_RAIN,
    SETTINGS_FIELD_SMART_CUT,
)
from .coordinator import StigaCoordinator


@dataclass(frozen=True)
class StigaSwitchDescription(SwitchEntityDescription):
    pass


SWITCH_DESCRIPTIONS: tuple[StigaSwitchDescription, ...] = (
    StigaSwitchDescription(
        key="rain_sensor",
        name="Rain Sensor",
        icon="mdi:weather-rainy",
        entity_category=EntityCategory.CONFIG,
    ),
    StigaSwitchDescription(
        key="anti_theft",
        name="Anti-Theft",
        icon="mdi:shield-lock",
        entity_category=EntityCategory.CONFIG,
    ),
    StigaSwitchDescription(
        key="keyboard_lock",
        name="Keyboard Lock",
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
    ),
    StigaSwitchDescription(
        key="push_notifications",
        name="Push Notifications",
        icon="mdi:bell",
        entity_category=EntityCategory.CONFIG,
    ),
    StigaSwitchDescription(
        key="obstacle_notifications",
        name="Obstacle Notifications",
        icon="mdi:bell-alert",
        entity_category=EntityCategory.CONFIG,
    ),
    StigaSwitchDescription(
        key="smart_cut_height",
        name="Smart Cutting Height",
        icon="mdi:tune",
        entity_category=EntityCategory.CONFIG,
    ),
    StigaSwitchDescription(
        key="long_exit",
        name="Long Exit",
        icon="mdi:exit-run",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities = [
        StigaSwitch(coord, description)
        for coord in coordinators
        for description in SWITCH_DESCRIPTIONS
    ]
    async_add_entities(entities)


class StigaSwitch(CoordinatorEntity[StigaCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    entity_description: StigaSwitchDescription

    def __init__(
        self,
        coordinator: StigaCoordinator,
        description: StigaSwitchDescription,
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

    @property
    def is_on(self) -> bool:
        s = self.coordinator.settings
        key = self.entity_description.key
        if key == "rain_sensor":
            return s.rain_sensor_enabled
        if key == "anti_theft":
            return s.anti_theft
        if key == "keyboard_lock":
            return s.keyboard_lock
        if key == "push_notifications":
            return s.push_notifications
        if key == "obstacle_notifications":
            return s.obstacle_notifications
        if key == "smart_cut_height":
            return s.smart_cut_height
        if key == "long_exit":
            return s.long_exit_enabled
        return False

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        key = self.entity_description.key
        int_val = 1 if value else 0

        if key == "rain_sensor":
            fields = {SETTINGS_FIELD_RAIN: {1: int_val}}
        elif key == "anti_theft":
            fields = {SETTINGS_FIELD_ANTI_THEFT: int_val}
        elif key == "keyboard_lock":
            fields = {SETTINGS_FIELD_KEYBOARD_LOCK: int_val}
        elif key == "push_notifications":
            fields = {SETTINGS_FIELD_PUSH_NOTIFICATIONS: {1: int_val}}
        elif key == "obstacle_notifications":
            fields = {SETTINGS_FIELD_OBSTACLE_NOTIFICATIONS: {1: int_val}}
        elif key == "smart_cut_height":
            fields = {SETTINGS_FIELD_SMART_CUT: int_val}
        elif key == "long_exit":
            fields = {SETTINGS_FIELD_LONG_EXIT: {1: int_val}}
        else:
            return

        await self.coordinator.async_update_setting(fields)

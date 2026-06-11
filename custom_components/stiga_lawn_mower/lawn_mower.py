"""Stiga lawn mower entity."""
from __future__ import annotations

import logging

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    ROBOT_CMD_GO_HOME,
    ROBOT_CMD_START,
    ROBOT_CMD_STOP,
)
from .coordinator import StigaCoordinator

_LOGGER = logging.getLogger(__name__)

# Map Stiga operation codes → HA LawnMowerActivity
_STATUS_MAP: dict[int, LawnMowerActivity] = {
    0: LawnMowerActivity.DOCKED,     # WAITING_FOR_COMMAND
    1: LawnMowerActivity.MOWING,     # MOWING
    2: LawnMowerActivity.RETURNING,  # GOING_HOME
    3: LawnMowerActivity.DOCKED,     # CHARGING
    4: LawnMowerActivity.DOCKED,     # DOCKED
    5: LawnMowerActivity.DOCKED,     # UPDATING
    6: LawnMowerActivity.ERROR,      # BLOCKED
    8: LawnMowerActivity.ERROR,      # LID_OPEN
    18: LawnMowerActivity.MOWING,    # CALIBRATION
    20: LawnMowerActivity.MOWING,    # BLADES_CALIBRATION
    25: LawnMowerActivity.MOWING,    # DOCKING_CALIBRATION
    27: LawnMowerActivity.DOCKED,    # STORING_DATA
    28: LawnMowerActivity.MOWING,    # PLANNING_ONGOING
    29: LawnMowerActivity.MOWING,    # REACHING_FIRST_POINT
    30: LawnMowerActivity.MOWING,    # NAVIGATING_TO_AREA
    32: LawnMowerActivity.MOWING,    # CUTTING_BORDER
    252: LawnMowerActivity.ERROR,    # STARTUP_REQUIRED
    255: LawnMowerActivity.ERROR,    # ERROR
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        StigaLawnMower(coord) for coord in coordinators
    )


class StigaLawnMower(CoordinatorEntity[StigaCoordinator], LawnMowerEntity):
    _attr_has_entity_name = True
    _attr_name = None  # use device name as entity name
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: StigaCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.unique_id}_lawn_mower"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )

    @property
    def activity(self) -> LawnMowerActivity:
        status_code = self.coordinator.data.operation if self.coordinator.data else 0
        return _STATUS_MAP.get(status_code, LawnMowerActivity.ERROR)

    async def async_start_mowing(self) -> None:
        await self.coordinator._mqtt.send_command(ROBOT_CMD_START)

    async def async_pause(self) -> None:
        await self.coordinator._mqtt.send_command(ROBOT_CMD_STOP)

    async def async_dock(self) -> None:
        await self.coordinator._mqtt.send_command(ROBOT_CMD_GO_HOME)

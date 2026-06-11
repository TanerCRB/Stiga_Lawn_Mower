"""Stiga binary sensors: connection, docked, charging, error, lid, rain/lift/bump/slope."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import StigaDeviceStatus
from .const import (
    DOMAIN,
    INFO_CODE_BUMP_SENSOR,
    INFO_CODE_LID_SENSOR,
    INFO_CODE_LIFT_SENSOR,
    INFO_CODE_RAIN_SENSOR,
    INFO_CODE_SLOPE_SENSOR,
    MANUFACTURER,
    OPERATION_CHARGING,
    OPERATION_DOCKED,
    OPERATION_ERROR,
    OPERATION_LID_OPEN,
)
from .coordinator import StigaCoordinator


@dataclass(frozen=True)
class StigaBinarySensorDescription(BinarySensorEntityDescription):
    pass


BINARY_SENSOR_DESCRIPTIONS: tuple[StigaBinarySensorDescription, ...] = (
    StigaBinarySensorDescription(
        key="cloud_connection",
        name="Cloud Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    StigaBinarySensorDescription(
        key="docked",
        name="Docked",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    StigaBinarySensorDescription(
        key="charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    StigaBinarySensorDescription(
        key="error",
        name="Error",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    StigaBinarySensorDescription(
        key="lid",
        name="Lid",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    StigaBinarySensorDescription(
        key="rain_sensor",
        name="Rain Sensor",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    StigaBinarySensorDescription(
        key="lift_sensor",
        name="Lift Sensor",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    StigaBinarySensorDescription(
        key="bump_sensor",
        name="Bump Sensor",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    StigaBinarySensorDescription(
        key="slope_sensor",
        name="Slope Sensor",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities = [
        StigaBinarySensor(coord, description)
        for coord in coordinators
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class StigaBinarySensor(CoordinatorEntity[StigaCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    entity_description: StigaBinarySensorDescription

    def __init__(
        self,
        coordinator: StigaCoordinator,
        description: StigaBinarySensorDescription,
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
        key = self.entity_description.key

        if key == "cloud_connection":
            return self.coordinator.mqtt_connected

        data: StigaDeviceStatus | None = self.coordinator.data
        if data is None:
            return False

        if key == "docked":
            return data.operation in OPERATION_DOCKED
        if key == "charging":
            return data.operation in OPERATION_CHARGING
        if key == "error":
            return data.operation in OPERATION_ERROR
        if key == "lid":
            return data.operation in OPERATION_LID_OPEN or data.info_code == INFO_CODE_LID_SENSOR
        if key == "rain_sensor":
            return data.info_code == INFO_CODE_RAIN_SENSOR
        if key == "lift_sensor":
            return data.info_code == INFO_CODE_LIFT_SENSOR
        if key == "bump_sensor":
            return data.info_code == INFO_CODE_BUMP_SENSOR
        if key == "slope_sensor":
            return data.info_code == INFO_CODE_SLOPE_SENSOR
        return False

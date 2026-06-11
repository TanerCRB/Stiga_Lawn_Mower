"""Stiga sensors: battery, GPS, network, mowing progress, settings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfArea,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import StigaDeviceStatus
from .const import DOMAIN, MANUFACTURER, ROBOT_STATUS
from .coordinator import StigaCoordinator


@dataclass(frozen=True)
class StigaSensorDescription(SensorEntityDescription):
    pass


SENSOR_DESCRIPTIONS: tuple[StigaSensorDescription, ...] = (
    # --- Main sensors ---
    StigaSensorDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    StigaSensorDescription(
        key="status",
        name="Status",
        icon="mdi:robot-mower",
    ),
    StigaSensorDescription(
        key="garden_completed",
        name="Garden Completion",
        icon="mdi:grass",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    StigaSensorDescription(
        key="zone",
        name="Current Zone",
        icon="mdi:map-marker-radius",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StigaSensorDescription(
        key="zone_completed",
        name="Zone Progress",
        icon="mdi:progress-check",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    # --- Diagnostic sensors ---
    StigaSensorDescription(
        key="battery_capacity",
        name="Battery Capacity",
        icon="mdi:battery-high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mAh",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="cutting_height",
        name="Cutting Height",
        icon="mdi:scissors-cutting",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="gps_satellites",
        name="GPS Satellites",
        icon="mdi:satellite-variant",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="gps_coverage",
        name="GPS Coverage",
        icon="mdi:crosshairs-gps",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="rtk_quality",
        name="RTK Quality",
        icon="mdi:satellite-uplink",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="rssi",
        name="RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="rsrp",
        name="RSRP",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="rsrq",
        name="RSRQ",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="signal_quality",
        name="Signal Quality",
        icon="mdi:signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="firmware_version",
        name="Firmware Version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    StigaSensorDescription(
        key="total_work_time",
        name="Total Work Time",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Garden layout sensors (from REST /api/perimeters) ---
    StigaSensorDescription(
        key="garden_area",
        name="Garden Area",
        icon="mdi:map-outline",
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
    ),
    StigaSensorDescription(
        key="garden_zones",
        name="Garden Zones",
        icon="mdi:layers-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StigaSensorDescription(
        key="obstacles_count",
        name="Obstacles",
        icon="mdi:wall",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    StigaSensorDescription(
        key="obstacles_area",
        name="Obstacle Area",
        icon="mdi:wall",
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    entities: list[StigaSensor] = []
    for coord in coordinators:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(StigaSensor(coord, description))
    async_add_entities(entities)


class StigaSensor(CoordinatorEntity[StigaCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: StigaSensorDescription

    def __init__(
        self,
        coordinator: StigaCoordinator,
        description: StigaSensorDescription,
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
    def native_value(self) -> Optional[int | float | str]:
        data: Optional[StigaDeviceStatus] = self.coordinator.data
        if data is None:
            return None
        key = self.entity_description.key

        if key == "battery":
            return data.battery_percent
        if key == "status":
            return ROBOT_STATUS.get(data.operation, str(data.operation))
        if key == "garden_completed":
            return data.garden_completed
        if key == "zone":
            return data.zone
        if key == "zone_completed":
            return data.zone_completed
        if key == "battery_capacity":
            return data.battery_capacity_mah
        if key == "cutting_height":
            return self.coordinator.settings.cutting_height
        if key == "gps_satellites":
            return data.gps_satellites
        if key == "gps_coverage":
            return data.gps_coverage
        if key == "rtk_quality":
            return data.rtk_quality
        if key == "rssi":
            return data.rssi
        if key == "rsrp":
            return data.rsrp
        if key == "rsrq":
            return data.rsrq
        if key == "signal_quality":
            return data.signal_quality
        if key == "firmware_version":
            return self.coordinator.device.firmware_version or None
        if key == "total_work_time":
            return self.coordinator.device.total_work_time
        info = self.coordinator.garden_info
        if key == "garden_area":
            if info and info.total_area_m2 is not None:
                return round(info.total_area_m2, 1)
            return None
        if key == "garden_zones":
            return info.zones_count if info else None
        if key == "obstacles_count":
            return info.obstacles_count if info else None
        if key == "obstacles_area":
            if info and info.obstacles_area_m2 is not None:
                return round(info.obstacles_area_m2, 1)
            return None
        return None

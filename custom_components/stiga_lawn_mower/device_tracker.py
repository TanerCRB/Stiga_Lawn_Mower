"""Stiga device tracker — shows the robot's GPS position on the HA map."""
from __future__ import annotations

import math
import logging

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import StigaCoordinator

_LOGGER = logging.getLogger(__name__)

# Metres per degree of latitude (constant everywhere on Earth)
_LAT_M_PER_DEG = 111320.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(StigaDeviceTracker(coord) for coord in coordinators)


class StigaDeviceTracker(CoordinatorEntity[StigaCoordinator], TrackerEntity):
    _attr_has_entity_name = True
    _attr_name = "Location"
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: StigaCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.unique_id}_location"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )

    @property
    def latitude(self) -> float | None:
        # Primary: RTK offset position (cm-level when base station is active)
        ref_lat = self.coordinator.reference_lat
        ref_lon = self.coordinator.reference_lon
        pos = self.coordinator.position
        if ref_lat is not None and ref_lon is not None and pos is not None:
            return ref_lat + pos.offset_lat_m / _LAT_M_PER_DEG
        # Fallback: standard GPS from STATUS location message (~5-10 m accuracy)
        status = self.coordinator.data
        if status and status.gps_lat is not None:
            return status.gps_lat
        return None

    @property
    def longitude(self) -> float | None:
        ref_lat = self.coordinator.reference_lat
        ref_lon = self.coordinator.reference_lon
        pos = self.coordinator.position
        if ref_lat is not None and ref_lon is not None and pos is not None:
            lon_m_per_deg = _LAT_M_PER_DEG * math.cos(math.radians(ref_lat))
            return ref_lon + pos.offset_lon_m / lon_m_per_deg
        status = self.coordinator.data
        if status and status.gps_lon is not None:
            return status.gps_lon
        return None

    @property
    def location_accuracy(self) -> int:
        """Return accuracy in metres — 1-3 m with RTK, 10 m with standard GPS."""
        pos = self.coordinator.position
        if pos is not None and self.coordinator.reference_lat is not None:
            # Using RTK offset — apply quality tier if available
            status = self.coordinator.data
            if status and status.rtk_quality is not None:
                if status.rtk_quality >= 80:
                    return 1
                if status.rtk_quality >= 50:
                    return 3
            return 3   # RTK offset without quality field — assume good accuracy
        return 10      # standard GPS fallback

    @property
    def extra_state_attributes(self) -> dict:
        pos = self.coordinator.position
        status = self.coordinator.data
        attrs: dict = {}
        if pos is not None and self.coordinator.reference_lat is not None:
            attrs["position_source"] = "rtk_offset"
            attrs["offset_lat_m"] = round(pos.offset_lat_m, 3)
            attrs["offset_lon_m"] = round(pos.offset_lon_m, 3)
            attrs["heading"] = round(pos.heading, 1)
            attrs["distance_m"] = round(
                math.hypot(pos.offset_lat_m, pos.offset_lon_m), 2
            )
        elif status and status.gps_lat is not None:
            attrs["position_source"] = "gps_status"
        if self.coordinator.reference_lat is None and (status is None or status.gps_lat is None):
            attrs["note"] = "Configure base station coordinates to show GPS position on map"

        info = self.coordinator.garden_info
        if info:
            if info.reference_lat is not None and info.reference_lon is not None:
                attrs["base_station_lat"] = info.reference_lat
                attrs["base_station_lon"] = info.reference_lon
            zone_polys = [
                {"id": z.id, "name": z.name, "polygon": z.polygon}
                for z in info.zones if z.polygon
            ]
            if zone_polys:
                attrs["zone_polygons"] = zone_polys
            obs_polys = [
                {"id": o.id, "name": o.name, "polygon": o.polygon}
                for o in info.obstacles_geo if o.polygon
            ]
            if obs_polys:
                attrs["obstacle_polygons"] = obs_polys

        return attrs

    @property
    def battery_level(self) -> int | None:
        status = self.coordinator.data
        return status.battery_percent if status else None

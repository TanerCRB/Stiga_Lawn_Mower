"""Stiga calendar entity: weekly mowing schedule read/write via MQTT."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .api import StigaScheduleBlock, StigaRobotSchedule
from .const import DOMAIN, MANUFACTURER
from .coordinator import StigaCoordinator

_LOGGER = logging.getLogger(__name__)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[StigaCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(StigaMowingCalendar(coord) for coord in coordinators)


def _slot_to_hm(slot: int) -> tuple[int, int]:
    return slot // 2, (slot % 2) * 30


def _hm_to_slot(hour: int, minute: int) -> int:
    return hour * 2 + (1 if minute >= 30 else 0)


def _build_event(block: StigaScheduleBlock, event_date: date, uid_prefix: str) -> CalendarEvent:
    start_h, start_m = _slot_to_hm(block.start_slot)
    end_total = block.end_slot + 1
    tz = dt_util.now().tzinfo
    start_dt = datetime(event_date.year, event_date.month, event_date.day, start_h, start_m, tzinfo=tz)
    if end_total >= 48:
        end_dt = datetime(event_date.year, event_date.month, event_date.day, 0, 0, tzinfo=tz) + timedelta(days=1)
    else:
        end_h, end_m = _slot_to_hm(end_total)
        end_dt = datetime(event_date.year, event_date.month, event_date.day, end_h, end_m, tzinfo=tz)
    return CalendarEvent(
        summary="Mowing",
        start=start_dt,
        end=end_dt,
        uid=f"{uid_prefix}_{block.day_index}_{block.start_slot}",
        description=_DAYS[block.day_index],
    )


class StigaMowingCalendar(CoordinatorEntity[StigaCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Mowing Schedule"
    _attr_supported_features = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT

    def __init__(self, coordinator: StigaCoordinator) -> None:
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_unique_id = f"{device.unique_id}_mowing_schedule"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.product_code,
            sw_version=device.firmware_version,
            serial_number=device.serial_number,
        )

    @property
    def event(self) -> Optional[CalendarEvent]:
        now = dt_util.now()
        uid_prefix = self.coordinator.device.unique_id
        schedule = self.coordinator.schedule
        for day_offset in range(8):
            check_date = (now + timedelta(days=day_offset)).date()
            day_index = check_date.weekday()
            for block in sorted(schedule.blocks, key=lambda b: b.start_slot):
                if block.day_index != day_index:
                    continue
                ev = _build_event(block, check_date, uid_prefix)
                if isinstance(ev.end, datetime) and ev.end > now:
                    return ev
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        uid_prefix = self.coordinator.device.unique_id
        schedule = self.coordinator.schedule
        current = start_date.date()
        while current <= end_date.date():
            day_index = current.weekday()
            for block in schedule.blocks:
                if block.day_index != day_index:
                    continue
                ev = _build_event(block, current, uid_prefix)
                if isinstance(ev.end, datetime) and isinstance(ev.start, datetime):
                    if ev.end > start_date and ev.start < end_date:
                        events.append(ev)
            current += timedelta(days=1)
        return events

    async def async_create_event(self, **kwargs: Any) -> None:
        dtstart: datetime = kwargs["dtstart"]
        dtend: datetime = kwargs["dtend"]

        day_index = dtstart.weekday()
        start_slot = _hm_to_slot(dtstart.hour, dtstart.minute)
        end_slot = _hm_to_slot(dtend.hour, dtend.minute) - 1

        if end_slot < start_slot:
            _LOGGER.warning("Invalid mowing window: end must be after start")
            return

        schedule = self.coordinator.schedule
        for block in schedule.blocks:
            if block.day_index != day_index:
                continue
            if start_slot <= block.end_slot and end_slot >= block.start_slot:
                _LOGGER.warning("Mowing window overlaps with existing block on %s", _DAYS[day_index])
                return

        new_blocks = list(schedule.blocks) + [StigaScheduleBlock(day_index, start_slot, end_slot)]
        new_blocks.sort(key=lambda b: (b.day_index, b.start_slot))
        new_schedule = StigaRobotSchedule(
            enabled=schedule.enabled,
            blocks=new_blocks,
            schedule_type=schedule.schedule_type,
        )
        await self.coordinator.async_update_schedule(new_schedule)

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        try:
            parts = uid.rsplit("_", 2)
            day_index = int(parts[-2])
            start_slot = int(parts[-1])
        except (ValueError, IndexError):
            _LOGGER.warning("Cannot parse calendar event uid: %s", uid)
            return

        schedule = self.coordinator.schedule
        new_blocks = [
            b for b in schedule.blocks
            if not (b.day_index == day_index and b.start_slot == start_slot)
        ]
        if len(new_blocks) == len(schedule.blocks):
            _LOGGER.warning("No mowing block found for uid: %s", uid)
            return

        new_schedule = StigaRobotSchedule(
            enabled=schedule.enabled,
            blocks=new_blocks,
            schedule_type=schedule.schedule_type,
        )
        await self.coordinator.async_update_schedule(new_schedule)

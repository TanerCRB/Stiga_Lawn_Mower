"""Stiga data coordinator — manages auth, REST, and MQTT lifecycle."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import StigaAuth, StigaDevice, StigaDeviceStatus, StigaGardenInfo, StigaMQTTClient, StigaRestClient, StigaRobotPosition, StigaRobotSchedule, StigaRobotSettings
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=30)
MQTT_RETRY_INTERVAL = 60  # seconds


class StigaCoordinator(DataUpdateCoordinator[StigaDeviceStatus]):
    def __init__(
        self,
        hass: HomeAssistant,
        auth: StigaAuth,
        device: StigaDevice,
        base_latitude: float | None = None,
        base_longitude: float | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device.unique_id}",
            update_interval=POLL_INTERVAL,
        )
        self.device = device
        self._auth = auth
        self._rest = StigaRestClient(auth)
        self._mqtt = StigaMQTTClient(device, auth)
        self._base_latitude = base_latitude
        self._base_longitude = base_longitude
        self._garden_info: StigaGardenInfo | None = None
        self._shutdown = False
        self._retry_task: asyncio.Task | None = None

    @property
    def settings(self) -> StigaRobotSettings:
        return self._mqtt.settings

    @property
    def schedule(self) -> StigaRobotSchedule:
        return self._mqtt.schedule

    @property
    def position(self) -> StigaRobotPosition | None:
        return self._mqtt.position

    @property
    def base_latitude(self) -> float | None:
        return self._base_latitude

    @property
    def base_longitude(self) -> float | None:
        return self._base_longitude

    @property
    def garden_info(self) -> StigaGardenInfo | None:
        return self._garden_info

    @property
    def mqtt_connected(self) -> bool:
        return self._mqtt.connected

    async def async_setup(self) -> None:
        """Start MQTT connection attempt; non-fatal if broker unreachable."""
        self._mqtt.add_status_callback(self._on_mqtt_status)
        self._mqtt.add_settings_callback(self._on_mqtt_settings)
        self._mqtt.add_schedule_callback(self._on_mqtt_schedule)
        self._mqtt.add_position_callback(self._on_mqtt_position)
        await self._try_connect_mqtt()
        try:
            self._garden_info = await self._rest.get_perimeters(self.device)
            _LOGGER.debug(
                "Garden perimeters: area=%s m², zones=%s, obstacles=%s",
                self._garden_info.total_area_m2,
                self._garden_info.zones_count,
                self._garden_info.obstacles_count,
            )
        except Exception as exc:
            _LOGGER.debug("Failed to fetch garden perimeters: %s", exc)

    async def _try_connect_mqtt(self) -> None:
        try:
            await self._mqtt.connect()
        except Exception as exc:
            _LOGGER.warning(
                "MQTT connection to %s failed: %s — will retry every %ds",
                self.device.broker_id,
                exc,
                MQTT_RETRY_INTERVAL,
            )
            self._schedule_retry()

    def _schedule_retry(self) -> None:
        if not self._shutdown:
            self._retry_task = self.hass.async_create_task(self._retry_loop())

    async def _retry_loop(self) -> None:
        await asyncio.sleep(MQTT_RETRY_INTERVAL)
        if self._shutdown:
            return
        if not self._mqtt.connected:
            _LOGGER.debug("Retrying MQTT connection for %s", self.device.name)
            await self._try_connect_mqtt()

    async def async_shutdown(self) -> None:
        """Disconnect MQTT cleanly on unload."""
        self._shutdown = True
        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
        await self._mqtt.disconnect()

    def _on_mqtt_status(self, status: StigaDeviceStatus) -> None:
        """Called from MQTT thread via call_soon_threadsafe."""
        self.async_set_updated_data(status)

    def _on_mqtt_settings(self, settings: StigaRobotSettings) -> None:
        """Settings received — push a coordinator update so config entities refresh."""
        self.async_set_updated_data(self._mqtt.status)

    def _on_mqtt_schedule(self, schedule: StigaRobotSchedule) -> None:
        """Schedule received — push a coordinator update so calendar entity refreshes."""
        self.async_set_updated_data(self._mqtt.status)

    def _on_mqtt_position(self, position: StigaRobotPosition) -> None:
        """Position received — push a coordinator update so device_tracker refreshes."""
        self.async_set_updated_data(self._mqtt.status)

    async def async_send_command(self, command_type: int) -> None:
        await self._mqtt.send_command(command_type)

    async def async_request_status(self) -> None:
        await self._mqtt.request_status()

    async def async_update_setting(self, settings_fields: dict) -> None:
        """Send a partial SETTINGS_UPDATE and request fresh settings in return."""
        await self._mqtt.send_settings_update(settings_fields)
        await asyncio.sleep(0.3)
        await self._mqtt.request_settings()

    async def async_update_schedule(self, schedule: StigaRobotSchedule) -> None:
        """Send SCHEDULING_SETTINGS_UPDATE and request fresh schedule in return."""
        await self._mqtt.send_schedule_update(schedule)
        await asyncio.sleep(0.3)
        await self._mqtt.request_schedule()

    async def _async_update_data(self) -> StigaDeviceStatus:
        """Request fresh status and position via MQTT; return last known state."""
        if self._mqtt.connected:
            try:
                await self._mqtt.request_status()
                await self._mqtt.request_position()
            except Exception as exc:
                _LOGGER.debug("MQTT poll request failed: %s", exc)
        return self._mqtt.status

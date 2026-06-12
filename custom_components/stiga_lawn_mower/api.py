"""Stiga API: Firebase auth, REST client, and MQTT client."""
from __future__ import annotations

import asyncio
import copy
import logging
import math
import os
import ssl
import struct
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import aiohttp
import paho.mqtt.client as mqtt

from .const import (
    BATTERY_FIELD_CAPACITY,
    BATTERY_FIELD_PERCENT,
    CUTTING_HEIGHT_BY_IDX,
    FIREBASE_API_KEY,
    FIREBASE_AUTH_URL,
    LOCATION_COVERAGE,
    LOCATION_RTK_QUALITY,
    LOCATION_SATELLITES,
    MQTT_BROKER_FALLBACK,
    MQTT_BROKER_FORMAT,
    MQTT_PORT,
    MQTT_RECONNECT_INTERVAL,
    MQTT_USERNAME,
    MOWING_FIELD_GARDEN_COMPLETED,
    MOWING_FIELD_ZONE,
    MOWING_FIELD_ZONE_COMPLETED,
    NETWORK_INNER,
    NETWORK_RSRP,
    NETWORK_RSRQ,
    NETWORK_RSSI,
    NETWORK_SQ,
    RAIN_DELAY_BY_IDX,
    ROBOT_CMD_POSITION_REQUEST,
    ROBOT_CMD_SCHEDULING_REQUEST,
    ROBOT_CMD_SCHEDULING_UPDATE,
    ROBOT_CMD_SETTINGS_REQUEST,
    ROBOT_CMD_SETTINGS_UPDATE,
    ROBOT_CMD_STATUS_REQUEST,
    SETTINGS_FIELD_ANTI_THEFT,
    SETTINGS_FIELD_KEYBOARD_LOCK,
    SETTINGS_FIELD_LONG_EXIT,
    SETTINGS_FIELD_OBSTACLE_NOTIFICATIONS,
    SETTINGS_FIELD_PUSH_NOTIFICATIONS,
    SETTINGS_FIELD_RAIN,
    SETTINGS_FIELD_SMART_CUT,
    SETTINGS_FIELD_ZONE_HEIGHT,
    STATUS_FIELD_BATTERY,
    STATUS_FIELD_DOCKING,
    STATUS_FIELD_ERROR,
    STATUS_FIELD_INFO,
    STATUS_FIELD_LOCATION,
    STATUS_FIELD_MOWING,
    STATUS_FIELD_NETWORK,
    STATUS_FIELD_TYPE,
    STIGA_API_BASE_URL,
)
from .protobuf import (
    decode_protobuf,
    decode_protobuf_repeated,
    encode_protobuf,
    encode_robot_command,
    encode_status_request_fields,
    patch_zone_cutting_mode,
)

_LOGGER = logging.getLogger(__name__)

# TLS client certificates for MQTT broker authentication.
# Source: https://github.com/matthewgream/stiga-api/blob/main/api/StigaAPICertificates.js
# These are embedded in the Stiga app and used for mutual TLS with the MQTT broker.
MQTT_CLIENT_CERT = """-----BEGIN CERTIFICATE-----
MIID3jCCAsYCCQDX19TYX4KbzTANBgkqhkiG9w0BAQsFADCBuzELMAkGA1UEBhMC
SVQxEDAOBgNVBAgMB1RyZXZpc28xHDAaBgNVBAcME0Nhc3RlbGZyYW5jbyBWZW5l
dG8xEjAQBgNVBAoMCVN0aWdhIFNQQTEVMBMGA1UECwwMQ29ubmVjdGl2aXR5MSQw
IgYDVQQDDBtyb2JvdC1tcXR0LWJyb2tlci5zdGlnYS5jb20xKzApBgkqhkiG9w0B
CQEWHGRpZ2l0YWwuaW5ub3ZhdGlvbkBzdGlnYS5jb20wIBcNMjExMjMwMDkyNTI3
WhgPMjE1ODExMjIwOTI1MjdaMIGjMQswCQYDVQQGEwJJVDEKMAgGA1UECAwBLjEK
MAgGA1UEBwwBLjESMBAGA1UECgwJU3RpZ2EgU1BBMRUwEwYDVQQLDAxDb25uZWN0
aXZpdHkxJDAiBgNVBAMMG3JvYm90LW1xdHQtYnJva2VyLnN0aWdhLmNvbTErMCkG
CSqGSIb3DQEJARYcZGlnaXRhbC5pbm5vdmF0aW9uQHN0aWdhLmNvbTCCASIwDQYJ
KoZIhvcNAQEBBQADggEPADCCAQoCggEBAKTfTuUMJBfsweC71o1s9NQl4/C7oYvr
33Nl2ogSQLI9PALqfvYU0uzoh/rktE8iJ9WM5LUCvmj+IOSQgwkhXnKymU9Mk5vy
TAbvh0XoVliF8+ERmxJb/03roNDJigUZUoBpDr6TftYSwab33SKtDetKkj/A4sHL
quro6nB6TCc3RZB6UVO/V2lN2FEvMAdSsrvgUfiDzoK30LRsyquDYdp1SGBch9cV
lyCUt55f8xjAZaRz2xEvxDfcjd17nnjEsL3eEcLv0h3wrC47g/JR4TCvfYp3q8+i
6/LPMb3KaTxRrjppx0CaWHI0N9TBNui5yV2GTh3RZdj+21VdSBqPnSMCAwEAATAN
BgkqhkiG9w0BAQsFAAOCAQEAknr/p4OjP/17tyVnfmwsIGH2VrxsIQdL56U07bfM
xmy/b/GydRJ0j/2i/paqgDd1mVokI9wpp/9lTx/wHNEkoZNvkxy9wwPGZvoeAuu9
JqILkjeiuTZZzA1wvdh8pPhB6DIJwuNC/b6d0FmCkSm8YD2AeTMeGjrub2j8h5Ez
uuOi7ONHqZ6+aW7fNVur1gtZ+M3I1DkjeEvTHXqNJ9EpX+Nx9+Dq9S+UPCTdT8gD
1KQdpiXB41jw3PSKZVqu+fODQnlMxAVvKFGUAmsx23sx/Wvdz4nVOv+ym2ONUWSz
mCsd99Oz3icQI5EHEcGJJ/PwYHMxjK7o5g7VnC/8xJVgnA==
-----END CERTIFICATE-----"""

MQTT_CLIENT_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEApN9O5QwkF+zB4LvWjWz01CXj8Luhi+vfc2XaiBJAsj08Aup+
9hTS7OiH+uS0TyIn1YzktQK+aP4g5JCDCSFecrKZT0yTm/JMBu+HRehWWIXz4RGb
Elv/Teug0MmKBRlSgGkOvpN+1hLBpvfdIq0N60qSP8Diwcuq6ujqcHpMJzdFkHpR
U79XaU3YUS8wB1Kyu+BR+IPOgrfQtGzKq4Nh2nVIYFyH1xWXIJS3nl/zGMBlpHPb
ES/EN9yN3XueeMSwvd4Rwu/SHfCsLjuD8lHhMK99inerz6Lr8s8xvcppPFGuOmnH
QJpYcjQ31ME26LnJXYZOHdFl2P7bVV1IGo+dIwIDAQABAoIBAHeHcfI6uBwkSHb+
l1DW8jSv9646yabgbZKDAEjwOrk+Dbjrevo7JKQe/R6XGmXYlFqNF+5nO9ZwjzZF
0soWyBuNgfpswQMpSZcppr+27oqlKqc8lVldGx3Ju0BDLO3/asGv6MGfuy/GT2EW
h9qw7ctst9TCqWLonlRKYlUDRRyUGjAEN10OgRk1RaDiWJF0EY/+1jEtyiKdnzd0
nv9L86PXnGg4z9wBkiHexeD0PShjHCWBAWDtQvkJeCpaLAoZ2Nd+JdcuEDkK3Thx
ynHTWCsuFWTQAWo/cbVJ/pQHUBCTZXGAe9RuPzzFqyAThiFElr0vn0Ml5655qtL2
XsfeiVECgYEA23O7HNQ9WF/A0dIU6srWbwafco3FuE0mraPhkZo/n4EMqow/y40U
gXXQ7Kp2R4/9uFU/hp409MwquSBlNzTAnN5KM/fiyHNiuxTywJSl2tsaNX5a32+T
1Lb+CDGl6RtZpjIZBi17WdT3GOKAE/D/3BFDyh0Nw99uvI5XD0vztckCgYEAwFSW
AEErWzuf/JOLeasAKEAcW3Q5upbrKnvFctaHxxH75snR6tTjbEbZq16rghNZYF7v
wegd5Fy60+/QTwzwvuygnNKqKREhdrryGQgiG7CD2SFqHAkSCcliB7dP0yyzkkR9
L+7obT2R6DB/nV4zv+OYk2MP249LKFk4oiblIYsCgYBuduIAEAHVI1XvCD3JNlMc
Tgwi4KRfMk6+5xhbb3aJNq+GhdRzBNAGnqSNDP0+5odDq32vqKFlfAQhbeIlGOO/
0tEtOaEpX5OaMmBDek/GS7X0qWbaw9J5J6fVvhASt9a3ps4b4vcNb/r1xsXLw+s2
/mXOLjPIngai2U+Pfp7tqQKBgB0GJsTPEN3pt5EEKw4nUhTA6AadGYEg+Ugl+XwF
B+RwwFTpq/YGPnO+lWaZGMS+asRyTzgx8SDfJYqKLCNhzorhZrODzw33eddTCung
IlWPY7ZGpp6od8JmU5bagP9bRZYTI9kx8n1Zx0UE3J1A9ApHLGVBk8kMbMkf/b3q
pLVVAoGAXbpuE8d+KRXCq52lWNBFMzmV2eYF2Td7JsY2WRAvPRCS/WeexVhOqxW6
v//2ZWhw8nfbPF+nA5ruwTj3Cy+Zv170CmQQdNSNXFsHM7dvMGlJOy4OSF9fVUBa
18JVKOJs/gLmrtCW73SZMAPjfPvkaFIn6+mwmXimqnIULJaHugQ=
-----END RSA PRIVATE KEY-----"""


class StigaAuthError(Exception):
    pass


class StigaAPIError(Exception):
    pass


@dataclass
class StigaDevice:
    uuid: str
    name: str
    mac_address: str
    broker_id: str
    product_code: str
    serial_number: str
    firmware_version: str = ""
    base_uuid: str = ""
    total_work_time: Optional[int] = None  # hours, from REST /garage attributes.total_work_time
    last_position_lat: Optional[float] = None  # absolute GPS from /api/garage, used as RTK reference proxy
    last_position_lon: Optional[float] = None

    @property
    def unique_id(self) -> str:
        return self.mac_address.replace(":", "").lower()


@dataclass
class StigaDeviceStatus:
    operation: int = 0
    # Error / info
    error_code1: int = 0
    error_code2: int = 0
    info_code: Optional[int] = None
    docking: bool = False
    # Battery
    battery_percent: Optional[int] = None
    battery_capacity_mah: Optional[int] = None
    # Mowing
    zone: Optional[int] = None
    zone_completed: Optional[float] = None
    garden_completed: Optional[float] = None
    # GPS / Location
    gps_satellites: Optional[int] = None
    gps_coverage: Optional[int] = None
    rtk_quality: Optional[int] = None
    # Cellular network
    rssi: Optional[int] = None
    rsrp: Optional[int] = None
    rsrq: Optional[int] = None
    signal_quality: Optional[int] = None


@dataclass
class StigaRobotSettings:
    """Robot configuration — sourced from MQTT LOG/SETTINGS (cmd 17 response)."""
    cutting_height: int = 45          # mm
    rain_sensor_enabled: bool = False
    rain_sensor_delay: int = 4        # hours
    anti_theft: bool = False
    keyboard_lock: bool = False
    push_notifications: bool = True
    obstacle_notifications: bool = False
    smart_cut_height: bool = False
    long_exit_enabled: bool = False


@dataclass
class StigaScheduleBlock:
    """One contiguous mowing window within a single day."""
    day_index: int   # 0=Monday … 6=Sunday
    start_slot: int  # 0–47  (slot n = n*30 min from midnight)
    end_slot: int    # 0–47, inclusive


@dataclass
class StigaRobotSchedule:
    """Weekly mowing schedule — sourced from MQTT LOG/SCHEDULING_SETTINGS (cmd 19 response)."""
    enabled: bool = False
    blocks: list = field(default_factory=list)  # list[StigaScheduleBlock]
    schedule_type: int = 5


@dataclass
class StigaRobotPosition:
    """Robot GPS position — sourced from MQTT LOG/ROBOT_POSITION (cmd 22 response).

    Offsets are in metres relative to the base station.  To get absolute lat/lon,
    add offsets to the base station's known coordinates (see coordinator.base_lat/lon).
    """
    offset_lat_m: float = 0.0   # metres north (+) / south (-)
    offset_lon_m: float = 0.0   # metres east (+) / west (-)
    heading: float = 0.0        # compass bearing, degrees 0–360


@dataclass
class StigaZoneInfo:
    """Per-zone data from REST GET /api/perimeters data_points blob."""
    id: int
    name: str
    cutting_mode: int  # 0=denseGrid, 1=chessBoard, 5=northSouth, 6=eastWest
    polygon: list = field(default_factory=list)  # [[lat, lon], ...]


@dataclass
class StigaObstacleInfo:
    """Obstacle/exclusion zone from REST GET /api/perimeters."""
    id: int
    name: str
    polygon: list = field(default_factory=list)  # [[lat, lon], ...]


@dataclass
class StigaGardenInfo:
    """Garden layout summary from REST GET /api/perimeters."""
    total_area_m2: float | None = None
    zones_count: int | None = None
    zones_area_m2: float | None = None
    obstacles_count: int | None = None
    obstacles_area_m2: float | None = None
    zones: list = field(default_factory=list)         # list[StigaZoneInfo]
    obstacles_geo: list = field(default_factory=list) # list[StigaObstacleInfo]
    reference_lat: float | None = None
    reference_lon: float | None = None


def _fixed64_to_double(val: int) -> float:
    """Reinterpret a uint64 (from protobuf fixed64) as an IEEE 754 little-endian double."""
    return struct.unpack("<d", val.to_bytes(8, "little"))[0]


def _ecef_to_wgs84(x: float, y: float, z: float) -> tuple[float, float]:
    """Convert ECEF (metres) to WGS84 (lat, lon) decimal degrees.

    Uses Bowring's iterative method — converges in 4-5 iterations.
    """
    a = 6378137.0           # WGS84 semi-major axis
    e2 = 0.00669437999014   # first eccentricity squared
    lon_deg = math.degrees(math.atan2(y, x))
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1.0 - e2))
    for _ in range(5):
        sin_lat = math.sin(lat)
        N = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
        lat = math.atan2(z + e2 * N * sin_lat, p)
    return math.degrees(lat), lon_deg


def _decode_ecef_reference(attrs: dict) -> tuple[float | None, float | None]:
    """Extract the ECEF reference point from field 5 of the perimeter protobuf blob.

    The blob layout (reverse-engineered, confirmed in stiga-probe-perimeter-points.js):
      field 1 = zones, field 2 = paths, field 3 = obstacles, field 5 = ECEF of reference
    Field 5 is a sub-message {1: x_m, 2: y_m, 3: z_m} (fixed64 doubles, metres).
    This is the highest-precision source for the RTK coordinate origin — more accurate
    than the API's preview.referencePosition (which may be rounded or absent).
    """
    dp_data = (attrs.get("data_points") or {}).get("data")
    if not dp_data:
        return None, None
    try:
        outer = decode_protobuf_repeated(bytes(dp_data))
        ecef_entries = outer.get(5, [])
        if not ecef_entries or not isinstance(ecef_entries[0], bytes):
            return None, None
        ef = decode_protobuf_repeated(ecef_entries[0])
        x = _fixed64_to_double(ef[1][0])
        y = _fixed64_to_double(ef[2][0])
        z = _fixed64_to_double(ef[3][0])
        lat, lon = _ecef_to_wgs84(x, y, z)
        # Sanity check: must be plausible Earth-surface coordinates
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None, None
        return lat, lon
    except Exception:
        return None, None


def _parse_last_position(attrs: dict) -> dict:
    """Extract last_position lat/lon from garage API device attributes.

    The cloud stores no dedicated RTK base coordinates — the device's last GPS
    fix (recorded near the dock) is the best available proxy, matching how the
    official JS client seeds its reference position.
    """
    coords = (attrs.get("last_position") or {}).get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        try:
            return {"last_position_lat": float(coords[0]), "last_position_lon": float(coords[1])}
        except (TypeError, ValueError):
            pass
    return {}


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _decode_perimeter_geometry(
    attrs: dict,
    ref_lat: float,
    ref_lon: float,
) -> tuple[list, list]:
    """Decode zone and obstacle polygons from raw perimeter attributes.

    Protobuf layout (reverse-engineered, see StigaAPIPerimeters.js):
      outer field 1 = zones, field 3 = obstacles (repeated length-delimited)
      each entry: field 1 = id, field 2 = points[], field 15 = name
      anchor: field 16 (zones) / field 6 (obstacles) → { 1: eastM fixed64, 2: northM fixed64 }
      point:  { 1: x, 2: y } zigzag-encoded signed centimetres offset from anchor

    Returns (zone_list, obstacle_list) each as [{"id", "name", "polygon": [[lat, lon], ...]}, ...].
    """
    dp_data = (attrs.get("data_points") or {}).get("data")
    if not dp_data:
        return [], []
    LAT_M_PER_DEG = 111320.0
    lon_m_per_deg = LAT_M_PER_DEG * math.cos(math.radians(ref_lat))

    try:
        outer = decode_protobuf_repeated(bytes(dp_data))
    except Exception:
        return [], []

    def _parse_entry(entry_bytes: bytes, anchor_field: int) -> dict | None:
        try:
            ef = decode_protobuf_repeated(entry_bytes)
        except Exception:
            return None
        ids = ef.get(1, [])
        if not ids or not isinstance(ids[0], int):
            return None
        zone_id = ids[0]

        names = ef.get(15, [])
        name_raw = names[0] if names else None
        if isinstance(name_raw, bytes):
            try:
                name = name_raw.decode("utf-8").strip("\x00") or f"Area {zone_id}"
            except UnicodeDecodeError:
                name = f"Area {zone_id}"
        else:
            name = f"Area {zone_id}"

        ancs = ef.get(anchor_field, [])
        if not ancs or not isinstance(ancs[0], bytes):
            return None
        try:
            af = decode_protobuf_repeated(ancs[0])
        except Exception:
            return None
        e_vals = af.get(1, [])
        n_vals = af.get(2, [])
        if not e_vals or not n_vals:
            return None
        anchor_e = _fixed64_to_double(e_vals[0])
        anchor_n = _fixed64_to_double(n_vals[0])

        polygon = []
        for pt_raw in ef.get(2, []):
            if isinstance(pt_raw, bytes) and pt_raw:
                try:
                    pf = decode_protobuf_repeated(pt_raw)
                    x = _zigzag(pf.get(1, [0])[0])
                    y = _zigzag(pf.get(2, [0])[0])
                except Exception:
                    x = y = 0
            else:
                x = y = 0
            east_m = anchor_e + x / 100
            north_m = anchor_n + y / 100
            polygon.append([
                round(ref_lat + north_m / LAT_M_PER_DEG, 7),
                round(ref_lon + east_m / lon_m_per_deg, 7),
            ])
        return {"id": zone_id, "name": name, "polygon": polygon}

    zone_list = []
    for entry_bytes in outer.get(1, []):
        if isinstance(entry_bytes, bytes):
            entry = _parse_entry(entry_bytes, anchor_field=16)
            if entry and len(entry["polygon"]) >= 3:
                zone_list.append(entry)

    obs_list = []
    for entry_bytes in outer.get(3, []):
        if isinstance(entry_bytes, bytes):
            entry = _parse_entry(entry_bytes, anchor_field=6)
            if entry and len(entry["polygon"]) >= 3:
                obs_list.append(entry)

    return zone_list, obs_list


def _decode_schedule_bitmap(bitmap: bytes) -> list[StigaScheduleBlock]:
    """Parse the 42-byte weekly bitmap (7 days × 6 bytes × 8 bits = 48 half-hour slots/day)."""
    if len(bitmap) != 42:
        return []
    blocks: list[StigaScheduleBlock] = []
    for day_index in range(7):
        block_start = -1
        for slot in range(48):
            byte_idx = day_index * 6 + slot // 8
            bit = (bitmap[byte_idx] >> (slot % 8)) & 1
            if bit and block_start == -1:
                block_start = slot
            elif not bit and block_start != -1:
                blocks.append(StigaScheduleBlock(day_index, block_start, slot - 1))
                block_start = -1
        if block_start != -1:
            blocks.append(StigaScheduleBlock(day_index, block_start, 47))
    return blocks


def _encode_schedule_bitmap(blocks: list[StigaScheduleBlock]) -> bytes:
    """Encode schedule blocks back to the 42-byte weekly bitmap."""
    bitmap = bytearray(42)
    for block in blocks:
        for slot in range(block.start_slot, block.end_slot + 1):
            byte_idx = block.day_index * 6 + slot // 8
            bitmap[byte_idx] |= 1 << (slot % 8)
    return bytes(bitmap)


class StigaAuth:
    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._token: Optional[str] = None
        self._token_expires: float = 0.0

    async def get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 300:
            return self._token
        await self._authenticate()
        return self._token  # type: ignore[return-value]

    async def _authenticate(self) -> None:
        url = f"{FIREBASE_AUTH_URL}?key={FIREBASE_API_KEY}"
        payload = {
            "email": self._email,
            "password": self._password,
            "returnSecureToken": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise StigaAuthError(
                        f"Authentication failed ({resp.status}): {body}"
                    )
                data = await resp.json()
        self._token = data["idToken"]
        self._token_expires = time.time() + int(data.get("expiresIn", 3600))
        _LOGGER.debug("Firebase token acquired, expires in %s s", data.get("expiresIn"))


class StigaRestClient:
    def __init__(self, auth: StigaAuth) -> None:
        self._auth = auth

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        token = await self._auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        url = f"{STIGA_API_BASE_URL}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status not in (200, 201, 204):
                    body = await resp.text()
                    raise StigaAPIError(
                        f"API request failed ({resp.status}): {body}"
                    )
                if resp.status == 204:
                    return {}
                return await resp.json()

    async def get_user(self) -> dict:
        return await self._request("GET", "/api/user")

    async def get_devices(self) -> list[StigaDevice]:
        data = await self._request(
            "GET", "/api/garage", params={"relationships": "base,connpack"}
        )
        devices: list[StigaDevice] = []
        for item in data.get("data", []):
            if item.get("type") != "devices":
                continue
            attrs = item.get("attributes", {})
            device = StigaDevice(
                uuid=attrs.get("uuid", ""),
                name=attrs.get("name", "Unknown Mower"),
                mac_address=attrs.get("mac_address", ""),
                broker_id=attrs.get("broker_id", ""),
                product_code=attrs.get("product_code", ""),
                serial_number=attrs.get("serial_number", ""),
                firmware_version=attrs.get("firmware_version", ""),
                base_uuid=attrs.get("base_uuid", ""),
                total_work_time=int(raw_twt) if (raw_twt := attrs.get("total_work_time")) is not None else None,
                **_parse_last_position(attrs),
            )
            _LOGGER.debug(
                "Found device: name=%s mac=%s broker=%s",
                device.name, device.mac_address, device.broker_id,
            )
            devices.append(device)
        return devices

    async def get_perimeters(
        self,
        device: StigaDevice,
        fallback_lat: float | None = None,
        fallback_lon: float | None = None,
    ) -> tuple[StigaGardenInfo, dict | None]:
        """Fetch garden layout and raw attributes (needed for later PATCH calls)."""
        if not device.uuid or not device.base_uuid:
            _LOGGER.debug("Skipping perimeter fetch: device missing uuid or base_uuid")
            return StigaGardenInfo(), None
        data = await self._request(
            "GET", "/api/perimeters",
            params={"base_uuid": device.base_uuid, "device_uuid": device.uuid},
        )
        try:
            attrs = data["data"]["attributes"]
            preview = attrs.get("preview") or {}
            zones_summary = preview.get("zones") or {}
            obstacles_summary = preview.get("obstacles") or {}

            # --- Determine RTK reference position (priority order) ---
            # 1. ECEF from protobuf field 5 — embedded in the data, highest precision
            # 2. API preview.referencePosition — may be rounded/absent
            # 3. HA-configured base coordinates — manual fallback

            ref_lat: float | None = None
            ref_lon: float | None = None
            ref_source: str = "none"

            ecef_lat, ecef_lon = _decode_ecef_reference(attrs)
            if ecef_lat is not None:
                ref_lat, ref_lon = ecef_lat, ecef_lon
                ref_source = "ECEF (protobuf field 5)"
            else:
                ref_pos = preview.get("referencePosition") or {}
                api_lat: float | None = ref_pos.get("lat")
                api_lon: float | None = ref_pos.get("lng")
                if api_lat is not None and api_lon is not None:
                    ref_lat, ref_lon = api_lat, api_lon
                    ref_source = "API referencePosition"
                elif fallback_lat is not None and fallback_lon is not None:
                    ref_lat, ref_lon = fallback_lat, fallback_lon
                    ref_source = "HA base config (fallback)"

            if ref_lat is not None:
                _LOGGER.debug(
                    "RTK reference for %s: (%.7f, %.7f) — source: %s",
                    device.name, ref_lat, ref_lon, ref_source,
                )
            else:
                _LOGGER.warning(
                    "No RTK reference available for %s — zone polygons will not be shown. "
                    "Configure base station coordinates in integration settings if ECEF field "
                    "and API referencePosition are both absent. Preview keys: %s",
                    device.name, list(preview.keys()),
                )

            # Decode polygon geometry
            zone_geo_list: list[dict] = []
            obs_geo_list: list[dict] = []
            if ref_lat is not None and ref_lon is not None:
                zone_geo_list, obs_geo_list = _decode_perimeter_geometry(attrs, ref_lat, ref_lon)
                if not zone_geo_list:
                    _LOGGER.warning(
                        "referencePosition found (%.6f, %.6f) but no zone polygons decoded — "
                        "data_points blob may be empty or use an unexpected protobuf layout. "
                        "dp_data present: %s, length: %s",
                        ref_lat, ref_lon,
                        bool((attrs.get("data_points") or {}).get("data")),
                        len((attrs.get("data_points") or {}).get("data") or []),
                    )
            zone_polygon_map = {z["id"]: z["polygon"] for z in zone_geo_list}

            zones: list[StigaZoneInfo] = []
            dp_data = (attrs.get("data_points") or {}).get("data")
            if isinstance(dp_data, list) and dp_data:
                try:
                    outer = decode_protobuf_repeated(bytes(dp_data))
                    for zone_bytes in outer.get(1, []):
                        if not isinstance(zone_bytes, bytes):
                            continue
                        zf = decode_protobuf(zone_bytes)
                        zone_id = zf.get(1)
                        if not isinstance(zone_id, int):
                            continue
                        raw_name = zf.get(15)
                        if isinstance(raw_name, bytes):
                            try:
                                name = raw_name.decode("utf-8").strip("\x00") or f"Zone {zone_id}"
                            except UnicodeDecodeError:
                                name = f"Zone {zone_id}"
                        else:
                            name = f"Zone {zone_id}"
                        cutting_mode = zf.get(8, 0)
                        zones.append(StigaZoneInfo(
                            id=zone_id,
                            name=name,
                            cutting_mode=int(cutting_mode) if isinstance(cutting_mode, int) else 0,
                            polygon=zone_polygon_map.get(zone_id, []),
                        ))
                    zones.sort(key=lambda z: z.id)
                except Exception as exc:
                    _LOGGER.debug("Failed to parse zone settings from data_points: %s", exc)

            obstacles_geo = [
                StigaObstacleInfo(id=o["id"], name=o["name"], polygon=o["polygon"])
                for o in obs_geo_list
            ]

            garden_info = StigaGardenInfo(
                total_area_m2=preview.get("m2Area"),
                zones_count=zones_summary.get("num"),
                zones_area_m2=zones_summary.get("m2Area"),
                obstacles_count=obstacles_summary.get("num"),
                obstacles_area_m2=obstacles_summary.get("m2Area"),
                zones=zones,
                obstacles_geo=obstacles_geo,
                reference_lat=ref_lat,
                reference_lon=ref_lon,
            )
            _LOGGER.debug(
                "Perimeters: area=%s m², zones=%s (%s with polygons), obstacles=%s (%s with polygons)",
                garden_info.total_area_m2,
                garden_info.zones_count,
                len([z for z in zones if z.polygon]),
                garden_info.obstacles_count,
                len(obstacles_geo),
            )
            return garden_info, attrs
        except (KeyError, TypeError) as exc:
            _LOGGER.debug("Failed to parse perimeter response: %s", exc)
            return StigaGardenInfo(), None

    async def patch_perimeter_cutting_mode(
        self,
        perimeter_attrs: dict,
        zone_id: int,
        mode_value: int,
    ) -> dict:
        """Patch cuttingMode for one zone, PATCH to cloud, return updated attributes."""
        attrs = copy.deepcopy(perimeter_attrs)

        dp = attrs.get("data_points") or {}
        raw_data = dp.get("data")
        if not isinstance(raw_data, list) or not raw_data:
            raise StigaAPIError("Perimeter data_points.data missing or invalid")

        dp["data"] = patch_zone_cutting_mode(raw_data, zone_id, mode_value)
        attrs["data_points"] = dp

        now_ms = int(time.time() * 1000)
        now_str = str(now_ms)
        for section_key in ("preview", "data_points"):
            section = attrs.get(section_key)
            if isinstance(section, dict):
                section["timestamp"] = now_ms
                section["checksum"] = now_str

        attrs = {k: v for k, v in attrs.items() if v is not None}

        uuid = attrs.get("uuid")
        if not uuid:
            raise StigaAPIError("Perimeter attributes missing uuid")

        await self._request("PATCH", f"/api/perimeters/{uuid}", json={"data": attrs})
        _LOGGER.debug("Patched cuttingMode zone=%s mode=%s perimeter=%s", zone_id, mode_value, uuid)
        return attrs


class StigaMQTTClient:
    def __init__(self, device: StigaDevice, auth: StigaAuth) -> None:
        self._device = device
        self._auth = auth
        self._client: Optional[mqtt.Client] = None
        self._status = StigaDeviceStatus()
        self._settings = StigaRobotSettings()
        self._callbacks: list[Callable[[StigaDeviceStatus], None]] = []
        self._settings_callbacks: list[Callable[[StigaRobotSettings], None]] = []
        self._schedule_callbacks: list[Callable[[StigaRobotSchedule], None]] = []
        self._position_callbacks: list[Callable[[StigaRobotPosition], None]] = []
        self._schedule = StigaRobotSchedule()
        self._position: Optional[StigaRobotPosition] = None
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._cert_path: Optional[str] = None
        self._key_path: Optional[str] = None
        self._mac: str = device.mac_address
        self._mac_norm: str = device.mac_address.replace(":", "").lower()

    def add_status_callback(
        self, callback: Callable[[StigaDeviceStatus], None]
    ) -> None:
        self._callbacks.append(callback)

    def add_settings_callback(
        self, callback: Callable[[StigaRobotSettings], None]
    ) -> None:
        self._settings_callbacks.append(callback)

    def add_schedule_callback(
        self, callback: Callable[[StigaRobotSchedule], None]
    ) -> None:
        self._schedule_callbacks.append(callback)

    def add_position_callback(
        self, callback: Callable[[StigaRobotPosition], None]
    ) -> None:
        self._position_callbacks.append(callback)

    @property
    def status(self) -> StigaDeviceStatus:
        return self._status

    @property
    def settings(self) -> StigaRobotSettings:
        return self._settings

    @property
    def schedule(self) -> StigaRobotSchedule:
        return self._schedule

    @property
    def position(self) -> Optional[StigaRobotPosition]:
        return self._position

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._loop = asyncio.get_event_loop()
        token = await self._auth.get_token()

        if not self._device.mac_address:
            raise StigaAPIError(f"Device '{self._device.name}' is missing mac_address.")

        primary_broker = MQTT_BROKER_FORMAT.format(broker_id=self._device.broker_id)
        mac = self._device.mac_address
        mac_norm = mac.replace(":", "").lower()
        uuid = self._device.uuid

        # Match JS clientId format: `${deviceUuid}_${Date.now().toString(36)}_${random}`
        # The broker ACL checks that clientId starts with the device UUID.
        _b36 = "0123456789abcdefghijklmnopqrstuvwxyz"
        def _to_base36(n: int) -> str:
            s = ""
            while n:
                s = _b36[n % 36] + s
                n //= 36
            return s or "0"
        import random as _random
        ts36 = _to_base36(int(time.time() * 1000))
        rand36 = "".join(_random.choices(_b36, k=7))
        client_id = f"{uuid}_{ts36}_{rand36}"

        import socket as _socket

        def _make_client(broker: str, timeout: int) -> mqtt.Client:
            # All blocking SSL/TLS ops must run outside the event loop.
            cert_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".pem", delete=False, prefix="stiga_cert_"
            )
            cert_file.write(MQTT_CLIENT_CERT)
            cert_file.flush()
            cert_file.close()

            key_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".pem", delete=False, prefix="stiga_key_"
            )
            key_file.write(MQTT_CLIENT_KEY)
            key_file.flush()
            key_file.close()

            self._cert_path = cert_file.name
            self._key_path = key_file.name

            _LOGGER.debug("MQTT: client_id=%s", client_id)
            c = mqtt.Client(client_id=client_id)
            c.username_pw_set(MQTT_USERNAME, token)
            # Stiga broker uses a self-signed certificate chain — disable server
            # cert verification while still using mutual TLS (client cert/key).
            c.tls_set(
                ca_certs=None,
                certfile=cert_file.name,
                keyfile=key_file.name,
                cert_reqs=ssl.CERT_NONE,
            )
            c.tls_insecure_set(True)
            # Slow down paho auto-reconnect — coordinator handles retries
            c.reconnect_delay_set(min_delay=300, max_delay=600)

            _LOGGER.debug("MQTT: trying %s:%s (timeout=%ds)", broker, MQTT_PORT, timeout)
            old_timeout = _socket.getdefaulttimeout()
            _socket.setdefaulttimeout(timeout)
            try:
                c.connect(broker, MQTT_PORT, keepalive=60)
            finally:
                _socket.setdefaulttimeout(old_timeout)
            return c

        # Try primary broker first with a short timeout, fall back to the
        # generic broker if it times out.
        # Known issue: broker_id-specific hosts may not respond even though
        # they resolve in DNS. github.com/matthewgream/stiga-api/issues/7
        try:
            client = await self._loop.run_in_executor(
                None, lambda: _make_client(primary_broker, 8)
            )
            _LOGGER.debug("MQTT: connected via primary broker %s", primary_broker)
        except (TimeoutError, OSError, _socket.timeout):
            _LOGGER.warning(
                "MQTT: primary broker %s timed out, trying fallback %s",
                primary_broker,
                MQTT_BROKER_FALLBACK,
            )
            client = await self._loop.run_in_executor(
                None, lambda: _make_client(MQTT_BROKER_FALLBACK, 15)
            )
            _LOGGER.debug("MQTT: connected via fallback broker %s", MQTT_BROKER_FALLBACK)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        self._client = client
        self._mac = mac
        self._mac_norm = mac_norm
        client.loop_start()

    def _on_subscribe(self, client: mqtt.Client, userdata: Any, mid: int, granted_qos: Any) -> None:
        _LOGGER.debug("MQTT SUBACK mid=%d granted_qos=%s", mid, granted_qos)

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int) -> None:
        if rc == 0:
            self._connected = True
            mac = self._mac
            client.on_subscribe = self._on_subscribe
            _LOGGER.info("MQTT connected for device %s", mac)
            # Topic format from StigaAPIElements.js ROBOT_MESSAGE_TOPICS:
            #   {mac}/LOG/+          — all log messages (STATUS, VERSION, SETTINGS, …)
            #   CMD_ROBOT_ACK/{mac}  — command acknowledgements
            #   {mac}/JSON_NOTIFICATION — firmware OTA / notifications
            for topic in [
                f"{mac}/LOG/+",
                f"CMD_ROBOT_ACK/{mac}",
                f"{mac}/JSON_NOTIFICATION",
                f"{mac}/LOG/SCHEDULING_SETTINGS",
            ]:
                res, mid = client.subscribe(topic, qos=0)
                _LOGGER.debug("MQTT subscribe '%s' res=%d mid=%d", topic, res, mid)
            # Request initial status and settings
            status_payload = encode_robot_command(
                ROBOT_CMD_STATUS_REQUEST, encode_status_request_fields()
            )
            client.publish(f"{mac}/CMD_ROBOT", status_payload, qos=2)
            _LOGGER.debug("MQTT: sent initial STATUS_REQUEST to %s/CMD_ROBOT", mac)
            settings_payload = encode_robot_command(ROBOT_CMD_SETTINGS_REQUEST)
            client.publish(f"{mac}/CMD_ROBOT", settings_payload, qos=2)
            _LOGGER.debug("MQTT: sent initial SETTINGS_REQUEST to %s/CMD_ROBOT", mac)
            schedule_payload = encode_robot_command(ROBOT_CMD_SCHEDULING_REQUEST)
            client.publish(f"{mac}/CMD_ROBOT", schedule_payload, qos=2)
            _LOGGER.debug("MQTT: sent initial SCHEDULING_SETTINGS_REQUEST to %s/CMD_ROBOT", mac)
            position_payload = encode_robot_command(ROBOT_CMD_POSITION_REQUEST)
            client.publish(f"{mac}/CMD_ROBOT", position_payload, qos=2)
            _LOGGER.debug("MQTT: sent initial POSITION_REQUEST to %s/CMD_ROBOT", mac)
        else:
            _LOGGER.error("MQTT connection failed with code %d", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        _LOGGER.debug("MQTT message on topic: %s (payload len=%d)", msg.topic, len(msg.payload))
        mac = self._mac
        if msg.topic == f"{mac}/LOG/STATUS":
            self._parse_status(msg.payload)
            if self._loop:
                for cb in self._callbacks:
                    self._loop.call_soon_threadsafe(cb, self._status)
        elif msg.topic == f"{mac}/LOG/SETTINGS":
            self._parse_settings(msg.payload)
            if self._loop:
                for cb in self._settings_callbacks:
                    self._loop.call_soon_threadsafe(cb, self._settings)
        elif msg.topic == f"{mac}/LOG/SCHEDULING_SETTINGS":
            self._parse_schedule(msg.payload)
            if self._loop:
                for cb in self._schedule_callbacks:
                    self._loop.call_soon_threadsafe(cb, self._schedule)
        elif msg.topic == f"{mac}/LOG/ROBOT_POSITION":
            self._parse_position(msg.payload)
            if self._loop and self._position is not None:
                for cb in self._position_callbacks:
                    self._loop.call_soon_threadsafe(cb, self._position)
        else:
            _LOGGER.debug("MQTT unhandled topic: %s", msg.topic)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self._connected = False
        if rc != 0:
            _LOGGER.warning("MQTT disconnected unexpectedly (rc=%d), stopping loop — broker rejected connection or subscription", rc)
            client.loop_stop()
        # Notify entities so cloud_connection binary sensor updates immediately
        if self._loop:
            for cb in self._callbacks:
                self._loop.call_soon_threadsafe(cb, self._status)

    @staticmethod
    def _to_int32(val: int) -> int:
        """Reinterpret uint32/uint64 varint as signed int32 (for RSSI, RSRP, RSRQ)."""
        val &= 0xFFFFFFFF
        return val - 0x100000000 if val > 0x7FFFFFFF else val

    def _parse_status(self, payload: bytes) -> None:
        try:
            fields = decode_protobuf(payload)

            if STATUS_FIELD_TYPE in fields:
                val = fields[STATUS_FIELD_TYPE]
                if isinstance(val, int):
                    self._status.operation = val

            if STATUS_FIELD_ERROR in fields:
                raw = fields[STATUS_FIELD_ERROR]
                if isinstance(raw, bytes):
                    err = decode_protobuf(raw)
                    self._status.error_code1 = err.get(1, 0) if isinstance(err.get(1), int) else 0
                    self._status.error_code2 = err.get(2, 0) if isinstance(err.get(2), int) else 0

            if STATUS_FIELD_INFO in fields:
                raw = fields[STATUS_FIELD_INFO]
                if isinstance(raw, bytes):
                    info = decode_protobuf(raw)
                    code = info.get(1)
                    self._status.info_code = code if isinstance(code, int) else None

            if STATUS_FIELD_DOCKING in fields:
                raw = fields[STATUS_FIELD_DOCKING]
                if isinstance(raw, bytes):
                    dock = decode_protobuf(raw)
                    self._status.docking = bool(dock.get(1, 0))
                elif isinstance(raw, int):
                    self._status.docking = bool(raw)

            if STATUS_FIELD_BATTERY in fields:
                raw = fields[STATUS_FIELD_BATTERY]
                if isinstance(raw, bytes):
                    batt = decode_protobuf(raw)
                    if BATTERY_FIELD_CAPACITY in batt and isinstance(batt[BATTERY_FIELD_CAPACITY], int):
                        self._status.battery_capacity_mah = batt[BATTERY_FIELD_CAPACITY]
                    if BATTERY_FIELD_PERCENT in batt and isinstance(batt[BATTERY_FIELD_PERCENT], int):
                        self._status.battery_percent = batt[BATTERY_FIELD_PERCENT]

            if STATUS_FIELD_MOWING in fields:
                raw = fields[STATUS_FIELD_MOWING]
                if isinstance(raw, bytes):
                    mow = decode_protobuf(raw)
                    if MOWING_FIELD_ZONE in mow and isinstance(mow[MOWING_FIELD_ZONE], int):
                        self._status.zone = mow[MOWING_FIELD_ZONE]
                    if MOWING_FIELD_ZONE_COMPLETED in mow and isinstance(mow[MOWING_FIELD_ZONE_COMPLETED], int):
                        self._status.zone_completed = mow[MOWING_FIELD_ZONE_COMPLETED]
                    if MOWING_FIELD_GARDEN_COMPLETED in mow and isinstance(mow[MOWING_FIELD_GARDEN_COMPLETED], int):
                        self._status.garden_completed = mow[MOWING_FIELD_GARDEN_COMPLETED]

            if STATUS_FIELD_LOCATION in fields:
                raw = fields[STATUS_FIELD_LOCATION]
                if isinstance(raw, bytes):
                    loc = decode_protobuf(raw)
                    if LOCATION_COVERAGE in loc and isinstance(loc[LOCATION_COVERAGE], int):
                        self._status.gps_coverage = loc[LOCATION_COVERAGE]
                    if LOCATION_SATELLITES in loc and isinstance(loc[LOCATION_SATELLITES], int):
                        self._status.gps_satellites = loc[LOCATION_SATELLITES]
                    if LOCATION_RTK_QUALITY in loc and isinstance(loc[LOCATION_RTK_QUALITY], int):
                        self._status.rtk_quality = loc[LOCATION_RTK_QUALITY]

            if STATUS_FIELD_NETWORK in fields:
                raw = fields[STATUS_FIELD_NETWORK]
                if isinstance(raw, bytes):
                    net = decode_protobuf(raw)
                    inner_raw = net.get(NETWORK_INNER)
                    if isinstance(inner_raw, bytes):
                        inner = decode_protobuf(inner_raw)
                        rssi = inner.get(NETWORK_RSSI)
                        if isinstance(rssi, int):
                            self._status.rssi = self._to_int32(rssi)
                        rsrp = inner.get(NETWORK_RSRP)
                        if isinstance(rsrp, int):
                            self._status.rsrp = self._to_int32(rsrp)
                        rsrq = inner.get(NETWORK_RSRQ)
                        if isinstance(rsrq, int):
                            self._status.rsrq = self._to_int32(rsrq)
                        sq = inner.get(NETWORK_SQ)
                        if isinstance(sq, int):
                            self._status.signal_quality = self._to_int32(sq)

        except Exception as exc:
            _LOGGER.debug("Error parsing STATUS message: %s", exc)

    def _parse_settings(self, payload: bytes) -> None:
        try:
            fields = decode_protobuf(payload)

            rain_raw = fields.get(SETTINGS_FIELD_RAIN)
            if isinstance(rain_raw, bytes):
                rain = decode_protobuf(rain_raw)
                enabled = rain.get(1)
                if isinstance(enabled, int):
                    self._settings.rain_sensor_enabled = bool(enabled)
                delay_idx = rain.get(2)
                if isinstance(delay_idx, int):
                    self._settings.rain_sensor_delay = RAIN_DELAY_BY_IDX.get(delay_idx, 4)

            kl = fields.get(SETTINGS_FIELD_KEYBOARD_LOCK)
            if isinstance(kl, int):
                self._settings.keyboard_lock = bool(kl)

            zh_raw = fields.get(SETTINGS_FIELD_ZONE_HEIGHT)
            if isinstance(zh_raw, bytes):
                zh = decode_protobuf(zh_raw)
                h_idx = zh.get(2)
                if isinstance(h_idx, int):
                    self._settings.cutting_height = CUTTING_HEIGHT_BY_IDX.get(h_idx, 45)

            at = fields.get(SETTINGS_FIELD_ANTI_THEFT)
            if isinstance(at, int):
                self._settings.anti_theft = bool(at)

            sc = fields.get(SETTINGS_FIELD_SMART_CUT)
            if isinstance(sc, int):
                self._settings.smart_cut_height = bool(sc)

            le_raw = fields.get(SETTINGS_FIELD_LONG_EXIT)
            if isinstance(le_raw, bytes):
                le = decode_protobuf(le_raw)
                le_val = le.get(1)
                if isinstance(le_val, int):
                    self._settings.long_exit_enabled = bool(le_val)

            pn_raw = fields.get(SETTINGS_FIELD_PUSH_NOTIFICATIONS)
            if isinstance(pn_raw, bytes):
                pn = decode_protobuf(pn_raw)
                pn_val = pn.get(1)
                if isinstance(pn_val, int):
                    self._settings.push_notifications = bool(pn_val)

            on_raw = fields.get(SETTINGS_FIELD_OBSTACLE_NOTIFICATIONS)
            if isinstance(on_raw, bytes):
                on_ = decode_protobuf(on_raw)
                on_val = on_.get(1)
                if isinstance(on_val, int):
                    self._settings.obstacle_notifications = bool(on_val)

        except Exception as exc:
            _LOGGER.debug("Error parsing SETTINGS message: %s", exc)

    async def send_command(self, command_type: int) -> None:
        if not self._client or not self._connected:
            raise StigaAPIError("MQTT not connected")
        payload = encode_robot_command(command_type)
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.publish(topic, payload, qos=2),
        )
        _LOGGER.debug("Sent command %d to %s", command_type, topic)

    async def request_status(self) -> None:
        """Send STATUS_REQUEST so robot publishes its current state."""
        if not self._client or not self._connected:
            return
        payload = encode_robot_command(ROBOT_CMD_STATUS_REQUEST, encode_status_request_fields())
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.publish(topic, payload, qos=2),
        )

    async def request_settings(self) -> None:
        """Send SETTINGS_REQUEST so robot publishes its current settings."""
        if not self._client or not self._connected:
            return
        payload = encode_robot_command(ROBOT_CMD_SETTINGS_REQUEST)
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.publish(topic, payload, qos=2),
        )

    async def send_settings_update(self, settings_fields: dict) -> None:
        """Send SETTINGS_UPDATE with a partial settings dict.

        Keys are protobuf field numbers from SETTINGS_FIELD_* constants.
        Values are ints (varint) or dicts (nested sub-messages).
        """
        if not self._client or not self._connected:
            raise StigaAPIError("MQTT not connected")
        fields_payload = encode_protobuf(settings_fields)
        payload = encode_robot_command(ROBOT_CMD_SETTINGS_UPDATE, fields_payload)
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.publish(topic, payload, qos=2),
        )
        _LOGGER.debug("Sent SETTINGS_UPDATE to %s", topic)

    def _parse_position(self, payload: bytes) -> None:
        try:
            fields = decode_protobuf(payload)
            # Fields 1–3 are fixed64 (wire type 1) encoding IEEE 754 doubles.
            # decoded[1] = offsetLongitudeMetres, decoded[2] = offsetLatitudeMetres,
            # decoded[3] = orientRad  — matches StigaAPIElements.js decodeRobotPosition.
            offset_lon_m = _fixed64_to_double(fields[1]) if isinstance(fields.get(1), int) else 0.0
            offset_lat_m = _fixed64_to_double(fields[2]) if isinstance(fields.get(2), int) else 0.0
            orient_rad = _fixed64_to_double(fields[3]) if isinstance(fields.get(3), int) else 0.0
            # Convert maths angle (0=East, CCW) to compass bearing (0=North, CW)
            heading = (450.0 - math.degrees(orient_rad)) % 360.0
            self._position = StigaRobotPosition(
                offset_lat_m=offset_lat_m,
                offset_lon_m=offset_lon_m,
                heading=heading,
            )
            _LOGGER.debug(
                "Parsed position: offset_lat=%.2fm offset_lon=%.2fm heading=%.1f°",
                offset_lat_m, offset_lon_m, heading,
            )
        except Exception as exc:
            _LOGGER.debug("Error parsing ROBOT_POSITION message: %s", exc)

    def _parse_schedule(self, payload: bytes) -> None:
        try:
            fields = decode_protobuf(payload)
            enabled = bool(fields.get(1, 0))
            bitmap = fields.get(2)
            schedule_type = int(fields.get(4, 5))
            blocks = _decode_schedule_bitmap(bitmap) if isinstance(bitmap, bytes) else []
            self._schedule = StigaRobotSchedule(enabled=enabled, blocks=blocks, schedule_type=schedule_type)
            _LOGGER.debug("Parsed schedule: enabled=%s blocks=%d", enabled, len(blocks))
        except Exception as exc:
            _LOGGER.debug("Error parsing SCHEDULING_SETTINGS: %s", exc)

    async def request_schedule(self) -> None:
        """Send SCHEDULING_SETTINGS_REQUEST so robot publishes its current schedule."""
        if not self._client or not self._connected:
            return
        payload = encode_robot_command(ROBOT_CMD_SCHEDULING_REQUEST)
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._client.publish(topic, payload, qos=2))

    async def request_position(self) -> None:
        """Send POSITION_REQUEST so robot publishes its current GPS position."""
        if not self._client or not self._connected:
            return
        payload = encode_robot_command(ROBOT_CMD_POSITION_REQUEST)
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._client.publish(topic, payload, qos=2))

    async def send_schedule_update(self, schedule: StigaRobotSchedule) -> None:
        """Send SCHEDULING_SETTINGS_UPDATE with the full weekly schedule."""
        if not self._client or not self._connected:
            raise StigaAPIError("MQTT not connected")
        bitmap = _encode_schedule_bitmap(schedule.blocks)
        fields_payload = encode_protobuf({
            1: 1 if schedule.enabled else 0,
            2: bitmap,
            4: schedule.schedule_type,
        })
        payload = encode_robot_command(ROBOT_CMD_SCHEDULING_UPDATE, fields_payload)
        topic = f"{self._mac}/CMD_ROBOT"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._client.publish(topic, payload, qos=2))
        _LOGGER.debug("Sent SCHEDULING_SETTINGS_UPDATE to %s (%d blocks)", topic, len(schedule.blocks))

    async def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            await asyncio.get_event_loop().run_in_executor(
                None, self._client.disconnect
            )
            self._client = None
            self._connected = False
        for path in [self._cert_path, self._key_path]:
            if path and os.path.exists(path):
                os.unlink(path)
        self._cert_path = None
        self._key_path = None

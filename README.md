# Stiga Lawn Mower

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

Unofficial Home Assistant integration for **Stiga A-series robot mowers** (Vista, A 1500, A 3000, …) controllable via the STIGA.GO app.

Not officially provided or supported by Stiga.

---

## Based on stiga-api

This integration is built entirely on the reverse-engineering work done by **[@matthewgream](https://github.com/matthewgream)** in the [stiga-api](https://github.com/matthewgream/stiga-api) project.

That project reverse-engineered the Stiga A-series communication protocol by deconstructing the official Android app — extracting the Firebase authentication flow, the REST API endpoints, the MQTT broker configuration, the mTLS certificates, and the Protobuf message format. Without that foundational work, this Home Assistant integration would not exist.
---

## Architecture

```
┌──────────────────┐    REST (every 6 h)   ┌──────────────────────┐
│  STIGA REST API  │ ────────────────────▶ │     Coordinator      │
│  - Auth/Refresh  │                       │  push-driven via     │
│  - /garage       │ ◀──── Discovery ───── │  async_set_updated_  │
│  - /perimeters   │                       │  data() per frame    │
└──────────────────┘                       └──────────────────────┘
                                                      ▲
┌──────────────────┐  Live status / cmds              │
│  STIGA MQTT      │ ────────────────────────────────▶│
│  (paho+mTLS)     │                                  │
│  cloud_push      │ ◀─── Commands ───────────────────│
└──────────────────┘                         HA Entity Layer
```

- **REST** handles authentication (Firebase), device discovery (`/garage`), and periodic refresh every 6 hours.
- **MQTT** delivers live status frames (activity, battery, GPS, network) and accepts commands (start, pause, dock, settings) with minimal latency.
- The coordinator is **push-driven**: MQTT frames trigger `async_set_updated_data` immediately; the 30-second REST poll acts as a liveness check only.

---

## Supported Models

All Stiga robots controllable via the **STIGA.GO app**:

- Vista models: A 6v, A 8v, A 10v, A 15v, …
- A-Series: A 500, A 1500, A 3000, …

---

## Features

### Lawn Mower Entity

| Feature | Notes |
|---|---|
| **Start mowing** | `lawn_mower.start_mowing` |
| **Pause** | Stops the robot in place (not dock) |
| **Return to dock** | `lawn_mower.dock` |
| **States** | `mowing`, `docked`, `returning`, `error` |

### Sensor Entities

| Sensor | Unit | Category | Notes |
|---|---|---|---|
| Battery | % | — | — |
| Status | — | — | — |
| Garden Completed | % | — | Garden completion while mowing |
| Zone | — | — | Current mowing zone number |
| Zone Completed | % | — | Completion within the current zone |
| Schedule Remaining | min | — | Minutes left in the active schedule window; `—` during spot cut |
| Battery Capacity | mAh | diagnostic | — |
| Cutting Height | mm | diagnostic | — |
| GPS Satellites | — | diagnostic | Number of visible satellites |
| GPS Coverage | — | diagnostic | — |
| RTK Quality | — | diagnostic | Only reported during RTK initialisation; `—` during normal mowing |
| RSSI | dBm | diagnostic | — |
| RSRP | dBm | diagnostic | — |
| RSRQ | dB | diagnostic | — |
| Signal Quality | % | diagnostic | — |
| Firmware Version | — | diagnostic | — |
| Total Work Time | h | diagnostic | Cumulative mowing hours |
| Garden Area | m² | — | — |
| Garden Zones | — | — | — |
| Obstacles | — | — | — |
| Obstacle Area | m² | — | — |

### Binary Sensor Entities

| Sensor | Notes |
|---|---|
| Cloud Connection | MQTT link to the STIGA cloud |
| Docked | Robot at charging station |
| Charging | Battery currently charging |
| Error | Active error condition (blocked, startup required) |
| Lid | Lid open/closed |
| Rain Sensor | Current rain detection state |
| Lift Sensor | Mower lifted off the ground |
| Bump Sensor | Collision detected |
| Slope Sensor | Slope too steep |

### Device Tracker Entity

| Entity | Notes |
|---|---|
| **Location** | Robot's real-time GPS position on the HA map — updated live while mowing |

### Number Entity (Configuration)

| Entity | Range | Step |
|---|---|---|
| Cutting Height | 20–60 mm | 5 mm |

### Switch Entities (Configuration)

| Switch | Notes |
|---|---|
| Rain Sensor | Enable/disable rain detection |
| Anti-Theft | PIN protection |
| Keyboard Lock | Lock physical buttons |
| Push Notifications | App push notifications |
| Obstacle Notifications | Notify on obstacle detection |
| Smart Cutting Height | Automatic height adjustment |
| Long Exit | Extended exit from charging station |

### Select Entities (Configuration)

| Select | Options | Notes |
|---|---|---|
| Rain Delay | 4 h / 8 h / 12 h | Delay before mowing resumes after rain |
| Cutting Mode | Dense Grid / Chess Board / North-South / East-West | Per mowing zone — one entity per zone |

### Button Entities (Diagnostic)

| Button | Notes |
|---|---|
| Calibrate Blades | Trigger blade calibration routine |
| Refresh Status | Request an immediate status update from the robot |

### Device Tracker — GPS Position on Map

The integration exposes a `device_tracker` entity that shows the robot's real-time position on the HA map, updated live as the robot mows.

**How it works:** The integration resolves the robot's absolute GPS position using two sources, applied in priority order:

1. **RTK offset (primary)** — when an RTK reference is available, the robot's metre-offset from the base station (received via MQTT) is combined with the reference coordinates to compute a centimetre-accurate position.
2. **GPS from status (fallback)** — the MQTT STATUS message also contains an absolute GPS fix (standard GPS, ~5–10 m accuracy). Used automatically when no RTK reference is configured or available — the device tracker works out of the box even without a base station.

The `position_source` attribute shows which source is active: `rtk_offset` or `gps_status`.

#### RTK reference — automatic detection

The integration determines the coordinate origin in this priority order:

1. **ECEF from protobuf** — the garden map blob always contains the RTK antenna's exact ECEF coordinates (X/Y/Z in metres). This is converted to WGS84 automatically — the most accurate source.
2. **API `referencePosition`** — some accounts include this field in the REST response. Used if ECEF is absent.
3. **HA-configured base station coordinates** — manual fallback, set during setup or via Reconfigure. Only needed if both automatic sources are absent.

In practice, automatic detection works for all robots that have a mapped garden. The manual coordinates act as a safety net for edge cases.

#### Setting up base station coordinates (fallback only)

If automatic detection fails (visible as a `WARNING` in the HA log), enter the GPS coordinates of your **RTK antenna** during initial setup or via **Reconfigure**:

| Field | Example |
|---|---|
| Base station latitude | `54.131528` |
| Base station longitude | `16.281694` |

**Accepted formats:**

| Format | Example |
|---|---|
| Decimal degrees (dot) | `54.131528` |
| Decimal degrees (comma) | `54,131528` |
| Degrees°Minutes'Seconds" | `54°07'53.5"N` |

#### Entity state

- **`home`** — robot is within the configured Home zone
- **`not_home`** — robot is outside the Home zone (normal state while mowing)
- **`unknown`** — RTK reference coordinates not yet available

#### Visualising the position

**Option 1 — Map card on a dashboard**

```yaml
type: map
entities:
  - device_tracker.<robot_name>_location
hours_to_show: 1
```

Replace `<robot_name>` with the robot name from the STIGA app (e.g. `device_tracker.bob_location`). The `hours_to_show: 1` option draws the mowing trail for the past hour.

**Option 2 — Map view** (HA sidebar)

Navigate to **Map** in the HA sidebar — the robot appears as a pin alongside all other tracked devices.

**Option 3 — Stiga Robot Card** (recommended)

The included Lovelace card shows the robot on a satellite map together with mowing zone polygons, obstacle polygons, and RTK antenna marker. See [Lovelace Card](#lovelace-card) below.

#### Extra attributes

| Attribute | Description |
|---|---|
| `position_source` | `rtk_offset` (reported accuracy 1–3 m) or `gps_status` (reported accuracy 10 m) |
| `offset_lat_m` | Metres north/south from the RTK reference origin (only when `rtk_offset`) |
| `offset_lon_m` | Metres east/west from the RTK reference origin (only when `rtk_offset`) |
| `heading` | Compass bearing the robot is facing (0–360°) |
| `distance_m` | Straight-line distance from the RTK reference origin (only when `rtk_offset`) |
| `base_station_lat` | Latitude of the RTK antenna (auto-detected) |
| `base_station_lon` | Longitude of the RTK antenna (auto-detected) |
| `zone_polygons` | List of mowing zone polygons `[{id, name, polygon: [[lat,lon],...]}]` |
| `obstacle_polygons` | List of obstacle polygons `[{id, name, polygon: [[lat,lon],...]}]` |

---

### Calendar Entity — Mowing Schedule

Displays the robot's weekly mowing schedule and allows creating or deleting time windows directly from Home Assistant — changes are sent to the robot via MQTT within seconds.

**Schedule granularity: 30 minutes** (hardware constraint). Times entered with non-30-minute precision are rounded down to the nearest half hour.

#### Visualising the schedule

**Option 1 — Built-in Calendar view** (sidebar)

Navigate to the **Calendar** section in the HA sidebar. The `calendar.stiga_mowing_schedule` entity appears automatically. The weekly view shows all active mowing windows.

**Option 2 — Calendar card on a dashboard**

```yaml
type: calendar
entities:
  - calendar.stiga_mowing_schedule
```

**Option 3 — Next event card**

```yaml
type: entity
entity: calendar.stiga_mowing_schedule
```

Shows the time remaining until the next scheduled mowing.

#### Adding a mowing window

1. Open the Calendar view.
2. Click on the desired day and time.
3. Fill in the event form (summary is ignored — all events are treated as mowing windows).
4. Click **Save** — the new window is sent to the robot immediately.

#### Removing a mowing window

1. Click on an existing event in the Calendar view.
2. Click the **Delete** button.
3. The updated schedule is sent to the robot immediately.

---

### Cutting Mode

Each mowing zone has its own **Cutting Mode** select entity that controls the pattern the robot uses when mowing that zone.

| Mode | Description |
|---|---|
| **Dense Grid** | Tight parallel passes — thorough, uniform cut (default) |
| **Chess Board** | Alternating perpendicular passes — decorative chess-board lawn pattern |
| **North-South** | Parallel passes aligned north–south |
| **East-West** | Parallel passes aligned east–west |

**Entity naming:**

| Scenario | Entity name |
|---|---|
| Single zone | `select.<robot>_cutting_mode` |
| Multiple zones | `select.<robot>_zone_1_cutting_mode`, `select.<robot>_zone_2_cutting_mode`, … |

**How it works:** The mode is stored in the Stiga cloud as part of the garden map (REST `/api/perimeters`). Changing the selection patches only the affected zone's bytes in the protobuf blob and sends a PATCH request to the cloud. The robot picks up the new mode on its next mowing session.

The cutting mode entities are created at integration load time based on the zones found in the garden map. If you remap your garden in the STIGA.GO app, reload the integration to refresh the zone list.

---

### Garden Layout Sensors

Four read-only sensors that reflect the garden map stored in the Stiga cloud. They are fetched once from the REST API (`/api/perimeters`) when the integration loads.

| Entity | Description |
|---|---|
| `sensor.<robot>_garden_area` | Total area of the mapped garden in m² |
| `sensor.<robot>_garden_zones` | Number of active mowing zones |
| `sensor.<robot>_obstacles` | Number of mapped obstacles |
| `sensor.<robot>_obstacle_area` | Total area covered by obstacles in m² |

These values change only when you remap your garden in the STIGA.GO app. To refresh them, reload the integration via **Settings → Devices & Services → Stiga Lawn Mower → Reload**.

> If the cloud fetch fails at startup (e.g. a transient network error), the integration retries automatically on the next poll cycle — no manual reload needed.

---

## Lovelace Card

A custom Lovelace card is included in the `lovelace/` folder. It shows live status, battery, garden progress, a map with the robot's real-time position and heading, sensor stats, and Start / Stop / Dock buttons — all in one card.

![Card layout: status badge, battery bar, map, stats grid, action buttons](https://raw.githubusercontent.com/TanerCRB/Stiga_Lawn_Mower/main/lovelace/preview.png)

### Installation

#### Step 1 — Copy the JS file

Copy `lovelace/stiga-robot-card.js` to the `www/` folder inside your Home Assistant config directory.

| HA installation type | Path |
|---|---|
| Home Assistant OS / Supervised | `/config/www/stiga-robot-card.js` |
| Docker | `<your-config-mount>/www/stiga-robot-card.js` |
| Core (venv) | `<config-dir>/www/stiga-robot-card.js` |

If the `www/` folder does not exist, create it. You can upload the file via the HA **File editor** add-on, **Samba/CIFS** share, or SSH.

#### Step 2 — Register the resource

1. Go to **Settings → Dashboards**.
2. Click the **three-dot menu** (top-right) → **Resources**.
3. Click **Add resource** and fill in:
   - **URL:** `/local/stiga-robot-card.js`
   - **Resource type:** JavaScript module
4. Click **Create**.

> If you do not see the Resources option, enable **Advanced mode** first: click your profile picture (bottom-left) → turn on **Advanced mode**.

#### Step 3 — Refresh the browser

Press **Ctrl+F5** (or **Cmd+Shift+R** on macOS) to force a hard reload. A normal refresh is not enough — the browser must discard the cached JS bundle.

#### Step 4 — Add the card to a dashboard

1. Open a dashboard → click the **pencil icon** (Edit dashboard).
2. Click **+ Add card** → scroll to the bottom → **Manual**.
3. Paste the YAML configuration (see below) and click **Save**.

### Card configuration

```yaml
type: custom:stiga-robot-card
entity_prefix: bob        # required — robot name from STIGA app, lowercase
columns: 8                # optional — card width (2–12 columns, default: full width)
map_height: 200           # optional — map height in px (default: 280)
show_map: false           # optional — hide the map section (default: true)
show_progress: false      # optional — hide battery & garden bars (default: true)
show_stats: false         # optional — hide stats grid (default: true)
show_buttons: false       # optional — hide action buttons (default: true)
dock_lat: 54.131500       # optional — charging station latitude
dock_lon: 16.281700       # optional — charging station longitude
dock_label: My Dock       # optional — charging station tooltip (default: "Charging Dock")
```

| Option | Type | Default | Description |
|---|---|---|---|
| `entity_prefix` | string | — | **Required.** Robot name from the STIGA app (lowercase, spaces → underscores) |
| `columns` | number | full width | Card width in grid columns (1–12). **Only works in the HA Sections dashboard** (2024.3+). In Masonry, width is set by the dashboard column layout. |
| `map_height` | number | `280` | Height of the map section in pixels |
| `show_map` | boolean | `true` | Show/hide the satellite map |
| `show_progress` | boolean | `true` | Show/hide battery and garden progress bars |
| `show_stats` | boolean | `true` | Show/hide the 6-cell stats grid |
| `show_buttons` | boolean | `true` | Show/hide Start / Stop / Dock buttons |
| `dock_lat` | number | — | Latitude of the physical charging dock (orange pin marker) |
| `dock_lon` | number | — | Longitude of the physical charging dock (orange pin marker) |
| `dock_label` | string | `Charging Dock` | Tooltip shown when hovering over the charging dock marker |

> **Dashboard column grid:** The HA Sections view uses a 12-column grid. `columns: 6` = half width, `columns: 4` = one third, `columns: 12` = full width. The minimum is 2 columns.

#### Charging dock marker

The RTK antenna (blue house marker) is automatically placed at the antenna's exact GPS position — this may differ from the physical charging station if the antenna is mounted elsewhere (e.g. on a wall or mast for better signal coverage).

To mark the actual charging station location on the map, add `dock_lat` and `dock_lon` to the card config. The coordinates can be obtained from Google Maps by right-clicking on the dock location and copying the displayed latitude/longitude.

```yaml
type: custom:stiga-robot-card
entity_prefix: bob
dock_lat: 54.131500
dock_lon: 16.281700
dock_label: Charging Station
```

Replace `bob` with the prefix that matches your robot's entity IDs.

#### How to find the correct `entity_prefix`

1. Go to **Developer Tools** (icon in the HA sidebar) → **States** tab.
2. In the filter box at the top, type `_status`.
3. Look for an entity named `sensor.<something>_status` whose friendly name matches your robot.
4. The `<something>` part (everything before `_status`) is your `entity_prefix`.

> Example: if you see `sensor.bob_status` → use `entity_prefix: bob`.
> If HA renamed the entity to `sensor.bob_status_2`, the prefix is still `bob` — see the override options below.

The card auto-discovers all entity IDs using the prefix:

| Entity used | Auto-generated ID |
|---|---|
| Status | `sensor.<prefix>_status` |
| Battery | `sensor.<prefix>_battery` |
| Garden Completed | `sensor.<prefix>_garden_completed` |
| Zone | `sensor.<prefix>_zone` |
| Zone Completed | `sensor.<prefix>_zone_completed` |
| Schedule Remaining | `sensor.<prefix>_schedule_remaining` |
| GPS Satellites | `sensor.<prefix>_gps_satellites` |
| RSSI | `sensor.<prefix>_rssi` |
| Garden Area | `sensor.<prefix>_garden_area` |
| Cloud Connection | `binary_sensor.<prefix>_cloud_connection` |
| GPS Position | `device_tracker.<prefix>_location` |
| Mower controls | `lawn_mower.<prefix>` |

If HA renamed any entity, override it individually:

```yaml
type: custom:stiga-robot-card
entity_prefix: bob
tracker: device_tracker.my_custom_tracker_name
lawn_mower: lawn_mower.garden_robot
```

### Features

| Feature | Notes |
|---|---|
| **Status badge** | Color-coded label (green/blue/yellow/red/purple); pulses when mowing or in error |
| **Battery bar** | Green → yellow → red as charge drops; shows % |
| **Garden progress** | Blue progress bar showing garden completion % |
| **Live map** | Google satellite imagery via Leaflet.js |
| **Robot marker** | Arrow pointing in direction of travel; color matches status |
| **RTK antenna marker** | Blue house icon at the RTK antenna's exact GPS position (auto-detected) |
| **Charging dock marker** | Orange pin at the physical charging station — shown when `dock_lat`/`dock_lon` are set in config |
| **Zone polygons** | Green filled polygons for each mowing zone, with zone name tooltip |
| **Zone progress gradient** | Active zone fills bottom-to-top with a sharp gradient showing % of zone already mowed |
| **Obstacle polygons** | Red dashed polygons for mapped obstacles |
| **Mowing trail** | Dark-green polyline tracing the robot's path during the current session; cleared when the robot becomes idle; up to 1000 points |
| **Next schedule window** | Row below the stats grid: shows "Next mowing: Wednesday 08:00 – 10:30" or "Schedule ends: Today 10:30" based on the calendar entity; hidden during spot cuts |
| **Stats grid** | Zone, Zone %, Satellites, Schedule remaining, Garden area (m²), RSSI |
| **Action buttons** | Start / Stop / Dock — call `lawn_mower` services directly |

### Map notes

The map is displayed automatically when the garden map has been set up in the STIGA.GO app. Zone polygons and the RTK antenna position are derived from the ECEF coordinates embedded in the garden data — no manual coordinate entry is needed.

The map uses Google satellite imagery (hybrid: satellite + road labels). An internet connection is required to load map tiles. The Leaflet.js library is loaded from `unpkg.com` on first use.

**Markers on the map:**

| Marker | Description |
|---|---|
| Coloured arrow | Robot's live position and heading |
| Blue house 🏠 | RTK antenna position (auto-detected from garden data) |
| Orange pin ⚡ | Physical charging dock (optional — set `dock_lat`/`dock_lon` in card config) |
| Green polygon | Mowing zone |
| Red dashed polygon | Obstacle / exclusion zone |

### Troubleshooting the card

#### "Custom element doesn't exist: stiga-robot-card"

This error appears when the card type is unknown to HA. Work through this checklist:

1. **File is not in `www/`** — confirm `stiga-robot-card.js` exists at `<config>/www/stiga-robot-card.js`. A common mistake is placing it in a subfolder (e.g. `www/lovelace/`) while the resource URL still says `/local/stiga-robot-card.js`.
2. **Resource not registered** — go to **Settings → Dashboards → ⋮ → Resources** and verify the entry `/local/stiga-robot-card.js` exists with type **JavaScript module**. If it is missing, add it.
3. **Browser cache** — after adding the resource, press **Ctrl+F5** (hard reload). A normal page refresh reuses the old bundle and will not pick up the new file.
4. **Wrong URL in resource** — the URL must start with `/local/`, not `/config/www/` or a full `http://` address.

#### Map is blank / tiles do not load

- The Leaflet map requires an internet connection to fetch Google satellite tiles. Check that your HA host has outbound internet access.
- If the map div appears but shows no robot arrow, the RTK reference coordinates could not be determined. Check the HA log for a `WARNING` from `custom_components.stiga_lawn_mower` mentioning `RTK reference`. As a fallback, enter base station coordinates via **Settings → Devices & Services → Stiga Lawn Mower → ⋮ → Reconfigure**.
- Zone polygons only appear if the garden has been mapped in the STIGA.GO app.

#### Card loads but shows "unknown" for all sensors

The `entity_prefix` does not match. Open **Developer Tools → States**, filter by `_status`, and find the correct prefix as described above.

#### Action buttons do nothing

The card calls `lawn_mower.start_mowing`, `lawn_mower.stop_mowing`, and `lawn_mower.dock` on the entity `lawn_mower.<prefix>`. If HA renamed your entity, add an explicit override:

```yaml
type: custom:stiga-robot-card
entity_prefix: bob
lawn_mower: lawn_mower.my_custom_entity_name
```

---

## Installation

### Via HACS (Recommended)

1. Install [HACS](https://hacs.xyz/) if you haven't already.
2. In HACS, add this repository as a **Custom Repository** (category: Integration).
3. Download **Stiga Lawn Mower**.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/stiga_lawn_mower/` folder to your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.

---

## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Stiga Lawn Mower**.
3. Enter your STIGA.GO account **email** and **password**.
4. Click **Submit** — the integration discovers all robots on your account.

---

## Troubleshooting

### Enable Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.stiga_lawn_mower: debug
```

### Cloud Connection Binary Sensor

The **Cloud Connection** binary sensor reflects the live MQTT connection state. If it is `Off`:
- Check your internet connection.
- Verify your credentials are correct.
- Restart the integration (Settings → Devices & Services → Stiga Lawn Mower → Reload).

### Diagnostics

Download a diagnostics report from **Settings** → **Devices & Services** → **Stiga Lawn Mower** → three-dot menu → **Download Diagnostics**.

---

## Contributing

Contributions are welcome. Open an issue or pull request on GitHub.

> **Note:** This integration is reverse-engineered and not officially supported by Stiga. It was developed with AI assistance (Claude Code). Use at your own risk.

---

## License

MIT License — see [LICENSE](LICENSE).

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/TanerCRB/Stiga_Lawn_Mower.svg?style=for-the-badge
[commits]: https://github.com/TanerCRB/Stiga_Lawn_Mower/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/TanerCRB/Stiga_Lawn_Mower.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40TanerCRB-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/TanerCRB/Stiga_Lawn_Mower.svg?style=for-the-badge
[releases]: https://github.com/TanerCRB/Stiga_Lawn_Mower/releases
[source]: https://github.com/TanerCRB/Stiga_Lawn_Mower/tree/main/custom_components/stiga_lawn_mower
[documentation]: https://github.com/TanerCRB/Stiga_Lawn_Mower/blob/main/README.md
[issues]: https://github.com/TanerCRB/Stiga_Lawn_Mower/issues

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

| Sensor | Unit | Category |
|---|---|---|
| Battery | % | — |
| Status | — | — |
| Garden Completion | % | — |
| Current Zone | — | — |
| Zone Progress | % | — |
| Battery Capacity | mAh | diagnostic |
| Cutting Height | mm | diagnostic |
| GPS Satellites | — | diagnostic |
| GPS Coverage | — | diagnostic |
| RTK Quality | — | diagnostic |
| RSSI | dBm | diagnostic |
| RSRP | dBm | diagnostic |
| RSRQ | dB | diagnostic |
| Signal Quality | % | diagnostic |
| Firmware Version | — | diagnostic |
| Total Work Time | s | diagnostic |

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

### Select Entity (Configuration)

| Select | Options |
|---|---|
| Rain Delay | 4 h, 8 h, 12 h |

### Button Entities (Diagnostic)

| Button | Notes |
|---|---|
| Calibrate Blades | Trigger blade calibration routine |
| Refresh Status | Request an immediate status update from the robot |

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

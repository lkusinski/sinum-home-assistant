# Sinum Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.11%2B-18BCEE.svg)](https://www.home-assistant.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Validate](https://github.com/lkusinski/sinum-home-assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/lkusinski/sinum-home-assistant/actions/workflows/validate.yml)

**Sinum Home Assistant** is a native Home Assistant integration for [Sinum](https://sinum.tech)
heating and home automation systems by **Tech Sterowniki**.

It connects directly to the Sinum cloud, discovers the rooms and devices available
to your account, and creates native Home Assistant entities for climate, weather,
switches, diagnostics and firmware updates.

![Sinum Home Assistant](assets/banner.png)

## Highlights

- **Native climate entities** for Sinum thermostats and WTP temperature regulators.
- **Current temperature, target temperature and HVAC action** exposed through the
  standard Home Assistant climate model.
- **Weather entity with hourly and daily forecasts**, including temperature,
  humidity, pressure, wind, UV index and solar irradiance.
- **Firmware update entities**, including devices whose update is available through
  the Sinum cloud but is not shown in the app.
- **Areas mapped 1:1 to Sinum rooms**, with automatic assignment of rooms,
  controllers, sensors, relays and system modules.
- **Relay switches** and a broad set of diagnostic sensors: signal strength,
  battery, uptime, IP address, latency, network channel and more.
- **Config flow and options flow** — no YAML required.
- **Refresh-token authentication** — the password is used only during setup or
  reauthentication and is never stored.
- **Conservative polling** — a five-request update cycle every 30 seconds by default.

## Preview

![Dashboard preview](assets/dashboard-preview.png)

## Installation

### HACS (recommended)

1. Open **HACS → Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/lkusinski/sinum-home-assistant` as an **Integration**.
4. Search for **Sinum Home Assistant**, install it and restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration → Sinum Home Assistant**.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lkusinski&repository=sinum-home-assistant&category=integration)

### Manual installation

Copy `custom_components/sinum_home_assistant` into your Home Assistant
`config/custom_components/` directory, then restart Home Assistant.

## Configuration

You need:

- the e-mail address and password of the Sinum account that owns the hub;
- the **cloud device ID** (`uid`) of the Sinum hub.

The cloud device ID is shown in the Sinum app / hub settings. Enter it exactly as
shown; it is stored in lowercase.

During setup the integration validates the account and the hub, obtains a refresh
token and creates the config entry. The password is not persisted.

### Options

| Option | Default | Description |
|---|---:|---|
| Polling interval | 30 s | Range: 15–300 seconds. |
| Enable weather | on | Adds the weather entity and forecast. |
| Enable system modules | on | Adds extender and transceiver diagnostics. |

## Entities

A typical installation creates:

| Platform | Examples |
|---|---|
| `climate` | Room thermostats and WTP temperature regulators |
| `weather` | Current conditions and hourly/daily forecast |
| `sensor` | Temperature, humidity, battery, signal, IP, latency, firmware |
| `binary_sensor` | Window contact, heating/cooling state, warnings, target reached |
| `switch` | Relay outputs |
| `update` | Hub, controller, extender and device firmware |

Entity IDs are generated from the room name, device name and entity name. Areas
and devices are created automatically.

## Requirements

- Home Assistant **2026.11** or newer.
- A Sinum account with cloud access enabled.
- Internet access to `backend.prd.sinum24.com`.

## Privacy

The integration communicates only with the Sinum cloud endpoints required to read
device state and send control commands. It stores the account e-mail, cloud device
ID and a refresh token in the Home Assistant config entry. The password is not
stored. No telemetry is sent anywhere else.

See [docs/PRIVACY.md](docs/PRIVACY.md) for details.

## Troubleshooting

- **Invalid e-mail or password** — verify the Sinum account credentials.
- **Invalid cloud device ID** — copy the `uid` from the Sinum app or hub settings.
- **Cannot connect** — check internet access and whether the Sinum cloud is reachable.
- **Some sensors are unknown** — network fields are empty for transceivers that do
  not report Wi-Fi/Ethernet details. This is expected.
- **Entity names differ from the app** — Home Assistant uses room + device names;
  rename entities freely in the UI.

More help: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Documentation

- [Installation and setup](docs/INSTALL.md)
- [Configuration and options](docs/CONFIGURATION.md)
- [Entity reference](docs/ENTITIES.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Development](docs/DEVELOPMENT.md)
- [Privacy](docs/PRIVACY.md)

## Copyright and trademarks

Copyright © 2026 **Tech Sterowniki**. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

Sinum and Tech Sterowniki are trademarks of Tech Sterowniki. All other product
names and trademarks are the property of their respective owners.

This repository is an independent Home Assistant integration. It is not an official
Tech Sterowniki release unless published by Tech Sterowniki.

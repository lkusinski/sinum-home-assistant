# Sinum Local API — research and roadmap

Last verified: 2026-11-12 (Europe/Warsaw).

This document records the local-API findings from the official TECH resources
and community projects. It is a roadmap, not a statement that the local
transport is enabled in the current integration.

## Official resources

- REST API reference: <https://apidocs.sinum.tech/> — **Sinum Central Device
  Local API**, OpenAPI 3.0, local server `http://{host}/api/v1`.
- Local Swagger snapshots published in the official
  <https://github.com/techsterowniki/sinum-mcp> repository
  (`swagger/e-home-main.json`, `e-home-pm.json`, `e-home-go.json`).
- Lua API manual:
  <https://www.techsterowniki.pl/!uploads/SINUM/LUA_user_manual.pdf>.
- Official MCP server:
  <https://github.com/techsterowniki/sinum-mcp> — MIT, API-token auth,
  `/devices` and `/scenes` operations.

## Authentication

The local API supports:

1. **Static API token** (preferred for integrations) — created in the Sinum
   web UI under **Settings → System → Integrations → External integration
   tokens** (or via `/settings/api-token` with an authenticated session).
2. **Username + password** — `POST /api/v1/login`, then `POST /api/v1/refresh`
   with the returned refresh token.
3. **Cloud login** — `POST /api/v1/cloud-login`.

Static tokens do not expire and can be revoked independently of the account
password.

## Relevant endpoints

| Area | Endpoint(s) | Possible use |
|---|---|---|
| Hub info | `GET /api/v1/info` | Setup probe, firmware and feature flags. |
| Rooms / floors | `GET /api/v1/rooms`, `/floors` | Area mapping. |
| Virtual devices | `GET/PATCH /api/v1/devices/virtual` | Thermostats, relays, gates, dimmers, AC modules. |
| WTP / SBUS / SLink / LoRa / Modbus | `/devices/{bus}` | Native sensors, relays, covers, fans, energy meters. |
| Custom Lua modules | `/devices/custom-device-module` | AC module and future custom devices. |
| Video | `/devices/video`, `/devices/video/{id}/snapshot`, `/stream` | Camera snapshots and WebRTC live view. |
| Scenes | `GET /scenes`, `POST /scenes/{id}/activate` | Scene buttons and services. |
| Schedules | `GET/PATCH /schedules` | Read-only schedule summary and optional writes. |
| Weather | `GET /weather` | Local weather data. |
| Energy Center | `/energy-center/*` | Diagnostics and future energy entities. |
| Alarm | `/devices/alarm-system` | Alarm zones and arm/disarm. |
| Variables | `/lua/variables` | Numeric Lua environment values. |

The local API also exposes a WebSocket transport (`/api/v1/ws` in the
community implementation; the official Go process exposes `/ws`) with
`device_state_changed` events. A reconnect must trigger a full REST refresh.

## Current status on our hub

The cloud `/proxy/info` response reports the central LAN address
`192.168.1.16`, firmware `1.25.1`, `device_type: sinum_lite`, and the `video`
label. From CT310 and from B7 HA, `GET http://192.168.1.16/api/v1/info`
failed to connect (2026-11-12). The central is in a different network segment,
so the local transport cannot be validated from the current test environment.

**Decision:** keep the verified cloud path as the default. Do not claim local
support until it can be probed against a reachable hub.

## Recommended next steps

1. Add an optional **connection mode: cloud / local** to the config and
   options flow (host/IP + static API token), retaining cloud as the fallback.
2. Reuse the existing normalized data model; local `/devices` groups match the
   cloud groups closely but must be validated against a reachable hub.
3. Add local WebSocket push as an optional transport, with exponential backoff
   and a full REST refresh after reconnect.
4. Add camera entities only for hub video devices using the local snapshot and
   WebRTC endpoints; do not route arbitrary Frigate cameras through Sinum.
5. Prefer read-only entities and explicit writes; keep administrative
   endpoints (users, backup, network, reboot, firmware install) out of HA.
6. Add contract tests from the official OpenAPI snapshots before enabling a
   local mode.

## Licensing note

The ideas above come from the official TECH API/MCP resources and public
documentation. The `Sinapse` community integration was reviewed only for
compatibility concepts; its source is proprietary, so no code was copied.
`tech-controllers` targets the **eModul** API, not Sinum, and was used only as
a quality/engineering reference.

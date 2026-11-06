# Changelog

All notable changes to this project will be documented in this file.

## 1.0.3 — 2026-11-06

- Use day/night-aware conditions in hourly forecasts.
- Keep controller and module connectivity sensors available while offline.
- Preserve a valid zero solar irradiance value.
- Avoid string `"None"` for missing sunrise/sunset attributes.
- Strip trailing whitespace from generated device names.
- Do not create system-module parent devices when that option is disabled.
- Clarify that firmware installation is performed in the Sinum app.

## 1.0.2 — 2026-11-06

- Clarify the copyright and trademark notice.

## 1.0.1 — 2026-11-06

- Use the product name for newly created config entries.
- Add lint validation to CI.

## 1.0.0 — 2026-11-05

First public release.

- Native Home Assistant integration for Sinum cloud accounts.
- Climate entities for thermostats and WTP temperature regulators.
- Weather entity with hourly and daily forecasts.
- Relay switches and firmware update entities.
- Room-to-area mapping and parent/child device hierarchy.
- Config flow, reauthentication and options flow.
- Diagnostics for battery, signal, network and system modules.

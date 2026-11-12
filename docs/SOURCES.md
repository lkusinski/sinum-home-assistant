# Sources and related projects

Reviewed 2026-11-12. This file records what was useful and how it may be used;
it does not imply endorsement by TECH Sterowniki.

| Source | License / status | Relevance |
|---|---|---|
| [techsterowniki/sinum-mcp](https://github.com/techsterowniki/sinum-mcp) | MIT, official | Local API snapshots (`swagger/`), API-token auth, `/devices` and `/scenes`; confirms the local API surface. |
| [apidocs.sinum.tech](https://apidocs.sinum.tech/) | Official documentation | Local API reference, auth, devices, video, schedules, energy, Lua. |
| [Sinapse — Sinum integration for HA](https://github.com/zaba848/Sinapse-Sinum_Integration_for_Home_Assistant) | Proprietary / source-available | Local API + `/api/v1/ws` + camera/WebRTC concepts; no code copied. |
| [mariusz-ostoja-swierczynski/tech-controllers](https://github.com/mariusz-ostoja-swierczynski/tech-controllers) | MIT | eModul (not Sinum) integration; reference for HA quality scale, diagnostics, tests, release workflow. |
| [Home Assistant discussion #1283](https://github.com/orgs/home-assistant/discussions/1283) | Public discussion | Sinum Cloud integration request and API/MCP pointers. |
| [TECH Sinum Lua manual](https://www.techsterowniki.pl/!uploads/SINUM/LUA_user_manual.pdf) | Official documentation | Custom devices, events, statistics and Lua API. |

## Search notes

- GitHub code search: only the Sinapse repository contains the local
  `/api/v1/ws` and extensive Sinum local API mappings; no other maintained
  Sinum HA integration was found.
- GitLab search for `sinum`, `tech sterowniki`, `ehome` and `home assistant
  sinum`: no relevant Sinum/TECH integration projects.
- The `tech-controllers` repository is for eModul, not Sinum; its API, device
  model and auth do not apply directly.

See [API-LOCAL.md](API-LOCAL.md) for the local API findings and roadmap.

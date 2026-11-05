# Security policy

## Reporting a vulnerability

Please report security issues privately using the repository security advisory
feature or by contacting the maintainers listed in `manifest.json`.

Do not open a public issue for credentials, tokens, account data or exploitable
vulnerabilities.

## Credential handling

- The Sinum password is used only for login and is never written to the config entry.
- The refresh token is stored in the Home Assistant config entry.
- Access tokens are kept in memory.
- Logs must never contain passwords, refresh tokens or access tokens.

## Supported versions

Only the latest release receives security fixes.

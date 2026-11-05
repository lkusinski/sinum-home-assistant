# Privacy

Sinum Home Assistant communicates with the Sinum cloud to read and control the
devices associated with your account.

## Data stored in Home Assistant

The config entry stores:

- the Sinum account e-mail address;
- the cloud device ID;
- a refresh token;
- integration options (polling interval, weather, system modules).

The account password is **not** stored. Access tokens are kept in memory only
and are renewed with the refresh token.

## Data sent to Sinum

Requests contain the account e-mail, cloud device ID, access token and the
standard OAuth client identifier. Control commands contain only the device and
property being changed.

## Data sent elsewhere

The integration does not send data to any other service. It does not include
telemetry, analytics or crash reporting.

## Removing data

Removing the config entry deletes the stored e-mail, device ID and refresh token.
Entity history remains in the Home Assistant recorder according to your
recorder retention settings.

## Trademarks

Sinum and Tech Sterowniki are trademarks of Tech Sterowniki. See `NOTICE.md`.

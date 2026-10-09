# Changelog

## 0.1.1

- Setting the temperature: the cloud accepts it with HTTP 202 and applies it
  asynchronously, so the requested value is now shown until the cloud reports
  it (up to 2 minutes), with a re-check 15 seconds after the write.
- Debug logging of API requests and responses (never the login exchange).
- Errors from the API are shown in the UI when setting a temperature fails.
- Refresh interval is now configurable (Configure button, 15-300 seconds) and
  defaults to 30 seconds instead of 60, so changes made on the thermostat or in
  the app show up sooner.

## 0.1.0

First public release.

- Config flow with email/password; refuses accounts on the legacy platform.
- Re-authentication flow when the password changes.
- Climate entity per zone with current/target temperature and set temperature.
- Read-only HVAC mode and action.
- Diagnostic sensors: signal strength, lockout code, water pressure, CH temperature.

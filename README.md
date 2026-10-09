# Intergas Orion (Comfort Touch) for Home Assistant

A Home Assistant custom integration for Intergas boilers connected through the
**new** Intergas gateway (the MQTT-based "Orion" platform, `ARCH_2_0`), as used
by the Intergas Comfort Touch app.

The built-in [`incomfort`](https://www.home-assistant.io/integrations/incomfort/)
integration only works with the older LAN2RF gateway, which has a local HTTP
API. The new gateway has no local API at all: it only talks to the Intergas
cloud. This integration therefore uses the same cloud API as the Comfort Touch
app.

> **Unofficial.** This project is not affiliated with, endorsed by or supported
> by Intergas. The API is undocumented and may change without notice.

## Status

Early release (0.1.x). Developed against an Intergas Xtreme boiler with a
Comfort Touch thermostat, single zone.

| Feature | State |
|---|---|
| Room temperature, target temperature | ✅ |
| Set target temperature | ⚠️ implemented, awaiting live confirmation |
| HVAC mode / action (read) | ✅ |
| Diagnostic sensors (signal, lockout code, pressure, CH temperature) | ✅ (when reported by the boiler) |
| Change HVAC mode (manual ↔ week schedule ↔ off) | ❌ not yet |
| Week schedule, presets, holiday mode, statistics | ❌ not yet |

## Requirements

- An Intergas Comfort Touch account on the new platform. The integration
  checks this when you add it and refuses accounts on the legacy platform.
- Internet access from Home Assistant to `app-api.orion.intergas.nl`.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/ldanicel/ha-intergas-orion` as an **Integration**.
2. Install **Intergas (Orion / Comfort Touch)** and restart Home Assistant.

### Manual

1. Copy `custom_components/intergas_orion/` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

### Configuration

Settings → Devices & Services → **Add Integration** →
"Intergas (Orion / Comfort Touch)", then sign in with your Comfort Touch email
and password.

## Entities

- **Climate**, one per zone: current room temperature, target temperature,
  HVAC mode (`heat` = manual, `auto` = week or holiday schedule, `off` =
  standby) and action (heating / idle / off).
- **Sensors** (created only if the boiler reports the value): water pressure,
  central heating temperature, lockout code, and heater/gateway signal
  strength (disabled by default).

## How it works

- Signs in with `POST /v1/accounts/authenticate` and uses the returned JWT as a
  bearer token. When the token expires (about an hour) it signs in again.
- Polls the heaters and zones every 30 seconds by default; change it under
  Settings → Devices & services → Intergas → Configure (15–300 seconds).
- Setting a temperature sends `PATCH .../zones/{n}` with
  `{"temperature_heater_setpoint": <value>}`, as the app does. The cloud
  accepts it immediately (HTTP 202) and the thermostat reports the new value
  about 40-70 seconds later; until then the entity shows the requested value.

See [docs/API.md](docs/API.md) for what is known about the API.

## Privacy

Your email and password are stored in Home Assistant's config entry, like any
other integration that signs in to a cloud account, and are only sent to
`app-api.orion.intergas.nl` over HTTPS. Nothing else is collected or sent
anywhere.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

The tests run the integration inside Home Assistant against a mocked cloud API.

## Contributing

Issues and pull requests are welcome, especially API captures from multi-zone
setups and other boiler models (please remove serial numbers, IDs and tokens).

## Acknowledgements

Developed with the assistance of Claude (Anthropic).

## License

[MIT](LICENSE)

"""Constants for the Intergas Orion integration."""

DOMAIN = "intergas_orion"

API_BASE = "https://app-api.orion.intergas.nl"

# Operating modes reported in heater["state"]["mode"].
# From the app's HeaterOperationalMode enum; OFF is standby.
MODE_OFF = "OFF"
MODE_MANUAL = "RUNNING_MANUAL_TEMPERATURE"
MODE_WEEK = "RUNNING_WEEK_SCHEME"
MODE_HOLIDAY = "RUNNING_HOLIDAY_SCHEME"

# Boiler parameters (GET/PATCH .../parameters) the app lets users change.
PARAM_OPERATIONAL_STATE = "heater_operational_state"  # 0 = off, 1 = on
PARAM_MAX_SUPPLY_TEMPERATURE = "ch_temperature"  # P050, maximum CH supply temperature

# Setpoint bounds enforced by the Comfort Touch thermostat.
MIN_TEMP = 5.0
MAX_TEMP = 30.0

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 300

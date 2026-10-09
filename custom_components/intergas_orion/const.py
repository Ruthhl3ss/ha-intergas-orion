"""Constants for the Intergas Orion integration."""

DOMAIN = "intergas_orion"

API_BASE = "https://app-api.orion.intergas.nl"

# Operating modes reported in heater["state"]["mode"].
MODE_STANDBY = "STANDBY"
MODE_MANUAL = "RUNNING_MANUAL_TEMPERATURE"
MODE_WEEK = "RUNNING_WEEK_SCHEME"
MODE_HOLIDAY = "RUNNING_HOLIDAY_SCHEME"

# Setpoint bounds enforced by the Comfort Touch thermostat.
MIN_TEMP = 5.0
MAX_TEMP = 30.0

DEFAULT_SCAN_INTERVAL = 60  # seconds

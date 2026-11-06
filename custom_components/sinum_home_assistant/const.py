"""Constants for the Sinum Home Assistant integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "sinum_home_assistant"
MANUFACTURER = "Sinum"
MODEL = "Sinum"

API_BASE = "https://backend.prd.sinum24.com/proxy"
OAUTH_URL = "https://backend.prd.sinum24.com/authentication/oauth/token"
APP_BASIC = "ZWhvbWU6dG9wX3NlY3JldA=="
TOKEN_SAFETY = 45

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_HUB_NAME = "hub_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_WEATHER = "enable_weather"
CONF_ENABLE_SYSTEM_MODULES = "enable_system_modules"
CONF_ENABLE_SCHEDULES = "enable_schedules"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 300

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.WEATHER,
)

TEMP_SCALE = 0.1

SINUM_TO_HVAC = {
    "heating": "heat",
    "cooling": "cool",
    "automatic": "auto",
    "off": "off",
}

HVAC_TO_SINUM = {
    "heat": "heating",
    "cool": "cooling",
    "auto": "automatic",
    "off": "off",
}

WEATHER_CONDITIONS = {
    200: "lightning-rainy",
    201: "lightning-rainy",
    202: "lightning-rainy",
    210: "lightning",
    211: "lightning",
    212: "lightning",
    221: "lightning",
    230: "lightning-rainy",
    231: "lightning-rainy",
    232: "lightning-rainy",
    300: "rainy",
    301: "rainy",
    302: "rainy",
    310: "rainy",
    311: "rainy",
    312: "rainy",
    313: "rainy",
    314: "rainy",
    321: "rainy",
    500: "rainy",
    501: "rainy",
    502: "pouring",
    503: "pouring",
    504: "pouring",
    511: "snowy-rainy",
    520: "rainy",
    521: "rainy",
    522: "rainy",
    531: "rainy",
    600: "snowy",
    601: "snowy",
    602: "snowy",
    611: "snowy-rainy",
    612: "snowy-rainy",
    613: "snowy-rainy",
    615: "snowy-rainy",
    616: "snowy-rainy",
    620: "snowy",
    621: "snowy",
    622: "snowy",
    701: "fog",
    711: "fog",
    721: "fog",
    731: "fog",
    741: "fog",
    751: "fog",
    761: "fog",
    762: "fog",
    771: "windy",
    781: "windy",
    800: "sunny",
    801: "partlycloudy",
    802: "partlycloudy",
    803: "cloudy",
    804: "cloudy",
}

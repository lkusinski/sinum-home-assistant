"""Weather platform for Sinum Home Assistant."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import TEMP_SCALE, WEATHER_CONDITIONS
from .coordinator import SinumHomeAssistantCoordinator
from .entity import SinumHomeAssistantEntity, weather_device_info

PARALLEL_UPDATES = 0


def _nested(data: Any, *keys: str | int) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _condition_from_id(value: Any, is_day: bool = True) -> str | None:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    if code == 800:
        return "sunny" if is_day else "clear-night"
    return WEATHER_CONDITIONS.get(code)


def _condition_from_text(text: Any, is_day: bool = True) -> str | None:
    value = str(text or "").lower()
    if not value:
        return None
    if "thunder" in value or "storm" in value:
        return "lightning-rainy"
    if "snow" in value or "sleet" in value:
        return "snowy-rainy" if "sleet" in value else "snowy"
    if "rain" in value or "shower" in value:
        return "rainy"
    if "fog" in value or "mist" in value or "haze" in value:
        return "fog"
    if "partly" in value:
        return "partlycloudy"
    if "cloud" in value or "overcast" in value:
        return "cloudy"
    if "clear" in value or "sun" in value:
        return "sunny" if is_day else "clear-night"
    if "wind" in value:
        return "windy"
    return None


def _is_day(weather: dict[str, Any]) -> bool:
    sunrise = weather.get("sunrise")
    sunset = weather.get("sunset")
    if not isinstance(sunrise, (int, float)) or not isinstance(
        sunset, (int, float)
    ):
        return True
    now = datetime.now(UTC).timestamp()
    return float(sunrise) <= now < float(sunset)


def _condition(weather: dict[str, Any], is_day: bool = True) -> str | None:
    current = weather.get("current") or {}
    condition = current.get("weather") or {}
    result = _condition_from_id(condition.get("id"), is_day)
    if result is not None:
        return result
    return _condition_from_text(
        condition.get("main") or condition.get("description"), is_day
    )


def _scaled(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return None


def _wind(weather: dict[str, Any], key: str = "speed") -> float | None:
    value = _nested(weather, "current", "wind", key)
    if value is None:
        value = _nested(weather, "hourly", 0, "wind", key)
    if key in ("speed", "gust"):
        return _scaled(value)
    return value if isinstance(value, (int, float)) else None


def _uv(weather: dict[str, Any]) -> float | None:
    value = _nested(weather, "current", "uv_index")
    if value is None:
        value = _nested(weather, "hourly", 0, "uv_index")
    return _scaled(value)


def _iso(timestamp: Any) -> str:
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(
            float(timestamp), tz=UTC
        ).isoformat()
    return str(timestamp)


def _daily_forecast(weather: dict[str, Any]) -> list[Forecast]:
    result: list[Forecast] = []
    for item in weather.get("daily", []) or []:
        if not isinstance(item, dict):
            continue
        condition = item.get("weather") or {}
        temperatures = item.get("temperature") or {}
        wind = item.get("wind") or {}
        rain = item.get("rain") or 0
        snow = item.get("snow") or 0
        result.append(
            {
                "datetime": _iso(item.get("timestamp") or item.get("time")),
                "condition": _condition_from_id(condition.get("id"), True),
                "native_temperature": _scaled(temperatures.get("max")),
                "native_templow": _scaled(temperatures.get("min")),
                "native_precipitation": round(float(rain) + float(snow), 1),
                "native_wind_speed": _scaled(wind.get("speed")),
                "native_wind_gust_speed": _scaled(wind.get("gust")),
                "wind_bearing": wind.get("degrees"),
                "uv_index": _scaled(item.get("uv_index")),
                "humidity": item.get("humidity"),
                "native_pressure": item.get("pressure"),
                "cloud_coverage": item.get("cloud_coverage"),
                "native_apparent_temperature": _scaled(
                    _nested(item, "feels_like", "day")
                    or item.get("feels_like")
                ),
                "is_daytime": True,
            }
        )
    return result


def _hourly_forecast(weather: dict[str, Any]) -> list[Forecast]:
    result: list[Forecast] = []
    for item in weather.get("hourly", []) or []:
        if not isinstance(item, dict):
            continue
        condition = item.get("weather") or {}
        wind = item.get("wind") or {}
        rain = item.get("rain") or 0
        snow = item.get("snow") or 0
        result.append(
            {
                "datetime": _iso(item.get("timestamp") or item.get("time")),
                "condition": _condition_from_id(condition.get("id"), True),
                "native_temperature": _scaled(item.get("temperature")),
                "native_apparent_temperature": _scaled(
                    item.get("feels_like")
                ),
                "native_precipitation": round(float(rain) + float(snow), 1),
                "precipitation_probability": item.get(
                    "precipitation_probability"
                ),
                "native_wind_speed": _scaled(wind.get("speed")),
                "native_wind_gust_speed": _scaled(wind.get("gust")),
                "wind_bearing": wind.get("degrees"),
                "uv_index": _scaled(item.get("uv_index")),
                "humidity": item.get("humidity"),
                "native_pressure": item.get("pressure"),
                "cloud_coverage": item.get("cloud_coverage"),
            }
        )
    return result


class SinumWeather(SinumHomeAssistantEntity, WeatherEntity):
    """Sinum cloud weather entity with daily and hourly forecasts."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_precipitation_unit = (
        UnitOfPrecipitationDepth.MILLIMETERS
    )
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
    ) -> None:
        super().__init__(coordinator, device_info, unique_key)

    @property
    def _weather(self) -> dict[str, Any]:
        return self.coordinator.data.weather or {}

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self._weather)

    @property
    def condition(self) -> str | None:
        return _condition(self._weather, _is_day(self._weather))

    @property
    def native_temperature(self) -> float | None:
        return _scaled(_nested(self._weather, "current", "temperature"))

    @property
    def native_apparent_temperature(self) -> float | None:
        return _scaled(_nested(self._weather, "current", "feels_like"))

    @property
    def native_dew_point(self) -> float | None:
        value = _nested(self._weather, "current", "dew_point")
        if value is None:
            value = _nested(self._weather, "hourly", 0, "dew_point")
        return _scaled(value)

    @property
    def humidity(self) -> float | None:
        value = _nested(self._weather, "current", "humidity")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def native_pressure(self) -> float | None:
        value = _nested(self._weather, "current", "pressure")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def native_wind_speed(self) -> float | None:
        return _wind(self._weather, "speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        return _wind(self._weather, "gust")

    @property
    def wind_bearing(self) -> float | None:
        value = _wind(self._weather, "degrees")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def uv_index(self) -> float | None:
        return _uv(self._weather)

    @property
    def cloud_coverage(self) -> float | None:
        value = _nested(self._weather, "current", "cloud_coverage")
        return float(value) if isinstance(value, (int, float)) else None

    async def async_forecast_daily(self) -> list[Forecast] | None:
        return _daily_forecast(self._weather)

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        return _hourly_forecast(self._weather)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        weather = self._weather
        current = weather.get("current") or {}
        condition = current.get("weather") or {}
        attrs: dict[str, Any] = {
            "city": weather.get("city_name"),
            "is_day": _is_day(weather),
            "sunrise": _iso(weather.get("sunrise")),
            "sunset": _iso(weather.get("sunset")),
            "condition_raw": condition.get("main")
            or condition.get("description"),
            "condition_id": condition.get("id"),
            "cloud_coverage": current.get("cloud_coverage"),
            "solar_irradiance": _nested(
                weather, "current", "solar", "irradiance"
            )
            or _nested(weather, "hourly", 0, "solar", "irradiance"),
            "wind_gust_speed": _wind(weather, "gust"),
        }
        return attrs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    if not coordinator.enable_weather or not coordinator.data.weather:
        return
    async_add_entities(
        [
            SinumWeather(
                coordinator,
                weather_device_info(entry.entry_id, coordinator.data),
                "weather",
            )
        ]
    )

"""Sensor platform for Sinum Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfIrradiance,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import TEMP_SCALE
from .coordinator import SinumHomeAssistantCoordinator
from .data import SinumHomeAssistantData
from .entity import (
    SinumDeviceEntity,
    SinumHomeAssistantEntity,
    hub_device_info,
    system_module_device_info,
    virtual_device_info,
    weather_device_info,
    wtp_device_info,
)

PARALLEL_UPDATES = 0

TEMPERATURE = "Temperatura"
HUMIDITY = "Wilgotność"
DEW_POINT = "Punkt rosy"
BATTERY = "Bateria"
SIGNAL = "Sygnał"
UPTIME = "Czas pracy"
FIRMWARE = "Wersja oprogramowania"
API_VERSION = "Wersja API"
IP_ADDRESS = "Adres IP"
LATENCY = "Opóźnienie"
CHANNEL = "Kanał sieci"
NETWORK = "Sieć"
PRESSURE = "Ciśnienie"
UV_INDEX = "Indeks UV"
CLOUD_COVERAGE = "Zachmurzenie"
WIND_SPEED = "Wiatr"
SOLAR_IRRADIANCE = "Irradiancja"
FEELS_LIKE = "Temperatura odczuwalna"


def _scale(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return None


def _value(device: dict[str, Any], key: str) -> Any:
    return device.get(key)


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _weather_current(weather: dict[str, Any], key: str) -> Any:
    return _nested(weather, "current", key)


def _weather_wind(
    weather: dict[str, Any], key: str = "speed"
) -> float | None:
    value = _nested(weather, "current", "wind", key)
    if value is None:
        value = _nested(weather, "hourly", 0, "wind", key)
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return None


def _weather_solar(weather: dict[str, Any], key: str = "irradiance") -> Any:
    value = _nested(weather, "current", "solar", key)
    if value is None:
        value = _nested(weather, "hourly", 0, "solar", key)
    return value if isinstance(value, (int, float)) else None


def _weather_uv(weather: dict[str, Any]) -> float | None:
    value = _weather_current(weather, "uv_index")
    if value is None:
        value = _nested(weather, "hourly", 0, "uv_index")
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return None


def _weather_temperature(weather: dict[str, Any]) -> float | None:
    return _scale(_weather_current(weather, "temperature"))


def _weather_humidity(weather: dict[str, Any]) -> Any:
    return _weather_current(weather, "humidity")


def _weather_pressure(weather: dict[str, Any]) -> Any:
    return _weather_current(weather, "pressure")


def _weather_clouds(weather: dict[str, Any]) -> Any:
    return _weather_current(weather, "cloud_coverage")


def _weather_feels_like(weather: dict[str, Any]) -> float | None:
    return _scale(_weather_current(weather, "feels_like"))


class SinumValueSensor(SinumHomeAssistantEntity, SensorEntity):
    """Sensor attached to the hub or weather device."""

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        name: str,
        value_fn: Callable[[SinumHomeAssistantData], Any],
        *,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        unit: str | None = None,
        icon: str | None = None,
        entity_category: EntityCategory | None = None,
        precision: int | None = None,
    ) -> None:
        super().__init__(coordinator, device_info, unique_key)
        self._attr_name = name
        self._value_fn = value_fn
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = entity_category
        self._attr_suggested_display_precision = precision

    @property
    def native_value(self) -> Any:
        return self._value_fn(self.coordinator.data)


class SinumDeviceSensor(SinumDeviceEntity, SensorEntity):
    """Sensor attached to a WTP, virtual or system-module device."""

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
        store: str,
        name: str,
        value_fn: Callable[[dict[str, Any]], Any],
        *,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        unit: str | None = None,
        icon: str | None = None,
        entity_category: EntityCategory | None = None,
        precision: int | None = None,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, store
        )
        self._attr_name = name
        self._value_fn = value_fn
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_entity_category = entity_category
        self._attr_suggested_display_precision = precision

    @property
    def native_value(self) -> Any:
        return self._value_fn(self._device())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[SensorEntity] = []

    hub_info = hub_device_info(entry.entry_id, data)
    entities.extend(
        [
            SinumValueSensor(
                coordinator,
                hub_info,
                "hub_uptime",
                UPTIME,
                lambda d: d.info.get("uptime"),
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.TOTAL_INCREASING,
                unit=UnitOfTime.SECONDS,
                icon="mdi:clock-outline",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            SinumValueSensor(
                coordinator,
                hub_info,
                "hub_firmware",
                FIRMWARE,
                lambda d: d.info.get("version"),
                icon="mdi:chip",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            SinumValueSensor(
                coordinator,
                hub_info,
                "hub_api",
                API_VERSION,
                lambda d: d.info.get("api"),
                icon="mdi:api",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            SinumValueSensor(
                coordinator,
                hub_info,
                "hub_ip",
                IP_ADDRESS,
                lambda d: d.info.get("ip"),
                icon="mdi:ip-network",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]
    )

    if coordinator.enable_weather and data.weather:
        weather_info = weather_device_info(entry.entry_id, data)
        entities.extend(
            [
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_temperature",
                    TEMPERATURE,
                    lambda d: _weather_temperature(d.weather or {}),
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfTemperature.CELSIUS,
                    precision=1,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_humidity",
                    HUMIDITY,
                    lambda d: _weather_humidity(d.weather or {}),
                    device_class=SensorDeviceClass.HUMIDITY,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=PERCENTAGE,
                    precision=0,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_pressure",
                    PRESSURE,
                    lambda d: _weather_pressure(d.weather or {}),
                    device_class=SensorDeviceClass.PRESSURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfPressure.HPA,
                    precision=0,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_uv",
                    UV_INDEX,
                    lambda d: _weather_uv(d.weather or {}),
                    state_class=SensorStateClass.MEASUREMENT,
                    unit="UV index",
                    icon="mdi:sun-wireless",
                    precision=1,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_clouds",
                    CLOUD_COVERAGE,
                    lambda d: _weather_clouds(d.weather or {}),
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=PERCENTAGE,
                    icon="mdi:cloud-percent",
                    precision=0,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_wind",
                    WIND_SPEED,
                    lambda d: _weather_wind(d.weather or {}),
                    device_class=SensorDeviceClass.WIND_SPEED,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
                    precision=1,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_solar",
                    SOLAR_IRRADIANCE,
                    lambda d: _weather_solar(d.weather or {}),
                    device_class=SensorDeviceClass.IRRADIANCE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
                    precision=0,
                ),
                SinumValueSensor(
                    coordinator,
                    weather_info,
                    "weather_feels_like",
                    FEELS_LIKE,
                    lambda d: _weather_feels_like(d.weather or {}),
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfTemperature.CELSIUS,
                    precision=1,
                ),
            ]
        )

    for device_id, device in data.wtp.items():
        parent = data.parents_wtp.get(device.get("parent_id"))
        info = wtp_device_info(entry.entry_id, device, parent, data)
        device_type = device.get("type")

        if device_type == "temperature_sensor":
            entities.append(
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_temperature",
                    device_id,
                    "wtp",
                    TEMPERATURE,
                    lambda d: _scale(d.get("temperature")),
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfTemperature.CELSIUS,
                    precision=1,
                )
            )
        elif device_type == "humidity_sensor":
            entities.append(
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_humidity",
                    device_id,
                    "wtp",
                    HUMIDITY,
                    lambda d: _scale(d.get("humidity")),
                    device_class=SensorDeviceClass.HUMIDITY,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=PERCENTAGE,
                    precision=1,
                )
            )

        if device.get("signal") is not None:
            entities.append(
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_signal",
                    device_id,
                    "wtp",
                    SIGNAL,
                    lambda d: d.get("signal"),
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=PERCENTAGE,
                    icon="mdi:wifi",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    precision=0,
                )
            )
        if device.get("battery") is not None:
            entities.append(
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_battery",
                    device_id,
                    "wtp",
                    BATTERY,
                    lambda d: d.get("battery"),
                    device_class=SensorDeviceClass.BATTERY,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=PERCENTAGE,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    precision=0,
                )
            )

    for device_id, device in data.virtual.items():
        info = virtual_device_info(entry.entry_id, device, data)
        entities.extend(
            [
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"virtual_{device_id}_temperature",
                    device_id,
                    "virtual",
                    TEMPERATURE,
                    lambda d: _scale(d.get("temperature")),
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfTemperature.CELSIUS,
                    precision=1,
                ),
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"virtual_{device_id}_humidity",
                    device_id,
                    "virtual",
                    HUMIDITY,
                    lambda d: _scale(d.get("humidity")),
                    device_class=SensorDeviceClass.HUMIDITY,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=PERCENTAGE,
                    precision=1,
                ),
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"virtual_{device_id}_dew_point",
                    device_id,
                    "virtual",
                    DEW_POINT,
                    lambda d: _scale(d.get("dew_point")),
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                    unit=UnitOfTemperature.CELSIUS,
                    precision=1,
                ),
            ]
        )

    if coordinator.enable_system_modules:
        for device_id, device in data.system_modules.items():
            info = system_module_device_info(entry.entry_id, device, data)
            entities.extend(
                [
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"system_module_{device_id}_signal",
                        device_id,
                        "system_modules",
                        SIGNAL,
                        lambda d: d.get("network_signal"),
                        state_class=SensorStateClass.MEASUREMENT,
                        unit=PERCENTAGE,
                        icon="mdi:wifi",
                        entity_category=EntityCategory.DIAGNOSTIC,
                        precision=0,
                    ),
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"system_module_{device_id}_latency",
                        device_id,
                        "system_modules",
                        LATENCY,
                        lambda d: d.get("link_latency"),
                        state_class=SensorStateClass.MEASUREMENT,
                        unit=UnitOfTime.MILLISECONDS,
                        icon="mdi:timer-outline",
                        entity_category=EntityCategory.DIAGNOSTIC,
                        precision=0,
                    ),
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"system_module_{device_id}_channel",
                        device_id,
                        "system_modules",
                        CHANNEL,
                        lambda d: d.get("network_channel"),
                        icon="mdi:radio-tower",
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"system_module_{device_id}_network",
                        device_id,
                        "system_modules",
                        NETWORK,
                        lambda d: d.get("network_name"),
                        icon="mdi:wifi-settings",
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"system_module_{device_id}_ip",
                        device_id,
                        "system_modules",
                        IP_ADDRESS,
                        lambda d: d.get("ip"),
                        icon="mdi:ip-network",
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                ]
            )

    async_add_entities(entities)

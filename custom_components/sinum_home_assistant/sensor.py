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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfIrradiance,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import TEMP_SCALE
from .coordinator import SinumHomeAssistantCoordinator
from .data import SinumHomeAssistantData
from .entity import (
    SinumDeviceEntity,
    SinumHomeAssistantEntity,
    generic_device_info,
    hub_device_info,
    schedule_device_info,
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


def _scale_factor(value: Any, factor: float | None) -> Any:
    if factor is None:
        return value
    if isinstance(value, (int, float)):
        return round(float(value) * factor, 3)
    return None


# Extra WTP device types. Values are only created when the field exists.
WTP_SENSOR_SPECS: dict[str, list[tuple]] = {
    "pressure_sensor": [
        ("pressure", "Ciśnienie", SensorDeviceClass.PRESSURE,
         UnitOfPressure.HPA, TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
    ],
    "co2_sensor": [
        ("co2", "CO2", None, "ppm", 1, 0, SensorStateClass.MEASUREMENT),
    ],
    "iaq_sensor": [
        ("iaq", "Indeks jakości powietrza", None, None, 1, 0,
         SensorStateClass.MEASUREMENT),
        ("iaq_accuracy", "Dokładność IAQ", None, None, None, None, None),
        ("air_quality", "Jakość powietrza", None, None, None, None, None),
    ],
    "aq_sensor": [
        ("pm1p0", "PM1.0", None, "µg/m³", 1, 0,
         SensorStateClass.MEASUREMENT),
        ("pm2p5", "PM2.5", None, "µg/m³", 1, 0,
         SensorStateClass.MEASUREMENT),
        ("pm4p0", "PM4.0", None, "µg/m³", 1, 0,
         SensorStateClass.MEASUREMENT),
        ("pm10p0", "PM10", None, "µg/m³", 1, 0,
         SensorStateClass.MEASUREMENT),
        ("air_quality", "Jakość powietrza", None, None, None, None, None),
    ],
    "light_sensor": [
        ("illuminance", "Natężenie światła", SensorDeviceClass.ILLUMINANCE,
         "lx", 1, 0, SensorStateClass.MEASUREMENT),
    ],
    "smoke_sensor": [
        ("dirt_level", "Zabrudzenie czujnika", None, PERCENTAGE, 1, 0,
         SensorStateClass.MEASUREMENT),
        ("uptime", "Czas pracy", SensorDeviceClass.DURATION,
         UnitOfTime.SECONDS, 1, 0, SensorStateClass.TOTAL_INCREASING),
    ],
    "motion_sensor": [
        ("time_since_motion", "Czas od ruchu", SensorDeviceClass.DURATION,
         UnitOfTime.SECONDS, 1, 0, SensorStateClass.MEASUREMENT),
    ],
    "radiator_actuator": [
        ("opening", "Otwarcie zaworu", None, PERCENTAGE, 1, 0,
         SensorStateClass.MEASUREMENT),
        ("valve_temperature", "Temperatura zaworu",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
    ],
    "throttle": [
        ("opening", "Otwarcie przepustnicy", None, PERCENTAGE, 1, 0,
         SensorStateClass.MEASUREMENT),
        ("impulses", "Impulsy", None, None, 1, 0,
         SensorStateClass.MEASUREMENT),
        ("flow", "Przepływ", None, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         1, 2, SensorStateClass.MEASUREMENT),
    ],
    "energy_meter": [
        ("current", "Prąd", SensorDeviceClass.CURRENT,
         UnitOfElectricCurrent.AMPERE, 0.001, 2,
         SensorStateClass.MEASUREMENT),
        ("voltage", "Napięcie", SensorDeviceClass.VOLTAGE,
         UnitOfElectricPotential.VOLT, 0.001, 2,
         SensorStateClass.MEASUREMENT),
        ("active_power", "Moc czynna", SensorDeviceClass.POWER,
         UnitOfPower.WATT, 0.001, 1, SensorStateClass.MEASUREMENT),
        ("energy_consumed_today", "Energia dzisiaj",
         SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, 0.001, 3,
         SensorStateClass.TOTAL_INCREASING),
        ("energy_consumed_yesterday", "Energia wczoraj",
         SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, 0.001, 3,
         SensorStateClass.TOTAL),
        ("energy_consumed_total", "Energia łącznie",
         SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, 0.001, 3,
         SensorStateClass.TOTAL_INCREASING),
    ],
    "ir_heater": [
        ("foil_current_temperature", "Temperatura folii",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
        ("triac_current_temperature", "Temperatura triaka",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
        ("pwm_duty", "Wypełnienie PWM", None, PERCENTAGE, 0.01, 2,
         SensorStateClass.MEASUREMENT),
        ("device_state", "Stan urządzenia", None, None, None, None, None),
    ],
    "dimmer": [
        ("ambient_light_intensity", "Światło otoczenia", None, PERCENTAGE,
         1, 0, SensorStateClass.MEASUREMENT),
        ("output_temperature", "Temperatura wyjścia",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
    ],
    "blind_controller": [
        ("target_opening", "Docelowe otwarcie", None, PERCENTAGE, 1, 0,
         SensorStateClass.MEASUREMENT),
        ("current_opening", "Bieżące otwarcie", None, PERCENTAGE, 1, 0,
         SensorStateClass.MEASUREMENT),
    ],
    "fan_coil_v2": [
        ("state", "Stan", None, None, None, None, None),
        ("fan_operation_mode", "Tryb wentylatora", None, None, None, None,
         None),
    ],
    "button": [
        ("action", "Ostatnia akcja", None, None, None, None, None),
    ],
}


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


class SinumScheduleSensor(SinumHomeAssistantEntity, SensorEntity):
    """Read-only thermal schedule value."""

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        schedule_id: int,
        name: str,
        value_fn: Callable[[dict[str, Any]], Any],
        *,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        precision: int | None = None,
    ) -> None:
        super().__init__(coordinator, device_info, unique_key)
        self._schedule_id = schedule_id
        self._value_fn = value_fn
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_suggested_display_precision = precision
        self._attr_icon = "mdi:calendar-clock"

    def _schedule(self) -> dict[str, Any]:
        return self.coordinator.data.schedules.get(self._schedule_id, {})

    @property
    def native_value(self) -> Any:
        return self._value_fn(self._schedule())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        schedule = self._schedule()
        return {
            "schedule_id": self._schedule_id,
            "modes": schedule.get("modes"),
            "associations": schedule.get("associations"),
            "fallback": _scale(schedule.get("fallback")),
            "associated_devices": sum(
                len(v)
                for v in (schedule.get("associations") or {}).values()
                if isinstance(v, list)
            ),
        }


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

    if coordinator.enable_schedules and data.schedules:
        for schedule_id, schedule in data.schedules.items():
            info = schedule_device_info(entry.entry_id, schedule, data)
            entities.extend(
                [
                    SinumScheduleSensor(
                        coordinator,
                        info,
                        f"schedule_{schedule_id}_current",
                        schedule_id,
                        "Temperatura docelowa",
                        lambda d: _scale(d.get("current_target_temperature")),
                        device_class=SensorDeviceClass.TEMPERATURE,
                        unit=UnitOfTemperature.CELSIUS,
                        precision=1,
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

        for key, name, device_class, unit, factor, precision, state_class in (
            WTP_SENSOR_SPECS.get(device_type, [])
        ):
            if key not in device:
                continue
            entities.append(
                SinumDeviceSensor(
                    coordinator,
                    info,
                    f"wtp_{device_id}_{key}",
                    device_id,
                    "wtp",
                    name,
                    lambda d, key=key, factor=factor: _scale_factor(
                        d.get(key), factor
                    ),
                    device_class=device_class,
                    state_class=state_class,
                    unit=unit,
                    precision=precision,
                )
            )


    for group, group_devices in data.device_groups.items():
        if group in ("wtp", "system_module"):
            continue
        for device_id, device in group_devices.items():
            if group == "virtual" and device.get("type") == "thermostat":
                continue
            info = generic_device_info(entry.entry_id, group, device, data)
            if (
                group == "virtual"
                and device.get("variant") == "temperature_sensor"
                and (device.get("variant_device") or {}).get("temperature")
                is not None
            ):
                entities.append(
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"{group}_{device_id}_temperature",
                        device_id,
                        group,
                        TEMPERATURE,
                        lambda d: _scale(
                            (d.get("variant_device") or {}).get("temperature")
                        ),
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        unit=UnitOfTemperature.CELSIUS,
                        precision=1,
                    )
                )
            for key, name, device_class, unit, factor, precision, state_class in (
                WTP_SENSOR_SPECS.get(device.get("type"), [])
            ):
                if key not in device:
                    continue
                entities.append(
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"{group}_{device_id}_{key}",
                        device_id,
                        group,
                        name,
                        lambda d, key=key, factor=factor: _scale_factor(
                            d.get(key), factor
                        ),
                        device_class=device_class,
                        state_class=state_class,
                        unit=unit,
                        precision=precision,
                    )
                )
            if device.get("signal") is not None:
                entities.append(
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"{group}_{device_id}_signal",
                        device_id,
                        group,
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
                        f"{group}_{device_id}_battery",
                        device_id,
                        group,
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
        if device.get("type") != "thermostat":
            continue
        info = virtual_device_info(entry.entry_id, device, data)
        entities.extend(
            [
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
            specs = []
            if device.get("network_signal") is not None:
                specs.append(
                    (
                        "signal",
                        SIGNAL,
                        SensorStateClass.MEASUREMENT,
                        PERCENTAGE,
                        "mdi:wifi",
                    )
                )
            if device.get("link_latency") is not None:
                specs.append(
                    (
                        "latency",
                        LATENCY,
                        SensorStateClass.MEASUREMENT,
                        UnitOfTime.MILLISECONDS,
                        "mdi:timer-outline",
                    )
                )
            if device.get("network_channel") is not None:
                specs.append(
                    (
                        "channel",
                        CHANNEL,
                        None,
                        None,
                        "mdi:radio-tower",
                    )
                )
            if device.get("network_name") is not None:
                specs.append(
                    (
                        "network",
                        NETWORK,
                        None,
                        None,
                        "mdi:wifi-settings",
                    )
                )
            ip = device.get("ip")
            if ip and ip != "127.0.0.1":
                specs.append(
                    ("ip", IP_ADDRESS, None, None, "mdi:ip-network")
                )
            for key, name, state_class, unit, icon in specs:
                value_key = {
                    "signal": "network_signal",
                    "latency": "link_latency",
                    "channel": "network_channel",
                    "network": "network_name",
                    "ip": "ip",
                }[key]
                entities.append(
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"system_module_{device_id}_{key}",
                        device_id,
                        "system_modules",
                        name,
                        lambda d, value_key=value_key: d.get(value_key),
                        state_class=state_class,
                        unit=unit,
                        icon=icon,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        precision=0 if key in ("signal", "latency") else None,
                    )
                )

    async_add_entities(entities)

"""Sensor platform for Sinum Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
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
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BRIDGE_ENABLED,
    CONF_BRIDGE_LABEL,
    CONF_BRIDGE_ROOM_ID,
    DEFAULT_BRIDGE_LABEL,
    TEMP_SCALE,
)
from .coordinator import SinumHomeAssistantCoordinator
from .data import SinumHomeAssistantData
from .entity import (
    SinumDeviceEntity,
    SinumHomeAssistantEntity,
    energy_center_device_info,
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


def _ec_flow_value(data: Any, key: str) -> Any:
    flow = (getattr(data, "energy_center", {}) or {}).get("flow") or {}
    item = ((flow.get("summary") or {}).get(key) or {})
    if item.get("available") is False:
        return None
    return item.get("value")


def _ec_battery_soc(data: Any) -> Any:
    flow = (getattr(data, "energy_center", {}) or {}).get("flow") or {}
    battery = ((flow.get("summary") or {}).get("battery") or {})
    state = battery.get("state_of_charge") or {}
    if battery.get("available") is False or state.get("available") is False:
        return None
    return state.get("value")


def _ec_energy(data: Any, section: str, period: str, key: str) -> Any:
    block = (getattr(data, "energy_center", {}) or {}).get(section) or {}
    if block.get("available") is False:
        return None
    return (block.get(period) or {}).get(key)


def _ec_storage(data: Any, key: str) -> Any:
    block = (getattr(data, "energy_center", {}) or {}).get("storage") or {}
    if block.get("available") is False:
        return None
    if key == "soc":
        state = block.get("state_of_charge") or {}
        if state.get("available") is False:
            return None
        return state.get("value")
    return block.get(key)


def _ec_currency(data: Any) -> Any:
    return (
        (getattr(data, "energy_center", {}) or {}).get("prices") or {}
    ).get("currency")


def _scale(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return None


def _scaled_field(device: dict[str, Any], key: str, factor: Any) -> Any:
    return _scale_factor(device.get(key), factor)


def _temperature_field(device: dict[str, Any], key: str) -> Any:
    return _valid_temperature(device.get(key))


def _valid_temperature(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        scaled = round(float(value) * TEMP_SCALE, 1)
        if -100.0 <= scaled <= 150.0:
            return scaled
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


MODULE_SENSOR_SPECS: dict[str, list[tuple]] = {
    "temperature_sensor": [
        ("temperature", TEMPERATURE, SensorDeviceClass.TEMPERATURE,
         UnitOfTemperature.CELSIUS, TEMP_SCALE, 1,
         SensorStateClass.MEASUREMENT),
    ],
    "humidity_sensor": [
        ("humidity", HUMIDITY, SensorDeviceClass.HUMIDITY, PERCENTAGE,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
    ],
    "battery": [
        ("soc", BATTERY, SensorDeviceClass.BATTERY, PERCENTAGE, None, 0,
         SensorStateClass.MEASUREMENT),
    ],
    "analog_input": [
        ("value", "Wartość", None, None, None, 2,
         SensorStateClass.MEASUREMENT),
    ],
    "analog_output": [
        ("value", "Wartość", None, None, None, 2,
         SensorStateClass.MEASUREMENT),
    ],
    "energy_meter": [
        ("total_active_power", "Moc", SensorDeviceClass.POWER,
         UnitOfPower.WATT, 0.001, 1, SensorStateClass.MEASUREMENT),
        ("energy_sum_total", "Energia", SensorDeviceClass.ENERGY,
         UnitOfEnergy.KILO_WATT_HOUR, 0.001, 1,
         SensorStateClass.TOTAL_INCREASING),
    ],
    "water_meter": [
        ("current_water_flow", "Przepływ", None,
         UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, None, 2,
         SensorStateClass.MEASUREMENT),
        ("total_water_volume", "Objętość", SensorDeviceClass.WATER,
         UnitOfVolume.CUBIC_METERS, 0.001, 1,
         SensorStateClass.TOTAL_INCREASING),
    ],
    "gas_meter": [
        ("current_gas_flow", "Przepływ", None,
         UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, None, 2,
         SensorStateClass.MEASUREMENT),
        ("gas_consumed_total", "Gaz", SensorDeviceClass.GAS,
         UnitOfVolume.CUBIC_METERS, 0.001, 1,
         SensorStateClass.TOTAL_INCREASING),
    ],
    "heat_pump": [
        ("target_temperature_indoor", "Temperatura zadana",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
        ("thermal_demand", "Zapotrzebowanie", None, None, None, None, None),
        ("target_temperature_mode", "Tryb temperatury", None, None, None,
         None, None),
    ],
    "heat_meter": [
        ("current_water_flow", "Przepływ", None,
         UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR, None, 2,
         SensorStateClass.MEASUREMENT),
        ("total_water_volume", "Objętość", SensorDeviceClass.WATER,
         UnitOfVolume.CUBIC_METERS, 0.001, 1,
         SensorStateClass.TOTAL_INCREASING),
        ("energy_consumed_total", "Energia", SensorDeviceClass.ENERGY,
         UnitOfEnergy.KILO_WATT_HOUR, 0.001, 1,
         SensorStateClass.TOTAL_INCREASING),
        ("flow_temperature", "Temperatura zasilania",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
        ("return_temperature", "Temperatura powrotu",
         SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS,
         TEMP_SCALE, 1, SensorStateClass.MEASUREMENT),
        ("active_power", "Moc", SensorDeviceClass.POWER,
         UnitOfPower.WATT, 0.001, 1, SensorStateClass.MEASUREMENT),
    ],
}


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


class SinumBridgeConfigSensor(SinumHomeAssistantEntity, SensorEntity):
    """Expose the bridge selection settings for the external worker."""

    _attr_name = "Bridge configuration"
    _attr_icon = "mdi:bridge"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _options(self) -> dict[str, Any]:
        return self.coordinator.config_entry.options

    @property
    def native_value(self) -> str:
        return str(
            self._options().get(CONF_BRIDGE_LABEL, DEFAULT_BRIDGE_LABEL)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        options = self._options()
        return {
            "sinum_bridge_config": True,
            "enabled": bool(options.get(CONF_BRIDGE_ENABLED, True)),
            "label": str(
                options.get(CONF_BRIDGE_LABEL, DEFAULT_BRIDGE_LABEL)
            ),
            "room_id": int(options.get(CONF_BRIDGE_ROOM_ID, 0) or 0),
        }


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
            SinumBridgeConfigSensor(coordinator, hub_info, "hub_bridge"),
        ]
    )

    energy_info = energy_center_device_info(entry.entry_id, data)
    energy_entities = [
        ("energy_pv_power", "Moc PV", lambda d: _ec_flow_value(d, "pv"),
         SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT,
         UnitOfPower.WATT, "mdi:solar-power", None, 0),
        ("energy_grid_power", "Moc sieci",
         lambda d: _ec_flow_value(d, "grid"),
         SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT,
         UnitOfPower.WATT, "mdi:transmission-tower", None, 0),
        ("energy_building_power", "Moc budynku",
         lambda d: _ec_flow_value(d, "building"),
         SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT,
         UnitOfPower.WATT, "mdi:home-lightning-bolt", None, 0),
        ("energy_battery_power", "Moc baterii",
         lambda d: _ec_flow_value(d, "battery"),
         SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT,
         UnitOfPower.WATT, "mdi:battery-charging", None, 0),
        ("energy_battery_soc", "Poziom baterii",
         lambda d: _ec_battery_soc(d),
         SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT,
         PERCENTAGE, "mdi:battery", None, 0),
        ("energy_consumption_today", "Zużycie dziś",
         lambda d: _ec_energy(d, "consumption", "today",
                              "total_consumption"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:home-lightning-bolt", None, 2),
        ("energy_consumption_total", "Zużycie total",
         lambda d: _ec_energy(d, "consumption", "total",
                              "total_consumption"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:home-lightning-bolt", None, 2),
        ("energy_production_today", "Produkcja dziś",
         lambda d: _ec_energy(d, "production", "today", "all"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-power", None, 2),
        ("energy_production_total", "Produkcja total",
         lambda d: _ec_energy(d, "production", "total", "all"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:solar-power", None, 2),
        ("energy_grid_export_today", "Eksport do sieci dziś",
         lambda d: _ec_energy(d, "production", "today", "grid_export"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:transmission-tower-export",
         None, 2),
        ("energy_storage_charged_today", "Bateria ładowana dziś",
         lambda d: _ec_storage(d, "energy_charged_today"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:battery-plus", None, 2),
        ("energy_storage_discharged_today", "Bateria rozładowana dziś",
         lambda d: _ec_storage(d, "energy_discharged_today"),
         SensorDeviceClass.ENERGY, SensorStateClass.TOTAL,
         UnitOfEnergy.KILO_WATT_HOUR, "mdi:battery-minus", None, 2),
        ("energy_storage_power", "Moc baterii (storage)",
         lambda d: _ec_storage(d, "power"),
         SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT,
         UnitOfPower.WATT, "mdi:battery-charging", None, 0),
        ("energy_storage_status", "Status baterii",
         lambda d: _ec_storage(d, "status"),
         None, None, None, "mdi:battery-heart-variant", None, None),
        ("energy_price_currency", "Waluta cen energii",
         lambda d: _ec_currency(d),
         None, None, None, "mdi:currency-usd",
         EntityCategory.DIAGNOSTIC, None),
    ]
    for (
        key,
        name,
        value_fn,
        device_class,
        state_class,
        unit,
        icon,
        category,
        precision,
    ) in energy_entities:
        entities.append(
            SinumValueSensor(
                coordinator,
                energy_info,
                key,
                name,
                value_fn,
                device_class=device_class,
                state_class=state_class,
                unit=unit,
                icon=icon,
                entity_category=category,
                precision=precision,
            )
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
            sensor_specs = (
                {**WTP_SENSOR_SPECS, **MODULE_SENSOR_SPECS}
                if group == "custom_device_module"
                else WTP_SENSOR_SPECS
            )
            for key, name, device_class, unit, factor, precision, state_class in (
                sensor_specs.get(device.get("type"), [])
            ):
                if key not in device:
                    continue
                if group == "custom_device_module" and key == "temperature":
                    value_fn = partial(_temperature_field, key=key)
                else:
                    value_fn = partial(
                        _scaled_field, key=key, factor=factor
                    )
                entities.append(
                    SinumDeviceSensor(
                        coordinator,
                        info,
                        f"{group}_{device_id}_{key}",
                        device_id,
                        group,
                        name,
                        value_fn,
                        device_class=device_class,
                        state_class=state_class,
                        unit=unit or device.get("unit"),
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

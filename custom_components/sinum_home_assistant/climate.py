"""Climate platform for Sinum Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SinumHomeAssistantError
from .const import HVAC_TO_SINUM, SINUM_TO_HVAC, TEMP_SCALE
from .coordinator import SinumHomeAssistantCoordinator
from .entity import (
    SinumDeviceEntity,
    virtual_device_info,
    wtp_device_info,
)

PARALLEL_UPDATES = 1

DEFAULT_MIN_TEMP = 5.0
DEFAULT_MAX_TEMP = 35.0


def _scaled(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value) * TEMP_SCALE, 1)
    return default


def _hvac_mode(value: Any) -> HVACMode:
    sinum_mode = str(value or "off")
    return HVACMode(SINUM_TO_HVAC.get(sinum_mode, "off"))


class SinumClimate(SinumDeviceEntity, ClimateEntity):
    """Thermostat or WTP temperature regulator."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_icon = "mdi:home-thermometer"

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
        store: str,
        device_class: str,
        *,
        is_virtual: bool,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, store
        )
        self._device_class = device_class
        self._is_virtual = is_virtual

    @property
    def hvac_modes(self) -> list[HVACMode]:
        declared = self._device().get("available_work_modes")
        if isinstance(declared, list) and declared:
            modes = [HVACMode.OFF]
            for mode in declared:
                hvac = SINUM_TO_HVAC.get(str(mode))
                if hvac is not None:
                    mapped = HVACMode(hvac)
                    if mapped not in modes:
                        modes.append(mapped)
            return modes
        return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def hvac_mode(self) -> HVACMode:
        device = self._device()
        if self._is_virtual:
            return _hvac_mode(device.get("mode"))
        return _hvac_mode(device.get("system_mode"))

    @property
    def native_current_temperature(self) -> float | None:
        return self.coordinator.data.current_temperature(self._device())

    @property
    def native_target_temperature(self) -> float | None:
        return _scaled(self._device().get("target_temperature"))

    @property
    def min_temp(self) -> float:
        device = self._device()
        mode = self.hvac_mode
        if self._is_virtual and mode == HVACMode.COOL:
            return _scaled(
                device.get("target_temperature_cooling_minimum"),
                DEFAULT_MIN_TEMP,
            ) or DEFAULT_MIN_TEMP
        if self._is_virtual and mode == HVACMode.HEAT:
            return _scaled(
                device.get("target_temperature_heating_minimum"),
                DEFAULT_MIN_TEMP,
            ) or DEFAULT_MIN_TEMP
        return _scaled(
            device.get("target_temperature_minimum"), DEFAULT_MIN_TEMP
        ) or DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        device = self._device()
        mode = self.hvac_mode
        if self._is_virtual and mode == HVACMode.COOL:
            return _scaled(
                device.get("target_temperature_cooling_maximum"),
                DEFAULT_MAX_TEMP,
            ) or DEFAULT_MAX_TEMP
        if self._is_virtual and mode == HVACMode.HEAT:
            return _scaled(
                device.get("target_temperature_heating_maximum"),
                DEFAULT_MAX_TEMP,
            ) or DEFAULT_MAX_TEMP
        return _scaled(
            device.get("target_temperature_maximum"), DEFAULT_MAX_TEMP
        ) or DEFAULT_MAX_TEMP

    @property
    def hvac_action(self) -> HVACAction:
        device = self._device()
        mode = self.hvac_mode
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._is_virtual:
            if device.get("state") is True:
                return (
                    HVACAction.COOLING
                    if mode == HVACMode.COOL
                    else HVACAction.HEATING
                )
            return HVACAction.IDLE
        reached = device.get("target_temperature_reached")
        if reached is False:
            return (
                HVACAction.COOLING
                if mode == HVACMode.COOL
                else HVACAction.HEATING
            )
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        device = self._device()
        attrs.update(
            {
                "hvac_mode_raw": device.get(
                    "mode" if self._is_virtual else "system_mode"
                ),
                "target_temperature_reached": device.get(
                    "target_temperature_reached"
                ),
                "window_open": device.get("is_window_open"),
                "schedule_id": device.get("schedule_id"),
                "mode_mutable": device.get("mode_mutable"),
            }
        )
        relays = (device.get("associations") or {}).get("relays") or []
        relay_ids = sorted(
            int(relay["id"])
            for relay in relays
            if isinstance(relay, dict) and relay.get("id") is not None
        )
        if relay_ids:
            attrs["relay_ids"] = relay_ids
            attrs["relay_states"] = {
                str(relay_id): self.coordinator.data.wtp.get(
                    relay_id, {}
                ).get("state")
                for relay_id in relay_ids
            }
            attrs["relay_last_changes"] = {
                str(relay_id): self.coordinator.data.wtp.get(
                    relay_id, {}
                ).get("time_since_state_change")
                for relay_id in relay_ids
            }
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        target = max(self.min_temp, min(self.max_temp, float(temperature)))
        raw = round(target / TEMP_SCALE)
        try:
            await self.coordinator.client.async_patch_device(
                self._device_class,
                self._device_id,
                {"target_temperature": raw},
            )
        except SinumHomeAssistantError as err:
            raise HomeAssistantError(
                f"Cannot set target temperature: {err}"
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode = HVAC_TO_SINUM.get(hvac_mode.value, "off")
        key = "mode" if self._is_virtual else "system_mode"
        try:
            await self.coordinator.client.async_patch_device(
                self._device_class,
                self._device_id,
                {key: mode},
            )
        except SinumHomeAssistantError as err:
            raise HomeAssistantError(
                f"Cannot set HVAC mode: {err}"
            ) from err
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[ClimateEntity] = []

    for device_id, device in data.virtual.items():
        if device.get("type") != "thermostat":
            continue
        entities.append(
            SinumClimate(
                coordinator,
                virtual_device_info(entry.entry_id, device, data),
                f"virtual_{device_id}_climate",
                device_id,
                "virtual",
                "virtual",
                is_virtual=True,
            )
        )

    for device_id, device in data.wtp.items():
        if device.get("type") != "temperature_regulator":
            continue
        parent = data.parents_wtp.get(device.get("parent_id"))
        entities.append(
            SinumClimate(
                coordinator,
                wtp_device_info(entry.entry_id, device, parent, data),
                f"wtp_{device_id}_climate",
                device_id,
                "wtp",
                "wtp",
                is_virtual=False,
            )
        )

    async_add_entities(entities)

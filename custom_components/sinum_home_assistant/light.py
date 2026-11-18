"""Light platform for Sinum custom device modules."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SinumHomeAssistantError
from .coordinator import SinumHomeAssistantCoordinator
from .entity import SinumDeviceEntity, custom_module_device_info

PARALLEL_UPDATES = 1


def _rgb_color(value: Any) -> tuple[int, int, int] | None:
    text = str(value or "").lstrip("#")
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return None


class SinumModuleLight(SinumDeviceEntity, LightEntity):
    """Dimmer or RGB controller module exposed as a light."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
        module_type: str,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, "custom_modules"
        )
        self._module_type = module_type
        if module_type == "dimmer":
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_supported_color_modes = {
                ColorMode.RGB,
                ColorMode.COLOR_TEMP,
            }
            self._attr_min_color_temp_kelvin = 2200
            self._attr_max_color_temp_kelvin = 6500

    @property
    def is_on(self) -> bool | None:
        state = self._device().get("state")
        return state if isinstance(state, bool) else None

    @property
    def brightness(self) -> int | None:
        device = self._device()
        raw = (
            device.get("target_level")
            if self._module_type == "dimmer"
            else device.get("brightness")
        )
        if not isinstance(raw, (int, float)):
            return None
        return max(0, min(255, round(float(raw) * 255 / 100)))

    @property
    def color_mode(self) -> ColorMode | None:
        if self._module_type == "dimmer":
            return ColorMode.BRIGHTNESS
        if self._device().get("color_mode") == "rgb":
            return ColorMode.RGB
        return ColorMode.COLOR_TEMP

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        if self._module_type == "dimmer":
            return None
        return _rgb_color(self._device().get("led_color"))

    @property
    def color_temp_kelvin(self) -> int | None:
        if self._module_type == "dimmer":
            return None
        value = self._device().get("white_temperature")
        return int(value) if isinstance(value, (int, float)) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        commands: list[tuple[str, dict[str, Any]]] = []
        if not self.is_on:
            commands.append(("turn_on", {}))
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if isinstance(brightness, int):
            level = max(1, min(100, round(brightness * 100 / 255)))
            command = (
                "set_level"
                if self._module_type == "dimmer"
                else "set_brightness"
            )
            commands.append((command, {command: [level, 1]}))
        rgb = kwargs.get(ATTR_RGB_COLOR)
        if (
            self._module_type != "dimmer"
            and isinstance(rgb, (list, tuple))
            and len(rgb) == 3
        ):
            color = "#{:02x}{:02x}{:02x}".format(
                *(int(value) for value in rgb)
            )
            commands.append(("set_color", {"set_color": [color, 1]}))
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if self._module_type != "dimmer" and isinstance(kelvin, int):
            commands.append(
                ("set_temperature", {"set_temperature": [kelvin, 1]})
            )
        if not commands:
            commands.append(("turn_on", {}))
        for command, payload in commands:
            await self._async_command(command, payload)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_command("turn_off", {})
        await self.coordinator.async_request_refresh()

    async def _async_command(
        self, command: str, payload: dict[str, Any]
    ) -> None:
        try:
            await self.coordinator.client.async_post(
                f"devices/custom-device-module/{self._device_id}"
                f"/command/{command}",
                payload,
            )
        except SinumHomeAssistantError as err:
            raise HomeAssistantError(
                f"Cannot control Sinum light module: {err}"
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[LightEntity] = []

    for module_id, module in data.custom_modules.items():
        module_type = str(module.get("type") or "")
        if module_type not in ("dimmer", "rgb_controller"):
            continue
        entities.append(
            SinumModuleLight(
                coordinator,
                custom_module_device_info(entry.entry_id, module, data),
                f"custom_module_{module_id}_light",
                module_id,
                module_type,
            )
        )

    async_add_entities(entities)

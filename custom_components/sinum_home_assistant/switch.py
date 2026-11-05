"""Switch platform for Sinum Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SinumHomeAssistantError
from .coordinator import SinumHomeAssistantCoordinator
from .entity import SinumDeviceEntity, wtp_device_info

PARALLEL_UPDATES = 1


class SinumRelaySwitch(SinumDeviceEntity, SwitchEntity):
    """WTP relay exposed as a switch."""

    _attr_name = None
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: SinumHomeAssistantCoordinator,
        device_info: Any,
        unique_key: str,
        device_id: int,
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, "wtp"
        )

    @property
    def is_on(self) -> bool | None:
        state = self._device().get("state")
        return state if isinstance(state, bool) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        device = self._device()
        attrs.update(
            {
                "work_mode": device.get("work_mode"),
                "timeout": device.get("timeout"),
                "timeout_enabled": device.get("timeout_enabled"),
                "inverted": device.get("inverted"),
                "address": device.get("address"),
                "parent_id": device.get("parent_id"),
            }
        )
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_state(False)

    async def _async_set_state(self, state: bool) -> None:
        try:
            await self.coordinator.client.async_patch_device(
                "wtp", self._device_id, {"state": state}
            )
        except SinumHomeAssistantError as err:
            raise HomeAssistantError(f"Cannot set relay state: {err}") from err
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SinumHomeAssistantCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[SwitchEntity] = []

    for device_id, device in data.wtp.items():
        if device.get("type") != "relay":
            continue
        parent = data.parents_wtp.get(device.get("parent_id"))
        entities.append(
            SinumRelaySwitch(
                coordinator,
                wtp_device_info(entry.entry_id, device, parent, data),
                f"wtp_{device_id}_switch",
                device_id,
            )
        )

    async_add_entities(entities)

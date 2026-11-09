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
from .data import is_managed_relay
from .entity import SinumDeviceEntity, generic_device_info, wtp_device_info

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
        device_class: str = "wtp",
        store: str = "wtp",
    ) -> None:
        super().__init__(
            coordinator, device_info, unique_key, device_id, store
        )
        self._device_class = device_class

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
                "time_since_state_change": device.get(
                    "time_since_state_change"
                ),
                "sinum_labels": device.get("labels"),
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
                self._device_class, self._device_id, {"state": state}
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
        if is_managed_relay(device):
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

    for group, group_devices in data.device_groups.items():
        if group in ("wtp", "virtual", "system_module"):
            continue
        for device_id, device in group_devices.items():
            if device.get("type") != "relay" or is_managed_relay(device):
                continue
            entities.append(
                SinumRelaySwitch(
                    coordinator,
                    generic_device_info(
                        entry.entry_id, group, device, data
                    ),
                    f"{group}_{device_id}_switch",
                    device_id,
                    device_class=group,
                    store=group,
                )
            )

    async_add_entities(entities)

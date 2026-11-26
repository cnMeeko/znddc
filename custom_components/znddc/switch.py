"""开关：开=启动（必要时先解锁），关=加锁断电设防。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZnddcCoordinator
from .entity import ZnddcEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZnddcCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZnddcPowerSwitch(coordinator)])


class ZnddcPowerSwitch(ZnddcEntity, SwitchEntity):
    """一个开关同时承担“启动 / 加锁”。"""

    _attr_icon = "mdi:moped"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "power", "启动")

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_powered

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "locked": self.coordinator.is_locked,
            "online": self.coordinator.is_online,
            "machine_no": self.coordinator.machine_no,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """启动：车辆处于设防状态时先解锁再启动。"""
        await self._async_command("start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭：加锁（断电设防）。"""
        await self._async_command("lock")

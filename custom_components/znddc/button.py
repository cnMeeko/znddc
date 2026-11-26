"""按钮：寻车、鞍座锁（点动）、手动刷新。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZnddcCoordinator
from .entity import ZnddcEntity


@dataclass(frozen=True, kw_only=True)
class ZnddcButtonDescription(ButtonEntityDescription):
    action: str = ""


BUTTONS: tuple[ZnddcButtonDescription, ...] = (
    ZnddcButtonDescription(
        key="find_car",
        name="寻车",
        icon="mdi:bullhorn",
        action="find",
    ),
    ZnddcButtonDescription(
        key="saddle_unlock",
        name="鞍座开锁",
        icon="mdi:lock-open-variant",
        action="saddle_unlock",
    ),
    ZnddcButtonDescription(
        key="refresh",
        name="刷新状态",
        icon="mdi:refresh",
        action="refresh",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZnddcCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ZnddcButton(coordinator, description) for description in BUTTONS]
    )


class ZnddcButton(ZnddcEntity, ButtonEntity):
    """点动按钮：按下即下发一次指令。"""

    entity_description: ZnddcButtonDescription

    def __init__(
        self,
        coordinator: ZnddcCoordinator,
        description: ZnddcButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key, description.name or "")
        self.entity_description = description
        self._attr_icon = description.icon

    async def async_press(self) -> None:
        if self.entity_description.action == "refresh":
            await self.coordinator.async_request_refresh()
            return
        await self._async_command(self.entity_description.action)

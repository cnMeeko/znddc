"""二进制传感器：在线、已设防、行车中。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    async_add_entities(
        [
            ZnddcBinarySensor(coordinator, "online", "在线", BinarySensorDeviceClass.CONNECTIVITY, "is_online"),
            ZnddcBinarySensor(coordinator, "locked", "已设防", BinarySensorDeviceClass.LOCK, "is_locked"),
            ZnddcBinarySensor(coordinator, "powered", "行车中", BinarySensorDeviceClass.POWER, "is_powered"),
        ]
    )


class ZnddcBinarySensor(ZnddcEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZnddcCoordinator,
        key: str,
        name: str,
        device_class: BinarySensorDeviceClass,
        source: str,
    ) -> None:
        super().__init__(coordinator, key, name)
        self._attr_device_class = device_class
        self._source = source

    @property
    def is_on(self) -> bool:
        return bool(getattr(self.coordinator, self._source))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.status
        return {
            "lock": status.get("lock"),
            "acc_power": status.get("accPower"),
            "start": status.get("start"),
        }

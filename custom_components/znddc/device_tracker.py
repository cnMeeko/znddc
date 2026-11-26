"""设备追踪：车辆 GPS 位置（可直接显示在 HA 地图上）。"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
    async_add_entities([ZnddcTracker(coordinator)])


class ZnddcTracker(ZnddcEntity, TrackerEntity):
    _attr_source_type = SourceType.GPS
    _attr_icon = "mdi:map-marker-radius"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "tracker", "定位")

    @property
    def latitude(self) -> float | None:
        return self.coordinator.latitude

    @property
    def longitude(self) -> float | None:
        return self.coordinator.longitude

    @property
    def location_accuracy(self) -> int:
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.status
        return {
            "address": self.coordinator.data.get("address"),
            "pos_time": status.get("posDt"),
            "gps_signal": status.get("gpsSignal"),
            "gsm_signal": status.get("gsmSignal"),
            "locked": self.coordinator.is_locked,
            "online": self.coordinator.is_online,
        }

"""传感器：电压、电流、电量、续航、今日里程/时长/均速、当前位置。"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZnddcCoordinator
from .entity import ZnddcEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZnddcCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZnddcVoltageSensor(coordinator),
            ZnddcCurrentSensor(coordinator),
            ZnddcBatterySensor(coordinator),
            ZnddcRangeSensor(coordinator),
            ZnddcTodayMileageSensor(coordinator),
            ZnddcTodayDurationSensor(coordinator),
            ZnddcTodaySpeedSensor(coordinator),
            ZnddcAddressSensor(coordinator),
        ]
    )


class _ZnddcSensor(ZnddcEntity, SensorEntity):
    def __init__(
        self,
        coordinator: ZnddcCoordinator,
        key: str,
        name: str,
        description: SensorEntityDescription | None = None,
    ) -> None:
        super().__init__(coordinator, key, name)
        if description is not None:
            self.entity_description = description
            self._attr_icon = description.icon


class ZnddcVoltageSensor(_ZnddcSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "voltage", "电压")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.voltage


class ZnddcCurrentSensor(_ZnddcSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:current-ac"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "current", "电流")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.current


class ZnddcBatterySensor(_ZnddcSensor):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "battery", "电量")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.battery_level


class ZnddcRangeSensor(_ZnddcSensor):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:map-marker-distance"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "range", "剩余续航")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.remaining_range


class ZnddcTodayMileageSensor(_ZnddcSensor):
    """当天行驶里程，附带分时与近 7 天数据。"""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "today_mileage", "今日里程")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.today_mileage

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = self.coordinator.data.get("today") or {}
        hourly = self.coordinator.data.get("hourly") or []
        return {
            "ride_time_min": self.coordinator.today_ride_minutes,
            "avg_speed_kmh": self.coordinator.today_speed,
            "raw_ride_time": today.get("rideTime"),
            "hourly": hourly[:24],
            "last_7_days": self.coordinator.data.get("history") or [],
        }


class ZnddcTodayDurationSensor(_ZnddcSensor):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "today_duration", "今日骑行时长")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.today_ride_minutes


class ZnddcTodaySpeedSensor(_ZnddcSensor):
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "today_speed", "今日平均速度")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.today_speed


class ZnddcAddressSensor(_ZnddcSensor):
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: ZnddcCoordinator) -> None:
        super().__init__(coordinator, "address", "当前位置")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("address")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.status
        return {
            "latitude": self.coordinator.latitude,
            "longitude": self.coordinator.longitude,
            "pos_time": status.get("posDt"),
            "gps_signal": status.get("gpsSignal"),
            "gsm_signal": status.get("gsmSignal"),
        }

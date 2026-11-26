"""数据协调器：轮询车辆状态、位置、当日与近 7 天里程。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ZnddcApi, ZnddcAuthError, ZnddcError
from .const import (
    ADDRESS_REFRESH_INTERVAL,
    CMD_FIND,
    CMD_LOCK,
    CMD_SADDLE_UNLOCK,
    CMD_START,
    CMD_UNLOCK,
    CMD_NAMES,
    DOMAIN,
    HISTORY_DAYS,
    HISTORY_REFRESH_INTERVAL,
    TODAY_REFRESH_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().replace("%", "").replace(",", "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool:
    """接口的布尔值可能是 0/1、true/false 或 "0"/"1"。"""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(value)


def _parse_duration_minutes(value: Any) -> float | None:
    """把 "HH:MM:SS" / 秒数 / 分钟数转成分钟。"""
    if value is None or value == "":
        return None
    if isinstance(value, str) and ":" in value:
        try:
            parts = [int(part) for part in value.split(":")]
        except ValueError:
            return None
        while len(parts) < 3:
            parts.append(0)
        hours, minutes, seconds = parts[-3], parts[-2], parts[-1]
        return round(hours * 60 + minutes + seconds / 60, 1)
    number = _to_float(value)
    if number is None:
        return None
    if number > 1000:  # 明显是秒
        return round(number / 60, 1)
    return round(number, 1)


class ZnddcCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """一辆车一个协调器。"""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: ZnddcApi,
        machine_no: str,
        machine_name: str,
        map_type: str,
        address_lookup: bool,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{machine_no}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.api = api
        self.machine_no = machine_no
        self.machine_name = machine_name
        self.map_type = map_type
        self.address_lookup = address_lookup

        self.data = {
            "status": {},
            "address": None,
            "today": {},
            "hourly": [],
            "history": [],
        }
        self._last_today_at: datetime | None = None
        self._last_history_at: datetime | None = None
        self._last_address_at: datetime | None = None
        self._address_coords: tuple[float, float] | None = None
        self._command_lock = asyncio.Lock()

    # ------------------------------------------------------------------ 轮询
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.api.async_get_status(self.machine_no, self.map_type)
        except ZnddcAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZnddcError as err:
            raise UpdateFailed(str(err)) from err

        if not status:
            raise UpdateFailed("未获取到车辆状态")

        now = dt_util.now()
        data: dict[str, Any] = {
            "status": status,
            "address": self.data.get("address"),
            "today": self.data.get("today") or {},
            "hourly": self.data.get("hourly") or [],
            "history": self.data.get("history") or [],
        }

        await self._async_maybe_address(status, data, now)
        await self._async_maybe_today(status, data, now)
        await self._async_maybe_history(data, now)
        return data

    async def _async_maybe_address(
        self,
        status: dict[str, Any],
        data: dict[str, Any],
        now: datetime,
    ) -> None:
        if not self.address_lookup:
            return
        lon = _to_float(status.get("lonC"))
        lat = _to_float(status.get("latC"))
        if lon is None or lat is None:
            return
        coords = (lon, lat)
        need = (
            self._address_coords != coords
            or not data.get("address")
            or self._last_address_at is None
            or (now - self._last_address_at).total_seconds()
            >= ADDRESS_REFRESH_INTERVAL
        )
        if not need:
            return
        try:
            address = await self.api.async_get_address(lon, lat, self.map_type)
        except ZnddcError as err:
            _LOGGER.debug("获取地址失败: %s", err)
            return
        if address:
            data["address"] = address
        self._address_coords = coords
        self._last_address_at = now

    async def _async_maybe_today(
        self,
        status: dict[str, Any],
        data: dict[str, Any],
        now: datetime,
    ) -> None:
        if (
            self._last_today_at is not None
            and (now - self._last_today_at).total_seconds() < TODAY_REFRESH_INTERVAL
            and (now.date() == self._last_today_at.date())
        ):
            return
        stamp = int(
            now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
        )
        try:
            data["today"] = await self.api.async_get_ride_by_date(self.machine_no, stamp)
            data["hourly"] = await self.api.async_get_ride_by_time(self.machine_no, stamp)
        except ZnddcError as err:
            _LOGGER.debug("获取今日里程失败: %s", err)
            return
        self._last_today_at = now

    async def _async_maybe_history(
        self, data: dict[str, Any], now: datetime
    ) -> None:
        if (
            self._last_history_at is not None
            and (now - self._last_history_at).total_seconds()
            < HISTORY_REFRESH_INTERVAL
        ):
            return
        history: list[dict[str, Any]] = []
        for offset in range(HISTORY_DAYS):
            day = now.date() - timedelta(days=offset)
            stamp = int(
                datetime(day.year, day.month, day.day, tzinfo=now.tzinfo).timestamp()
                * 1000
            )
            try:
                if offset == 0 and data.get("today"):
                    ride = data["today"]
                else:
                    ride = await self.api.async_get_ride_by_date(
                        self.machine_no, stamp
                    )
            except ZnddcError:
                ride = {}
            history.append(
                {
                    "date": day.isoformat(),
                    "mile": _to_float(ride.get("mile")),
                    "ride_time": ride.get("rideTime"),
                }
            )
        data["history"] = history
        self._last_history_at = now

    # ------------------------------------------------------------------ 指令
    async def async_send_command(self, action: str) -> None:
        """执行一个动作：start / lock / find / saddle_unlock。"""
        async with self._command_lock:
            if action == "start":
                status = self.data.get("status") or {}
                if _to_bool(status.get("lock")) and not self.is_powered:
                    await self._async_run(CMD_UNLOCK)
                    await asyncio.sleep(0.8)
                await self._async_run(CMD_START)
            elif action == "lock":
                await self._async_run(CMD_LOCK)
            elif action == "find":
                await self._async_run(CMD_FIND)
            elif action == "saddle_unlock":
                await self._async_run(CMD_SADDLE_UNLOCK)
            else:
                raise ZnddcError(f"未知指令: {action}")

        try:
            await self.async_refresh()
        except ZnddcError as err:  # 极少数情况下刷新失败不影响指令结果
            _LOGGER.debug("指令后刷新失败: %s", err)
        # 车辆状态上报可能有延迟，8 秒后再补一次
        async_call_later(self.hass, 8, self._async_late_refresh)

    async def _async_late_refresh(self, _now: Any) -> None:
        try:
            await self.async_refresh()
        except ZnddcError:
            pass

    async def _async_run(self, cmd: int) -> None:
        name = CMD_NAMES.get(cmd, str(cmd))
        _LOGGER.debug("下发指令 %s(车辆 %s)", name, self.machine_no)
        try:
            serial = await self.api.async_ter_control(self.machine_no, cmd)
            ok, message = await self.api.async_wait_command(serial)
        except ZnddcAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZnddcError as err:
            raise ZnddcError(f"{name}指令发送失败: {err}") from err
        if not ok:
            raise ZnddcError(
                f"{name}指令执行失败{('：' + message) if message else '，请稍后重试'}"
            )

    # ------------------------------------------------------------------ 便捷属性
    @property
    def status(self) -> dict[str, Any]:
        return self.data.get("status") or {}

    @property
    def bms(self) -> dict[str, Any]:
        bms = self.status.get("bmsInfo")
        return bms if isinstance(bms, dict) else {}

    @property
    def is_online(self) -> bool:
        return _to_bool(self.status.get("onLine"))

    @property
    def is_locked(self) -> bool:
        return _to_bool(self.status.get("lock"))

    @property
    def is_powered(self) -> bool:
        value = self.status.get("accPower")
        if value is None:
            value = self.status.get("start")
        return _to_bool(value)

    @property
    def voltage(self) -> float | None:
        raw = _to_float(self.bms.get("overallEU"))
        return round(raw / 100, 1) if raw is not None else None

    @property
    def current(self) -> float | None:
        raw = _to_float(self.bms.get("overallEI"))
        return round(raw / 100, 1) if raw is not None else None

    @property
    def battery_level(self) -> float | None:
        raw = _to_float(self.bms.get("soc"))
        if raw is not None:
            return round(raw / 10, 1)
        return _to_float(self.status.get("socPercent"))

    @property
    def remaining_range(self) -> float | None:
        return _to_float(self.status.get("surplusMileage"))

    @property
    def today_mileage(self) -> float | None:
        return _to_float((self.data.get("today") or {}).get("mile"))

    @property
    def today_speed(self) -> float | None:
        return _to_float((self.data.get("today") or {}).get("speed"))

    @property
    def today_ride_minutes(self) -> float | None:
        return _parse_duration_minutes((self.data.get("today") or {}).get("rideTime"))

    @property
    def latitude(self) -> float | None:
        return _to_float(self.status.get("latC"))

    @property
    def longitude(self) -> float | None:
        return _to_float(self.status.get("lonC"))

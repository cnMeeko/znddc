"""智能电动车管家云端接口封装（纯 aiohttp，无需额外依赖）。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    ACCOUNT_ID,
    API_BASE,
    CMD_POLL_ATTEMPTS,
    CMD_POLL_INTERVAL,
    LOGIN_TYPE_EMAIL,
    LOGIN_TYPE_PHONE,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=20)


class ZnddcError(Exception):
    """接口调用异常基类。"""


class ZnddcCannotConnect(ZnddcError):
    """网络不可用或返回异常。"""


class ZnddcAuthError(ZnddcError):
    """账号密码错误或登录过期。"""


def _is_ok(payload: dict[str, Any]) -> bool:
    return str(payload.get("ret")) in ("1", "True", "true")


def _code(payload: dict[str, Any]) -> str:
    value = payload.get("code")
    return "" if value is None else str(value)


def _msg(payload: dict[str, Any]) -> str:
    return str(payload.get("msg") or "未知错误")


class ZnddcApi:
    """一个账号对应一个实例，内部维护 token。"""

    def __init__(
        self,
        session: ClientSession,
        account: str,
        password: str,
        login_type: str | None = None,
    ) -> None:
        self._session = session
        self.account = (account or "").strip()
        password = (password or "").strip()
        # 原 App 输入法容易把结尾句点打成中文句号，这里自动纠正
        if password.endswith("。"):
            password = password[:-1] + "."
        self.password = password
        self.login_type = login_type
        self.token: str | None = None
        self._login_lock = asyncio.Lock()

    # ------------------------------------------------------------------ 基础
    @property
    def is_phone(self) -> bool:
        if self.login_type == LOGIN_TYPE_PHONE:
            return True
        if self.login_type == LOGIN_TYPE_EMAIL:
            return False
        # 未指定时按格式兜底判断
        return bool(re.fullmatch(r"1\d{10}", self.account))

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = API_BASE + path
        try:
            async with self._session.get(
                url, params=params, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    raise ZnddcCannotConnect(f"HTTP {response.status}")
                text = await response.text()
        except (ClientError, asyncio.TimeoutError) as err:
            raise ZnddcCannotConnect(f"网络异常: {err}") from err

        try:
            payload = json.loads(text)
        except ValueError as err:
            raise ZnddcCannotConnect("接口返回内容不是合法 JSON") from err
        if not isinstance(payload, dict):
            raise ZnddcCannotConnect("接口返回结构异常")
        return payload

    # ------------------------------------------------------------------ 登录
    async def async_login(self) -> str:
        """登录并缓存 token。"""
        if self.is_phone:
            params: dict[str, Any] = {"phone": self.account, "loginType": "11"}
        else:
            params = {"mail": self.account, "loginType": "12"}
        params["accountId"] = ACCOUNT_ID
        params["password"] = self.password

        payload = await self._get("user/loginT.do", params)
        if not _is_ok(payload):
            raise ZnddcAuthError(_msg(payload))

        data = payload.get("data") or {}
        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            raise ZnddcAuthError("登录成功但未返回 token")
        self.token = str(token)
        return self.token

    async def _async_ensure_token(self) -> str:
        if self.token:
            return self.token
        async with self._login_lock:
            if not self.token:
                await self.async_login()
        assert self.token is not None
        return self.token

    async def _async_call(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        token = await self._async_ensure_token()
        call_params = dict(params or {})
        call_params["token"] = token

        payload = await self._get(path, call_params)
        if _code(payload) == "-1002" and retry_auth:
            _LOGGER.debug("token 失效，重新登录")
            async with self._login_lock:
                self.token = None
                await self.async_login()
            call_params["token"] = self.token
            payload = await self._get(path, call_params)
        return payload

    # ------------------------------------------------------------------ 业务
    async def async_get_devices(self) -> list[dict[str, Any]]:
        """当前账号下已绑定的车辆列表。"""
        payload = await self._async_call("machineBound/findListByUserId.do")
        if not _is_ok(payload):
            raise ZnddcError(_msg(payload))
        data = payload.get("data")
        if isinstance(data, dict):
            data = data.get("list") or data.get("records") or []
        return [item for item in (data or []) if isinstance(item, dict)]

    async def async_get_status(
        self, machine_no: str, map_type: str = "2"
    ) -> dict[str, Any]:
        payload = await self._async_call(
            "machine/getMachineStatusST.do",
            {"machineNo": machine_no, "mapType": map_type},
        )
        if not _is_ok(payload):
            raise ZnddcError(_msg(payload))
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    async def async_get_address(
        self, lon: float, lat: float, map_type: str = "2"
    ) -> str | None:
        payload = await self._async_call(
            "map/getAdd.do", {"mapType": map_type, "lon": lon, "lat": lat}
        )
        if not _is_ok(payload):
            return None
        data = payload.get("data")
        return str(data) if data else None

    async def async_get_ride_by_date(
        self, machine_no: str, date_stamp_ms: int
    ) -> dict[str, Any]:
        payload = await self._async_call(
            "history/getRideByDateST.do",
            {"machineNo": machine_no, "dateStamp": date_stamp_ms},
        )
        if not _is_ok(payload):
            return {}
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    async def async_get_ride_by_time(
        self, machine_no: str, date_stamp_ms: int
    ) -> list[dict[str, Any]]:
        payload = await self._async_call(
            "history/getRideByTimeST.do",
            {"machineNo": machine_no, "dateStamp": date_stamp_ms},
        )
        if not _is_ok(payload):
            return []
        data = payload.get("data")
        return [item for item in (data or []) if isinstance(item, dict)]

    async def async_get_bms(self, machine_no: str) -> dict[str, Any]:
        """BMS 详情（部分车型无 BMS 时返回空）。"""
        payload = await self._async_call(
            "machine/getBmsInfo.do", {"machineNo": machine_no}
        )
        if not _is_ok(payload):
            return {}
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    async def async_ter_control(self, machine_no: str, cmd: int) -> str:
        """下发控制指令，返回用于轮询回执的 serialNo。"""
        payload = await self._async_call(
            "machine/terControl.do", {"machineNo": machine_no, "type": cmd}
        )
        if not _is_ok(payload):
            raise ZnddcError(_msg(payload))
        data = payload.get("data")
        if isinstance(data, dict):
            serial = data.get("serialNo") or data.get("serial")
        else:
            serial = data
        if not serial:
            raise ZnddcError("指令已发送但未获得回执编号")
        return str(serial)

    async def async_wait_command(self, serial_no: str) -> tuple[bool, str]:
        """轮询指令执行结果。"""
        message = ""
        for attempt in range(CMD_POLL_ATTEMPTS + 1):
            payload = await self._async_call("machine/loop.do", {"serialNo": serial_no})
            data = payload.get("data")
            if _is_ok(payload) and isinstance(data, dict):
                if str(data.get("success")) in ("True", "true", "1"):
                    return True, message
                if data.get("message"):
                    message = str(data.get("message"))
            if attempt < CMD_POLL_ATTEMPTS:
                await asyncio.sleep(CMD_POLL_INTERVAL)
        return False, message

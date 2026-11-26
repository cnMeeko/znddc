"""配置流程：账号密码登录 -> 选择车辆。"""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZnddcApi, ZnddcAuthError, ZnddcCannotConnect, ZnddcError
from .const import (
    CONF_ACCOUNT,
    CONF_ADDRESS_LOOKUP,
    CONF_LOGIN_TYPE,
    CONF_MACHINE_NAME,
    CONF_MACHINE_NO,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_ADDRESS_LOOKUP,
    DEFAULT_LOGIN_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGIN_TYPES,
    LOGIN_TYPE_EMAIL,
    LOGIN_TYPE_PHONE,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


def _machine_label(item: dict[str, Any]) -> str:
    machine_no = str(item.get("machineNo") or "").strip()
    nick = (
        item.get("nickName")
        or item.get("machineName")
        or item.get("machineModel")
        or NAME
    )
    return f"{nick} ({machine_no})" if machine_no else str(nick)


def _machine_name(item: dict[str, Any]) -> str:
    machine_no = str(item.get("machineNo") or "").strip()
    return str(item.get("nickName") or item.get("machineName") or f"电动车 {machine_no}")


class ZnddcConfigFlow(ConfigFlow, domain=DOMAIN):
    """添加账号。"""

    VERSION = 1

    def __init__(self) -> None:
        self._account = ""
        self._password = ""
        self._login_type = DEFAULT_LOGIN_TYPE
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_ACCOUNT].strip()
            password = user_input[CONF_PASSWORD]
            login_type = user_input.get(CONF_LOGIN_TYPE, DEFAULT_LOGIN_TYPE)

            if login_type == LOGIN_TYPE_PHONE and not re.fullmatch(r"1\d{10}", account):
                errors["base"] = "invalid_account"
            elif login_type == LOGIN_TYPE_EMAIL and not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+", account
            ):
                errors["base"] = "invalid_account"
            else:
                session = async_get_clientsession(self.hass)
                api = ZnddcApi(session, account, password, login_type)
                try:
                    devices = await api.async_get_devices()
                except ZnddcAuthError:
                    errors["base"] = "invalid_auth"
                except ZnddcCannotConnect:
                    errors["base"] = "cannot_connect"
                except ZnddcError as err:
                    _LOGGER.warning("获取车辆列表失败: %s", err)
                    errors["base"] = "unknown"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("登录测试异常")
                    errors["base"] = "unknown"
                else:
                    if not devices:
                        errors["base"] = "no_device"
                    elif len(devices) == 1:
                        return await self._async_create(
                            account, password, login_type, devices[0]
                        )
                    else:
                        self._account = account
                        self._password = password
                        self._login_type = login_type
                        self._devices = devices
                        return await self.async_step_select_machine()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOGIN_TYPE, default=DEFAULT_LOGIN_TYPE
                    ): vol.In(LOGIN_TYPES),
                    vol.Required(CONF_ACCOUNT): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"name": NAME},
        )

    async def async_step_select_machine(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            machine_no = user_input[CONF_MACHINE_NO]
            item = next(
                (
                    dev
                    for dev in self._devices
                    if str(dev.get("machineNo")) == machine_no
                ),
                {"machineNo": machine_no},
            )
            return await self._async_create(
                self._account, self._password, self._login_type, item
            )

        options = {
            str(dev.get("machineNo")): _machine_label(dev) for dev in self._devices
        }
        return self.async_show_form(
            step_id="select_machine",
            data_schema=vol.Schema({vol.Required(CONF_MACHINE_NO): vol.In(options)}),
        )

    async def _async_create(
        self,
        account: str,
        password: str,
        login_type: str,
        item: dict[str, Any],
    ) -> FlowResult:
        machine_no = str(item.get("machineNo") or "").strip()
        await self.async_set_unique_id(machine_no)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_machine_name(item),
            data={
                CONF_ACCOUNT: account,
                CONF_PASSWORD: password,
                CONF_LOGIN_TYPE: login_type,
                CONF_MACHINE_NO: machine_no,
                CONF_MACHINE_NAME: _machine_name(item),
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry: ConfigEntry | None = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            login_type = user_input.get(
                CONF_LOGIN_TYPE, entry.data.get(CONF_LOGIN_TYPE, DEFAULT_LOGIN_TYPE)
            )
            api = ZnddcApi(
                session,
                user_input[CONF_ACCOUNT],
                user_input[CONF_PASSWORD],
                login_type,
            )
            try:
                await api.async_login()
            except ZnddcAuthError:
                errors["base"] = "invalid_auth"
            except ZnddcCannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("重新认证异常")
                errors["base"] = "unknown"
            else:
                new_data = dict(entry.data)
                new_data[CONF_ACCOUNT] = user_input[CONF_ACCOUNT].strip()
                new_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                new_data[CONF_LOGIN_TYPE] = login_type
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOGIN_TYPE,
                        default=entry.data.get(CONF_LOGIN_TYPE, DEFAULT_LOGIN_TYPE),
                    ): vol.In(LOGIN_TYPES),
                    vol.Required(
                        CONF_ACCOUNT, default=entry.data.get(CONF_ACCOUNT, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ZnddcOptionsFlow(config_entry)


class ZnddcOptionsFlow(OptionsFlow):
    """轮询间隔与地址反查。"""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_ADDRESS_LOOKUP,
                        default=options.get(
                            CONF_ADDRESS_LOOKUP, DEFAULT_ADDRESS_LOOKUP
                        ),
                    ): bool,
                }
            ),
        )

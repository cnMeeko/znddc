"""集成入口。"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZnddcApi
from .const import (
    API_BASE,
    CONF_ACCOUNT,
    CONF_ADDRESS_LOOKUP,
    CONF_LOGIN_TYPE,
    CONF_MACHINE_NAME,
    CONF_MACHINE_NO,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_ADDRESS_LOOKUP,
    DEFAULT_MAP_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ZnddcCoordinator

ZnddcConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: ZnddcConfigEntry) -> bool:
    """建立一辆车的协调器。"""
    api = ZnddcApi(
        async_get_clientsession(hass),
        entry.data[CONF_ACCOUNT],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_LOGIN_TYPE),
    )
    coordinator = ZnddcCoordinator(
        hass,
        entry,
        api,
        machine_no=entry.data[CONF_MACHINE_NO],
        machine_name=entry.data.get(CONF_MACHINE_NAME, "智能电动车"),
        map_type=DEFAULT_MAP_TYPE,
        address_lookup=entry.options.get(
            CONF_ADDRESS_LOOKUP, DEFAULT_ADDRESS_LOOKUP
        ),
        scan_interval=int(
            entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZnddcConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(
    hass: HomeAssistant, entry: ZnddcConfigEntry
) -> None:
    """修改选项后重新加载。"""
    await hass.config_entries.async_reload(entry.entry_id)


__all__ = ["async_setup_entry", "async_unload_entry", "API_BASE"]

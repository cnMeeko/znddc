"""实体公共基类。"""

from __future__ import annotations

import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ZnddcError
from .const import API_BASE, DOMAIN
from .coordinator import ZnddcCoordinator

_LOGGER = logging.getLogger(__name__)


class ZnddcEntity(CoordinatorEntity[ZnddcCoordinator]):
    """带设备信息的实体基类。"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZnddcCoordinator,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.machine_no}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.machine_no)},
            manufacturer="智能电动车管家",
            name=coordinator.machine_name,
            model=str(coordinator.status.get("machineModel") or "智能电动车"),
            serial_number=coordinator.machine_no,
            configuration_url=API_BASE,
        )

    @property
    def available(self) -> bool:
        return super().available

    async def _async_command(self, action: str) -> None:
        try:
            await self.coordinator.async_send_command(action)
        except ZnddcError as err:
            _LOGGER.warning("执行 %s 失败: %s", action, err)
            raise HomeAssistantError(str(err)) from err

"""Lock platform for the EVO-START integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, device_info, vehicle_name

_LOGGER = logging.getLogger(__name__)

REFRESH_DELAY_SECONDS = 2.5


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EvoStartLock(coordinator, vehicle_id, vehicle_name(coordinator, vehicle_id))
        for vehicle_id in coordinator.get_all_vehicle_ids()
    )


class EvoStartLock(CoordinatorEntity, LockEntity):
    _attr_icon = "mdi:lock"
    _attr_has_entity_name = True
    _attr_translation_key = "central_lock"

    def __init__(self, coordinator, vehicle_id, name):
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"evo_start_{vehicle_id}_vcl_lok"
        self._attr_device_info = device_info(vehicle_id, name)
        self._command_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return super().available and self._vehicle_id in self.coordinator.vehicles_data

    @property
    def is_locked(self) -> bool | None:
        bit = self.coordinator.get_vehicle_flags(self._vehicle_id).get("vcl_lok")
        if bit not in ("0", "1"):
            return None
        return bit == "0"

    async def _run(self, label: str, command) -> None:
        if self._command_lock.locked():
            _LOGGER.info("Ignoring %s for %s: a command is already in progress", label, self._vehicle_id)
            return
        async with self._command_lock:
            if not await command(self._vehicle_id):
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key=f"{label}_failed")
            await asyncio.sleep(REFRESH_DELAY_SECONDS)
            await self.coordinator.async_request_refresh()

    async def async_lock(self, **kwargs: Any) -> None:
        await self._run("lock", self.coordinator.async_remote_lock)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._run("unlock", self.coordinator.async_remote_unlock)

"""Switch platform for the EVO-START integration: engine on/off as one switch."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, device_info, vehicle_name

_LOGGER = logging.getLogger(__name__)

# The module reports the new engine state some time after a command; hold the
# requested state until it does, or until this many seconds have passed.
PENDING_SECONDS = 120
REFRESH_DELAY_SECONDS = 3


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EvoStartEngineSwitch(coordinator, vehicle_id, vehicle_name(coordinator, vehicle_id))
        for vehicle_id in coordinator.get_all_vehicle_ids()
    )


class EvoStartEngineSwitch(CoordinatorEntity, SwitchEntity):
    _attr_icon = "mdi:car-key"
    _attr_has_entity_name = True
    _attr_translation_key = "remote_start"

    def __init__(self, coordinator, vehicle_id, name):
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"evo_start_{vehicle_id}_engine_switch"
        self._attr_device_info = device_info(vehicle_id, name)
        self._command_lock = asyncio.Lock()
        self._pending: bool | None = None
        self._pending_until = 0.0

    def _engine_on(self) -> bool | None:
        flag = self.coordinator.get_vehicle_flags(self._vehicle_id).get("vcl_eng")
        return None if flag not in ("0", "1") else flag == "1"

    @property
    def available(self) -> bool:
        return super().available and self._vehicle_id in self.coordinator.vehicles_data

    @property
    def is_on(self) -> bool | None:
        if self._pending is not None and time.monotonic() < self._pending_until:
            return self._pending
        return self._engine_on()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"engine_reported_on": self._engine_on(), "command_pending": self._pending is not None}

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending is not None and (
            self._engine_on() == self._pending or time.monotonic() >= self._pending_until
        ):
            self._pending = None
        super()._handle_coordinator_update()

    async def _send(self, turn_on: bool) -> None:
        if self._command_lock.locked():
            _LOGGER.info("Ignoring engine command for %s: a command is already in progress", self._vehicle_id)
            return
        if self._engine_on() is turn_on and self._pending is None:
            return
        async with self._command_lock:
            flags = self.coordinator.get_vehicle_flags(self._vehicle_id)
            if turn_on and flags.get("dor_frn") == "1":
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="hood_open")
            command = self.coordinator.async_remote_start if turn_on else self.coordinator.async_remote_stop
            if not await command(self._vehicle_id):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="start_failed" if turn_on else "stop_failed"
                )
            self._pending = turn_on
            self._pending_until = time.monotonic() + PENDING_SECONDS
            self.async_write_ha_state()
            await asyncio.sleep(REFRESH_DELAY_SECONDS)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(False)

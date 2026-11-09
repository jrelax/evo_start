"""Button platform for the EVO-START integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, device_info, vehicle_name

_LOGGER = logging.getLogger(__name__)

REFRESH_DELAY_SECONDS = 3

BUTTON_TYPES = {
    "remote_start": {"icon": "mdi:car-key", "action": "start"},
    "remote_stop": {"icon": "mdi:car-off", "action": "stop"},
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EvoStartButton(coordinator, vehicle_id, button_id, cfg, vehicle_name(coordinator, vehicle_id))
        for vehicle_id in coordinator.get_all_vehicle_ids()
        for button_id, cfg in BUTTON_TYPES.items()
    )


class EvoStartButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, vehicle_id, button_id, button_cfg, name):
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._action = button_cfg["action"]
        self._attr_translation_key = button_id
        self._attr_unique_id = f"evo_start_{vehicle_id}_{button_id}"
        self._attr_icon = button_cfg["icon"]
        self._attr_device_info = device_info(vehicle_id, name)
        self._command_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        """Show Start only while the engine is off and Stop only while it is on."""
        engine = self.coordinator.get_vehicle_flags(self._vehicle_id).get("vcl_eng")
        if engine is None:
            return True
        engine_on = str(engine) == "1"
        return not engine_on if self._action == "start" else engine_on

    async def async_press(self) -> None:
        if self._command_lock.locked():
            _LOGGER.info("Ignoring %s for %s: a command is already in progress", self._action, self._vehicle_id)
            return
        async with self._command_lock:
            flags = self.coordinator.get_vehicle_flags(self._vehicle_id)
            if self._action == "start" and flags.get("dor_frn") == "1":
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="hood_open")

            if self._action == "start":
                ok = await self.coordinator.async_remote_start(self._vehicle_id)
            else:
                ok = await self.coordinator.async_remote_stop(self._vehicle_id)
            if not ok:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key=f"{self._action}_failed")

            await asyncio.sleep(REFRESH_DELAY_SECONDS)
            await self.coordinator.async_request_refresh()

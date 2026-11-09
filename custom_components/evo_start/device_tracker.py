"""Device tracker platform for the EVO-START integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, device_info, vehicle_name

FLAG_LABELS = {
    "lig_smal": "Small lights",
    "lig_big": "Headlights",
    "dor_frn": "Hood",
    "dor_rb": "Right back door",
    "dor_rf": "Right front door",
    "dor_lb": "Left rear door",
    "dor_lf": "Left front door",
    "vcl_on2": "Relay 2",
    "vcl_on1": "Relay 1",
    "wnd_top": "Sunroof",
    "wnd_rb": "Right back window",
    "wnd_rf": "Right front window",
    "wnd_lb": "Left rear window",
    "vcl_anit": "Anti-theft",
    "vcl_repair": "Car repair",
    "vcl_air": "Air Conditioner",
    "brk_fot": "Foot brake",
    "brk_han": "Handbrake",
    "gps_cls": "GPS short circuit",
    "gps_opn": "GPS open circuit",
    "gps_loc": "GPS position",
    "gps_power": "GPS power",
    "alm_tpms": "Tire pressure",
    "alm_bat": "Low voltage",
    "alm_belt_m": "Seat belt",
    "alm_acc": "Illegal ignition",
    "alm_dor": "Illegal door opening",
    "alm_vib": "Vibration",
    "alm_ultrasonic": "Ultrasound",
    "alm_dor_open": "Door not closed after locking",
}

ALERT_FLAGS = {
    "alm_tpms", "alm_bat", "alm_belt_m", "alm_acc",
    "alm_dor", "alm_vib", "alm_ultrasonic", "alm_dor_open",
}


def _coordinate(raw: Any) -> float | None:
    """Parse a coordinate; treat 0.0 (no GPS fix) as unknown."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return None if abs(value) < 0.0001 else value


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EvoStartDeviceTracker(coordinator, vehicle_id, vehicle_name(coordinator, vehicle_id))
        for vehicle_id in coordinator.get_all_vehicle_ids()
    )


class EvoStartDeviceTracker(CoordinatorEntity, TrackerEntity):
    _attr_icon = "mdi:car"

    def __init__(self, coordinator, vehicle_id, name):
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"evo_start_vehicle_tracker_{vehicle_id}"
        self._attr_name = f"EVO-START {name}"
        self._attr_device_info = device_info(vehicle_id, name)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _lloc(self) -> dict[str, Any]:
        return (self.coordinator.get_vehicle_data(self._vehicle_id) or {}).get("lloc", {})

    @property
    def latitude(self) -> float | None:
        return _coordinate(self._lloc().get("lat"))

    @property
    def longitude(self) -> float | None:
        return _coordinate(self._lloc().get("lng"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        flags = self.coordinator.get_vehicle_flags(self._vehicle_id)
        if not flags:
            return {}
        attributes: dict[str, Any] = {}
        for key, value in flags.items():
            if value not in ("0", "1"):
                continue
            if key in ALERT_FLAGS:
                state = "⚠️ alert" if value == "1" else "✅ normal"
            else:
                state = "🔴 open" if value == "1" else "🟢 close"
            attributes[FLAG_LABELS.get(key, key)] = state
        lloc = self._lloc()
        attributes["speed_kmh"] = lloc.get("speed")
        try:
            attributes["gps_time"] = dt_util.utc_from_timestamp(int(lloc["tdt"])).isoformat()
        except (KeyError, TypeError, ValueError):
            attributes["gps_time"] = None
        try:
            attributes["heading"] = int(lloc["dir"])
        except (KeyError, TypeError, ValueError):
            attributes["heading"] = None
        return attributes

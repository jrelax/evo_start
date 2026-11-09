"""Sensor platform for the EVO-START integration."""
from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, device_info, vehicle_name

_LOGGER = logging.getLogger(__name__)


def _open_closed(x: Any) -> str:
    return "🔓 Open" if str(x) == "1" else ("🔒 Closed" if str(x) == "0" else "❓ Unknown")


def _timestamp(x: Any):
    return dt_util.utc_from_timestamp(int(x)) if int(x) > 0 else None


def _text(x: Any) -> str:
    return str(x)[:255]


def _sensor(
    name: str,
    icon: str,
    key: str,
    source: str,
    transform: Callable[[Any], Any],
    unit: str | None = None,
    device_class: SensorDeviceClass | None = None,
    state_class: SensorStateClass | None = None,
    precision: int | None = None,
) -> dict[str, Any]:
    return {
        "name": name, "icon": icon, "key": key, "source": source, "transform": transform,
        "unit": unit, "device_class": device_class, "state_class": state_class, "precision": precision,
    }


SENSOR_TYPES: dict[str, dict[str, Any]] = {
    "battery": _sensor(
        "Battery Voltage", "mdi:car-battery", "volt", "lloc", lambda x: round(int(x) / 10, 1),
        "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT,
    ),
    "temperature": _sensor(
        "Vehicle Temperature", "mdi:thermometer", "temp", "lloc", float,
        "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, 0,
    ),
    "mileage": _sensor(
        "Vehicle Mileage", "mdi:counter", "mileage", "lloc", int,
        "km", SensorDeviceClass.DISTANCE, SensorStateClass.TOTAL_INCREASING, 0,
    ),
    "speed": _sensor(
        "Vehicle Speed", "mdi:speedometer", "speed", "lloc", int,
        "km/h", SensorDeviceClass.SPEED, SensorStateClass.MEASUREMENT, 0,
    ),
    "gps_online": _sensor(
        "GPS Online", "mdi:crosshairs-gps", "gpsol", "lloc",
        lambda x: "📍 Connected" if x == "1" else "❌ Offline",
    ),
    "gsm_status": _sensor(
        "GSM Signal", "mdi:signal", "gsmol", "lloc",
        lambda x: "📶 OK" if x == "1" else "❌ No Signal",
    ),
    "engine": _sensor(
        "Engine Status", "mdi:engine", "vcl_eng", "flags",
        lambda x: "🟢 On" if str(x) == "1" else ("🔴 Off" if str(x) == "0" else "❓ Unknown"),
    ),
    "trunk_status": _sensor("Trunk Status", "mdi:car-back", "dor_trk", "flags", _open_closed),
    "door_lock_status": _sensor(
        "Door Lock Status", "mdi:lock", "vcl_lok", "flags",
        lambda x: "🔓 Unlocked" if str(x) == "1" else ("🔒 Locked" if str(x) == "0" else "❓ Unknown"),
    ),
    "hood_status": _sensor("Hood Status", "mdi:car-hood", "dor_frn", "flags", _open_closed),
    "left_front_door": _sensor("Left Front Door", "mdi:car-door", "dor_lf", "flags", _open_closed),
    "right_front_door": _sensor("Right Front Door", "mdi:car-door", "dor_rf", "flags", _open_closed),
    "left_rear_door": _sensor("Left Rear Door", "mdi:car-door", "dor_lb", "flags", _open_closed),
    "right_rear_door": _sensor("Right Rear Door", "mdi:car-door", "dor_rb", "flags", _open_closed),
    "trip_odometer": _sensor(
        "Trip Odometer", "mdi:counter", "odometer_km", "trips", float,
        "km", SensorDeviceClass.DISTANCE, SensorStateClass.TOTAL_INCREASING, 1,
    ),
    "distance_today": _sensor(
        "Distance Today", "mdi:map-marker-distance", "distance_today_km", "trips", float,
        "km", SensorDeviceClass.DISTANCE, SensorStateClass.TOTAL_INCREASING, 1,
    ),
    "distance_this_month": _sensor(
        "Distance This Month", "mdi:calendar-month-outline", "distance_month_km", "trips", float,
        "km", SensorDeviceClass.DISTANCE, SensorStateClass.TOTAL_INCREASING, 1,
    ),
    "trips_today": _sensor(
        "Trips Today", "mdi:car-clock", "trips_today", "trips", int,
        None, None, SensorStateClass.TOTAL_INCREASING,
    ),
    "last_trip_distance": _sensor(
        "Last Trip Distance", "mdi:map-marker-path", "last_trip_km", "trips", float,
        "km", SensorDeviceClass.DISTANCE, None, 1,
    ),
    "last_trip_max_speed": _sensor(
        "Last Trip Max Speed", "mdi:speedometer", "last_trip_max_speed", "trips", int,
        "km/h", SensorDeviceClass.SPEED, None, 0,
    ),
    "last_trip_duration": _sensor(
        "Last Trip Duration", "mdi:timer-outline", "last_trip_duration_min", "trips", int,
        "min", SensorDeviceClass.DURATION, None, 0,
    ),
    "last_trip_from": _sensor("Last Trip From", "mdi:map-marker-outline", "last_trip_from", "trips", _text),
    "last_trip_to": _sensor("Last Trip To", "mdi:map-marker-check-outline", "last_trip_to", "trips", _text),
    "last_report": _sensor(
        "Last Report", "mdi:clock-check-outline", "tdt", "lloc", _timestamp, None, SensorDeviceClass.TIMESTAMP,
    ),
    "subscription_expires": _sensor(
        "Subscription Expires", "mdi:calendar-alert", "expire_date", "vehicle", _timestamp,
        None, SensorDeviceClass.TIMESTAMP,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        EvoStartSensor(coordinator, vehicle_id, sensor_id, cfg, vehicle_name(coordinator, vehicle_id))
        for vehicle_id in coordinator.get_all_vehicle_ids()
        for sensor_id, cfg in SENSOR_TYPES.items()
    )


class EvoStartSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, vehicle_id, sensor_id, sensor_cfg, name):
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._sensor_id = sensor_id
        self._cfg = sensor_cfg
        self._attr_name = f"EVO-START {name} {sensor_cfg['name']}"
        self._attr_unique_id = f"evo_start_{vehicle_id}_{sensor_id}"
        self._attr_icon = sensor_cfg["icon"]
        self._attr_native_unit_of_measurement = sensor_cfg["unit"]
        self._attr_device_class = sensor_cfg["device_class"]
        self._attr_state_class = sensor_cfg["state_class"]
        if sensor_cfg["precision"] is not None:
            self._attr_suggested_display_precision = sensor_cfg["precision"]
        self._attr_device_info = device_info(vehicle_id, name)

    @property
    def native_value(self):
        source = self._cfg["source"]
        key = self._cfg["key"]
        if source == "trips":
            raw = self.coordinator.get_vehicle_trips(self._vehicle_id).get(key)
        else:
            vehicle_data = self.coordinator.get_vehicle_data(self._vehicle_id)
            vehicle_flags = self.coordinator.get_vehicle_flags(self._vehicle_id)
            if not vehicle_data or not vehicle_flags:
                return None
            if source == "flags":
                raw = vehicle_flags.get(key)
            elif source == "vehicle":
                raw = vehicle_data.get(key)
            else:
                raw = vehicle_data["lloc"].get(key)
        try:
            return self._cfg["transform"](raw)
        except (TypeError, ValueError) as err:
            _LOGGER.debug("Cannot parse %s for %s: %s", key, self._vehicle_id, err)
            return None

"""The EVO-START integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import EvoStartCoordinator

# 2.0.0 (French) unique ID suffixes -> v1/English suffixes
V2_UNIQUE_ID_SUFFIXES = {
    "_verrouillage_central": "_vcl_lok",
    "_satellite_gps": "_gps_online",
    "_gsm_signal": "_gsm_status",
    "_distance_aujourdhui": "_distance_today",
    "_distance_ce_mois": "_distance_this_month",
    "_dernier_trajet_distance": "_last_trip_distance",
    "_dernier_trajet_vitesse_max": "_last_trip_max_speed",
}
V2_TRACKER_PREFIX = "evo_start_traceur_"

# Sensors registered before they had a device class: unique ID suffix -> (device class, native unit)
UNIT_SYSTEM_SENSORS = {
    "_mileage": (SensorDeviceClass.DISTANCE, "km"),
    "_speed": (SensorDeviceClass.SPEED, "km/h"),
    "_temperature": (SensorDeviceClass.TEMPERATURE, "°C"),
}

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.LOCK,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


def _v1_unique_id(uid: str) -> str | None:
    if uid.startswith(V2_TRACKER_PREFIX):
        return "evo_start_vehicle_tracker_" + uid[len(V2_TRACKER_PREFIX):]
    for old, new in V2_UNIQUE_ID_SUFFIXES.items():
        if uid.startswith("evo_start_") and uid.endswith(old):
            return uid[: -len(old)] + new
    return None


@callback
def _migrate_v2_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename 2.0.0 unique IDs; drop a 2.0.0 entity whose v1 twin is still registered."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        new_uid = _v1_unique_id(entity.unique_id)
        if new_uid is None:
            continue
        if registry.async_get_entity_id(entity.domain, DOMAIN, new_uid):
            registry.async_remove(entity.entity_id)
        else:
            registry.async_update_entity(entity.entity_id, new_unique_id=new_uid)


@callback
def _adopt_unit_system(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Give pre-3.0.2 distance and speed sensors the display unit of the HA unit system.

    Home Assistant applies the unit system only when an entity is first registered.
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        match = next((v for k, v in UNIT_SYSTEM_SENSORS.items() if entity.unique_id.endswith(k)), None)
        if entity.domain != "sensor" or match is None:
            continue
        options = entity.options.get("sensor", {})
        device_class, native_unit = match
        suggested = entity.options.get("sensor.private", {}).get("suggested_unit_of_measurement")
        if options.get("unit_of_measurement") or (suggested and suggested != native_unit):
            continue
        if device_class == SensorDeviceClass.TEMPERATURE:
            unit = hass.config.units.temperature_unit
        else:
            unit = hass.config.units.get_converted_unit(device_class, native_unit)
        if unit and unit != native_unit:
            registry.async_update_entity_options(
                entity.entity_id, "sensor", {**options, "unit_of_measurement": unit}
            )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version == 1 and entry.minor_version < 3:
        _adopt_unit_system(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=3)
    return entry.version == 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _migrate_v2_entities(hass, entry)
    coordinator = EvoStartCoordinator(
        hass, entry, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    await coordinator.async_load_odometer()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok

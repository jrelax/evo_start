"""The EVO-START integration."""
from __future__ import annotations

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

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.LOCK,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


@callback
def _migrate_v2_unique_id(entity: er.RegistryEntry) -> dict | None:
    uid = entity.unique_id
    if uid.startswith(V2_TRACKER_PREFIX):
        return {"new_unique_id": "evo_start_vehicle_tracker_" + uid[len(V2_TRACKER_PREFIX):]}
    for old, new in V2_UNIQUE_ID_SUFFIXES.items():
        if uid.startswith("evo_start_") and uid.endswith(old):
            return {"new_unique_id": uid[: -len(old)] + new}
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await er.async_migrate_entries(hass, entry.entry_id, _migrate_v2_unique_id)
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

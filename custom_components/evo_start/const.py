"""Constants for the EVO-START integration."""
DOMAIN = "evo_start"
MANUFACTURER = "Fortin"
MODEL = "EVO-START"


def device_info(vehicle_id: str, vehicle_name: str) -> dict:
    return {
        "identifiers": {(DOMAIN, f"evo_start_vehicle_{vehicle_id}")},
        "name": vehicle_name,
        "manufacturer": MANUFACTURER,
        "model": MODEL,
    }


def vehicle_name(coordinator, vehicle_id: str) -> str:
    data = coordinator.get_vehicle_data(vehicle_id) or {}
    return data.get("dev_name") or (data.get("carinfo") or {}).get("cname") or f"Vehicle {vehicle_id}"

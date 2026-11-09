# EVO-START for Home Assistant

Custom integration for vehicles with a **Fortin EVO-START** module. Uses the EVO-START cloud API (`shk.topm2m.net`).

Entity IDs, unique IDs and state values match the original English v1 release, so it is a drop-in upgrade.

## Entities (per vehicle)

| Platform | Entity | Notes |
|---|---|---|
| sensor | Battery Voltage, Vehicle Temperature, Vehicle Mileage, Vehicle Speed | from the last location report |
| sensor | GPS Online, GSM Signal, Engine Status, Door Lock Status, Hood/Trunk/door status | v1 state strings (`🔒 Locked`, `🟢 On`, …) |
| sensor | Trip Odometer, Distance Today, Distance This Month, Trips Today, Last Trip Distance, Last Trip Max Speed | from the trip history; Trip Odometer starts at the current month's trips and is stored in `.storage` |
| lock | Central Lock | lock / unlock |
| button | Remote Start, Remote Stop | Start is refused while the hood is open |
| device_tracker | GPS position | flags as attributes; (0, 0) fixes are ignored |

## Account

The EVO-START server allows one **web** session and one **mobile** session per account. A new login ends the earlier session of the same kind. The Android and iOS apps share the mobile session.

This integration logs in as `web`, so it does not end your phone app's session. 2.0.0 logged in as Android and ended the iPhone app's session. A separate EVO-START user for Home Assistant also avoids any conflict with the web portal.

## Installation

### Marketplace (Home Assistant 2026.11 and later)

The Marketplace replaces HACS. Its catalog lists the upstream `CLARENNE-Q/evo_start` (2.0.0, French). Add this repository as a custom repository to install this version.

1. If EVO-START is installed from the catalog, uninstall it in the **Marketplace**. Your config entry and entities stay.
2. Open **Marketplace** in the sidebar. Connect it to GitHub if it asks: custom repositories need the connection.
3. Add the custom repository `https://github.com/jrelax/evo_start`, type **Integration**.
4. Open **EVO-START** and install it.
5. Restart Home Assistant.
6. Add **EVO-START** under **Settings › Devices & Services**, or enable your existing entry.

The Marketplace installs the newest release, or the default branch when the repository has no releases.

### Manual

1. Copy `custom_components/evo_start` to `/config/custom_components/`.
2. Restart Home Assistant.
3. Add **EVO-START** under **Settings › Devices & Services**.

### Upgrading from 2.0.0

At setup, the integration changes the 2.0.0 unique IDs to the English ones. Your entity IDs and history stay. If both v1 and 2.0.0 entities are registered, it removes the 2.0.0 duplicates. It imports the trip odometer from `evo_start_odometer.json`.

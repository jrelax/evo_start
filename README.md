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

Copy `custom_components/evo_start` to `/config/custom_components/`, restart, then add **EVO-START** under Settings › Devices & Services.

# EVO-START V1 for Home Assistant

Home Assistant integration for vehicles with a **Fortin EVO-START V1** remote starter: the system that uses the EVO-START mobile app and the `shk.topm2m.net` cloud.

This is a fork of [CLARENNE-Q/evo_start](https://github.com/CLARENNE-Q/evo_start). Version 3.0.0 is in English and keeps the entity IDs of the original English release. It also keeps the useful parts of the upstream 2.0.0 rewrite. It is not affiliated with Fortin.

## Features

Each vehicle on the account becomes one device with these entities:

| Platform | Entities | Notes |
|---|---|---|
| sensor | Battery Voltage, Vehicle Temperature, Vehicle Mileage, Vehicle Speed | From the last location report. Mileage is the value the module reports. |
| sensor | Engine Status, Door Lock Status, Hood Status, Trunk Status, 4 door sensors, GPS Online, GSM Signal | Text states, for example `🔒 Locked`, `🟢 On`, `🔓 Open` |
| sensor | Trip Odometer, Distance Today, Distance This Month, Trips Today, Last Trip Distance, Last Trip Max Speed | From the trip history. Trip Odometer starts with the current month's trips. |
| lock | Central Lock | Lock and unlock |
| button | Remote Start, Remote Stop | Start shows only when the engine is off, Stop only when it is on. Start is refused while the hood is open. |
| device_tracker | Vehicle position | Status flags as attributes. A (0, 0) position is ignored. |

The integration polls the cloud every 60 seconds. The car name comes from the name set in the EVO-START app.

Distance, speed and temperature follow the Home Assistant unit system: mi, mph and °F on US customary, km, km/h and °C on metric. To change one sensor, set its unit in the entity settings.

There is no fuel economy (MPG) sensor. The module's trip fuel value is a fixed fraction of the trip distance, the same for every vehicle, so it is an estimate, not a measurement.

## Account and sessions

The EVO-START server allows one **web** session and one **mobile** session per account. A new login ends the earlier session of the same kind. The Android and iOS apps share the mobile session.

This integration logs in as `web`, so your phone app stays logged in. A separate EVO-START user for Home Assistant also keeps it apart from the web portal.

## Installation

### Marketplace (Home Assistant 2026.11 and later)

The Marketplace replaces HACS. Its catalog lists the upstream repository, not this fork. Add this fork as a custom repository.

1. If EVO-START is installed from the catalog, uninstall it in the **Marketplace**. Your config entry and entities stay.
2. Open **Marketplace** in the sidebar. Connect it to GitHub if it asks: custom repositories need the connection.
3. Add the custom repository `https://github.com/jrelax/evo_start`, type **Integration**.
4. Open **EVO-START** and install it.
5. Restart Home Assistant.
6. Add **EVO-START** under **Settings › Devices & Services**, or enable your existing entry. Enter your EVO-START email and password.

### Manual

1. Copy `custom_components/evo_start` to `/config/custom_components/`.
2. Restart Home Assistant.
3. Add **EVO-START** under **Settings › Devices & Services**.

## Upgrading

- **From the original English release:** a drop-in upgrade. Unique IDs, entity IDs and states do not change. The trip sensors are new.
- **From upstream 2.0.0 (French):** at setup, the integration changes the 2.0.0 unique IDs to the English ones, so entity IDs and history stay. If both sets of entities are registered, it removes the 2.0.0 duplicates. It imports the trip odometer from `evo_start_odometer.json`.

## Changes from upstream 2.0.0

- English names, states and messages again, with the original unique IDs.
- **Door Lock Status** is correct. 2.0.0 shows a locked car as unlocked.
- **Vehicle Mileage** is the module's odometer again. 2.0.0 replaced it with a trip counter that started at 0.
- Logs in as `web`, not as an Android phone. The 2.0.0 Android login ended the session of the phone app, iPhone included.
- Car names come from the app. Before, every car was named `Vehicle <id>`.
- Kept from 2.0.0: TLS certificate checks, session reuse, request timeouts, the login check during setup, the hood interlock and the trip sensors.

## Credits

Original integration by [CLARENNE-Q](https://github.com/CLARENNE-Q). Multi-vehicle support and the 2.0.0 trip telemetry came from contributors to the upstream repository.

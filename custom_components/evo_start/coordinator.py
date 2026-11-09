"""Data coordinator for the EVO-START integration."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

API_URL = "https://shk.topm2m.net/webinv/do&req_seq={seq}"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_TIMEOUT = ClientTimeout(total=15)
RET_OK = "000000"

CODE_LOGIN = "100010"
CODE_VEHICLES = "20101010"
CODE_TRIPS = "901010"
CODE_LOCK = "303110"
CODE_UNLOCK = "303115"
CODE_START = "303120"
CODE_STOP = "303125"

STORAGE_KEY = f"{DOMAIN}_odometer"
STORAGE_VERSION = 1
LEGACY_ODOMETER_FILE = "evo_start_odometer.json"
TRIP_LOOKBACK_MAX = timedelta(days=31)

BIT_FIELDS = {
    "lig_smal": 1, "lig_big": 2, "dor_frn": 3, "dor_trk": 4, "dor_rb": 5,
    "dor_rf": 6, "dor_lb": 7, "dor_lf": 8, "vcl_on2": 9, "vcl_on1": 10,
    "wnd_top": 12, "wnd_rb": 13, "wnd_rf": 14, "wnd_lb": 15, "vcl_anit": 16,
    "vcl_repair": 18, "vcl_lok": 19, "vcl_eng": 20, "vcl_acc": 21, "vcl_air": 22,
    "brk_fot": 23, "brk_han": 24, "gps_cls": 29, "gps_opn": 30, "gps_loc": 31,
    "gps_power": 32, "alm_tpms": 33, "alm_bat": 34, "alm_belt_m": 35,
    "alm_acc": 36, "alm_dor": 37, "alm_vib": 38, "alm_ultrasonic": 39,
    "alm_dor_open": 40,
}

# After inversion, vcl_lok "1" = unlocked and "0" = locked, as in v1.
INVERTED_FLAGS = {"vcl_lok"}


class AuthenticationError(Exception):
    """The EVO-START server rejected the credentials."""


class EvoStartCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the EVO-START cloud API and sends vehicle commands."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry | None, email: str, password: str
    ) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=60)
        )
        self._session = async_get_clientsession(hass)
        self.email = email.strip()
        self._password_sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        self.uid: str | None = None
        self.ssk: str | None = None
        self.vehicles_data: dict[str, Any] = {}
        self.vehicles_flags: dict[str, Any] = {}
        self.vehicles_trips: dict[str, Any] = {}
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}" if entry else STORAGE_KEY
        )
        self._odometer: dict[str, dict[str, Any]] = {}

    def _build_payload(self, code: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        now = datetime.now()
        uid = self.uid or "00000000"
        return {
            "sys_head": {
                "code": code,
                "consumer_ssn": uid + str(int(now.timestamp())),
                "trans_date": now.strftime("%Y%m%d"),
                "trans_time": now.strftime("%H%M%S"),
                "build_make": "Home Assistant",
                "build_model": "Evo_Start Vehicle",
                "build_release": "1.0",
            },
            "app_head": {
                "ssk": self.ssk,
                "uid": uid,
                "chnl": "web",
                "lang": "en",
            },
            "body": body or {},
        }

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = API_URL.format(seq=int(datetime.now().timestamp() * 1000))
        try:
            async with self._session.post(
                url, headers=HEADERS, data=json.dumps(payload), timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"HTTP error {response.status}")
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed(f"Network error: {err}") from err

    @staticmethod
    def _ret_code(response: dict[str, Any]) -> str | None:
        return response.get("sys_head", {}).get("ret_code")

    async def login(self) -> None:
        self.uid = None
        self.ssk = None
        response = await self._post(
            self._build_payload(CODE_LOGIN, {"name": self.email, "paswd": self._password_sha1})
        )
        if self._ret_code(response) != RET_OK:
            raise AuthenticationError(f"Login rejected (ret_code {self._ret_code(response)})")
        body = response.get("body", {})
        self.uid = body.get("uid")
        self.ssk = body.get("ssk")

    async def _request(self, code: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a read request; log in again once if the session was rejected."""
        if not self.ssk:
            await self.login()
        response = await self._post(self._build_payload(code, body))
        if self._ret_code(response) != RET_OK:
            await self.login()
            response = await self._post(self._build_payload(code, body))
        return response

    async def async_load_odometer(self) -> None:
        stored = await self._store.async_load()
        if stored is None:
            stored = await self.hass.async_add_executor_job(self._read_legacy_odometer)
            if stored:
                await self._store.async_save(stored)
        self._odometer = stored or {}

    def _read_legacy_odometer(self) -> dict[str, dict[str, Any]]:
        path = self.hass.config.path(LEGACY_ODOMETER_FILE)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as file:
                legacy = json.load(file)
        except (OSError, ValueError) as err:
            _LOGGER.warning("Cannot read %s: %s", path, err)
            return {}
        _LOGGER.info("Imported trip odometer from %s", path)
        return {
            tid: {
                "odometer_km": float(row.get("odometre_km", 0.0)),
                "last_trip_end_ts": int(row.get("dernier_ts_traite", 0)),
            }
            for tid, row in legacy.items()
        }

    async def _fetch_trips(self, tid: str) -> dict[str, Any]:
        now = dt_util.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        state = self._odometer.get(tid, {"odometer_km": 0.0, "last_trip_end_ts": 0})
        last_ts = int(state["last_trip_end_ts"])

        query_start = month_start
        if last_ts and dt_util.utc_from_timestamp(last_ts) < month_start:
            query_start = max(dt_util.utc_from_timestamp(last_ts), month_start - TRIP_LOOKBACK_MAX)

        response = await self._request(
            CODE_TRIPS,
            {
                "mode": "10",
                "bgdt": str(int(query_start.timestamp())),
                "eddt": str(int(now.timestamp())),
                "tid": tid,
            },
        )
        if self._ret_code(response) != RET_OK:
            raise UpdateFailed(f"Trip query rejected (ret_code {self._ret_code(response)})")
        rows = sorted(response.get("body", {}).get("rows", []), key=lambda r: int(r.get("edtdt", 0)))

        odometer_km = float(state["odometer_km"])
        new_last_ts = last_ts
        for row in rows:
            end_ts = int(row.get("edtdt", 0))
            if end_ts > last_ts:
                odometer_km += max(int(row.get("trip", 0)), 0) / 1000.0
                new_last_ts = max(new_last_ts, end_ts)

        if new_last_ts != last_ts:
            self._odometer[tid] = {"odometer_km": round(odometer_km, 2), "last_trip_end_ts": new_last_ts}
            await self._store.async_save(self._odometer)

        month_rows = [r for r in rows if int(r.get("bgtdt", 0)) >= month_start.timestamp()]
        today_rows = [r for r in month_rows if int(r.get("bgtdt", 0)) >= day_start.timestamp()]
        last = rows[-1] if rows else {}
        return {
            "odometer_km": round(odometer_km, 1),
            "distance_today_km": round(sum(int(r.get("trip", 0)) for r in today_rows) / 1000.0, 2),
            "distance_month_km": round(sum(int(r.get("trip", 0)) for r in month_rows) / 1000.0, 1),
            "trips_today": len(today_rows),
            "last_trip_km": round(int(last["trip"]) / 1000.0, 2) if "trip" in last else None,
            "last_trip_max_speed": int(last["top"]) if "top" in last else None,
        }

    def _fallback_trips(self, tid: str) -> dict[str, Any]:
        if tid in self.vehicles_trips:
            return self.vehicles_trips[tid]
        stored = self._odometer.get(tid)
        return {"odometer_km": round(stored["odometer_km"], 1)} if stored else {}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            response = await self._request(CODE_VEHICLES)
        except AuthenticationError as err:
            raise UpdateFailed(str(err)) from err
        if self._ret_code(response) != RET_OK:
            raise UpdateFailed(f"Vehicle query rejected (ret_code {self._ret_code(response)})")

        vehicles: dict[str, Any] = {}
        flags: dict[str, Any] = {}
        trips: dict[str, Any] = {}
        for row in response.get("body", {}).get("rows", []):
            tid = row.get("tid")
            if not tid:
                continue
            lloc = row.get("lloc") or {}
            vehicles[tid] = {"lloc": lloc, "carinfo": row.get("carinfo", {}), "tid": tid}
            flags[tid] = self.decode_vst(lloc.get("vst", ""))
            try:
                trips[tid] = await self._fetch_trips(tid)
            except (UpdateFailed, AuthenticationError, ValueError, TypeError, KeyError) as err:
                _LOGGER.debug("Trip data unavailable for %s: %s", tid, err)
                trips[tid] = self._fallback_trips(tid)

        self.vehicles_data = vehicles
        self.vehicles_flags = flags
        self.vehicles_trips = trips
        return {"vehicles": vehicles, "flags": flags, "trips": trips}

    @staticmethod
    def decode_vst(vst: str) -> dict[str, str | None]:
        if not vst:
            return {}
        try:
            bits = bin(int("1" + vst[:10], 16))[2:].zfill(41)
        except ValueError:
            _LOGGER.debug("Invalid VST value: %s", vst)
            return {}
        flags: dict[str, str | None] = {}
        for key, idx in BIT_FIELDS.items():
            if idx >= len(bits):
                flags[key] = None
                continue
            bit = bits[idx]
            if key in INVERTED_FLAGS:
                bit = "0" if bit == "1" else "1"
            flags[key] = bit
        return flags

    def get_vehicle_data(self, vehicle_id: str) -> dict[str, Any] | None:
        return self.vehicles_data.get(vehicle_id)

    def get_vehicle_flags(self, vehicle_id: str) -> dict[str, Any]:
        return self.vehicles_flags.get(vehicle_id, {})

    def get_vehicle_trips(self, vehicle_id: str) -> dict[str, Any]:
        return self.vehicles_trips.get(vehicle_id, {})

    def get_all_vehicle_ids(self) -> list[str]:
        return list(self.vehicles_data.keys())

    async def _send_command(self, code: str, vehicle_id: str, label: str) -> bool:
        if vehicle_id not in self.vehicles_data:
            _LOGGER.error("Vehicle %s not found", vehicle_id)
            return False
        try:
            response = await self._request(code, {"tid": vehicle_id})
        except (UpdateFailed, AuthenticationError) as err:
            _LOGGER.error("Remote %s failed for vehicle %s: %s", label, vehicle_id, err)
            return False
        if self._ret_code(response) == RET_OK:
            _LOGGER.info("Remote %s sent to vehicle %s", label, vehicle_id)
            return True
        _LOGGER.error(
            "Remote %s rejected for vehicle %s (ret_code %s)", label, vehicle_id, self._ret_code(response)
        )
        return False

    async def async_remote_start(self, vehicle_id: str) -> bool:
        return await self._send_command(CODE_START, vehicle_id, "start")

    async def async_remote_stop(self, vehicle_id: str) -> bool:
        return await self._send_command(CODE_STOP, vehicle_id, "stop")

    async def async_remote_lock(self, vehicle_id: str) -> bool:
        return await self._send_command(CODE_LOCK, vehicle_id, "lock")

    async def async_remote_unlock(self, vehicle_id: str) -> bool:
        return await self._send_command(CODE_UNLOCK, vehicle_id, "unlock")

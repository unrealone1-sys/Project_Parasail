"""ParaSail ingestion layer (development phase P2).

Every provider is wrapped behind a common interface with:
  * a freshness contract (max age before data is considered stale),
  * a disk cache (so the offline contingency has something to serve),
  * a normalised output on the common spatiotemporal grid.

Policy: when a live endpoint is unavailable, serve the most recent cached
fields and FLAG THEIR AGE - graceful degradation, never silent failure.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import Config
from .processing import QualityGateError

log = logging.getLogger("parasail.ingestion")

API_TIMEOUT_S = 20.0


@dataclass
class SourcedField:
    """One normalised environmental field value with provenance."""
    variable: str            # sst, chlorophyll_a, wind_speed, wave_height, ...
    source: str              # open-meteo, copernicus, erddap
    value: float
    ts: str                  # ISO-8601 UTC
    fetched_at: str
    age_hours: float
    stale: bool              # True -> served from cache under outage


# --------------------------------------------------------------------------- #
# Cached fetch core
# --------------------------------------------------------------------------- #
class CachedFetcher:
    """HTTP GET with disk cache + freshness contract + offline fallback."""

    def __init__(self, source: str, cache_dir: str, freshness_hours: float):
        self.source = source
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.freshness = timedelta(hours=freshness_hours)

    def _key(self, url: str, params: dict) -> Path:
        blob = json.dumps({"url": url, "params": params}, sort_keys=True)
        return self.cache / (hashlib.sha256(blob.encode()).hexdigest()[:24] + ".json")

    def fetch(self, url: str, params: dict) -> tuple[dict, float, bool]:
        """Return (payload, age_hours, served_from_cache)."""
        cache_file = self._key(url, params)
        if cache_file.exists():
            blob = json.loads(cache_file.read_text(encoding="utf-8"))
            age = (time.time() - blob["fetched_at"]) / 3600.0
            if age <= self.freshness.total_seconds() / 3600.0:
                return blob["payload"], age, True

        try:
            with httpx.Client(timeout=API_TIMEOUT_S) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
            cache_file.write_text(
                json.dumps({"fetched_at": time.time(), "payload": payload}),
                encoding="utf-8",
            )
            return payload, 0.0, False
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            log.warning("%s live fetch failed (%s); falling back to cache",
                        self.source, exc)
            if cache_file.exists():
                blob = json.loads(cache_file.read_text(encoding="utf-8"))
                age = (time.time() - blob["fetched_at"]) / 3600.0
                return blob["payload"], age, True
            raise


# --------------------------------------------------------------------------- #
# Open-Meteo (hourly meteorological + marine forecasts) -> weather-safety W
# --------------------------------------------------------------------------- #
class OpenMeteoSource:
    # Core variables feed the advisory scoring pipeline (W component).
    CORE_WEATHER = ["wind_speed_10m", "wind_gusts_10m"]
    CORE_MARINE = ["wave_height", "sea_surface_temperature"]
    # Extended variables feed the dashboard telemetry panel: wind direction,
    # barometric pressure, air temperature, humidity, wave period/direction
    # and surface currents. Requested as separate groups so an unsupported
    # variable or endpoint error degrades only that group, never the core.
    EXT_WEATHER = ["wind_direction_10m", "surface_pressure",
                   "temperature_2m", "relative_humidity_2m"]
    EXT_MARINE = ["wave_period", "wave_direction",
                  "ocean_current_velocity", "ocean_current_direction"]
    VARIABLES = CORE_WEATHER + CORE_MARINE + EXT_WEATHER + EXT_MARINE
    MARINE_VARIABLES = CORE_MARINE + EXT_MARINE

    def __init__(self, cfg: Config):
        conf = cfg.ingestion["open_meteo"]
        self.fetcher = CachedFetcher("open-meteo", conf["cache_dir"],
                                     conf["freshness_hours"])
        self.base = conf["base"]
        self.marine_base = conf.get(
            "marine_base", "https://marine-api.open-meteo.com/v1")

    def _nearest_now_index(self, times: list[str]) -> int:
        now = datetime.now(timezone.utc)
        best_i, best_delta = 0, None
        for i, t in enumerate(times):
            try:
                tt = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            delta = abs((tt - now).total_seconds())
            if best_delta is None or delta < best_delta:
                best_i, best_delta = i, delta
        return best_i

    def fetch_points(self, points: list[tuple[float, float]],
                     hours: int = 24) -> dict[tuple[float, float], dict]:
        """Batched current-conditions fetch for a grid of points.

        Open-Meteo accepts comma-separated coordinate lists and answers with
        one payload per point, so a whole suggestion grid costs a handful of
        HTTP calls. Values are taken at the hour closest to now. Each
        variable group (core weather / extended weather / core marine /
        extended marine) degrades independently.
        """
        if not points:
            return {}
        lats = ",".join(f"{p[0]:.4f}" for p in points)
        lons = ",".join(f"{p[1]:.4f}" for p in points)
        out: dict[tuple[float, float], dict] = {p: {} for p in points}
        for endpoint, variables in (
            (f"{self.base}/forecast", self.CORE_WEATHER),
            (f"{self.base}/forecast", self.EXT_WEATHER),
            (f"{self.marine_base}/marine", self.CORE_MARINE),
            (f"{self.marine_base}/marine", self.EXT_MARINE),
        ):
            try:
                payload, age, cached = self.fetcher.fetch(
                    endpoint,
                    {
                        "latitude": lats, "longitude": lons,
                        "hourly": ",".join(variables),
                        "forecast_days": max(1, hours // 24 + 1),
                        "timezone": "UTC",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("open-meteo %s unavailable (%s); continuing "
                            "without %s", endpoint, exc, ",".join(variables))
                continue
            entries = payload if isinstance(payload, list) else [payload]
            for point, entry in zip(points, entries):
                hourly = entry.get("hourly", {})
                idx = self._nearest_now_index(hourly.get("time", []))
                for var in variables:
                    values = hourly.get(var, [])
                    value = (values[idx] if idx < len(values)
                             and values[idx] is not None
                             else next((v for v in values if v is not None), None))
                    if value is not None:
                        out[point][var] = float(value)
        return out

    def fetch_point(self, lat: float, lon: float,
                    start: datetime, hours: int) -> list[SourcedField]:
        start_iso = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        out: list[SourcedField] = []
        # Each source degrades independently: a failing endpoint (outage,
        # unsupported variable, rate limit) never kills the whole advisory.
        for endpoint, variables in (
            (f"{self.base}/forecast", ["wind_speed_10m", "wind_gusts_10m"]),
            (f"{self.marine_base}/marine", ["wave_height"]),
        ):
            try:
                payload, age, cached = self.fetcher.fetch(
                    endpoint,
                    {
                        "latitude": lat, "longitude": lon,
                        "hourly": ",".join(variables),
                        "forecast_days": max(1, hours // 24 + 1),
                        "timezone": "UTC",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("open-meteo %s unavailable (%s); continuing "
                            "without %s", endpoint, exc, ",".join(variables))
                continue
            hourly = payload.get("hourly", {})
            times = hourly.get("time", [])
            for var in variables:
                values = hourly.get(var, [])
                for t, v in zip(times[:hours], values[:hours]):
                    if v is None:
                        continue
                    out.append(SourcedField(
                        variable=var, source="open-meteo", value=float(v),
                        ts=t + ":00Z",
                        fetched_at=datetime.now(timezone.utc).isoformat(),
                        age_hours=age, stale=cached,
                    ))
        if not out:
            raise QualityGateError(
                "no weather fields available from any Open-Meteo endpoint")
        return out


# --------------------------------------------------------------------------- #
# ERDDAP (SST / chlorophyll-a gridded fields) - environmental features
# --------------------------------------------------------------------------- #
class ErddapSource:
    def __init__(self, cfg: Config):
        conf = cfg.ingestion["erddap"]
        self.fetcher = CachedFetcher("erddap", conf["cache_dir"],
                                     conf["freshness_hours"])
        self.base = conf["base"]

    def fetch_grid(self, dataset: str, variable: str, bbox: list[float],
                   ts: str) -> list[SourcedField]:
        lon_min, lat_min, lon_max, lat_max = bbox
        payload, age, cached = self.fetcher.fetch(
            f"{self.base}/{dataset}/index.json",
            {"variable": variable,
             "min_lon": lon_min, "max_lon": lon_max,
             "min_lat": lat_min, "max_lat": lat_max,
             "time": ts},
        )
        now = datetime.now(timezone.utc).isoformat()
        return [
            SourcedField(variable=variable, source="erddap",
                         value=float(row["value"]),
                         ts=row.get("time", ts), fetched_at=now,
                         age_hours=age, stale=cached)
            for row in payload.get("rows", [])
        ]


# --------------------------------------------------------------------------- #
# Occurrence corpora (GBIF via pygbif; OBIS analogous) - training data
# --------------------------------------------------------------------------- #
def fetch_gbif_occurrences(scientific_name: str, bbox: list[float],
                           limit: int = 5000) -> list[dict]:
    """Historical occurrences for habitat models and data-availability weights."""
    try:
        from pygbif import occurrences as gbif_occ
    except ImportError:
        log.warning("pygbif not installed; returning no occurrences")
        return []
    lon_min, lat_min, lon_max, lat_max = bbox
    result = gbif_occ.search(
        scientificName=scientific_name, limit=limit,
        geometry=f"ENVELOPE({lon_min},{lon_max},{lat_min},{lat_max})",
    )
    out = []
    for rec in result.get("results", []):
        if rec.get("decimalLatitude") is None or rec.get("decimalLongitude") is None:
            continue
        out.append({
            "species": scientific_name,
            "lat": float(rec["decimalLatitude"]),
            "lon": float(rec["decimalLongitude"]),
            "ts": rec.get("eventDate"),
            "dataset": "gbif",
        })
    return out


# --------------------------------------------------------------------------- #
# Taxonomy normalisation (WoRMS AphiaID)
# --------------------------------------------------------------------------- #
def resolve_aphia_id(scientific_name: str) -> int | None:
    try:
        import pyworms
    except ImportError:
        log.warning("pyworms not installed; taxonomy unverified")
        return None
    matches = pyworms.aphiaRecordsByName(scientific_name, marine_only=True)
    if matches and isinstance(matches[0], list):
        matches = matches[0]
    if matches:
        return int(matches[0]["AphiaID"])
    return None


# --------------------------------------------------------------------------- #
# Facade used by the API / validation suite
# --------------------------------------------------------------------------- #
class IngestionService:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.open_meteo = OpenMeteoSource(cfg)
        self.erddap = ErddapSource(cfg)

    def weather_fields(self, lat, lon, start, hours) -> list[SourcedField]:
        return self.open_meteo.fetch_point(lat, lon, start, hours)

    def environmental_fields(self, ts: str) -> list[SourcedField]:
        return self.erddap.fetch_grid(
            "noaaCoastwatchSST", "sst", self.cfg.region["bbox"], ts)

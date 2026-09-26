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
    ts: str                  # ISO-8601 UTC (valid time of the forecast)
    fetched_at: str          # ISO-8601 UTC (when we actually fetched it)
    age_hours: float         # hours since fetch (0 = live, >0 = cached)
    stale: bool              # True -> served from cache under outage


@dataclass
class AlertItem:
    """One security/disaster alert for a region."""
    id: str
    title: str
    description: str
    severity: str            # extreme, severe, moderate, minor, info
    urgency: str             # immediate, expected, future, past
    certainty: str           # observed, likely, possible, unlikely
    event_type: str          # cyclone, flood, tsunami, storm_surge, high_wind, etc.
    areas: list[str]         # affected districts/coastal zones
    issued_at: str           # ISO-8601 UTC
    expires_at: str | None   # ISO-8601 UTC or None
    source: str              # IMD, INCOIS, NDMA, CAP, SAC
    source_url: str | None
    languages: dict[str, str]  # language_code -> localized title/description


@dataclass
class TelemetryField:
    """One telemetry value with exact retrieval provenance."""
    variable: str            # wind_speed_10m, wave_height, etc.
    source: str              # open-meteo, copernicus, erddap
    value: float
    ts: str                  # ISO-8601 UTC (valid time of the forecast)
    fetched_at: str          # ISO-8601 UTC (when we actually fetched it from provider)
    age_hours: float         # hours since fetch (0 = live fetch, >0 = cached)
    stale: bool              # True -> served from cache under outage


# --------------------------------------------------------------------------- #
# Cached fetch core
# --------------------------------------------------------------------------- #
class CachedFetcher:
    """HTTP GET with disk cache + freshness contract + offline fallback.

    Modes controlled by `freshness_hours` and `offline_policy`:
      - freshness_hours == 0: no cache, always live fetch
      - offline_policy == "fail_on_stale": raise on live fetch failure
      - offline_policy == "serve_cached_with_age_flag" (default): graceful fallback
    """

    def __init__(self, source: str, cache_dir: str, freshness_hours: float,
                 offline_policy: str = "serve_cached_with_age_flag"):
        self.source = source
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.freshness = timedelta(hours=freshness_hours)
        self.offline_policy = offline_policy
        self.use_cache = freshness_hours > 0

    def _key(self, url: str, params: dict) -> Path:
        blob = json.dumps({"url": url, "params": params}, sort_keys=True)
        return self.cache / (hashlib.sha256(blob.encode()).hexdigest()[:24] + ".json")

    def fetch(self, url: str, params: dict) -> tuple[dict, float, bool]:
        """Return (payload, age_hours, served_from_cache)."""
        cache_file = self._key(url, params)

        # If caching disabled, skip straight to live fetch
        if not self.use_cache:
            return self._live_fetch(url, params, cache_file)

        # Check cache first
        if cache_file.exists():
            blob = json.loads(cache_file.read_text(encoding="utf-8"))
            age = (time.time() - blob["fetched_at"]) / 3600.0
            if age <= self.freshness.total_seconds() / 3600.0:
                return blob["payload"], age, True

        # Live fetch
        try:
            return self._live_fetch(url, params, cache_file)
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            log.warning("%s live fetch failed (%s)", self.source, exc)
            if self.offline_policy == "fail_on_stale":
                raise
            if cache_file.exists():
                blob = json.loads(cache_file.read_text(encoding="utf-8"))
                age = (time.time() - blob["fetched_at"]) / 3600.0
                log.warning("%s serving stale cache (age=%.2fh) per offline_policy",
                            self.source, age)
                return blob["payload"], age, True
            raise

    def _live_fetch(self, url: str, params: dict, cache_file: Path) -> tuple[dict, float, bool]:
        """Perform live HTTP fetch and write to cache."""
        with httpx.Client(timeout=API_TIMEOUT_S) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        if self.use_cache:
            cache_file.write_text(
                json.dumps({"fetched_at": time.time(), "payload": payload}),
                encoding="utf-8",
            )
        return payload, 0.0, False


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
                                     conf["freshness_hours"],
                                     cfg.ingestion.get("offline_policy", "serve_cached_with_age_flag"))
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
                     hours: int = 24,
                     groups: tuple = ("core_weather", "ext_weather",
                                      "core_marine", "ext_marine")
                     ) -> dict[tuple[float, float], dict[str, TelemetryField]]:
        """Batched current-conditions fetch for a grid of points.

        Open-Meteo accepts comma-separated coordinate lists and answers with
        one payload per point, so a whole suggestion grid costs a handful of
        HTTP calls; large grids are chunked to keep request URLs sane.
        `groups` selects which variable groups are fetched (the suggestion
        layer needs only the two core groups). Values are taken at the hour
        closest to now. Each variable group degrades independently.

        Returns: dict mapping (lat, lon) -> dict of variable -> TelemetryField
        (includes fetched_at, age_hours, stale per field).
        """
        if not points:
            return {}
        available = {
            "core_weather": (f"{self.base}/forecast", self.CORE_WEATHER),
            "ext_weather": (f"{self.base}/forecast", self.EXT_WEATHER),
            "core_marine": (f"{self.marine_base}/marine", self.CORE_MARINE),
            "ext_marine": (f"{self.marine_base}/marine", self.EXT_MARINE),
        }
        out: dict[tuple[float, float], dict[str, TelemetryField]] = {p: {} for p in points}
        CHUNK = 100
        fetched_at = datetime.now(timezone.utc).isoformat()
        for start in range(0, len(points), CHUNK):
            chunk = points[start:start + CHUNK]
            lats = ",".join(f"{p[0]:.4f}" for p in chunk)
            lons = ",".join(f"{p[1]:.4f}" for p in chunk)
            for name in groups:
                endpoint, variables = available[name]
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
                                "without %s", endpoint, exc,
                                ",".join(variables))
                    continue
                entries = payload if isinstance(payload, list) else [payload]
                for point, entry in zip(chunk, entries):
                    if entry.get("elevation") is not None:
                        # terrain height (0 over open water): the suggestion
                        # layer uses it to keep fish zones off the mainland
                        out[point].setdefault("elevation",
                                              float(entry["elevation"]))
                    hourly = entry.get("hourly", {})
                    idx = self._nearest_now_index(hourly.get("time", []))
                    for var in variables:
                        values = hourly.get(var, [])
                        value = (values[idx] if idx < len(values)
                                 and values[idx] is not None
                                 else next((v for v in values if v is not None), None))
                        if value is not None:
                            out[point][var] = TelemetryField(
                                variable=var,
                                source="open-meteo",
                                value=float(value),
                                ts=hourly.get("time", [""])[idx] + ":00Z" if idx < len(hourly.get("time", [])) else fetched_at,
                                fetched_at=fetched_at,
                                age_hours=age,
                                stale=cached,
                            )
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
                                     conf["freshness_hours"],
                                     cfg.ingestion.get("offline_policy", "serve_cached_with_age_flag"))
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
# Security/Disaster Alerts (IMD, INCOIS, NDMA, CAP) - public safety
# --------------------------------------------------------------------------- #
class AlertSource:
    """Fetches official disaster/weather alerts for Indian coastal regions.
    
    Sources (all public, no auth required):
      - IMD (India Meteorological Department): cyclone, heavy rain, heat wave
      - INCOIS (Indian National Centre for Ocean Information Services):
        tsunami, storm surge, high waves, swell surge
      - NDMA (National Disaster Management Authority): multi-hazard alerts
      - CAP (Common Alerting Protocol) feeds via NDMA/IMD
      - SAC (Space Applications Centre): satellite-based alerts
    
    All endpoints return CAP/XML or JSON; we normalise to AlertItem.
    """

    # Regional CAP/JSON endpoints (public, no key)
    ENDPOINTS = {
        "imd": "https://mausam.imd.gov.in/backend/api/cap",
        "incois": "https://incois.gov.in/api/alerts",
        "ndma": "https://ndma.gov.in/api/alerts",
        "cap_india": "https://cap.ndma.gov.in/feed",
        "sac": "https://sac.gov.in/api/alerts",
    }

    def __init__(self, cfg: Config):
        conf = cfg.ingestion.get("alerts", {})
        self.cache_dir = Path(conf.get("cache_dir", ".cache/alerts"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.freshness_hours = conf.get("freshness_hours", 1)  # alerts: 1h freshness
        self.timeout = conf.get("timeout_s", 15.0)

    def _fetch_one(self, name: str, url: str) -> list[AlertItem]:
        """Fetch and normalise alerts from one source."""
        cache_file = self.cache_dir / f"{name}.json"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url)
                resp.raise_for_status()
                raw = resp.text
            # Cache successful fetch
            cache_file.write_text(raw, encoding="utf-8")
            return self._parse_alerts(name, raw)
        except Exception as exc:  # noqa: BLE001
            log.warning("alerts %s fetch failed (%s); using cache", name, exc)
            if cache_file.exists():
                raw = cache_file.read_text(encoding="utf-8")
                return self._parse_alerts(name, raw)
            return []

    def _parse_alerts(self, source: str, raw: str) -> list[AlertItem]:
        """Parse CAP/XML or JSON into AlertItem list."""
        import xml.etree.ElementTree as ET
        items: list[AlertItem] = []
        try:
            # Try JSON first (some endpoints)
            data = json.loads(raw)
            if isinstance(data, dict):
                data = data.get("alerts") or data.get("features") or [data]
            for a in data if isinstance(data, list) else []:
                items.append(self._normalise_alert(source, a, is_json=True))
            return items
        except json.JSONDecodeError:
            pass
        # Try CAP/XML
        try:
            root = ET.fromstring(raw)
            for alert in root.findall(".//{urn:oasis:names:tc:emergency:cap:1.2}alert"):
                items.append(self._normalise_alert(source, alert, is_json=False))
            return items
        except ET.ParseError:
            log.warning("alerts %s: unparseable response", source)
            return []

    def _normalise_alert(self, source: str, data: Any, is_json: bool) -> AlertItem | None:
        """Convert source-specific format to AlertItem."""
        try:
            if is_json:
                # Common JSON fields across IMD/INCOIS/NDMA
                event = data.get("event") or data.get("eventType") or "unknown"
                return AlertItem(
                    id=str(data.get("identifier") or data.get("id") or hashlib.md5(str(data).encode()).hexdigest()[:12]),
                    title=data.get("headline") or data.get("title") or event,
                    description=data.get("description") or data.get("instruction") or "",
                    severity=(data.get("severity") or "moderate").lower(),
                    urgency=(data.get("urgency") or "expected").lower(),
                    certainty=(data.get("certainty") or "likely").lower(),
                    event_type=self._map_event_type(event),
                    areas=[a for a in (data.get("areas") or data.get("geocode") or "").split(",") if a],
                    issued_at=data.get("sent") or data.get("issuedAt") or data.get("effective") or datetime.now(timezone.utc).isoformat(),
                    expires_at=data.get("expires") or data.get("expiresAt") or None,
                    source=source.upper(),
                    source_url=data.get("url") or data.get("link") or None,
                    languages=self._extract_languages(data),
                )
            else:
                # CAP XML
                ns = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
                info = data.find("cap:info", ns)
                if info is None:
                    return None
                event = info.findtext("cap:event", default="unknown", namespaces=ns)
                return AlertItem(
                    id=data.findtext("cap:identifier", default="", namespaces=ns) or hashlib.md5(ET.tostring(data)).hexdigest()[:12],
                    title=info.findtext("cap:headline", default=event, namespaces=ns),
                    description=info.findtext("cap:description", default="", namespaces=ns),
                    severity=(info.findtext("cap:severity", default="Moderate", namespaces=ns)).lower(),
                    urgency=(info.findtext("cap:urgency", default="Expected", namespaces=ns)).lower(),
                    certainty=(info.findtext("cap:certainty", default="Likely", namespaces=ns)).lower(),
                    event_type=self._map_event_type(event),
                    areas=[a.text for a in info.findall("cap:area/cap:areaDesc", ns) if a.text],
                    issued_at=data.findtext("cap:sent", default="", namespaces=ns) or datetime.now(timezone.utc).isoformat(),
                    expires_at=info.findtext("cap:expires", default=None, namespaces=ns),
                    source=source.upper(),
                    source_url=info.findtext("cap:web", default=None, namespaces=ns),
                    languages={},
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("alerts %s: normalise failed (%s)", source, exc)
        return None

    @staticmethod
    def _map_event_type(event: str) -> str:
        """Map free-text event to standardised type."""
        e = event.lower()
        if any(k in e for k in ("cyclone", "hurricane", "typhoon")):
            return "cyclone"
        if any(k in e for k in ("tsunami",)):
            return "tsunami"
        if any(k in e for k in ("storm surge", "storm-surge")):
            return "storm_surge"
        if any(k in e for k in ("high wave", "swell surge", "rough sea")):
            return "high_waves"
        if any(k in e for k in ("heavy rain", "extreme rain", "cloudburst")):
            return "heavy_rain"
        if any(k in e for k in ("flood", "inundation")):
            return "flood"
        if any(k in e for k in ("heat wave", "heatwave")):
            return "heat_wave"
        if any(k in e for k in ("high wind", "gale", "squall")):
            return "high_wind"
        if any(k in e for k in ("thunderstorm", "lightning")):
            return "thunderstorm"
        return "other"

    def _extract_languages(self, data: dict) -> dict[str, str]:
        """Extract localised text if available (IMD provides Hindi/English)."""
        out = {"en": data.get("headline") or data.get("title") or ""}
        if "headline_hi" in data:
            out["hi"] = data["headline_hi"]
        if "description_hi" in data:
            out["hi"] = out.get("hi", "") + " | " + data["description_hi"]
        return out

    def fetch_for_location(self, lat: float, lon: float, radius_km: float = 200) -> list[AlertItem]:
        """Fetch all alerts, filter to those affecting the given location.

        Uses a simple text-based area match as a first pass. For production,
        proper geospatial filtering against alert polygons should be implemented
        when the sources provide structured geometry (CAP <area> with polygons).
        """
        all_alerts: list[AlertItem] = []
        for name, url in self.ENDPOINTS.items():
            all_alerts.extend(self._fetch_one(name, url))

        # First, try to match by coordinate using known district/state names
        # for the given location. This is a best-effort text-based filter.
        # In production, we'd use a reverse geocoder to get the district/state
        # and then match against alert.areas, or parse CAP <area> polygons.
        relevant = []
        for alert in all_alerts:
            # If no areas specified, assume it's relevant (broadcast alert)
            if not alert.areas:
                relevant.append(alert)
                continue

            # Simple text match on known coastal districts/states
            # This is a lightweight filter; proper implementation needs
            # a geocoding service or polygon containment check
            for area in alert.areas:
                area_lower = area.lower()
                # Match against known Indian coastal states/districts
                coastal_keywords = [
                    "kerala", "karnataka", "goa", "maharashtra", "gujarat",
                    "tamil nadu", "andhra pradesh", "odisha", "west bengal",
                    "lakshadweep", "andaman", "nicobar", "puducherry",
                    "daman", "diu", "kutch", "saurashtra", "konkan",
                    "malabar", "coromandel", "sundarbans", "godavari",
                    "krishna", "kaveri", "mahandi", "brahmaputra",
                    "kochi", "mangalore", "chennai", "visakhapatnam",
                    "paradip", "haldia", "kandla", "mormugao", "new mangalore",
                    "tuticorin", "ennore", "gangavaram", "kakinada",
                    "nagapattinam", "cuddalore", "pondicherry", "karaikal",
                    "ernakulam", "alappuzha", "kollam", "thiruvananthapuram",
                    "kasaragod", "kannur", "kozhikode", "malappuram",
                    "thrissur", "palakkad", "idukki", "kottayam", "pathanamthitta"
                ]
                if any(kw in area_lower for kw in coastal_keywords):
                    relevant.append(alert)
                    break

        # Sort: most severe/urgent first
        severity_order = {"extreme": 0, "severe": 1, "moderate": 2, "minor": 3, "info": 4}
        urgency_order = {"immediate": 0, "expected": 1, "future": 2, "past": 3}
        relevant.sort(key=lambda a: (severity_order.get(a.severity, 5), urgency_order.get(a.urgency, 5)))
        return relevant


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
        self.alerts = AlertSource(cfg)

    def weather_fields(self, lat, lon, start, hours) -> list[SourcedField]:
        return self.open_meteo.fetch_point(lat, lon, start, hours)

    def environmental_fields(self, ts: str) -> list[SourcedField]:
        return self.erddap.fetch_grid(
            "noaaCoastwatchSST", "sst", self.cfg.region["bbox"], ts)

    def alerts_for_location(self, lat: float, lon: float, radius_km: float = 200) -> list[AlertItem]:
        return self.alerts.fetch_for_location(lat, lon, radius_km)

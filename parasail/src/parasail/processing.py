"""ParaSail processing layer (development phase P2).

Coordinate/timestamp validation, taxonomy normalisation, regridding onto the
common spatiotemporal grid, feature engineering and quality gates - plus the
freshness audit that keeps degraded data visible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import Config


class QualityGateError(ValueError):
    """Raised when an input fails a quality gate - reject, never silently fix."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_coordinates(lat: float, lon: float, bbox: list[float]) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise QualityGateError(f"latitude out of range: {lat}")
    if not (-180.0 <= lon <= 180.0):
        raise QualityGateError(f"longitude out of range: {lon}")
    lon_min, lat_min, lon_max, lat_max = bbox
    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
        raise QualityGateError(
            f"point ({lat}, {lon}) outside configured region bbox {bbox}")


def validate_timestamp(start: datetime, hours: int,
                       now: datetime | None = None) -> None:
    if hours <= 0 or hours > 72:
        raise QualityGateError(
            "advisory horizon must be within (0, 72] hours - "
            "beyond a few days forecasts compound uncertainty")
    now = now or datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if abs((start - now).total_seconds()) > 7 * 86400:
        raise QualityGateError("start more than 7 days from now")


# --------------------------------------------------------------------------- #
# Common spatiotemporal grid
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GridSpec:
    res_deg: float
    step_hours: int

    @classmethod
    def from_config(cls, cfg: Config) -> "GridSpec":
        g = cfg.region["grid"]
        return cls(res_deg=float(g["res_deg"]), step_hours=int(g["step_hours"]))

    def snap(self, lat: float, lon: float) -> tuple[float, float]:
        """Snap a point onto the nearest grid node."""
        r = self.res_deg
        return (round(math.floor(lat / r) * r + r / 2.0, 4),
                round(math.floor(lon / r) * r + r / 2.0, 4))


# --------------------------------------------------------------------------- #
# Feature engineering
# --------------------------------------------------------------------------- #
def sst_anomaly(sst_c: float, climatology_c: float) -> float:
    """Thermal anomaly in kelvin - positive anomaly often tracks pelagic
    aggregation for small pelagics in the case-study region."""
    return sst_c - climatology_c


def wind_stress(wind_ms: float) -> float:
    """Bulk wind stress magnitude (N m^-2) with drag coefficient after
    Large & Pond (1981), closed form."""
    cd = 1.2e-3 if wind_ms < 11.0 else (0.49e-3 + 0.065e-3 * wind_ms)
    rho_air = 1.225
    return rho_air * cd * wind_ms ** 2


def weather_safety(wind_ms: float, wave_m: float | None, cfg: Config) -> float:
    """Map wind and waves onto W in [0, 1] for small vessels.

    W = 1 at calm conditions, falling linearly to 0 at the configured
    safety limits (by default Beaufort 5 winds / 1.5 m waves). When wave
    observations are unavailable (marine endpoint down), W is computed
    from wind alone and the freshness audit flags the degradation.
    """
    limits = cfg.advisory["weather_safety"]
    w_wind = max(0.0, 1.0 - wind_ms / limits["max_wind_ms"])
    if wave_m is None:
        return w_wind
    w_wave = max(0.0, 1.0 - wave_m / limits["max_wave_height_m"])
    return 0.5 * (w_wind + w_wave)


# --------------------------------------------------------------------------- #
# Quality gates + freshness audit
# --------------------------------------------------------------------------- #
def quality_gate(fields: list) -> list:
    """Drop non-finite values; a field that arrives with no data at all
    raises, because scoring on nothing would be silent fabrication."""
    kept = [f for f in fields
            if f.value is not None and math.isfinite(f.value)]
    if not fields:
        raise QualityGateError("no environmental fields arrived")
    return kept


def freshness_audit(fields: list) -> dict:
    """Summarise data age so every advisory can display it."""
    if not fields:
        return {"max_age_hours": None, "stale_sources": []}
    stale = sorted({f.source for f in fields if f.stale})
    return {
        "max_age_hours": round(max(f.age_hours for f in fields), 2),
        "stale_sources": stale,
        "degraded": bool(stale),
    }

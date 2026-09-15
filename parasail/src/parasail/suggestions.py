"""ParaSail fish-location suggestions (habitat-envelope method).

Approximate "where might the fish be" hints around a requested position:
a ~50 km grid of live sea-temperature readings is scored against the
species' preferred thermal envelope, and the best-spaced cells are returned
with distance, compass bearing and the nearest coastal landmark.

This is explicitly an UNTRAINED habitat estimate (the honest fallback path
described in the paper); the LSTM tendency model replaces it once trained.
"""
from __future__ import annotations

import math

EARTH_R_KM = 6371.0
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2)
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(phi2)
    x = (math.cos(phi1) * math.sin(phi2)
         - math.sin(phi1) * math.cos(phi2) * math.cos(dlmb))
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def compass(deg: float) -> str:
    return COMPASS[int(((deg + 11.25) % 360) // 22.5)]


def grid(center_lat: float, center_lon: float,
         half_deg: float = 0.24, step_deg: float = 0.12) -> list[tuple]:
    n = int(round(half_deg / step_deg))
    return [(round(center_lat + i * step_deg, 4),
             round(center_lon + j * step_deg, 4))
            for i in range(-n, n + 1) for j in range(-n, n + 1)]


def thermal_suitability(sst_c: float, lo: float, hi: float,
                        falloff_c: float = 1.5) -> float:
    """1.0 inside the preferred band, falling linearly to 0 outside it."""
    if lo <= sst_c <= hi:
        return 1.0
    d = (lo - sst_c) if sst_c < lo else (sst_c - hi)
    return max(0.0, 1.0 - d / falloff_c)


def nearest_landmark(lat: float, lon: float,
                     landmarks: list[dict]) -> tuple[str, float, str]:
    best = min(landmarks,
               key=lambda lm: haversine_km(lat, lon, lm["lat"], lm["lon"]))
    dist = haversine_km(lat, lon, best["lat"], best["lon"])
    direction = compass(bearing_deg(best["lat"], best["lon"], lat, lon))
    return best["name"], dist, direction


def fish_suggestions(cfg, ingestion, species_name: str,
                     lat: float, lon: float, max_spots: int = 4) -> dict:
    entry = cfg.species_entry(species_name)
    if entry is None:
        raise ValueError(f"species {species_name!r} not in registry")
    lo, hi = entry.get("preferred_sst_c", [22.0, 29.0])

    points = grid(lat, lon)
    data = ingestion.open_meteo.fetch_points(points, hours=24)

    scored = []
    for p in points:
        sst = data.get(p, {}).get("sea_surface_temperature")
        if sst is None:
            continue
        scored.append({
            "lat": p[0], "lon": p[1],
            "sst_c": round(sst, 1),
            "suitability": round(thermal_suitability(sst, lo, hi), 3),
        })
    scored.sort(key=lambda s: (-s["suitability"], s["lat"], s["lon"]))

    # keep the best cells that are sensibly far apart, so hints spread out
    picked: list[dict] = []
    for s in scored:
        if len(picked) >= max_spots:
            break
        if all(haversine_km(s["lat"], s["lon"], q["lat"], q["lon"]) >= 10.0
               for q in picked):
            picked.append(s)
    if not picked:
        picked = scored[:1]

    landmarks = cfg.region.get("landmarks", [])
    for s in picked:
        d = haversine_km(lat, lon, s["lat"], s["lon"])
        s["distance_km"] = round(d, 1)
        s["bearing"] = compass(bearing_deg(lat, lon, s["lat"], s["lon"]))
        if landmarks:
            name, ldist, ldir = nearest_landmark(s["lat"], s["lon"], landmarks)
            s["landmark"] = name
            s["landmark_distance_km"] = round(ldist, 1)
            s["landmark_direction"] = ldir

    return {
        "species": entry["scientific_name"],
        "common_name": entry["common_name"],
        "center": {"lat": lat, "lon": lon},
        "suggestions": picked,
        "method": "habitat envelope on live sea temperature (untrained)",
        "note": ("Estimated from the species' preferred sea-temperature range "
                 "over a ~50 km grid of live readings. Indicative hints, not "
                 "a trained prediction - always local knowledge first."),
    }

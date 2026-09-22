"""ParaSail fish-location suggestions.

Approximate "where might the fish be" hints around a requested position: a
~50 km grid of live sea readings is scored for suitability, and the
best-spaced cells are returned with distance, compass bearing and the
nearest coastal landmark.

TWO SCORERS, one geometry path:
  * a TRAINED habitat model (scripts/train_habitat.py) when an artifact
    exists for the species - gradient-boosted-free, calibrated probability
    of presence from sea temperature, distance to shore and month;
  * the thermal ENVELOPE fallback otherwise: 1.0 inside the species'
    preferred band, linear falloff outside. It is untrained, and the API
    response says so.
The trained artifact is adopted only where it beat the envelope under
spatial-block cross-validation AND transferred to a held-out survey, so its
absence is a measured result rather than a missing file. Either way the
response names the method, the threshold and the training-record count.

The likely-fish ZONE is built only from cells that lie strictly on the open
ocean - tested against a local Natural Earth ocean mask (prepared by
scripts/prepare_ocean_mask.py) in addition to live marine data - and is
drawn as the traced outline of those cells, so it follows the coastline at
grid resolution and never covers the mainland or backwaters.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

EARTH_R_KM = 6371.0
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# suggestion grid: ~50 km search radius, ~3.3 km cells (the resolution of
# the zone boundary - finer cells hug the coastline more tightly)
GRID_HALF_DEG = 0.24
GRID_STEP_DEG = 0.03

# --- ocean mask (Natural Earth 1:10m, public domain) ----------------------- #
_OCEAN_MASK_PATH = (Path(__file__).resolve().parent / "data"
                    / "ocean_mask.geojson")
_ocean_mask: list | None = None
_sea_grid_cache: dict = {}    # (clat, clon, step) -> {(i, j): over_ocean}


def _load_ocean_mask() -> list | None:
    """Lazily parse the ocean mask: [{bbox, ext, holes}] with rings as
    (lon, lat) tuples. Returns None when the file is missing or unreadable
    - the zone layer then falls back to the live marine/elevation mask
    alone (best effort, no hard dependency)."""
    global _ocean_mask
    if _ocean_mask is not None:
        return _ocean_mask or None
    polys: list = []
    try:
        data = json.loads(_OCEAN_MASK_PATH.read_text(encoding="utf-8"))
        geoms = data.get("coordinates") or []
        if data.get("type") == "Polygon":
            geoms = [geoms]
        for rings in geoms:            # Polygon geometry: [ext, *holes]
            ext = [(p[0], p[1]) for p in rings[0]]
            holes = [[(p[0], p[1]) for p in r] for r in rings[1:]]
            lons = [p[0] for p in ext]
            lats = [p[1] for p in ext]
            polys.append({
                "bbox": (min(lons), min(lats), max(lons), max(lats)),
                "ext": ext, "holes": holes})
    except Exception:  # noqa: BLE001 - the mask is optional
        return None
    _ocean_mask = polys
    return polys or None


def _point_in_ring(x: float, y: float, ring: list) -> bool:
    """Even-odd ray casting; works for (lon, lat) and lattice tuples."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _point_in_ocean(lon: float, lat: float, polys: list) -> bool:
    for poly in polys:
        b = poly["bbox"]
        if not (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]):
            continue
        if _point_in_ring(lon, lat, poly["ext"]):
            if not any(_point_in_ring(lon, lat, h) for h in poly["holes"]):
                return True
    return False


# --- distance to shore (a model feature the serving path must supply) ------ #
_SHORE_BUCKET_DEG = 0.25
_shore_index: dict | None = None
_shore_dist_cache: dict = {}   # (clat, clon, step) -> {(i, j): km}


def _build_shore_index(polys: list) -> dict:
    """Bucket the mask's coastline vertices so a distance query touches a few
    dozen points instead of the whole mask."""
    idx: dict = {}
    for poly in polys:
        for lon, lat in poly["ext"]:
            idx.setdefault((int(lon // _SHORE_BUCKET_DEG),
                            int(lat // _SHORE_BUCKET_DEG)), []).append((lon, lat))
    return idx


def distance_to_shore_km(lat: float, lon: float,
                         polys: list | None = None) -> float | None:
    """Great-circle distance to the nearest mapped coastline vertex, using the
    same mask the zone geometry trusts. None when no mask is available, which
    makes the model path decline rather than guess. Vertex spacing after
    simplification is a few hundred metres, well inside the accuracy of the
    training-side `shoredistance` field."""
    global _shore_index
    polys = polys if polys is not None else _load_ocean_mask()
    if not polys:
        return None
    if _shore_index is None:
        _shore_index = _build_shore_index(polys)
    bi, bj = int(lon // _SHORE_BUCKET_DEG), int(lat // _SHORE_BUCKET_DEG)
    for radius in (1, 2, 4):
        cands: list = []
        for i in range(bi - radius, bi + radius + 1):
            for j in range(bj - radius, bj + radius + 1):
                cands.extend(_shore_index.get((i, j), ()))
        if cands:
            return min(haversine_km(lat, lon, alat, alon)
                       for alon, alat in cands)
    return None


def _shore_dist_grid(center_lat: float, center_lon: float,
                     half_deg: float, step_deg: float) -> dict:
    """{(i, j): distance_to_shore_km} for one suggestion grid, cached per
    centre like the sea classification - the shoreline does not move."""
    key = (round(center_lat, 4), round(center_lon, 4), step_deg)
    if key in _shore_dist_cache:
        return _shore_dist_cache[key]
    polys = _load_ocean_mask()
    n = int(round(half_deg / step_deg))
    out: dict = {}
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            d = distance_to_shore_km(center_lat + i * step_deg,
                                     center_lon + j * step_deg, polys)
            if d is not None:
                out[(i, j)] = d
    _shore_dist_cache[key] = out
    return out


# --- optional trained habitat model ---------------------------------------- #
_MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
_habitat_models: dict = {}      # slug -> HabitatModel | None
DEFAULT_ZONE_THRESHOLD = 0.5


def _species_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def load_habitat_model(species_name: str):
    """Lazily load models/habitat_<slug>.joblib in the pattern of
    _load_ocean_mask(): cached, and None on any failure so a missing or
    unreadable artifact degrades to the envelope instead of failing."""
    slug = _species_slug(species_name)
    if slug in _habitat_models:
        return _habitat_models[slug]
    model = None
    try:
        path = _MODEL_DIR / f"habitat_{slug}.joblib"
        if path.exists():
            from .models.habitat import HabitatModel
            model = HabitatModel.load(str(path))
    except Exception:  # noqa: BLE001 - the model is optional
        model = None
    _habitat_models[slug] = model
    return model


def _ocean_cells(center_lat: float, center_lon: float,
                 half_deg: float, step_deg: float) -> dict:
    """For one suggestion grid: {(i, j): cell lies on the open ocean}.

    A cell counts as ocean only when its centre AND its four inset corners
    all sit inside the mapped ocean, so the drawn zone never touches the
    mapped coastline. The classification is cached per centre - the ocean
    does not move. Without a mask file every cell passes (the live
    marine/elevation mask then does the work alone)."""
    key = (round(center_lat, 4), round(center_lon, 4), step_deg)
    if key in _sea_grid_cache:
        return _sea_grid_cache[key]
    polys = _load_ocean_mask()
    n = int(round(half_deg / step_deg))
    out: dict = {}
    if polys is None:
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                out[(i, j)] = True
    else:
        inset = 0.45 * step_deg
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                lat = center_lat + i * step_deg
                lon = center_lon + j * step_deg
                # cheap reject first: land cells cost one test, not five
                if not _point_in_ocean(lon, lat, polys):
                    out[(i, j)] = False
                    continue
                out[(i, j)] = all(
                    _point_in_ocean(lon + dx * inset, lat + dy * inset, polys)
                    for dx in (-1, 1) for dy in (-1, 1))
    _sea_grid_cache[key] = out
    return out


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


def _is_sea(cell_data: dict, over_ocean: bool) -> bool:
    """Open-water test for one grid cell: it must lie on the mapped open
    ocean (Natural Earth mask) AND be served by the marine model (wave
    height defined) AND sit at sea level (elevation <= 5 m). Together
    these keep zones strictly off the mainland, backwaters and lagoons."""
    if not over_ocean:
        return False
    if "wave_height" not in cell_data:
        return False
    elev = cell_data.get("elevation")
    return elev is None or elev <= 5.0


def zone_polygon(scored: list[dict], center_lat: float, center_lon: float,
                 threshold: float = 0.5,
                 step_deg: float = GRID_STEP_DEG) -> tuple[dict | None, int]:
    """Strictly-sea perimeter around the best grid cells, MPA-style.

    Qualifying sea cells are unioned and their OUTLINE is traced edge by
    edge (collinear edges merged), producing many-vertex polygons that
    follow the coastline and the suitability boundary at grid resolution -
    no convex bridging, no blocky rectangles. Sea cells are strongly
    preferred (sea + threshold, then sea + half-threshold, then best sea
    cell); scored cells are used only when the sea mask yields nothing.
    Returns (GeoJSON geometry, qualifying cell count).
    """
    sea = [c for c in scored if c.get("sea")]
    cells = [c for c in sea if c["suitability"] >= threshold]
    if not cells:
        cells = [c for c in sea if c["suitability"] >= threshold / 2]

    def _rank(c):    # best first; ties go to cells near the requested point
        return (-c["suitability"],
                (c["lat"] - center_lat) ** 2 + (c["lon"] - center_lon) ** 2)

    if not cells and sea:
        cells = sorted(sea, key=_rank)[:1]
    if not cells:
        return None, 0    # no sea cells: no zone - never draw over land

    # integer lattice: corner (a, b) sits at
    # (lat + a*step/2, lon + b*step/2); cell (i, j) spans corners
    # (2i-1, 2j-1) .. (2i+1, 2j+1)
    idx = {(int(round((c["lat"] - center_lat) / step_deg)),
            int(round((c["lon"] - center_lon) / step_deg)))
           for c in cells}

    # boundary edges, directed counter-clockwise around each cell, emitted
    # only where the neighbour cell is absent (shared edges cancel out)
    edges: list = []
    by_start: dict = {}
    for (i, j) in idx:
        sides = (
            ((i, j - 1), (2 * i - 1, 2 * j - 1), (2 * i + 1, 2 * j - 1)),
            ((i + 1, j), (2 * i + 1, 2 * j - 1), (2 * i + 1, 2 * j + 1)),
            ((i, j + 1), (2 * i + 1, 2 * j + 1), (2 * i - 1, 2 * j + 1)),
            ((i - 1, j), (2 * i - 1, 2 * j + 1), (2 * i - 1, 2 * j - 1)),
        )
        for nb, s, e in sides:
            if nb not in idx:
                k = len(edges)
                edges.append((s, e))
                by_start.setdefault(s, []).append(k)

    # chain edges into closed rings
    used = [False] * len(edges)
    rings: list = []
    for k in range(len(edges)):
        if used[k]:
            continue
        used[k] = True
        start = edges[k][0]
        cur = edges[k][1]
        ring = [start]
        while cur != start:
            ring.append(cur)
            nxt = next((c for c in by_start.get(cur, []) if not used[c]),
                       None)
            if nxt is None:
                break
            used[nxt] = True
            cur = edges[nxt][1]
        # merge collinear runs so the outline reads as long edges, not a
        # staircase of single-cell steps
        merged: list = []
        for c in ring:
            if len(merged) >= 2:
                a, b = merged[-2], merged[-1]
                if (b[0] - a[0]) * (c[1] - b[1]) == (b[1] - a[1]) * (c[0] - b[0]):
                    merged.pop()
            merged.append(c)
        rings.append(merged)

    def to_xy(corner) -> list:
        return [round(center_lon + corner[1] * step_deg / 2.0, 4),
                round(center_lat + corner[0] * step_deg / 2.0, 4)]

    def signed_area(ring) -> float:
        s = 0.0
        for p, q in zip(ring, ring[1:] + ring[:1]):
            s += p[0] * q[1] - q[0] * p[1]
        return s / 2.0

    outers = [r for r in rings if signed_area(r) > 0]
    holes = [r for r in rings if signed_area(r) <= 0]
    polygons = []
    for o in outers:
        mine = [h for h in holes if _point_in_ring(h[0][0], h[0][1], o)]
        polygons.append([[to_xy(c) for c in r] + [to_xy(r[0])]
                         for r in [o] + mine])
    if not polygons:
        return None, 0
    geometry = ({"type": "MultiPolygon",
                 "coordinates": [p for p in polygons]}
                if len(polygons) > 1
                else {"type": "Polygon", "coordinates": polygons[0]})
    return geometry, len(cells)


def fish_suggestions(cfg, ingestion, species_name: str,
                     lat: float, lon: float, max_spots: int = 4) -> dict:
    entry = cfg.species_entry(species_name)
    if entry is None:
        raise ValueError(f"species {species_name!r} not in registry")
    lo, hi = entry.get("preferred_sst_c", [22.0, 29.0])

    # scorer selection: a trained artifact when one exists for this species
    # (and the species cleared the training-record floor), the thermal
    # envelope otherwise. `suggestions.method` can pin either path.
    prefs = cfg.raw.get("suggestions") or {}
    method_pref = str(prefs.get("method", "auto")).lower()
    min_records = int(prefs.get("min_training_records", 50))
    model = None
    if method_pref in ("auto", "model"):
        candidate = load_habitat_model(entry["scientific_name"])
        if candidate is not None:
            trained_n = int(candidate.metadata.get("n_presence") or 0)
            model = candidate if trained_n >= min_records else None
    zone_threshold = float(model.metadata.get("threshold")
                           or DEFAULT_ZONE_THRESHOLD) if model is not None \
        else DEFAULT_ZONE_THRESHOLD
    month = datetime.now(timezone.utc).month

    points = grid(lat, lon, half_deg=GRID_HALF_DEG, step_deg=GRID_STEP_DEG)
    data = ingestion.open_meteo.fetch_points(
        points, hours=24, groups=("core_weather", "core_marine"))
    ocean = _ocean_cells(lat, lon, GRID_HALF_DEG, GRID_STEP_DEG)
    shore = _shore_dist_grid(lat, lon, GRID_HALF_DEG, GRID_STEP_DEG) \
        if model is not None else {}

    scored = []
    for p in points:
        d = data.get(p, {})
        sst = d.get("sea_surface_temperature")
        if sst is None:
            continue
        cell = (int(round((p[0] - lat) / GRID_STEP_DEG)),
                int(round((p[1] - lon) / GRID_STEP_DEG)))
        distance_km = shore.get(cell)
        if model is not None and distance_km is not None:
            from .models.habitat import build_features
            suitability = float(model.suitability(
                build_features(sst, distance_km, month))[0])
        else:
            # no artifact, or the mask cannot supply distance-to-shore: the
            # untrained envelope answers rather than a model fed a guess
            suitability = thermal_suitability(sst, lo, hi)
        scored.append({
            "lat": p[0], "lon": p[1],
            "sst_c": round(sst, 1),
            "distance_to_shore_km": round(distance_km, 1)
            if distance_km is not None else None,
            "suitability": round(suitability, 3),
            "sea": _is_sea(d, ocean.get(cell, True)),
        })
    scored.sort(key=lambda s: (-s["suitability"], s["lat"], s["lon"]))

    # keep the best SEA cells that are sensibly far apart, so hints spread
    # out and stay over water (fall back to all cells when the sea mask
    # has nothing - e.g. a point picked far inland); ties prefer cells
    # near the requested point
    def _rank(s):
        return (-s["suitability"],
                (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2)

    sea_scored = sorted((s for s in scored if s["sea"]), key=_rank)
    pick_from = sea_scored or sorted(scored, key=_rank)
    picked: list[dict] = []
    for s in pick_from:
        if len(picked) >= max_spots:
            break
        if all(haversine_km(s["lat"], s["lon"], q["lat"], q["lon"]) >= 10.0
               for q in picked):
            picked.append(s)
    if not picked:
        picked = pick_from[:1]

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

    zone, zone_cells = zone_polygon(scored, lat, lon, threshold=zone_threshold)

    if model is not None:
        n = int(model.metadata.get("n_presence") or 0)
        ho = model.metadata.get("held_out_survey_min_auc")
        method = f"trained habitat model ({n} presences"
        method += f"; held-out survey AUC {ho:.2f})" if ho else ")"
        note = ("Calibrated probability of presence from live sea temperature, "
                "distance to shore and month, trained on open occurrence "
                f"records ({n} presences after spatial thinning). The model "
                "beat the thermal envelope under spatial-block validation and "
                "transferred to a held-out survey - but it is habitat "
                "discrimination from open data, not catch prediction: always "
                "local knowledge first.")
    else:
        method = "habitat envelope on live sea temperature (untrained)"
        note = ("Estimated from the species' preferred sea-temperature range "
                "over a ~50 km grid of live sea readings; the zone and the "
                "dots sit strictly on the open ocean. Indicative hints, not "
                "a trained prediction - always local knowledge first.")

    return {
        "species": entry["scientific_name"],
        "common_name": entry["common_name"],
        "center": {"lat": lat, "lon": lon},
        "suggestions": picked,
        "zone": zone,
        "zone_cells": zone_cells,
        "zone_threshold": zone_threshold,
        "method": method,
        "training_records": int(model.metadata.get("n_presence") or 0)
        if model is not None else None,
        "note": note,
    }

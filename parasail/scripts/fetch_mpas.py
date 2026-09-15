"""Fetch marine protected area boundaries into data/mpas_india.geojson.

Companion to scripts/load_mpas.py (which loads the result into PostGIS).
Two complementary sources, both fetched live and merged:

  A. WDPCA - UNEP-WCMC's public ProtectedPlanet ArcGIS service
     (https://data-gis.unep-wcmc.org, service ProtectedPlanet/WDPCA, layer 1).
     Carries the INTERNATIONAL designations for India (World Heritage,
     Ramsar) with authoritative geometry. Queried for realm IN
     ('Marine','Coastal'); the raw response is cached in
     data/wdpa_india_raw.geojson (--refresh re-downloads).

  B. OpenStreetMap via the Overpass API - India's NATIONAL-designation
     marine/coastal protected areas (marine national parks + wildlife
     sanctuaries under the WLPA 1972) that the public WDPCA endpoint does
     not carry. Candidates are matched against a curated allowlist of
     known marine/coastal PAs (WII/MoEFCC marine protected area inventory,
     mainland coast) so terrestrial reserves and neighbouring-country
     areas never enter the registry. Overpass mirrors are tried in turn
     with retries - the public endpoints rate-limit aggressively.

Known gap (documented, not approximated): the Gulf of Kachchh Marine
SANCTUARY (the buffer zone around the marine national park) is in neither
source; the national-park core IS covered. Replace this file with a full
WDPA India export (protectedplanet.net country download, marine subset)
if/when one is available - properties are compatible.

Output: GeoJSON FeatureCollection, EPSG:4326, polygons simplified
(Douglas-Peucker, ~0.0015 deg) to keep the dashboard payload small.
Properties per feature (all consumed by scripts/load_mpas.py):
  name, authority, desig, iucn_cat, no_take,
  valid_from (from status year, else null), valid_to (null),
  source ('wdpa' | 'osm'), origin (site id / OSM type+id)

Usage:
  python scripts/fetch_mpas.py                       # fetch + build
  python scripts/fetch_mpas.py --refresh             # re-download WDPCA raw
  python scripts/fetch_mpas.py --out my_mpas.geojson
  python scripts/fetch_mpas.py --wdpa-file wdpa.geojson   # offline raw input
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config  # noqa: E402

# UNEP-WCMC public ProtectedPlanet service (international designations).
WDPCA_POLY_URL = (
    "https://data-gis.unep-wcmc.org/server/rest/services/ProtectedPlanet/"
    "WDPCA/FeatureServer/1/query"
)

# Public Overpass endpoints, tried in order with backoff. The mail.ru and
# kumi mirrors have historically answered fastest for India-bbox queries;
# overpass-api.de rate-limits aggressively.
OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]

# Curated allowlist: India's national-designation marine / coastal protected
# areas (Wildlife Sanctuaries, National Parks) on the mainland coast.
# 'pattern' is matched case-insensitively against the OSM name (name or
# name:en); 'key' groups duplicate mappings of the same protected area (the
# variant with the most vertices wins); 'desig' is the legal designation.
OSM_ALLOWLIST = [
    # order matters: specific patterns must precede generic ones
    {"pattern": "marine (gulf of kachchh) national park", "key": "gok-marine-np",
     "desig": "National Park (marine)"},
    {"pattern": "gulf of mannar marine national park", "key": "gom-marine-np",
     "desig": "National Park (marine)"},
    # the Gujarat park is also mapped under the bare name "Marine National
    # Park" - exact match only, or it would swallow Gulf of Mannar above
    {"pattern": "marine national park", "key": "gok-marine-np", "exact": True,
     "desig": "National Park (marine)"},
    {"pattern": "malvan marine sanctuary", "key": "malvan",
     "desig": "Marine Sanctuary"},
    {"pattern": "gahirmatha", "key": "gahirmatha",
     "desig": "Wildlife Sanctuary (marine)"},
    {"pattern": "bhitarkanika", "key": "bhitarkanika",
     "desig": "Wildlife Sanctuary / National Park"},
    {"pattern": "point calimere", "key": "point-calimere",
     "desig": "Wildlife Sanctuary (coastal)"},
    {"pattern": "nalabana", "key": "nalabana",
     "desig": "Wildlife Sanctuary (Chilika lagoon)"},
    {"pattern": "lothian island", "key": "lothian",
     "desig": "Wildlife Sanctuary (Sundarbans)"},
    {"pattern": "haliday island", "key": "haliday",
     "desig": "Wildlife Sanctuary (Sundarbans)"},
    {"pattern": "coringa", "key": "coringa",
     "desig": "Wildlife Sanctuary (mangrove)"},
    {"pattern": "thane creek flamingo", "key": "thane-creek-flamingo",
     "desig": "Wildlife Sanctuary (coastal)"},
    {"pattern": "pitti wls", "key": "pitti",
     "desig": "Wildlife Sanctuary (bird island)"},
    {"pattern": "kachchh desert wls", "key": "kachchh-desert",
     "desig": "Wildlife Sanctuary (coastal desert / mudflats)"},
]
# Never import these even if the name matches (proposals, buffers, other
# countries' mapping of shared ecosystems).
OSM_EXCLUDE = ("esz", "proposed", "buffer")

ATTRIBUTION = (
    "Marine protected area boundaries: WDPCA (UNEP-WCMC & IUCN) and "
    "OpenStreetMap contributors (ODbL)"
)


# --------------------------------------------------------------------------- #
# small geometry helpers (no shapely dependency - the API container stays slim)
# --------------------------------------------------------------------------- #
def _simplify(ring: list[list[float]], tol: float) -> list[list[float]]:
    """Douglas-Peucker on a lon/lat ring; keeps the polygon contract intact
    (never returns fewer than 4 coordinates incl. closing point)."""

    def dp(pts: list[list[float]], first: int, last: int, keep: set) -> None:
        if last <= first + 1:
            return
        ax, ay = pts[first]
        bx, by = pts[last]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, idx = -1.0, -1
        for i in range(first + 1, last):
            # perpendicular distance to the chord (degrees are fine as a
            # relative tolerance at this scale)
            d = abs(dy * (pts[i][0] - ax) - dx * (pts[i][1] - ay)) / norm
            if d > best:
                best, idx = d, i
        if best > tol:
            keep.add(idx)
            dp(pts, first, idx, keep)
            dp(pts, idx, last, keep)

    if len(ring) <= 4:
        return ring
    body = ring[:-1]  # drop closing point; re-close after simplifying
    keep = {0, len(body) - 1}
    dp(body, 0, len(body) - 1, keep)
    out = [body[i] for i in range(len(body)) if i in keep]
    out.append(out[0])
    if len(out) < 4:  # degenerate collapse - keep the original tiny ring
        return ring
    return out


def _simplify_geom(geom: dict, tol: float) -> dict:
    if geom["type"] == "Polygon":
        rings = [[list(p) for p in ring] for ring in geom["coordinates"]]
        rings = [_simplify(r, tol) for r in rings]
        return {"type": "Polygon", "coordinates": rings}
    if geom["type"] == "MultiPolygon":
        polys = [
            [_simplify([list(p) for p in ring], tol) for ring in poly]
            for poly in geom["coordinates"]
        ]
        return {"type": "MultiPolygon", "coordinates": polys}
    return geom


def _vertex_count(geom: dict) -> int:
    if geom["type"] == "Polygon":
        return sum(len(r) for r in geom["coordinates"])
    return sum(len(r) for poly in geom["coordinates"] for r in poly)


def _point_in_ring(pt: list[float], ring: list[list[float]]) -> bool:
    """Ray-casting containment test (used to assign relation inner rings /
    holes to their outer ring)."""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                inside = not inside
    return inside


def _stitch_rings(ways: list[list[list[float]]]) -> list[list[list[float]]]:
    """Join open way geometries (as returned by Overpass `out geom`) into
    closed rings by matching endpoints. Ways that are already closed pass
    through. Returns only rings that close."""
    remaining = [w for w in ways if len(w) >= 2]
    rings: list[list[list[float]]] = []
    while remaining:
        chain = remaining.pop(0)
        changed = True
        while changed and (chain[0] != chain[-1]):
            changed = False
            for i, w in enumerate(remaining):
                if w[0] == chain[-1]:
                    chain = chain + w[1:]
                elif w[-1] == chain[-1]:
                    chain = chain + list(reversed(w))[1:]
                elif w[-1] == chain[0]:
                    chain = w + chain[1:]
                elif w[0] == chain[0]:
                    chain = list(reversed(w)) + chain[1:]
                else:
                    continue
                remaining.pop(i)
                changed = True
                break
        if chain[0] == chain[-1] and len(chain) >= 4:
            rings.append(chain)
    return rings


def _geom_from_osm(element: dict) -> dict | None:
    """Build a GeoJSON Polygon/MultiPolygon from an Overpass element with
    geometry (`out geom`). Relations: outer member ways stitched into rings,
    inner rings (holes) attached to the outer that contains them."""
    if element["type"] == "way":
        pts = [[p["lon"], p["lat"]] for p in element.get("geometry", [])]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            return {"type": "Polygon", "coordinates": [pts]}
        return None

    outers: list[list[list[float]]] = []
    inners: list[list[list[float]]] = []
    for m in element.get("members", []):
        if m.get("type") != "way" or "geometry" not in m:
            continue
        pts = [[p["lon"], p["lat"]] for p in m["geometry"]]
        if len(pts) < 2:
            continue  # single points are useless, 2-point connectors are not
        (outers if m.get("role") != "inner" else inners).append(pts)

    outer_rings = _stitch_rings(outers)
    inner_rings = _stitch_rings(inners)
    if not outer_rings:
        return None

    polygons = []
    for o in outer_rings:
        poly = [o]
        keep = []
        for h in inner_rings:
            if _point_in_ring(h[0], o):
                poly.append(h)
            else:
                keep.append(h)
        inner_rings = keep
        polygons.append(poly)
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


# --------------------------------------------------------------------------- #
# source A: WDPCA (UNEP-WCMC)
# --------------------------------------------------------------------------- #
def fetch_wdpa(bbox: list[float], cache: Path, refresh: bool) -> list[dict]:
    import httpx

    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text(encoding="utf-8"))
        feats = raw.get("features", [])
        print(f"wdpa: using cached {cache.name} ({len(feats)} features)")
        # the cache may be a raw distribution export (Web Mercator metres,
        # full country list) - normalise before use
        return _wdpa_features(feats, bbox)

    params = {
        "where": "prnt_iso3='IND' AND realm IN ('Marine','Coastal')",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    print("wdpa: querying UNEP-WCMC ProtectedPlanet service ...")
    r = httpx.get(WDPCA_POLY_URL, params=params, timeout=90.0,
                  headers={"User-Agent": "ParaSail-MPA-registry/1.0"})
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding="utf-8")
    print(f"wdpa: fetched {len(feats)} marine/coastal features -> {cache.name}")
    return _wdpa_features(feats, bbox)


def _flatten_coords(geom: dict) -> list[list[float]]:
    out: list[list[float]] = []

    def walk(node) -> None:
        if isinstance(node[0], (int, float)):
            out.append(node)
        else:
            for sub in node:
                walk(sub)

    walk(geom["coordinates"])
    return out


_MERC_R = 6378137.0  # WGS84 sphere radius (Web Mercator)


def _fix_3857(geom: dict) -> dict:
    """Some WDPCA distributions (e.g. the HDX export) store geometries in
    Web Mercator metres even though GeoJSON defaults to EPSG:4326 degrees.
    Detect out-of-range coordinates and convert in place."""
    import math

    def walk(node):
        if isinstance(node[0], (int, float)):
            if abs(node[0]) > 180 or abs(node[1]) > 90:
                lon = math.degrees(node[0] / _MERC_R)
                lat = math.degrees(
                    2.0 * math.atan(math.exp(node[1] / _MERC_R))
                    - math.pi / 2.0)
                node[0], node[1] = lon, lat
        else:
            for sub in node:
                walk(sub)

    walk(geom["coordinates"])
    return geom


def _wdpa_features(feats: list[dict], bbox: list[float]) -> list[dict]:
    """Normalise CRS to degrees, then keep only features intersecting the
    configured region bbox."""
    lon0, lat0, lon1, lat1 = bbox
    kept = []
    for f in feats:
        g = f.get("geometry")
        if not g:
            continue
        _fix_3857(g)
        xs = [c[0] for c in _flatten_coords(g)]
        ys = [c[1] for c in _flatten_coords(g)]
        if max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1:
            continue
        kept.append(f)
    return kept


# --------------------------------------------------------------------------- #
# source B: OpenStreetMap via Overpass
# --------------------------------------------------------------------------- #
def _overpass(query: str, timeout_total: int = 240) -> dict:
    import httpx

    last_err = None
    deadline = time.monotonic() + timeout_total
    attempt = 0
    while time.monotonic() < deadline:
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        attempt += 1
        try:
            r = httpx.post(endpoint, data={"data": query}, timeout=60.0,
                           headers={"User-Agent": "ParaSail-MPA-registry/1.0"})
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            last_err = f"{endpoint} -> HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001 - mirror failures rotate
            last_err = f"{endpoint} -> {exc}"
        print(f"  overpass: {last_err}; rotating mirror ...")
        time.sleep(min(3 * attempt, 10))
    raise RuntimeError(f"all Overpass mirrors failed (last: {last_err})")


def _allowlist_match(name: str) -> dict | None:
    low = name.lower()
    if any(x in low for x in OSM_EXCLUDE):
        return None
    for entry in OSM_ALLOWLIST:
        if entry.get("exact"):
            if low.strip() == entry["pattern"]:
                return entry
        elif entry["pattern"] in low:
            return entry
    return None


def fetch_osm(bbox: list[float], ids: list[str] | None = None) -> list[dict]:
    """When `ids` is given (["relation/415570", "way/678002187", ...]) the
    discovery stage is skipped and exactly those elements are fetched - the
    fast path once the allowlisted set is known."""

    def selected(elements: list[dict]) -> list[dict]:
        wanted = []
        for e in elements:
            t = e.get("tags", {})
            name = t.get("name") or t.get("name:en") or ""
            if not name:
                continue
            entry = _allowlist_match(name)
            if entry is None:
                continue
            wanted.append({"type": e["type"], "id": e["id"], "name": name,
                           "entry": entry})
        return wanted

    if ids:
        parts = []
        for i in ids:
            typ, oid = i.split("/")
            parts.append(f"{typ}({oid});")
        geom_query = f"[out:json][timeout:180];({''.join(parts)});out geom;"
        print(f"osm: fast path - fetching {len(ids)} explicit elements ...")
        g = _overpass(geom_query)
        wanted = selected(g.get("elements", []))
    else:
        lon0, lat0, lon1, lat1 = bbox
        bb = f"({lat0},{lon0},{lat1},{lon1})"
        # stage 1: tags only (cheap), then allowlist filtering
        tag_query = f"""
[out:json][timeout:120];
(
  relation["boundary"~"protected_area|national_park"]{bb};
  way["boundary"~"protected_area|national_park"]{bb};
);
out tags;"""
        print("osm: stage 1 - listing protected areas in the region bbox ...")
        d = _overpass(tag_query)
        wanted = []
        seen = set()
        for e in d.get("elements", []):
            if (e["type"], e["id"]) in seen:
                continue
            t = e.get("tags", {})
            name = t.get("name") or t.get("name:en") or ""
            if not name:
                continue
            entry = _allowlist_match(name)
            if entry is None:
                continue
            seen.add((e["type"], e["id"]))
            wanted.append({"type": e["type"], "id": e["id"], "name": name,
                           "entry": entry})
        print(f"osm: {len(wanted)} allowlisted elements "
              f"({len(d.get('elements', []))} candidates scanned)")

        # stage 2: geometry for the selected ids only
        parts = [f"{w['type']}({w['id']});" for w in wanted]
        geom_query = f"[out:json][timeout:180];({''.join(parts)});out geom;"
        print("osm: stage 2 - fetching geometry for selected areas ...")
        g = _overpass(geom_query)

    by_id = {(e["type"], e["id"]): e for e in g.get("elements", [])}

    feats: list[dict] = []
    for w in wanted:
        e = by_id.get((w["type"], w["id"]))
        if not e:
            continue
        geom = _geom_from_osm(e)
        if not geom:
            print(f"  osm: skipping {w['name']!r} (no closed polygon assembled)")
            continue
        feats.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": w["name"],
                "authority": "MoEFCC / State WLPA (via OpenStreetMap)",
                "desig": w["entry"]["desig"],
                "iucn_cat": None,
                "no_take": None,
                "valid_from": None,
                "valid_to": None,
                "source": "osm",
                "origin": f"osm:{w['type']}/{w['id']}",
                "_key": w["entry"]["key"],
            },
        })
    return feats


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/mpas_india.geojson",
                    help="output GeoJSON path (default: data/mpas_india.geojson)")
    ap.add_argument("--wdpa-file", default=None,
                    help="use this WDPCA GeoJSON instead of the live service")
    ap.add_argument("--refresh", action="store_true",
                    help="re-download the WDPCA raw cache")
    ap.add_argument("--osm-ids", default=None,
                    help="comma list of OSM elements to fetch directly "
                         "(e.g. relation/415570,way/678002187); skips the "
                         "Overpass discovery stage - the fast path once the "
                         "allowlisted set is known")
    ap.add_argument("--tolerance", type=float, default=0.0015,
                    help="Douglas-Peucker tolerance in degrees (default 0.0015)")
    args = ap.parse_args()

    cfg = load_config()
    bbox = [float(x) for x in cfg.region["bbox"]]
    root = Path(__file__).resolve().parents[1]

    # ---- source A --------------------------------------------------------
    if args.wdpa_file:
        raw = json.loads(Path(args.wdpa_file).read_text(encoding="utf-8"))
        wdpa_feats = _wdpa_features(raw.get("features", []), bbox)
        print(f"wdpa: loaded {len(wdpa_feats)} in-bbox features from "
              f"{args.wdpa_file}")
    else:
        wdpa_feats = fetch_wdpa(bbox, root / "data" / "wdpa_india_raw.geojson",
                                args.refresh)

    wdpa_out: list[dict] = []
    wdpa_names: set[str] = set()
    for f in wdpa_feats:
        p = f.get("properties") or {}
        name = (p.get("name_eng") or p.get("name") or "").strip()
        geom = f.get("geometry")
        # Marine/coastal only: the registry exists to block FISHING, so
        # terrestrial parks (Kaziranga, Western Ghats, ...) never enter it.
        # The live query filters in SQL; this re-check covers cached and
        # --wdpa-file inputs, which carry the full India extract.
        if p.get("realm") not in ("Marine", "Coastal"):
            continue
        if not name or not geom or geom.get("type") not in ("Polygon",
                                                            "MultiPolygon"):
            continue
        yr = p.get("status_yr")
        wdpa_out.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": name,
                "authority": "UNEP-WCMC WDPCA",
                "desig": p.get("desig_eng") or p.get("desig"),
                "iucn_cat": p.get("iucn_cat"),
                "no_take": p.get("no_take"),
                "valid_from": f"{int(yr)}-01-01" if yr else None,
                "valid_to": None,
                "source": "wdpa",
                "origin": f"wdpa:{p.get('site_id')}",
            },
        })
        wdpa_names.add(name.lower())
    print(f"wdpa: {len(wdpa_out)} usable marine/coastal features")

    # ---- source B --------------------------------------------------------
    try:
        osm_ids = ([s.strip() for s in args.osm_ids.split(",") if s.strip()]
                   if args.osm_ids else None)
        osm_feats = fetch_osm(bbox, ids=osm_ids)
    except RuntimeError as exc:
        print(f"osm: FAILED ({exc})")
        print("osm: continuing with WDPCA-only (re-run later to add OSM areas)")
        osm_feats = []

    # dedup within OSM by allowlist key: keep the most detailed geometry;
    # drop OSM duplicates of sites WDPCA already carries (exact name match)
    best: dict[str, dict] = {}
    for f in osm_feats:
        key = f["properties"].pop("_key")
        if f["properties"]["name"].lower() in wdpa_names:
            continue
        if key not in best or (_vertex_count(f["geometry"])
                               > _vertex_count(best[key]["geometry"])):
            best[key] = f
    osm_out = list(best.values())
    print(f"osm: {len(osm_out)} features after dedup "
          f"({len(osm_feats)} raw, {len(osm_feats) - len(osm_out)} dropped)")

    # ---- merge, simplify, write -------------------------------------------
    def _valid(geom: dict) -> bool:
        polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                 else geom["coordinates"])
        return all(len(ring) >= 4 for poly in polys for ring in poly)

    features = []
    for f in wdpa_out + osm_out:
        f["geometry"] = _simplify_geom(f["geometry"], args.tolerance)
        if not _valid(f["geometry"]):
            print(f"  dropping {f['properties']['name']!r} "
                  "(degenerate ring)")
            continue
        features.append(f)

    out = {
        "type": "FeatureCollection",
        "name": "parasail-mpa-registry",
        "attribution": ATTRIBUTION,
        "featureCount": len(features),
        "features": features,
    }
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out), encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"\nwrote {len(features)} protected areas -> {out_path} "
          f"({size_kb:.0f} KB)")
    for f in features:
        p = f["properties"]
        print(f"  [{p['source']:4s}] {p['name']}  ({f['geometry']['type']}, "
              f"{_vertex_count(f['geometry'])} pts)")
    print("\nnext: python scripts/load_mpas.py --geojson "
          f"{out_path.relative_to(root) if str(out_path).startswith(str(root)) else args.out} --truncate")


if __name__ == "__main__":
    main()

"""Build the local ocean mask used by the fish-zone layer (one-time prep).

Uses the GSHHG coastline (Wessel & Smith, public domain), intermediate
resolution: land polygons (level 1) are unioned over the India-region
bounding box and subtracted from it, leaving the OPEN-OCEAN polygons.
Coastal lagoons and backwaters (e.g. the Vembanad belt) fall on the land
side of the mainland shoreline, so zones built from this mask stay
strictly on the sea - never over the mainland or backwaters.

Downloads (or reuses) gshhg-shp-2.3.7.zip (~149 MB) into .cache/, then
writes a simplified GeoJSON next to the package data for runtime use.

Usage:
    python scripts/prepare_ocean_mask.py            # use cached download
    python scripts/prepare_ocean_mask.py --refresh  # re-download GSHHG

Requires shapely + pyshp (prep only; the API runtime imports neither).
Source: https://www.soest.hawaii.edu/pwessel/gshhg/
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

GSHHG_URL = "https://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.3.7.zip"
CACHE = Path(__file__).resolve().parent.parent / ".cache" / "gshhg-shp-2.3.7.zip"
OUT = (Path(__file__).resolve().parent.parent / "src" / "parasail" / "data"
       / "ocean_mask.geojson")
# India-region bbox with generous margin: every dashboard location's
# ~50 km suggestion grid must fall fully inside (lon_min, lat_min,
# lon_max, lat_max)
BBOX = (60.0, 0.0, 100.0, 30.0)
SIMPLIFY_DEG = 0.004   # ~450 m - finer than the 0.03-degree zone cells
RES = "i"              # GSHHG resolution: c crude, l low, i ~1 km, h ~200 m


def main() -> int:
    try:
        import shapefile                     # pyshp
        from shapely.geometry import box, shape, mapping
        from shapely.ops import unary_union
    except ImportError:
        print("prep-only deps missing: pip install shapely pyshp")
        return 1

    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-download the GSHHG archive")
    args = ap.parse_args()

    if args.refresh or not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {GSHHG_URL} ...")
        urllib.request.urlretrieve(GSHHG_URL, CACHE)
    print(f"archive: {CACHE} ({CACHE.stat().st_size / 1e6:.0f} MB)")

    prefix = f"GSHHS_shp/{RES}/GSHHS_{RES}_L1."
    extract_dir = CACHE.parent / f"gshhg_{RES}_L1"
    needed = set()
    with zipfile.ZipFile(CACHE) as zf:
        for name in zf.namelist():
            if name.startswith(prefix) and name.endswith(
                    (".shp", ".shx", ".dbf", ".prj")):
                needed.add(name)
        if not needed:
            print(f"no L1 shapefiles for resolution {RES!r} in archive")
            return 1
        if not (extract_dir / f"GSHHS_{RES}_L1.shp").exists():
            extract_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(extract_dir, members=needed)
    shp_path = extract_dir / "GSHHS_shp" / RES / f"GSHHS_{RES}_L1.shp"

    region = box(*BBOX)
    pad = box(BBOX[0] - 5, BBOX[1] - 5, BBOX[2] + 5, BBOX[3] + 5)
    reader = shapefile.Reader(str(shp_path))
    pieces = []
    for sr in reader.iterShapes():
        geom = shape(sr.__geo_interface__)
        b = geom.bounds
        if b[0] > pad.bounds[2] or b[2] < pad.bounds[0]:
            continue
        if b[1] > pad.bounds[3] or b[3] < pad.bounds[1]:
            continue
        clipped = geom.intersection(pad)
        if not clipped.is_empty:
            pieces.append(clipped)
    print(f"land polygons in region: {len(pieces)}")

    land = unary_union(pieces)
    ocean = region.difference(land).simplify(
        SIMPLIFY_DEG, preserve_topology=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(mapping(ocean), separators=(",", ":")),
                   encoding="utf-8")
    polys = getattr(ocean, "geoms", [ocean])
    verts = sum(len(p.exterior.coords) for p in polys)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB, "
          f"{len(polys)} polygon(s), ~{verts} exterior vertices)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Compare observed fishing effort (Global Fishing Watch) against the
protected-area registry and distance to shore.

What this answers, and how far it can be trusted:

  * how much observed effort fell inside protected-area boundaries;
  * how the fleet distributes across distance-from-shore bands.

Two limits must travel with any number this prints: AIS sees mostly larger
vessels (small boats are under-represented), and GFW effort is fishing
activity, not catch. So a low inside-MPA figure is a compliance signal, not
proof, and coverage of the box by MPAs is printed alongside it - "0% of
effort inside MPAs" is meaningless when the box holds no MPAs at all.

Usage:
  python scripts/analyse_effort_vs_mpa.py                      # newest extract
  python scripts/analyse_effort_vs_mpa.py --csv data/gfw_effort_....csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parasail.suggestions import (distance_to_shore_km,  # noqa: E402
                                  _load_ocean_mask, _point_in_ocean)


def point_in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def load_mpas(path: Path) -> list[tuple[str, tuple, list]]:
    """[(name, bbox, polygons)] - the bbox makes the point test cheap."""
    out = []
    for f in json.loads(path.read_text(encoding="utf-8")).get("features", []):
        geom = f.get("geometry") or {}
        polys = ([geom["coordinates"]] if geom.get("type") == "Polygon"
                 else geom.get("coordinates") or [])
        xs = [pt[0] for poly in polys for pt in poly[0]]
        ys = [pt[1] for poly in polys for pt in poly[0]]
        if xs:
            out.append((f["properties"].get("name", "?"),
                        (min(xs), min(ys), max(xs), max(ys)), polys))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=None,
                    help="effort extract (default: newest data/gfw_effort_*.csv)")
    args = ap.parse_args()

    path = args.csv or max((ROOT / "data").glob("gfw_effort_*.csv"),
                           key=lambda p: p.stat().st_mtime)
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    mpas = load_mpas(ROOT / "data" / "mpas_india_osm.geojson")
    mask = _load_ocean_mask()
    print(f"effort extract: {path.name} ({len(rows):,} records)")

    total = inside = on_ocean = 0.0
    hits: collections.Counter = collections.Counter()
    bands: collections.Counter = collections.Counter()
    for r in rows:
        h = float(r["hours"] or 0)
        lon, lat = float(r["lon"]), float(r["lat"])
        total += h
        if mask and _point_in_ocean(lon, lat, mask):
            on_ocean += h
        d = distance_to_shore_km(lat, lon, mask)
        bands["0-5 km" if d is not None and d < 5 else
              "5-20 km" if d is not None and d < 20 else
              "20-50 km" if d is not None and d < 50 else
              "50-111 km" if d is not None else ">111 km / no coast within 1 deg"] += h
        for name, (x0, y0, x1, y1), polys in mpas:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            for poly in polys:
                if point_in_ring(lon, lat, poly[0]) and not any(
                        point_in_ring(lon, lat, hole) for hole in poly[1:]):
                    inside += h
                    hits[name] += h
                    break
            break

    print(f"total observed effort : {total:,.0f} h   "
          f"({on_ocean / max(total, 1) * 100:.1f}% on the mapped ocean)")
    print(f"inside a protected area: {inside:,.0f} h "
          f"({inside / max(total, 1) * 100:.3f}% of observed effort)")
    for name, h in hits.most_common(8):
        print(f"    {h:10,.0f} h  {name[:54]}")
    if not hits:
        print("    (no effort fell inside any registry polygon in this box)")
    print("by distance from shore:")
    for band in ("0-5 km", "5-20 km", "20-50 km", "50-111 km",
                 ">111 km / no coast within 1 deg"):
        if bands[band]:
                    print(f"    {band:32s} {bands[band]:10,.0f} h "
                  f"({bands[band] / max(total, 1) * 100:5.1f}%)")
    print("\ncaveats: AIS over-represents larger vessels; effort is activity, "
          "not catch; 'inside an MPA' is a compliance signal, not proof.")


if __name__ == "__main__":
    main()

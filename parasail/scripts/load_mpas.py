"""Load marine protected area polygons into the ParaSail registry (P5).

The fail-closed MPA guard needs BOUNDARIES, not just an inventory: it
answers "is this lat/lon inside an MPA?" via PostGIS ST_Contains against
the mpa_polygons table (db/schema.sql).

Input: a GeoJSON FeatureCollection (EPSG:4326) of protected-area polygons.
Recommended sources for the geometry:
  * WDPA / Protected Planet (UNEP-WCMC) - download the India subset,
    filter marine PA types, export GeoJSON. Clear terms + attribution.
  * MPAtlas, Bhuvan (ISRO), or OSM boundary=protected_area extracts.
Cross-validate names/types/years against the Dataful MoEFCC inventory
("Year- and State-wise Name and Area of Marine Protected Areas in India")
- that dataset is an attribute inventory WITHOUT geometry and cannot serve
as the registry on its own.

Feature properties used (all optional except name):
  name        -> mpa_polygons.name        (fallback: "unnamed-<n>")
  authority   -> mpa_polygons.authority   (fallback: "wdpa")
  desig       -> mpa_polygons.desig       (legal designation)
  iucn_cat    -> mpa_polygons.iucn_cat
  no_take     -> mpa_polygons.no_take
  source      -> mpa_polygons.source      ('wdpa' | 'osm')
  valid_from  -> mpa_polygons.valid_from  (YYYY-MM-DD)
  valid_to    -> mpa_polygons.valid_to    (YYYY-MM-DD)

Build the input with scripts/fetch_mpas.py (WDPCA + OpenStreetMap merge).
Pre-existing databases are migrated in place: the geometry column is
widened to geometry(Geometry,4326) - marine PAs are MultiPolygons
(island groups) - and missing attribute columns are added.

Usage:
  python scripts/load_mpas.py --geojson data/mpas_india.geojson --truncate
  python scripts/load_mpas.py --geojson mpas.geojson
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--geojson", required=True,
                    help="GeoJSON FeatureCollection of MPA boundaries (EPSG:4326)")
    ap.add_argument("--truncate", action="store_true",
                    help="replace the whole registry instead of upserting by name")
    args = ap.parse_args()

    try:
        import psycopg
    except ImportError:
        sys.exit("psycopg is required: pip install 'psycopg[binary]'")

    features = json.loads(
        Path(args.geojson).read_text(encoding="utf-8")).get("features", [])
    if not features:
        sys.exit("no features found in the GeoJSON file")

    cfg = load_config()
    dsn = cfg.database_url.replace("postgresql+psycopg://", "postgresql://")

    rows, skipped = [], 0
    for i, f in enumerate(features):
        geom = f.get("geometry")
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            skipped += 1
            continue
        props = f.get("properties") or {}
        name = (props.get("name") or props.get("NAME")
                or props.get("wdpa_name") or f"unnamed-{i}")
        rows.append((
            str(name),
            str(props.get("authority") or props.get("AUTHORITY") or "wdpa"),
            props.get("desig"),
            props.get("iucn_cat"),
            props.get("no_take"),
            props.get("source"),
            props.get("valid_from"),
            props.get("valid_to"),
            json.dumps(geom),
        ))
    if not rows:
        sys.exit(f"no polygon features found ({skipped} skipped: no geometry)")

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        if args.truncate:
            cur.execute("TRUNCATE mpa_polygons;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mpa_polygons (
              id SERIAL PRIMARY KEY,
              name TEXT NOT NULL,
              authority TEXT,
              geometry geometry(Geometry, 4326) NOT NULL,
              valid_from DATE,
              valid_to DATE
            );
            """)
        # -- migrate pre-existing registries in place -----------------------
        # widen Polygon -> Geometry (marine PAs are MultiPolygons) and add
        # the attribute columns older schemas lack
        cur.execute(
            "SELECT type FROM geometry_columns "
            "WHERE f_table_name = 'mpa_polygons' AND f_geometry_column = 'geometry';")
        row = cur.fetchone()
        if row and row[0] == "POLYGON":
            cur.execute(
                "ALTER TABLE mpa_polygons ALTER COLUMN geometry "
                "TYPE geometry(Geometry, 4326) USING ST_Force2D(geometry);")
        for col in ("desig TEXT", "iucn_cat TEXT", "no_take TEXT",
                    "source TEXT"):
            cur.execute(f"ALTER TABLE mpa_polygons "
                        f"ADD COLUMN IF NOT EXISTS {col};")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS mpa_geom_idx "
            "ON mpa_polygons USING GIST (geometry);")
        cur.executemany(
            """
            INSERT INTO mpa_polygons (name, authority, desig, iucn_cat,
                                      no_take, source, valid_from, valid_to,
                                      geometry)
            SELECT %(name)s, %(authority)s, %(desig)s, %(iucn)s, %(no_take)s,
                   %(source)s, %(from)s, %(to)s,
                   ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326))
            WHERE NOT EXISTS (
              SELECT 1 FROM mpa_polygons WHERE name = %(name)s
            )
            """,
            [{"name": r[0], "authority": r[1], "desig": r[2], "iucn": r[3],
              "no_take": r[4], "source": r[5], "from": r[6], "to": r[7],
              "geom": r[8]} for r in rows])
        inserted = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        cur.execute("SELECT count(*) FROM mpa_polygons;")
        total = cur.fetchone()[0]
        conn.commit()
    print(f"loaded {len(rows)} polygons ({skipped} features skipped: no geometry)")
    print(f"registry now holds {total} marine protected areas")
    print("\nNext: restart/refresh - advisories will now clear points against "
          "real boundaries instead of failing closed.")


if __name__ == "__main__":
    main()

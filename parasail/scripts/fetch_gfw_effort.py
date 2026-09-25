# -*- coding: utf-8 -*-
"""Fetch AIS-derived fishing effort for the study region from Global Fishing
Watch (4Wings API) and cache it as CSV.

What this is, and what it is NOT
--------------------------------
GFW gives **effort**: hours fished, per vessel, per day, with a position,
flag and gear type. It does **not** give catch. So it cannot produce a
catch-accuracy number on its own - that needs landings (CMFRI). What it can
do, honestly:

  * correct presence-only sampling bias: background points can be weighted by
    where the fleet actually fished, so the model is not comparing
    "recorded" against "never visited";
  * describe the fleet: which flags and gears work the area, and when;
  * provide a WEAK agreement check against the advisory zones - weak because
    fishers follow fish and habit, so agreement is partly circular.

Token: GFW_API_TOKEN in parasail/.env (gitignored) or the environment.

Usage:
  python scripts/fetch_gfw_effort.py                      # last 12 months
  python scripts/fetch_gfw_effort.py --start 2026-01-01 --end 2026-03-31
  python scripts/fetch_gfw_effort.py --bbox 71.5,6.5,78.5,13.5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
OUT_DIR = ROOT / "data"
BASE = "https://gateway.api.globalfishingwatch.org/v3"
EFFORT_DATASET = "public-global-fishing-effort:latest"
BBOX = (72.0, 7.0, 78.0, 13.0)          # Kerala / SW coast of India
COLS = ["date", "lat", "lon", "hours", "flag", "geartype", "vessel_id",
        "ship_name", "vessel_type"]


def token() -> str:
    tok = os.environ.get("GFW_API_TOKEN", "").strip()
    if not tok and ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("GFW_API_TOKEN="):
                tok = line.split("=", 1)[1].strip()
    if not tok:
        raise SystemExit("GFW_API_TOKEN is not set (parasail/.env or the "
                         "environment) - see docs/PREDICTION.md")
    return tok


def fetch(start: str, end: str, bbox: tuple, *, max_pages: int = 40,
          log=print) -> list[dict]:
    """Daily effort records for the bbox over [start, end]."""
    H = {"Authorization": f"Bearer {token()}",
         "Content-Type": "application/json"}
    geo = {"type": "Polygon", "coordinates": [[
        [bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]],
        [bbox[0], bbox[3]], [bbox[0], bbox[1]]]]}
    params = {"spatial-resolution": "LOW", "temporal-resolution": "DAILY",
              "datasets[0]": EFFORT_DATASET, "date-range": f"{start},{end}",
              "format": "JSON"}
    rows: list[dict] = []
    offset = 0
    with httpx.Client(timeout=300) as client:
        for page in range(max_pages):
            r = client.post(f"{BASE}/4wings/report", params=params,
                            headers=H, json={"geojson": geo})
            r.raise_for_status()
            payload = r.json()
            entries = payload.get("entries") or []
            got = 0
            for entry in entries:
                for key, records in entry.items():
                    if not isinstance(records, list):
                        continue
                    for rec in records:
                        rows.append({
                            "date": rec.get("date"),
                            "lat": rec.get("lat"), "lon": rec.get("lon"),
                            "hours": rec.get("hours"),
                            "flag": rec.get("flag"),
                            "geartype": rec.get("geartype"),
                            "vessel_id": rec.get("vesselId"),
                            "ship_name": (rec.get("shipName") or "").strip(),
                            "vessel_type": rec.get("vesselType")})
                        got += 1
            log(f"  page {page + 1}: {got} records (total {len(rows)})")
            if got == 0 or len(entries) < 2:
                break
            offset += 1
            params["offset"] = offset
    return rows


def summarise(rows: list[dict], log=print) -> dict:
    if not rows:
        return {}
    hours = sum(float(r["hours"] or 0) for r in rows)
    days = sorted({r["date"] for r in rows if r["date"]})
    flags: dict = {}
    gears: dict = {}
    for r in rows:
        flags[r["flag"]] = flags.get(r["flag"], 0) + float(r["hours"] or 0)
        gears[r["geartype"]] = gears.get(r["geartype"], 0) + float(r["hours"] or 0)
    top = lambda d, n=5: sorted(d.items(), key=lambda kv: -kv[1])[:n]  # noqa: E731
    log(f"  records: {len(rows)} | total effort: {hours:,.0f} hours")
    log(f"  dates: {days[0]} .. {days[-1]} ({len(days)} days)")
    log("  top flags (hours): " + ", ".join(
        f"{k} {v:,.0f}" for k, v in top(flags)))
    log("  top gears (hours): " + ", ".join(
        f"{k} {v:,.0f}" for k, v in top(gears)))
    return {"records": len(rows), "hours": round(hours, 1),
            "start": days[0], "end": days[-1],
            "flags": dict(top(flags, 8)), "gears": dict(top(gears, 8))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (default: 12 months ago)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--bbox", default=",".join(str(v) for v in BBOX),
                    help="min_lon,min_lat,max_lon,max_lat")
    ap.add_argument("--max-pages", type=int, default=40)
    args = ap.parse_args()

    end = args.end or date.today().isoformat()
    start = args.start or (date.fromisoformat(end) - timedelta(days=365)).isoformat()
    bbox = tuple(float(v) for v in args.bbox.split(","))
    print(f"GFW fishing effort | {start} .. {end} | bbox {bbox}")

    rows = fetch(start, end, bbox, max_pages=args.max_pages)
    stats = summarise(rows)
    if not rows:
        raise SystemExit("no effort records returned for that window/bbox")

    OUT_DIR.mkdir(exist_ok=True)
    # include the bbox in the name: the same window over a different box is a
    # different extract, and silently overwriting one with the other loses data
    tag = hashlib.sha1(",".join(f"{v:g}" for v in bbox).encode()).hexdigest()[:6]
    csv_path = OUT_DIR / f"gfw_effort_{start}_{end}_{tag}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    (OUT_DIR / f"gfw_effort_{start}_{end}_{tag}.json").write_text(
        json.dumps(stats, indent=2), encoding="utf-8")
    print(f"wrote {csv_path.relative_to(ROOT)} ({len(rows)} rows)")
    print("NOTE: effort only - no catch. Catch-level accuracy still needs "
          "landings (CMFRI). Use this for sampling-bias correction and "
          "fleet description.")


if __name__ == "__main__":
    main()

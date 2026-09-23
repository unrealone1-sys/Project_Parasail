# -*- coding: utf-8 -*-
"""Train the habitat-suitability model for the suggested-fish layer.

Replaces the hand-set thermal envelope with a presence-vs-background model
that has a measured, cross-validated skill score. Everything here is
reproducible from open data:

  presences   OBIS occurrence records for the registry species (bbox-filtered)
  background  OBIS records of the same taxonomic class in the same bbox
              ("target-group background" - the standard presence-only
              protocol; it keeps presence and background on one environmental
              distribution and one set of derived fields)

Environment comes from OBIS's pre-joined reanalysis fields, because the open
alternative (Open-Meteo marine) carries no data before ~2022-12:

  sst                -> feature sst_c
  shoredistance (m)  -> feature distance_to_shore_km
  date_mid           -> feature month_sin / month_cos

sss and bathymetry are kept in the training table as DIAGNOSTIC columns only.
They are deliberately NOT features: neither can be supplied on the serving
path without a new data source, and a feature that exists in training but not
at inference is how models silently break. The serving path reproduces
distance_to_shore_km from the ocean mask and takes sst from Open-Meteo live,
so one documented caveat remains - the SST product differs between training
(reanalysis) and serving (forecast). It is recorded in the metrics file.

Skill is estimated with spatial-block cross-validation (N/S x inshore/
offshore), and the current envelope is scored on the identical folds, so the
adoption decision is a like-for-like comparison rather than an assertion.

Usage:
  python scripts/train_habitat.py                     # all registry species
  python scripts/train_habitat.py --species Sardinella\\ longiceps
  python scripts/train_habitat.py --min-records 30 --seed 7
Outputs (both gitignored):
  data/habitat_training_<slug>.csv   the training table actually used
  data/habitat_metrics.json          per-species metrics + adoption decision
  models/habitat_<slug>.joblib       artifact for the serving path
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parasail.config import load_config                      # noqa: E402
from parasail.models.habitat import (FEATURE_ORDER, HabitatModel,   # noqa: E402
                                     build_features)
from parasail.suggestions import thermal_suitability         # noqa: E402

OBIS = "https://api.obis.org/v3/occurrence"
DEFAULT_BBOX = "POLYGON((72 7,78 7,78 13,72 13,72 7))"   # SW coast of India
MIN_TRAINING_RECORDS = 50        # below this a model would be meaningless
INSHORE_KM = 50.0                # block split: shelf vs slope
ADOPT_MARGIN = 0.02              # model must beat the envelope by this AUC


# --------------------------------------------------------------------------- #
# data acquisition
# --------------------------------------------------------------------------- #
def obis_fetch(client: httpx.Client, *, bbox: str, size: int, **params) -> dict:
    r = client.get(OBIS, params={"geometry": bbox, "size": size, **params},
                   timeout=120)
    r.raise_for_status()
    return r.json()


def usable(rec: dict) -> bool:
    """A record needs all three features - sst, distance to shore, month."""
    return (rec.get("sst") is not None
            and rec.get("shoredistance") is not None
            and rec.get("date_mid") is not None
            and rec.get("decimalLatitude") is not None
            and rec.get("decimalLongitude") is not None)


def row_from(rec: dict, label: int, source: str) -> dict:
    mid = rec["date_mid"]
    try:                                     # OBIS date_mid is epoch millis
        dt = datetime.fromtimestamp(float(mid) / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        dt = None
    return {
        "label": label,
        "lat": float(rec["decimalLatitude"]),
        "lon": float(rec["decimalLongitude"]),
        "month": dt.month if dt else None,
        "sst_c": float(rec["sst"]),
        "distance_to_shore_km": float(rec["shoredistance"]) / 1000.0,
        "sss": rec.get("sss"),               # diagnostic only
        "bathymetry_m": rec.get("bathymetry"),  # diagnostic only
        "source": source,
        "dataset_id": rec.get("dataset_id") or rec.get("datasetName"),
    }


def thin_presences(rows: list[dict], res_deg: float = 0.1) -> list[dict]:
    """Spatial thinning: keep one record per (cell, month).

    Raw OBIS presences are dominated by one or two surveys, so a single
    cruise can contribute dozens of near-identical rows and the model then
    learns the cruise's sampling signature instead of a habitat response.
    Thinning makes each retained record a distinct place-and-time.
    """
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: (r["lat"], r["lon"])):
        key = (round(r["lat"] / res_deg), round(r["lon"] / res_deg), r["month"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def collect_species(client: httpx.Client, name: str, bbox: str,
                    max_background: int, rng: random.Random,
                    log=print) -> tuple[list[dict], str | None, dict]:
    """Presences (thinned) plus a dataset-matched target-group background.

    The background is drawn first from the SAME datasets as the presences -
    other taxa recorded on the same surveys - so both classes share one
    sampling effort and one environmental product. Only if that cannot fill
    the quota is the wider class pool used, and the mix is reported.
    """
    diag: dict = {}
    pres_raw = obis_fetch(client, bbox=bbox, size=1000, scientificname=name)
    raw_rows = [row_from(r, 1, "obis") for r in pres_raw.get("results", [])
                if usable(r)]
    raw_rows = [r for r in raw_rows if r["month"]]
    diag["n_presence_raw"] = len(raw_rows)
    pres_rows = thin_presences(raw_rows)
    diag["n_presence_thinned"] = len(pres_rows)
    diag["top_datasets"] = [d for d, _ in
                            collections.Counter(
                                r["dataset_id"] for r in raw_rows
                            ).most_common(3)]
    log(f"  presences: {len(raw_rows)} raw -> {len(pres_rows)} after thinning "
        f"(0.1 deg x month)")

    if not pres_rows:
        return [], "no usable presence records", diag

    # 1) background from the presences' own datasets (matched effort)
    wanted = max_background
    matched: list[dict] = []
    for ds, count in collections.Counter(
            r["dataset_id"] for r in raw_rows).most_common(4):
        if not ds or len(matched) >= wanted:
            continue
        try:
            resp = obis_fetch(client, bbox=bbox, size=1000, datasetid=ds)
        except Exception as exc:                      # noqa: BLE001
            log(f"    dataset {ds[:8]}... unavailable ({exc})")
            continue
        rows = [row_from(r, 0, "obis:matched")
                for r in resp.get("results", [])
                if usable(r) and r.get("scientificName") != name]
        rows = [r for r in rows if r["month"]]
        matched.extend(rows)
        log(f"    matched background from dataset {ds[:8]}...: {len(rows)}")
    matched = thin_presences(matched)
    diag["n_background_matched"] = len(matched)

    # 2) top up from the class pool if the matched frame is too small
    pooled: list[dict] = []
    if len(matched) < wanted:
        first = raw_rows[0]
        for param, value in (("class", first.get("class")),
                             ("phylum", first.get("phylum"))):
            if not value:
                continue
            resp = obis_fetch(client, bbox=bbox, size=1000, **{param: value})
            pooled = [row_from(r, 0, f"obis:pooled:{param}")
                      for r in resp.get("results", [])
                      if usable(r) and r.get("scientificName") != name]
            pooled = [r for r in pooled if r["month"]]
            if len(pooled) >= wanted:
                break
        pooled = thin_presences(pooled)
        diag["n_background_pooled"] = len(pooled)

    pool = matched + pooled
    if len(pool) > wanted:
        pool = rng.sample(pool, wanted)
    if not pool:
        return pres_rows, "no background pool available", diag
    log(f"  background: {len(pool)} ({diag.get('n_background_matched', 0)} "
        f"dataset-matched + {diag.get('n_background_pooled', 0)} pooled, "
        f"ratio {len(pool)/len(pres_rows):.1f}x)")
    return pres_rows + pool, None, diag


# --------------------------------------------------------------------------- #
# features / blocks / metrics
# --------------------------------------------------------------------------- #
def feature_matrix(rows: list[dict]) -> np.ndarray:
    return np.vstack([
        build_features(sst_c=r["sst_c"],
                       distance_to_shore_km=r["distance_to_shore_km"],
                       month=r["month"]) for r in rows])


def assign_blocks(rows: list[dict]) -> None:
    """Spatial blocks (N/S x inshore/offshore) so neighbours cannot leak
    between folds - the usual guard against inflated presence-only scores."""
    lats = sorted(r["lat"] for r in rows)
    lat_split = lats[len(lats) // 2]
    for r in rows:
        r["block"] = f"{'N' if r['lat'] >= lat_split else 'S'}" \
                     f"{'I' if r['distance_to_shore_km'] < INSHORE_KM else 'O'}"


def auc(y: np.ndarray, score: np.ndarray) -> float:
    """Rank-based AUC (Mann-Whitney), NaN when one class is absent."""
    pos, neg = y == 1, y == 0
    if not pos.any() or not neg.any():
        return float("nan")
    order = np.argsort(score)
    ranks = np.empty(len(score), dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    # average ranks for ties
    _, inv, counts = np.unique(score, return_inverse=True, return_counts=True)
    for k, c in enumerate(counts):
        if c > 1:
            ranks[inv == k] = ranks[inv == k].mean()
    n1, n0 = int(pos.sum()), int(neg.sum())
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def tss(y: np.ndarray, score: np.ndarray, threshold: float) -> float:
    pred = score >= threshold
    tp = int(((y == 1) & pred).sum()); fn = int(((y == 1) & ~pred).sum())
    tn = int(((y == 0) & ~pred).sum()); fp = int(((y == 0) & pred).sum())
    sens = tp / (tp + fn) if tp + fn else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    return float(sens + spec - 1)


def precision_at_k(y: np.ndarray, score: np.ndarray, frac: float = 0.1) -> float:
    k = max(1, int(round(len(y) * frac)))
    top = np.argsort(-score)[:k]
    return float((y[top] == 1).mean())


def best_threshold(y: np.ndarray, score: np.ndarray) -> float:
    cands = np.unique(np.round(score, 3))
    if len(cands) > 120:                     # keep the sweep cheap
        cands = np.quantile(cands, np.linspace(0, 1, 120))
    best, best_t = -1.0, 0.5
    for t in cands:
        v = tss(y, score, float(t))
        if v > best:
            best, best_t = v, float(t)
    return best_t


def leave_one_dataset_out(rows: list[dict], X: np.ndarray, y: np.ndarray, *,
                          min_records: int = 8, seed: int = 42,
                          log=print) -> list[dict]:
    """Hold out every presence from one survey at a time.

    This is the honest test of whether the score reflects habitat or the
    sampling signature of the surveys the model was trained on: a model that
    learned "which cruise is this" collapses when the cruise is new.
    The test set is balanced with background rows drawn from outside training.
    """
    counts = collections.Counter(r["dataset_id"] for r, lbl in zip(rows, y)
                                 if lbl == 1)
    folds = [d for d, c in counts.most_common() if d and c >= min_records][:3]
    rng = random.Random(seed)
    bg_idx = [i for i, lbl in enumerate(y) if lbl == 0]
    out: list[dict] = []
    for ds in folds:
        test_pres = np.array([(lbl == 1 and r["dataset_id"] == ds)
                              for r, lbl in zip(rows, y)])
        n_bg = min(len(bg_idx), max(30, int(test_pres.sum()) * 3))
        if not n_bg:
            continue
        bg_pick = set(rng.sample(bg_idx, n_bg))
        test_idx = np.array(list(np.nonzero(test_pres)[0]) + sorted(bg_pick))
        train_idx = np.array([i for i in range(len(y)) if i not in set(test_idx)])
        if len(train_idx) < 20 or y[train_idx].min() == y[train_idx].max():
            continue
        m = HabitatModel(n_estimators=300, max_depth=12, seed=seed)
        m.fit(X[train_idx], y[train_idx])
        score = m.suitability(X[test_idx])
        out.append({"dataset": str(ds)[:8], "n_test_presence": int(test_pres.sum()),
                    "auc": round(auc(y[test_idx], score), 4)})
        log(f"  held-out survey {str(ds)[:8]}: {int(test_pres.sum())} presences, "
            f"AUC {out[-1]['auc']:.3f}")
    return out


# --------------------------------------------------------------------------- #
# effort-aware training (the path that removes the presence-only ceiling)
# --------------------------------------------------------------------------- #
EFFORT_COLUMNS = ("date", "lat", "lon", "catch_kg", "effort_hours",
                  "sst_c", "distance_to_shore_km")


def load_effort_csv(path: Path, species: str | None = None) -> list[dict]:
    """Landings/effort export -> labelled rows.

    Required columns: date, lat, lon, catch_kg, effort_hours, sst_c,
    distance_to_shore_km (optional `species`, used to filter rows).

    Why this matters more than any modelling change: a trip that applied
    effort and caught none of the target species is a TRUE ABSENCE, and the
    open occurrence record cannot supply one. Absences are what turn a
    habitat guess into a catch prediction; `effort_hours` weights each row by
    how much evidence it carries.
    """
    import csv as _csv
    rows: list[dict] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        reader = _csv.DictReader(fh)
        missing = [c for c in EFFORT_COLUMNS
                   if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit("effort CSV is missing column(s): "
                             + ", ".join(missing))
        for raw in reader:
            if species and raw.get("species") and raw["species"] != species:
                continue
            try:
                catch = float(raw["catch_kg"])
                effort = float(raw["effort_hours"])
                lat = float(raw["lat"])
                lon = float(raw["lon"])
                sst = float(raw["sst_c"])
                dist = float(raw["distance_to_shore_km"])
                dt = datetime.fromisoformat(str(raw["date"])[:10])
            except (TypeError, ValueError):
                continue
            if effort <= 0:
                continue
            rows.append({
                "label": 1 if catch > 0 else 0,
                "weight": max(effort, 0.1),
                "cpue": catch / effort,
                "lat": lat, "lon": lon, "month": dt.month,
                "sst_c": sst, "distance_to_shore_km": dist,
                "date": dt.date().isoformat(), "source": "effort-export"})
    return rows


def spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    """Rank correlation without scipy: Pearson on ranks. This is the number a
    fisher actually cares about - does the score track what was caught?"""
    if len(a) < 5 or np.all(a == a[0]) or np.all(b == b[0]):
        return None
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return round(float((ra * rb).sum() / denom), 4) if denom else None


def train_from_effort(cfg, name: str, rows: list[dict], *, seed: int,
                      out_dir: Path, model_dir: Path, log=print) -> dict:
    """Train, validate and (only if it earns it) publish from effort data.

    Cross-validation is by TIME block, not space: effort records are dense and
    spatially autocorrelated, so spatial folds leak. Holding out whole date
    ranges asks the operational question instead - would this have been right
    on days it had never seen?
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    entry = cfg.species_entry(name) or {}
    lo, hi = entry.get("preferred_sst_c", [22.0, 29.0])
    base = {"species": name, "slug": slug, "source": "effort-export",
            "generated_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds"),
            "features": FEATURE_ORDER,
            "method_note": ("effort-weighted presence/absence with time-block "
                            "cross-validation - the catch-level path")}
    n_pres = sum(1 for r in rows if r["label"] == 1)
    n_abs = len(rows) - n_pres
    log(f"  effort rows: {len(rows)} ({n_pres} positive, {n_abs} true absences)")
    if n_pres < 20 or n_abs < 20:
        reason = (f"needs at least 20 rows of each kind; have {n_pres} "
                  f"positive and {n_abs} absent")
        log(f"  -> no model: {reason}")
        return {**base, "n_presence": n_pres, "n_absence": n_abs,
                "adopted": False, "reason": reason, "model": None}

    rows = sorted(rows, key=lambda r: r["date"])
    X = feature_matrix(rows)
    y = np.array([r["label"] for r in rows])
    w = np.array([r["weight"] for r in rows])
    cpue = np.array([r["cpue"] for r in rows])
    folds = np.array_split(np.arange(len(rows)), 4)       # time-ordered
    hyper = dict(cfg.raw.get("models", {}).get("habitat", {}))

    oof = np.full(len(y), np.nan)
    for test_idx in folds:
        train_idx = np.setdiff1d(np.arange(len(y)), test_idx)
        if len(train_idx) < 10 or y[train_idx].min() == y[train_idx].max():
            continue
        m = HabitatModel(n_estimators=hyper.get("n_estimators", 400),
                         max_depth=hyper.get("max_depth", 12), seed=seed)
        m.clf.fit(X[train_idx], y[train_idx], sample_weight=w[train_idx])
        oof[test_idx] = m.suitability(X[test_idx])
    have = ~np.isnan(oof)
    auc_effort = auc(y[have], oof[have])
    env_scores = np.array([thermal_suitability(r["sst_c"], lo, hi)
                           for r in rows])
    auc_env = auc(y[have], env_scores[have])
    rho = spearman(oof[have], cpue[have])

    final = HabitatModel(n_estimators=hyper.get("n_estimators", 400),
                         max_depth=hyper.get("max_depth", 12), seed=seed)
    final.clf.fit(X, y, sample_weight=w)
    try:
        from sklearn.isotonic import IsotonicRegression
        final.calibrator = IsotonicRegression(out_of_bounds="clip").fit(
            oof[have], y[have])
    except Exception as exc:                             # noqa: BLE001
        log(f"  calibration skipped: {exc}")
    thr = best_threshold(y, final.suitability(X))
    adopted = bool(auc_effort >= 0.65 and rho is not None and rho >= 0.20
                   and auc_effort > auc_env + ADOPT_MARGIN)
    log(f"  AUC {auc_effort:.3f} vs envelope {auc_env:.3f} | "
        f"Spearman(score, CPUE) {rho} | "
        f"{'ADOPTED' if adopted else 'not adopted'}")
    metrics = {"auc": round(auc_effort, 4), "auc_envelope": round(auc_env, 4),
               "spearman_score_cpue": rho,
               "precision_at_10pct": round(
                   precision_at_k(y, final.suitability(X)), 4),
               "threshold": round(thr, 3), "n_presence": n_pres,
               "n_absence": n_abs,
               "folds": [{"block": f"time-{i + 1}", "n": int(len(t))}
                         for i, t in enumerate(folds)]}
    if adopted:
        final.metadata = {"species": name, "n_presence": n_pres,
                          "n_background": n_abs, "threshold": round(thr, 3),
                          "trained_at": base["generated_at"]}
        final.save(str(model_dir / f"habitat_{slug}.joblib"))
        log(f"  artifact: models/habitat_{slug}.joblib (effort-trained)")
    return {**base, "n_presence": n_pres, "n_absence": n_abs,
            "adopted": adopted, "model": metrics,
            "reason": None if adopted else
            ("needs AUC >= 0.65, Spearman >= 0.20 and a margin over the "
             f"envelope (got AUC {auc_effort:.3f}, rho {rho})")}


# --------------------------------------------------------------------------- #
# training
# --------------------------------------------------------------------------- #
def train_species(cfg, client: httpx.Client, name: str, *, bbox: str,
                  min_records: int, seed: int, out_dir: Path,
                  model_dir: Path, n_estimators: int | None = None,
                  max_depth: int | None = None, log=print) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    entry = cfg.species_entry(name)
    lo, hi = (entry or {}).get("preferred_sst_c", [22.0, 29.0])
    rng = random.Random(seed)
    log(f"\n{name}  (envelope band {lo}-{hi} C)")

    rows, problem, diag = collect_species(client, name, bbox,
                                          max_background=2 * 200, rng=rng,
                                          log=log)
    base = {"species": name, "slug": slug, "generated_at":
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "features": FEATURE_ORDER, "envelope_band_c": [lo, hi],
            "training_data": diag,
            "train_serve_note": ("training environment from OBIS reanalysis "
                                 "fields; serving environment from Open-Meteo "
                                 "live - documented product shift"),
            "caveats": [
                "presence-only data: the background approximates absences, so "
                "scores are habitat discrimination, not catch probability",
                "OBIS records carry sampling bias; thinning (0.1 deg x month) "
                "and dataset-matched background reduce, but cannot remove, it",
                "a held-out SURVEY (leave-one-dataset-out) is the honest test "
                "of whether the signal is habitat or cruise signature"]}
    n_pres = sum(1 for r in rows if r["label"] == 1)
    if problem or n_pres < min_records:
        reason = problem or (f"only {n_pres} usable presences after thinning; "
                             f"minimum is {min_records}")
        log(f"  -> no model: {reason}")
        return {**base, "n_presence": n_pres, "adopted": False,
                "reason": reason, "model": None, "envelope": None}

    assign_blocks(rows)
    X, y = feature_matrix(rows), np.array([r["label"] for r in rows])
    blocks = sorted({r["block"] for r in rows})
    log("  blocks: " + str({b: sum(1 for r in rows if r["block"] == b)
                            for b in blocks}))

    # out-of-fold predictions (model) and envelope scores on identical rows
    oof_model = np.full(len(y), np.nan)
    oof_env = np.array([thermal_suitability(r["sst_c"], lo, hi) for r in rows])
    hyper = dict(cfg.raw.get("models", {}).get("habitat", {}))
    if n_estimators is not None:
        hyper["n_estimators"] = n_estimators
    if max_depth is not None:
        hyper["max_depth"] = max_depth
    fold_rows = []
    for b in blocks:
        test = np.array([r["block"] == b for r in rows])
        train = ~test
        if y[train].min() == y[train].max() or not test.any():
            fold_rows.append({"block": b, "skipped": "single class in train"})
            continue
        m = HabitatModel(n_estimators=hyper.get("n_estimators", 400),
                         max_depth=hyper.get("max_depth", 12), seed=seed)
        m.fit(X[train], y[train])
        oof_model[test] = m.suitability(X[test])
        fold_rows.append({"block": b, "n_test": int(test.sum()),
                          "auc_model": round(auc(y[test], oof_model[test]), 4),
                          "auc_envelope": round(auc(y[test], oof_env[test]), 4)})
    have = ~np.isnan(oof_model)
    auc_model = auc(y[have], oof_model[have])
    auc_env = auc(y[have], oof_env[have])

    # final model on everything, calibrated on the out-of-fold predictions
    final = HabitatModel(n_estimators=hyper.get("n_estimators", 400),
                         max_depth=hyper.get("max_depth", 12), seed=seed)
    final.fit(X, y)
    try:
        from sklearn.isotonic import IsotonicRegression
        cal = IsotonicRegression(out_of_bounds="clip")
        cal.fit(oof_model[have], y[have])
        final.calibrator = cal
    except Exception as exc:                     # noqa: BLE001
        log(f"  calibration skipped: {exc}")
    final.metadata = {"species": name, "n_presence": n_pres,
                      "n_background": len(rows) - n_pres,
                      "threshold": None,          # set below, once tuned
                      "held_out_survey_min_auc": None,
                      "trained_at": datetime.now(timezone.utc)
                      .isoformat(timespec="seconds")}

    cal_scores = final.suitability(X)
    thr = best_threshold(y, cal_scores)
    loso = leave_one_dataset_out(rows, X, y, seed=seed, log=log)
    loso_min = min((f["auc"] for f in loso), default=None)
    model_metrics = {
        "auc": round(auc_model, 4), "tss": round(tss(y, cal_scores, thr), 4),
        "precision_at_10pct": round(precision_at_k(y, cal_scores), 4),
        "threshold": round(thr, 3), "folds": fold_rows,
        "held_out_survey": loso, "held_out_survey_min_auc": loso_min}
    env_thr = best_threshold(y, oof_env)
    env_metrics = {
        "auc": round(auc_env, 4), "tss": round(tss(y, oof_env, env_thr), 4),
        "precision_at_10pct": round(precision_at_k(y, oof_env), 4),
        "threshold": round(env_thr, 3)}
    beats_envelope = auc_model > auc_env + ADOPT_MARGIN
    generalises = loso_min is None or loso_min >= 0.60
    adopted = bool(beats_envelope and generalises)
    log(f"  AUC model {auc_model:.3f} vs envelope {auc_env:.3f}"
        + ("" if beats_envelope else " (does not beat the envelope)")
        + ("" if generalises else " (fails the held-out-survey check)"))
    log(f"  {'ADOPTED' if adopted else 'NOT adopted - envelope kept'} | "
        f"TSS {model_metrics['tss']:+.3f}  precision@10% "
        f"{model_metrics['precision_at_10pct']:.3f}  threshold "
        f"{model_metrics['threshold']}")
    reason = None
    if not adopted:
        reason = ("model AUC {:.3f} did not beat the envelope {:.3f} by {:.2f}"
                  .format(auc_model, auc_env, ADOPT_MARGIN) if not beats_envelope
                  else "did not generalise to a held-out survey (min AUC {})"
                  .format(loso_min))

    # table + artifact
    csv_path = out_dir / f"habitat_training_{slug}.csv"
    cols = ["species", "label", "lat", "lon", "month", "sst_c",
            "distance_to_shore_km", "sss", "bathymetry_m", "source",
            "dataset_id", "block"]
    with csv_path.open("w", encoding="utf-8") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(
                str(r.get(c, "")) if c != "species" else name
                for c in cols) + "\n")

    if adopted:
        final.metadata["threshold"] = round(thr, 3)
        final.metadata["held_out_survey_min_auc"] = loso_min
        final.save(str(model_dir / f"habitat_{slug}.joblib"))
        log(f"  artifact: models/habitat_{slug}.joblib")

    return {**base, "n_presence": n_pres,
            "n_background": len(rows) - n_pres, "n_rows": len(rows),
            "blocks": {b: sum(1 for r in rows if r["block"] == b)
                       for b in blocks},
            "adopted": adopted, "reason": reason,
            "model": model_metrics, "envelope": env_metrics,
            "training_table": str(csv_path.relative_to(ROOT))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--species", action="append", default=None,
                    help="registry species to train (default: all)")
    ap.add_argument("--bbox", default=DEFAULT_BBOX)
    ap.add_argument("--min-records", type=int, default=MIN_TRAINING_RECORDS)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-estimators", type=int, default=None,
                    help="override models.habitat.n_estimators")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="override models.habitat.max_depth (shallow suits "
                         "small presence samples)")
    ap.add_argument("--effort", type=Path, default=None,
                    help="landings/effort CSV (columns: date, lat, lon, "
                         "catch_kg, effort_hours, sst_c, distance_to_shore_km; "
                         "optional species). When given, training uses TRUE "
                         "ABSENCES and effort weights instead of an OBIS "
                         "background - the catch-level path")
    args = ap.parse_args()

    cfg = load_config()
    names = args.species or [s["scientific_name"]
                             for s in cfg.raw.get("species", [])]
    out_dir = ROOT / "data"
    model_dir = ROOT / "models"
    out_dir.mkdir(exist_ok=True)
    model_dir.mkdir(exist_ok=True)

    report = {"generated_at": datetime.now(timezone.utc).isoformat(
        timespec="seconds"), "bbox": args.bbox, "min_records": args.min_records,
        "seed": args.seed, "species": {}}
    if args.effort:
        effort_rows = load_effort_csv(args.effort)
        print(f"effort export: {len(effort_rows)} usable rows from {args.effort}")
        report["source"] = "effort-export"
        for name in names:
            report["species"][name] = train_from_effort(
                cfg, name, effort_rows, seed=args.seed, out_dir=out_dir,
                model_dir=model_dir)
    else:
      with httpx.Client() as client:
        for name in names:
            report["species"][name] = train_species(
                cfg, client, name, bbox=args.bbox,
                min_records=args.min_records, seed=args.seed,
                out_dir=out_dir, model_dir=model_dir,
                n_estimators=args.n_estimators, max_depth=args.max_depth)

    metrics_path = out_dir / "habitat_metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    adopted = [n for n, r in report["species"].items() if r["adopted"]]
    print(f"\nmetrics -> {metrics_path.relative_to(ROOT)}")
    print(f"models adopted for: {adopted or 'none'}")
    print("species without a model keep the thermal envelope (by design)")
    if not adopted:
        print("NOTE: no species cleared the adoption bar - the envelope "
              "remains the served method, and that is the reported result.")


if __name__ == "__main__":
    main()

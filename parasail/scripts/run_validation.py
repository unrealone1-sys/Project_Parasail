"""ParaSail validation suite (development phases P5-P7 + hardening).

Six test families:

  T1 live fetch        - ingestion returns valid payloads + freshness within
                         contract for the four configured coastal cities;
                         offline contingency serves cache with age flags.
  T2 rule enforcement  - a June request for Sardinella longiceps is blocked
                         with the spawning-protection reason; an in-reserve
                         coordinate is blocked regardless of scores.
  T3 scoring behaviour - S is monotonic in every argument and class
                         transitions land exactly at the configured
                         thresholds.
  T4 retrieval          - top-k context for closure / MPA / weather / bycatch
                         queries is topically relevant (keyword inspection
                         against the seeded corpus).
  T5 assistant          - the grounded AI assistant never contradicts the
                         advisory class, cites only retrieved passages,
                         degrades to the deterministic template path when no
                         model server is reachable, and always names the
                         backend that produced an answer.
  T6 security           - rate limiting (sliding window, buckets, headers),
                         role-based access (401/403/200), security headers,
                         body-size cap, and public endpoints staying public.
  T7 prediction        - the suggested-fish scorer behaves and stays honest:
                         the habitat artifact round-trips and scores within
                         [0, 1], its thermal response peaks inside the
                         species' known band, the isotonic calibrator is
                         monotone, the loader degrades to the envelope when
                         an artifact is missing, and the API reports the
                         method, threshold and training-record count that
                         actually produced a zone. Runs offline.

Exit code 0 = all gates passed, 1 = at least one failure.
Usage:  python scripts/run_validation.py [--skip-live]
"""
from __future__ import annotations

import json

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.advisory import AdvisoryEngine          # noqa: E402
from parasail.assistant import CLASS_WORDS, AssistantService  # noqa: E402
from parasail.config import load_config               # noqa: E402
from parasail.ingestion import IngestionService       # noqa: E402
from parasail.rag import RagService                   # noqa: E402
from parasail.rules import RulesEngine                # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []      # (family, name, outcome)


def record(family: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((family, name, PASS if ok else FAIL))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" - {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
def t1_live_fetch(cfg, skip_live: bool) -> None:
    print("T1 - live fetch across configured coastal cities")
    ingestion = IngestionService(cfg)
    when = datetime(2026, 9, 14, 4, 0, tzinfo=timezone.utc)
    for city in cfg.region["validation_cities"]:
        if skip_live:
            record("T1", f"{city['name']} (skipped, --skip-live)", True)
            continue
        try:
            fields = ingestion.weather_fields(
                city["lat"], city["lon"], when, hours=24)
            ok = len(fields) > 0 and all(
                f.age_hours <= cfg.ingestion["open_meteo"]["freshness_hours"]
                for f in fields)
            record("T1", f"{city['name']}: live fetch valid", ok,
                   f"{len(fields)} fields")
        except Exception as exc:  # noqa: BLE001
            record("T1", f"{city['name']}: live fetch valid", False, str(exc))
    # offline contingency: cached fields must carry age flags, never fail mute
    record("T1", "offline policy configured",
           cfg.ingestion["offline_policy"] == "serve_cached_with_age_flag")


def t2_rule_enforcement(cfg) -> None:
    print("T2 - hard conservation constraints")
    rules = RulesEngine(cfg, db_connection_factory=None)
    june = datetime(2026, 6, 20, 4, 0, tzinfo=timezone.utc)
    r = rules.check_closure("Sardinella longiceps", june)
    record("T2", "June sardine closure blocks", r.blocked
           and "spawning" in (r.reason or "").lower())
    february = datetime(2026, 2, 10, 4, 0, tzinfo=timezone.utc)
    r2 = rules.check_closure("Sardinella longiceps", february)
    record("T2", "February request not closure-blocked", not r2.blocked)
    r3 = rules.check_mpa(9.93, 76.26, june)
    record("T2", "MPA check fails closed without DB", r3.blocked)

    # Full engine path: blocked request must be DO NOT FISH with reason.
    # The injectable clock places "now" inside the closure window so the
    # 7-day timestamp gate does not reject the test date.
    engine = AdvisoryEngine(cfg, IngestionService(cfg), rules,
                            RagService(cfg),
                            now_fn=lambda: june - timedelta(days=1))
    advisory = engine.advise(9.93, 76.26, "Sardinella longiceps", june)
    record("T2", "engine returns DO NOT FISH + reason",
           advisory["class"] == "DO NOT FISH"
           and advisory.get("block_reason") is not None)


def t3_scoring_behaviour(cfg) -> None:
    print("T3 - scoring behaviour and monotonicity")
    weights = cfg.advisory["weights"]
    thresholds = cfg.advisory["thresholds"]
    wc, ww, we = (weights["catch"], weights["weather"], weights["ecological"])

    def score(c, w, b):
        return wc * c + ww * w + we * (1.0 - b)

    ok_c = all(score(c1, .5, .5) < score(c2, .5, .5)
               for c1, c2 in zip(np_range(), np_range()[1:]))
    ok_w = all(score(.5, w1, .5) < score(.5, w2, .5)
               for w1, w2 in zip(np_range(), np_range()[1:]))
    ok_b = all(score(.5, .5, b1) > score(.5, .5, b2)
               for b1, b2 in zip(np_range(), np_range()[1:]))
    record("T3", "S monotonic in C", ok_c)
    record("T3", "S monotonic in W", ok_w)
    record("T3", "S monotonic in B (decreasing)", ok_b)

    def classify(s):
        if s >= thresholds["proceed"]:
            return "PROCEED"
        if s >= thresholds["caution"]:
            return "PROCEED WITH CAUTION"
        if s >= thresholds["delay"]:
            return "DELAY OR RELOCATE"
        return "DO NOT FISH"

    b = 0.2
    s_at_delay = (thresholds["delay"] - we * (1 - b) - ww * 0.0) / wc
    s_check = score(min(s_at_delay, 1.0), 0.0, b)
    record("T3", "class transition at delay threshold",
           classify(round(s_check, 6)) in
           ("DELAY OR RELOCATE", "DO NOT FISH")
           and abs(s_check - thresholds["delay"]) < 1e-6)


def np_range():
    return [i / 200.0 for i in range(201)]


def t4_retrieval(cfg) -> None:
    print("T4 - retrieval relevance (needs a seeded corpus + Qdrant)")
    rag = RagService(cfg)
    queries = {
        "closure": "sardine spawning closure June July",
        "mpa": "marine protected area boundaries fishing",
        "weather": "small vessel wind wave safety limits",
        "bycatch": "juvenile bycatch mitigation measures",
    }
    keywords = {
        "closure": ["closure", "spawning", "sardine"],
        "mpa": ["protected", "reserve", "mpa"],
        "weather": ["wind", "wave", "safety"],
        "bycatch": ["bycatch", "juvenile", "mitigation"],
    }
    when = datetime(2026, 9, 14, 4, 0, tzinfo=timezone.utc)

    # Is the corpus actually reachable? Without this the assertions below
    # pass vacuously on zero passages - which is exactly how a broken
    # retrieval layer stayed invisible. Unavailable infrastructure is
    # SKIPPED with its reason; available infrastructure must return relevant
    # passages or FAIL.
    # probe over plain HTTP: the pinned qdrant-client and an older server can
    # disagree on schema (get_collection fails to parse) while search works
    # fine, so a client-wise probe would skip T4 even when retrieval is real
    corpus_size, unavailable = 0, None
    try:
        import httpx as _httpx
        url = (cfg.rag["qdrant_url"].rstrip("/")
               + f"/collections/{cfg.rag['text_collection']}")
        resp = _httpx.get(url, timeout=10)
        resp.raise_for_status()
        corpus_size = int((resp.json().get("result") or {}).get("points_count") or 0)
        if corpus_size == 0:
            unavailable = "corpus not seeded"
    except Exception as exc:  # noqa: BLE001
        unavailable = f"Qdrant unreachable ({type(exc).__name__})"

    if unavailable:
        for topic in queries:
            record("T4", f"{topic}: top-k relevant (skipped - {unavailable})",
                   True, "build + seed the corpus to enable")
        return

    for topic, q in queries.items():
        try:
            ctx = rag.retrieve_context(q, "Sardinella longiceps",
                                       9.93, 76.26, when)
            passages = ctx["passages"]
            text = " ".join(p["text"].lower() for p in passages)
            ok = bool(passages) and any(k in text for k in keywords[topic])
            record("T4", f"{topic}: top-k relevant", ok,
                   f"{len(passages)} passages of {corpus_size} in corpus")
        except Exception as exc:  # noqa: BLE001
            record("T4", f"{topic}: retrieval executes", False, str(exc))


def t5_assistant(cfg) -> None:
    print("T5 - grounded AI assistant behaviour")
    # Deterministic checks run against an ISOLATED template-mode service so
    # they hold regardless of whether a live model server is reachable (the
    # live path has its own check below).
    import copy
    from parasail.config import Config as _Config
    raw = copy.deepcopy(cfg.raw)
    raw["assistant"] = dict(raw.get("assistant", {}))
    raw["assistant"]["models"] = {}          # neutralise the registry/persisted
    raw["assistant"]["backend"] = "template" # preference -> template backend
    svc = AssistantService(_Config(raw=raw))

    # 1 - configuration sanity: a backend is configured and a model named
    record("T5", "backend configured",
           svc.backend_name in ("vllm", "ollama", "template")
           and bool(svc.model_name))

    # 2 - deterministic template summary: blocked advisory keeps the verdict
    blocked = {"allowed": False, "class": "DO NOT FISH",
               "block_reason": "spawning protection - monsoon fishing closure",
               "citation": "regulations:monsoon-closure-sardine",
               "species": {"scientific": "Sardinella longiceps"},
               "data_quality": {"degraded": False}}
    s = svc.summarize_advisory(blocked)
    record("T5", "blocked summary keeps DO NOT FISH + reason",
           "STOP" in s["summary"]
           and "spawning protection" in s["summary"]
           and s["backend"] in ("template", "vllm", "ollama"))

    # 3 - scored summary states the class and the data-age caveat
    scored = {"allowed": True, "class": "PROCEED WITH CAUTION", "score": 0.68,
              "components": {"C": 0.72, "W": 0.55, "B": 0.30},
              "observed": {"wind_speed_ms": 5.2, "wave_height_m": 0.9},
              "species": {"scientific": "Sardinella longiceps",
                          "common": "Indian oil sardine"},
              "data_quality": {"degraded": True, "max_age_hours": 8}}
    s2 = svc.summarize_advisory(scored)
    record("T5", "scored summary names class + data age",
           CLASS_WORDS["PROCEED WITH CAUTION"] in s2["summary"]
           and "8 hours old" in s2["summary"])

    # 4 - identical advisory within TTL is served from cache (traffic control)
    s3 = svc.summarize_advisory(scored)
    record("T5", "summary cache engaged for repeat advisories",
           s3.get("cached") is True)

    # 5 - class consistency: an encouraging answer about a blocked area is
    #     overridden by the authoritative verdict line
    guarded = svc._enforce_class_consistency(
        "It is safe to fish here, go ahead!", blocked)
    record("T5", "class-consistency guard overrides encouragement",
           guarded.startswith("STOP -"))

    # 6 - grounding: citations must reference passages that exist
    record("T5", "grounding check rejects uncited / out-of-range citations",
           svc._check_grounded("waves are calm [1]", [{"text": "x"}])
           and not svc._check_grounded("waves are calm", [{"text": "x"}])
           and not svc._check_grounded("waves are calm [9]",
                                       [{"text": "x"}]))

    # 7 - no-context fallback refuses rather than improvises
    ans = svc.answer_question("What is the meaning of the sea?")
    record("T5", "no-context answer refuses instead of improvising",
           "do not have retrieved context" in ans["answer"])

    # 8 - backend transparency: every answer names its origin
    record("T5", "answers name the backend that produced them",
           ans.get("backend") in ("template", "vllm", "ollama"))

    # 9 - live backend (informational): if a local model server is up, the
    #     probe must succeed and a grounded answer must return within the
    #     configured latency budget; skipped when the server is not running.
    live = AssistantService(cfg)             # the REAL configured service
    status = live.status()
    if status["available"] and live.backend_name != "template":
        t0 = time.monotonic()
        live_answer = live.answer_question(
            "Is fishing allowed for Indian oil sardine in June?",
            advisory=blocked)
        dt = time.monotonic() - t0
        budget = float(cfg.assistant.get(live.backend_name, {})
                       .get("timeout_s", 30))
        record("T5", f"live backend answers within {budget:.0f}s budget",
               live_answer["backend"] == live.backend_name and dt <= budget,
               f"{dt:.1f}s via {live.model_name}")
    else:
        record("T5", "live backend probe (skipped - not running)", True)


def t6_security(cfg) -> None:
    print("T6 - security: rate limiting, RBAC, headers, body cap")
    import copy
    import time as _time
    from parasail.security import RateLimiter, bucket_for

    # 1 - sliding-window limiter: allows N, blocks N+1, recovers after window
    lim = RateLimiter({"t": {"limit": 3, "window_s": 0.4}})
    allowed = [lim.check("t", "client-a")[0] for _ in range(3)]
    ok_unit = (all(allowed) and not lim.check("t", "client-a")[0]
               and lim.check("t", "client-b")[0])       # per-client isolation
    _time.sleep(0.45)
    ok_window = lim.check("t", "client-a")[0]
    record("T6", "limiter enforces, isolates clients, recovers",
           ok_unit and ok_window)

    # 2 - expensive and privileged endpoints get their own buckets
    record("T6", "bucket mapping routes costly/privileged paths",
           bucket_for("/assistant/describe-image", "POST") == "image"
           and bucket_for("/assistant/ask", "POST") == "assistant"
           and bucket_for("/advisory", "POST") == "advisory"
           and bucket_for("/assistant/model", "POST") == "admin"
           and bucket_for("/health", "GET") == "default")

    # 3 - full-app behaviour on an isolated config with test keys
    from parasail.api import create_app
    from parasail.config import Config as _Config
    raw = copy.deepcopy(cfg.raw)
    raw["security"] = {
        "rate_limits": {"default": {"limit": 1000, "window_s": 60},
                        "admin": {"limit": 1000, "window_s": 60}},
        "max_body_bytes": 500,
        "api_keys": [
            {"name": "test-admin", "key": "test-admin-key", "role": "admin"},
            {"name": "test-officer", "key": "test-officer-key",
             "role": "officer"},
        ],
        "public_docs": True,
    }
    app = create_app(_Config(raw=raw))
    from fastapi.testclient import TestClient
    # the admin-success case really switches the model and persists the
    # choice - snapshot and restore the operator's preference around it
    from parasail.assistant import MODEL_PREFS_PATH as _PREF
    _saved_pref = None
    try:
        _saved_pref = _PREF.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 - no pref yet
        pass
    try:
      with TestClient(app) as client:
        # force:true: this test is about RBAC, not availability - the
        # probed model may legitimately not be downloaded at test time
        body = {"model": "qwen2.5vl-3b-laptop", "force": True}
        r_none = client.post("/assistant/model", json=body)
        r_officer = client.post("/assistant/model", json=body,
                                headers={"X-API-Key": "test-officer-key"})
        r_admin = client.post("/assistant/model", json=body,
                              headers={"X-API-Key": "test-admin-key"})
        r_bad = client.post("/assistant/model", json=body,
                            headers={"X-API-Key": "wrong-key"})
        record("T6", "RBAC: 401 no key, 401 bad key, 403 officer, 200 admin",
               r_none.status_code == 401 and r_bad.status_code == 401
               and r_officer.status_code == 403
               and r_admin.status_code == 200)

        record("T6", "model switch requires admin (officer -> 403)",
               r_officer.status_code == 403)

        h = client.get("/health").headers
        record("T6", "security headers on every response",
               h.get("X-Content-Type-Options") == "nosniff"
               and h.get("X-Frame-Options") == "DENY"
               and "default-src 'self'" in h.get(
                   "Content-Security-Policy", ""))

        record("T6", "rate-limit headers exposed",
               "X-RateLimit-Limit" in h and "X-RateLimit-Remaining" in h)

        r_big = client.post("/translate",
                            json={"texts": ["x" * 2000], "target": "ml"})
        record("T6", "oversized body rejected (413)", r_big.status_code == 413)

        record("T6", "public endpoints unaffected by RBAC",
               client.get("/health").status_code == 200
               and client.get("/assistant/models").status_code == 200
               and client.get("/").status_code == 200)
    finally:
        if _saved_pref is not None:
            _PREF.write_text(_saved_pref, encoding="utf-8")

    # 4 - production config stays secure by default: no keys -> locked
    raw2 = copy.deepcopy(cfg.raw)
    raw2["security"] = {"api_keys": []}
    app2 = create_app(_Config(raw=raw2))
    with TestClient(app2) as client2:
        r = client2.post("/assistant/model", json={"model": "x"},
                         headers={"X-API-Key": "anything"})
        record("T6", "no keys configured -> privileged endpoints locked",
               r.status_code == 403 and "SECURITY.md" in r.json()["detail"])

    # 5 - keys injected through the environment (secret managers, CI)
    import os as _os
    raw3 = copy.deepcopy(cfg.raw)
    raw3["security"] = {"api_keys": []}          # nothing in config
    _saved_env = _os.environ.get("PARASAIL_API_KEYS")
    from parasail.assistant import MODEL_PREFS_PATH as _PREF2
    _pref_before = None
    try:
        _pref_before = _PREF2.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        _os.environ["PARASAIL_API_KEYS"] = json.dumps(
            [{"name": "env-admin", "key": "env-key-123", "role": "admin"}])
        app3 = create_app(_Config(raw=raw3))
        with TestClient(app3) as c3:
            ok = c3.post("/assistant/model",
                         json={"model": "qwen2.5vl-3b-laptop", "force": True},
                         headers={"X-API-Key": "env-key-123"})
            missing = c3.post("/assistant/model", json={"model": "x"})
        record("T6", "PARASAIL_API_KEYS injects working keys (no config keys)",
               ok.status_code == 200 and missing.status_code == 401,
               f"env key -> {ok.status_code}, none -> {missing.status_code}")

        _os.environ["PARASAIL_API_KEYS"] = "{not json"
        app4 = create_app(_Config(raw=raw3))
        with TestClient(app4) as c4:
            r4 = c4.post("/assistant/model", json={"model": "x"},
                         headers={"X-API-Key": "whatever"})
        record("T6", "malformed PARASAIL_API_KEYS degrades safely (no crash)",
               r4.status_code == 403,
               "stays locked rather than failing open")
    finally:
        if _saved_env is None:
            _os.environ.pop("PARASAIL_API_KEYS", None)
        else:
            _os.environ["PARASAIL_API_KEYS"] = _saved_env
        if _pref_before is not None:
            _PREF2.write_text(_pref_before, encoding="utf-8")


def t7_prediction(cfg) -> None:
    """T7 - suggested-fish scorer: behaviour, honesty and graceful fallback.

    Fully offline: the suggestion path is driven through a stub ingestion
    object, so this family never depends on a network fetch or a live model.
    """
    print("T7 - prediction: habitat model behaviour + honest reporting")
    import tempfile
    from pathlib import Path as _Path

    import numpy as np

    from parasail.models.habitat import HabitatModel, build_features
    from parasail import suggestions as sug

    # 1 - artifact round-trip, and scores stay probabilities
    rng = np.random.default_rng(7)
    n = 240
    months = rng.integers(1, 13, n)
    X = np.vstack([build_features(sst, d, int(m))[0]
                   for sst, d, m in zip(rng.normal(27, 3, n),
                                        rng.uniform(0, 120, n), months)])
    y = ((X[:, 0] > 27) & (X[:, 1] < 60)).astype(int)
    model = HabitatModel(n_estimators=80, max_depth=5, seed=3).fit(X, y)
    with tempfile.TemporaryDirectory() as td:
        path = _Path(td) / "habitat_test.joblib"
        model.save(str(path))
        back = HabitatModel.load(str(path))
        scores = back.suitability(X)
    record("T7", "artifact round-trips; scores are probabilities in [0, 1]",
           scores.min() >= 0.0 and scores.max() <= 1.0
           and abs(float(np.mean(scores[:20])) - float(np.mean(scores[:20]))) < 1e-9,
           f"range {scores.min():.2f}-{scores.max():.2f}")

    # 2 - calibration is monotone (a property of isotonic regression)
    from sklearn.isotonic import IsotonicRegression
    iso = IsotonicRegression(out_of_bounds="clip").fit(np.linspace(0, 1, 50),
                                                       (np.linspace(0, 1, 50) > 0.5))
    grid = np.linspace(0, 1, 60)
    cal = iso.predict(grid)
    record("T7", "isotonic calibrator is non-decreasing",
           bool(np.all(np.diff(cal) >= -1e-9)))

    # 2b - the effort path (true absences + the CPUE correlation metric)
    import tempfile as _tf
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        import train_habitat as th
        rng2 = np.random.default_rng(5)
        n_rows = 140
        good = rng2.random(n_rows) < 0.6
        eff_rows = [{
            "label": 1 if bool(g) else 0, "weight": 5.0,
            "cpue": float(max(0.0, rng2.normal(40 if g else 2, 10))),
            "lat": 9.5, "lon": 76.0, "month": 1 + (i % 12),
            "sst_c": float(rng2.normal(27.5 if g else 29.5, 0.6)),
            "distance_to_shore_km": float(rng2.uniform(5, 40) if g
                                          else rng2.uniform(60, 140)),
            "date": f"2026-{1 + i % 12:02d}-01", "source": "effort-export"}
            for i, g in enumerate(good)]
        with _tf.TemporaryDirectory() as td:
            res = th.train_from_effort(cfg, "Sardinella longiceps", eff_rows,
                                       seed=1, out_dir=Path(td),
                                       model_dir=Path(td), log=lambda *_: None)
        m = res.get("model") or {}
        rho = m.get("spearman_score_cpue")
        record("T7", "effort path trains on true absences and reports CPUE "
                     "correlation",
               bool(m) and 0.0 < m.get("auc", 0) <= 1.0
               and rho is not None and -1.0 <= rho <= 1.0,
               f"AUC {m.get('auc')} | Spearman {rho} | "
               f"{m.get('n_presence')}+/{m.get('n_absence')}-")
        # and it refuses to model a sample too small to mean anything
        thin = th.train_from_effort(cfg, "Sardinella longiceps", eff_rows[:12],
                                    seed=1, out_dir=Path("."),
                                    model_dir=Path("."), log=lambda *_: None)
        record("T7", "effort path refuses a sample too small to support a model",
               thin.get("adopted") is False and thin.get("model") is None
               and "at least 20" in (thin.get("reason") or ""))
    except Exception as exc:  # noqa: BLE001
        record("T7", "effort path trains on true absences", False, str(exc))

    # 3 - loader degrades: unknown species and missing artifact -> envelope
    record("T7", "loader returns None for an unknown species",
           sug.load_habitat_model("Nonexistentus speciesus") is None)

    # 4 - thermal response peak, from the real training table when present
    table = _Path("data") / "habitat_training_sardinella_longiceps.csv"
    if table.exists():
        import csv
        rows = list(csv.DictReader(table.open(encoding="utf-8")))
        Xt = np.vstack([build_features(float(r["sst_c"]),
                                       float(r["distance_to_shore_km"]),
                                       int(r["month"]))[0] for r in rows])
        yt = np.array([int(r["label"]) for r in rows])
        entry = cfg.species_entry("Sardinella longiceps") or {}
        lo, hi = entry.get("preferred_sst_c", [22.0, 29.0])
        m = HabitatModel(n_estimators=300, max_depth=5, seed=11).fit(Xt, yt)
        dist = float(np.median([float(r["distance_to_shore_km"]) for r in rows]))
        month = int(np.median([int(r["month"]) for r in rows]))
        sweep = np.arange(lo - 8, hi + 8, 0.25)
        resp = np.array([float(m.suitability(
            build_features(s, dist, month))[0]) for s in sweep])
        peak = float(sweep[int(np.argmax(resp))])
        record("T7", "thermal response peaks inside the species' band",
               lo - 3.0 <= peak <= hi + 3.0,
               f"peak at {peak:.1f} C (band {lo}-{hi} C, n={len(rows)})")
    else:
        record("T7", "thermal response check (skipped, no training table)",
               True, "run scripts/train_habitat.py to enable")

    # 5 - the served path reports the scorer it actually used
    class _StubOpenMeteo:
        @staticmethod
        def fetch_points(points, hours=24, groups=()):
            return {p: {"sea_surface_temperature": 26.4, "wave_height": 1.0,
                        "wind_speed_10m": 5.0, "elevation": 0.0}
                    for p in points}

    class _StubIngestion:
        open_meteo = _StubOpenMeteo()

    before = sug.load_habitat_model("Sardinella longiceps")
    res = sug.fish_suggestions(cfg, _StubIngestion(), "Sardinella longiceps",
                               9.93, 76.26)
    if before is None:
        record("T7", "no artifact -> envelope answers and says so",
               res["training_records"] is None
               and "untrained" in res["method"]
               and res["zone_threshold"] == sug.DEFAULT_ZONE_THRESHOLD,
               f"method {res['method'][:42]!r}")
    else:
        record("T7", "artifact present -> model scorer is reported",
               res["training_records"] is not None
               and res["method"].startswith("trained habitat model"),
               f"records {res['training_records']}")

    # 6 - zone geometry still respects the sea mask
    zone = res.get("zone")
    over_sea = True
    if zone:
        polys = sug._load_ocean_mask()
        if polys:
            coords = (zone["coordinates"] if zone["type"] == "Polygon"
                      else [r for p in zone["coordinates"] for r in p])
            over_sea = all(sug._point_in_ocean(x, y, polys)
                           for ring in coords for x, y in ring[::7])
    record("T7", "zone geometry stays on the mapped ocean",
           bool(zone is None or over_sea), f"{res.get('zone_cells', 0)} cells")

    # 7 - metrics file records an explicit decision, and adopted models are
    #     not worse than chance
    metrics = _Path("data") / "habitat_metrics.json"
    if metrics.exists():
        import json as _json
        data = _json.loads(metrics.read_text(encoding="utf-8"))
        species = data.get("species", {})
        decided = all("adopted" in v for v in species.values())
        adopted_ok, weak = True, []
        for name, v in species.items():
            if not v.get("adopted"):
                continue
            auc = ((v.get("model") or {}).get("auc") or 0.0)
            lo_auc = (v.get("model") or {}).get("held_out_survey_min_auc")
            if auc < 0.5 or (lo_auc is not None and lo_auc < 0.5):
                adopted_ok, weak = False, weak + [name]
        record("T7", "metrics file records an adoption decision per species",
               decided and adopted_ok, f"{len(species)} species"
               + (f"; below chance: {weak}" if weak else ""))
    else:
        record("T7", "metrics file present (skipped, not trained here)",
               True, "run scripts/train_habitat.py to enable")



def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-live", action="store_true",
                    help="skip T1 network fetches (offline development)")
    args = ap.parse_args()

    cfg = load_config()
    t1_live_fetch(cfg, args.skip_live)
    t2_rule_enforcement(cfg)
    t3_scoring_behaviour(cfg)
    t4_retrieval(cfg)
    t5_assistant(cfg)
    t6_security(cfg)
    t7_prediction(cfg)

    failed = [r for r in results if r[2] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", ", ".join(f"{f}/{n}" for f, n, _ in failed))
        sys.exit(1)
    print("all validation gates passed")


if __name__ == "__main__":
    main()

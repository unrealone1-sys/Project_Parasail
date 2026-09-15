"""ParaSail advisory engine (development phase P5).

Pipeline for one advisory request:
  1. validate (quality gates) and normalise onto the common grid,
  2. run hard conservation constraints (closure calendar + MPA geometry) -
     a blocked request returns DO NOT FISH with reason and citation,
  3. score the sustainability index
         S = w_c*C + w_w*W + w_e*(1 - B)
     with C = lambda*Chat + (1 - lambda)*Hhat (data-availability blend),
  4. attach retrieved context (passages + tiles) and the freshness audit,
  5. return a machine- and human-readable advisory.

The output schema is deliberately the same for blocked and scored requests.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from .config import Config
from .ingestion import IngestionService, SourcedField
from .processing import (freshness_audit, quality_gate, validate_coordinates,
                         validate_timestamp, weather_safety)
from .rag import RagService
from .rules import RulesEngine

SCHEMA_VERSION = "1.0"


class AdvisoryEngine:
    def __init__(self, cfg: Config, ingestion: IngestionService,
                 rules: RulesEngine, rag: RagService,
                 tendency_fn=None, habitat_fn=None, bycatch_fn=None,
                 now_fn=None):
        self.cfg = cfg
        self.ingestion = ingestion
        self.rules = rules
        self.rag = rag
        # Prediction functions are injected so the engine composes with any
        # combination of trained / fallback models.
        self.tendency_fn = tendency_fn or (lambda **_: 0.5)
        self.habitat_fn = habitat_fn or (lambda **_: 0.5)
        self.bycatch_fn = bycatch_fn or self._default_bycatch
        # Injectable clock: keeps the validation suite deterministic.
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------ #
    def advise(self, lat: float, lon: float, species: str,
               start: datetime, hours: int = 24) -> dict:
        # 1 - quality gates -------------------------------------------------
        validate_coordinates(lat, lon, self.cfg.region["bbox"])
        validate_timestamp(start, hours, now=self._now())
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        entry = self.cfg.species_entry(species)
        if entry is None:
            return self._blocked(lat, lon, species,
                                 f"species {species!r} not in registry",
                                 "config:species-registry")

        # 2 - hard constraints BEFORE any scoring ---------------------------
        constraint = self.rules.evaluate(lat, lon, species, start)
        if constraint.blocked:
            return self._blocked(lat, lon, species, constraint.reason,
                                 constraint.citation)

        # 3 - live fields -> components ------------------------------------
        fields = quality_gate(
            self.ingestion.weather_fields(lat, lon, start, hours))
        env = self._summarise(fields)
        w = weather_safety(env["wind_speed"], env["wave_height"], self.cfg)

        lam = float(entry.get("data_availability", 0.5))
        c_hat = self.tendency_fn(lat=lat, lon=lon, start=start, hours=hours,
                                 env=env, species=species)
        h_hat = self.habitat_fn(lat=lat, lon=lon, when=start, env=env,
                                species=species)
        c = lam * c_hat + (1.0 - lam) * h_hat
        b = self.bycatch_fn(lat=lat, lon=lon, when=start, env=env,
                            species=species)

        weights = self.cfg.advisory["weights"]
        s = (weights["catch"] * c
             + weights["weather"] * w
             + weights["ecological"] * (1.0 - b))
        s = round(min(max(s, 0.0), 1.0), 4)

        # 4 - explainability: retrieval, never confabulation ----------------
        query = (f"{entry['common_name']} fishing advisory near "
                 f"({lat:.2f}, {lon:.2f}) on {start.date().isoformat()}: "
                 "closures, protected areas, weather safety, bycatch")
        context = self.rag.retrieve_context(query, species, lat, lon, start)

        # 5 - assemble -------------------------------------------------------
        return {
            "schema": SCHEMA_VERSION,
            "allowed": True,
            "class": self._classify(s),
            "score": s,
            "components": {
                "C": round(c, 4), "W": round(w, 4), "B": round(b, 4),
                "lambda": lam, "c_hat": round(c_hat, 4),
                "h_hat": round(h_hat, 4),
            },
            "observed": {
                "wind_speed_ms": round(env["wind_speed"], 1),
                "wind_gusts_ms": (round(env["wind_gusts"], 1)
                                  if env.get("wind_gusts") is not None else None),
                "wave_height_m": (round(env["wave_height"], 2)
                                  if env.get("wave_height") is not None else None),
                "sst_c": round(env["sst"], 1),
            },
            "species": {"scientific": entry["scientific_name"],
                        "common": entry["common_name"]},
            "position": {"lat": lat, "lon": lon},
            "window": {"start": start.isoformat(), "hours": hours},
            "data_quality": freshness_audit(fields),
            "context": context,
        }

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _classify(self, s: float) -> str:
        t = self.cfg.advisory["thresholds"]
        if s >= t["proceed"]:
            return "PROCEED"
        if s >= t["caution"]:
            return "PROCEED WITH CAUTION"
        if s >= t["delay"]:
            return "DELAY OR RELOCATE"
        return "DO NOT FISH"

    def _blocked(self, lat, lon, species, reason, citation) -> dict:
        return {
            "schema": SCHEMA_VERSION,
            "allowed": False,
            "class": "DO NOT FISH",
            "score": None,
            "block_reason": reason,
            "citation": citation,
            "species": {"scientific": species},
            "position": {"lat": lat, "lon": lon},
            "context": {"passages": [], "tiles": []},
        }

    def _default_bycatch(self, **kw) -> float:
        """Conservative constant mid-risk bycatch proxy when no trained
        estimator is wired; keeps the ecological term honest rather than
        silently optimistic."""
        return 0.30

    @staticmethod
    def _summarise(fields: list[SourcedField]) -> dict:
        agg: dict[str, list[float]] = {}
        for f in fields:
            agg.setdefault(f.variable, []).append(f.value)
        mean = {k: sum(v) / len(v) for k, v in agg.items()}
        return {
            "wind_speed": mean.get("wind_speed_10m", 0.0),
            "wind_gusts": mean.get("wind_gusts_10m"),
            "wave_height": mean.get("wave_height"),  # None if marine source down
            "sst": mean.get("sea_surface_temperature", 28.0),
            "chlorophyll_a": mean.get("chlorophyll_a", 0.5),
            "field_count": len(fields),
        }

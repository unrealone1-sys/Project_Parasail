"""ParaSail - configuration loader.

Everything region- or policy-specific (species registry, closures, score
weights, model checkpoints) is loaded from config.yaml so that retargeting
the system never requires code edits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_PATH = os.environ.get(
    "PARASAIL_CONFIG", str(Path(__file__).resolve().parents[2] / "config.yaml")
)


@dataclass(frozen=True)
class Config:
    raw: dict = field(repr=False)

    # -- region ------------------------------------------------------------
    @property
    def region(self) -> dict:
        return self.raw["region"]

    @property
    def species(self) -> list[dict]:
        return self.raw["species"]

    def species_entry(self, scientific_name: str) -> dict | None:
        return next(
            (s for s in self.species
             if s["scientific_name"].lower() == scientific_name.lower()),
            None,
        )

    # -- advisory ----------------------------------------------------------
    @property
    def advisory(self) -> dict:
        return self.raw["advisory"]

    @property
    def models(self) -> dict:
        return self.raw["models"]

    @property
    def rag(self) -> dict:
        return self.raw["rag"]

    @property
    def assistant(self) -> dict:
        """Grounded AI assistant (phase P7). Absent keys fall back to the
        deterministic template path so older configs keep working."""
        return self.raw.get("assistant", {})

    @property
    def ingestion(self) -> dict:
        return self.raw["ingestion"]

    @property
    def database_url(self) -> str:
        return self.raw["database"]["url"]


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> Config:
    """Load and cache the YAML configuration.

    Containerised deployments override service URLs through the environment
    (set by docker-compose.yml) so the same config.yaml serves laptop and
    Docker runs: inside the compose network, PostGIS and Qdrant are reached
    by service name, not localhost.
    """
    cfg_path = Path(path or DEFAULT_PATH)
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"ParaSail configuration not found at {cfg_path}. "
            "Set PARASAIL_CONFIG or run from the repository root."
        )
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if os.environ.get("PARASAIL_QDRANT_URL"):
        raw["rag"]["qdrant_url"] = os.environ["PARASAIL_QDRANT_URL"]
    if os.environ.get("PARASAIL_DATABASE_URL"):
        raw["database"]["url"] = os.environ["PARASAIL_DATABASE_URL"]
    if os.environ.get("PARASAIL_VLLM_URL"):
        raw.setdefault("assistant", {}).setdefault("vllm", {})[
            "base_url"] = os.environ["PARASAIL_VLLM_URL"]
        if raw["assistant"].get("backend") not in ("vllm", "template"):
            raw["assistant"]["backend"] = "vllm"
    if os.environ.get("PARASAIL_OLLAMA_URL"):
        raw.setdefault("assistant", {}).setdefault("ollama", {})[
            "base_url"] = os.environ["PARASAIL_OLLAMA_URL"]
    return Config(raw=raw)

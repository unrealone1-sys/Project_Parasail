"""ParaSail rules engine (development phase P5) - hard conservation constraints.

Constraint execution happens AHEAD of scoring: a request inside an active
MPA or seasonal closure is refused with the blocking reason and citation,
and no score configuration can override it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .config import Config

log = logging.getLogger("parasail.rules")

# PostgreSQL/PostGIS query for MPA containment. Uses ST_Contains on the
# 4326 polygons; the GiST index keeps this sub-millisecond at regional scale.
MPA_QUERY = """
SELECT m.name, m.authority
FROM   mpa_polygons m
WHERE  ST_Contains(m.geometry, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))
  AND (m.valid_from IS NULL OR m.valid_from <= %(ts)s::date)
  AND (m.valid_to   IS NULL OR m.valid_to   >= %(ts)s::date)
LIMIT  1;
"""


@dataclass
class ConstraintResult:
    blocked: bool
    reason: str | None = None
    citation: str | None = None

    def as_dict(self) -> dict:
        return {"blocked": self.blocked, "reason": self.reason,
                "citation": self.citation}


class RulesEngine:
    """Two hard rules: seasonal closures and marine protected areas."""

    def __init__(self, cfg: Config, db_connection_factory=None):
        self.cfg = cfg
        # Late dependency: psycopg connection factory (keeps unit tests light).
        self._connect = db_connection_factory

    # -- rule 1: species-month closure calendar ---------------------------
    def check_closure(self, species_name: str,
                      when: datetime) -> ConstraintResult:
        entry = self.cfg.species_entry(species_name)
        if entry is None:
            return ConstraintResult(
                True, f"unknown species {species_name!r} - not in registry",
                "config:species-registry")
        month = when.month
        for closure in entry.get("closures", []):
            if month in closure["months"]:
                return ConstraintResult(
                    True,
                    f"seasonal closure active for {entry['common_name']} "
                    f"({entry['scientific_name']}) in month {month}: "
                    + closure["reason"],
                    closure["citation"],
                )
        return ConstraintResult(False)

    # -- rule 2: marine protected area containment -------------------------
    def check_mpa(self, lat: float, lon: float,
                  when: datetime) -> ConstraintResult:
        if self._connect is None:
            # No database wired (unit-test / offline mode): cannot clear the
            # point, so we fail CLOSED - conservation before convenience.
            return ConstraintResult(
                True, "MPA registry unavailable - request cannot be cleared",
                "system:fail-closed")
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(MPA_QUERY, {"lat": lat, "lon": lon, "ts": when})
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001 - unreachable DB fails closed, never open
            log.warning("MPA registry unreachable at (%.4f, %.4f): %s: %s",
                        lat, lon, type(exc).__name__, exc)
            return ConstraintResult(
                True, "MPA registry unreachable - request cannot be cleared",
                "system:fail-closed")
        if row:
            name, authority = row
            return ConstraintResult(
                True,
                f"position falls inside marine protected area '{name}'"
                + (f" ({authority})" if authority else ""),
                f"mpa:{name}",
            )
        return ConstraintResult(False)

    # -- combined ----------------------------------------------------------
    def evaluate(self, lat: float, lon: float, species_name: str,
                 when: datetime) -> ConstraintResult:
        for result in (self.check_closure(species_name, when),
                       self.check_mpa(lat, lon, when)):
            if result.blocked:
                return result
        return ConstraintResult(False)

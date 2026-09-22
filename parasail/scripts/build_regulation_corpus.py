# -*- coding: utf-8 -*-
"""Build a STARTER regulation corpus for the retrieval layer (JSONL).

Everything here comes from this repository - nothing is invented:

  * the closures declared in ``config.yaml`` (their months, reason and
    citation ids), rendered as retrieved guidance;
  * the protected-area registry actually loaded into PostGIS
    (``data/mpas_india_osm.geojson``: 16 real Indian MPAs, OSM/ODbL) with
    the behaviour the advisory layer applies inside them;
  * the advisory system's own semantics - the four classes and their
    configured thresholds, the fail-closed guard, the bycatch term, and the
    assistant's guardrails - as system documentation;
  * the seeded regional news corpus (``src/parasail/data/ocean_news.json``),
    which already carries its own sources.

WHY A "STARTER" CORPUS: official closure notifications and protected-area
rules are jurisdiction-specific legal texts. This file cannot ship them, so
it ships what the deployment is actually configured with, clearly attributed,
so the assistant can cite real sources instead of answering from priors. An
operator MUST replace or extend it with the official notifications for their
coast before any public use - see docs/PREDICTION.md and docs/AI_ASSISTANT.md.
Every document says what it is and where it came from.

Usage:
  python scripts/build_regulation_corpus.py                 # -> data/regulations.jsonl
  python scripts/build_regulation_corpus.py --out other.jsonl
Then seed it:
  python scripts/seed_regulations.py --corpus data/regulations.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parasail.config import load_config   # noqa: E402

REVIEW = ("This entry is deployment-configured, not an official legal text: "
          "verify it against the managing authority's current notification "
          "before relying on it.")

# study-coast bbox used when a document has no tighter one (Kerala coast)
COAST_BBOX = [72.0, 7.0, 78.0, 13.0]


def closure_docs(cfg) -> list[dict]:
    """One document per closure declared in config.yaml."""
    out = []
    for sp in cfg.raw.get("species", []):
        name = sp.get("scientific_name")
        common = sp.get("common_name", name)
        for cl in sp.get("closures") or []:
            names = ["", "January", "February", "March", "April", "May",
                     "June", "July", "August", "September", "October",
                     "November", "December"]
            months = " and ".join(names[m] for m in cl.get("months", [])
                                  if 1 <= m <= 12)
            out.append({
                "text": (f"{common} ({name}) is under a seasonal closure. "
                         f"Configured closure months: {months}. Reason: "
                         f"{cl.get('reason', 'not stated')}. During these "
                         "months the advisory for this species is STOP "
                         "(DO NOT FISH) regardless of weather or how likely "
                         "the fish are: conservation rules run before any "
                         f"scoring. {REVIEW}"),
                "source": "config.yaml (deployment closure registry)",
                "citation": cl.get("citation", "regulations:closure"),
                "species": name,
                "bbox": COAST_BBOX,
            })
    return out


def mpa_docs(path: Path) -> list[dict]:
    """One document per protected area in the loaded registry."""
    out = []
    try:
        geo = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                  # noqa: BLE001
        return out
    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        name = props.get("name")
        if not name:
            continue
        bbox = feat.get("bbox")
        if not bbox:
            xs, ys = [], []
            geom = feat.get("geometry") or {}
            rings = ([geom.get("coordinates")] if geom.get("type") == "Polygon"
                     else geom.get("coordinates") or [])
            for poly in rings:
                for ring in poly:
                    for x, y in ring:
                        xs.append(x); ys.append(y)
            bbox = [min(xs), min(ys), max(xs), max(ys)] if xs else COAST_BBOX
        out.append({
            "text": (f"{name} is a designated marine protected area in this "
                     "deployment's registry. The advisory layer treats it as a "
                     "hard constraint: a request whose coordinates fall inside "
                     "its boundary is refused with DO NOT FISH (STOP) before "
                     "any scoring, and the refusal names the park. Boundaries "
                     "come from OpenStreetMap contributors (ODbL) and are "
                     f"cross-checked against the WDPA registry. {REVIEW}"),
            "source": f"protected-area registry (OSM contributors, ODbL; "
                      f"authority field: {props.get('authority', 'n/a')})",
            "citation": f"mpa:{name}",
            "species": None,
            "bbox": [round(float(v), 4) for v in bbox],
        })
    return out


def system_docs(cfg) -> list[dict]:
    """The advisory system's own semantics, from this repository."""
    adv = cfg.raw.get("advisory", {})
    th = adv.get("thresholds", {})
    w = adv.get("weights", {})
    cls = [("PROCEED", th.get("proceed", 0.75), "GO"),
           ("PROCEED WITH CAUTION", th.get("caution", 0.60), "GO CAREFULLY"),
           ("DELAY OR RELOCATE", th.get("delay", 0.40), "WAIT OR MOVE"),
           ("DO NOT FISH", 0.0, "STOP")]
    lines = "; ".join(f"{name} when the index is at or above {lo} ({word})"
                      for name, lo, word in cls[:3])
    return [
        {"text": (f"The advisory has four classes, from the configured "
                  f"thresholds: {lines}; DO NOT FISH below "
                  f"{th.get('delay', 0.40)}, or whenever a hard constraint "
                  "applies. The class is computed by the deterministic rules "
                  "engine and scoring, never by the AI assistant, and the "
                  "assistant may not contradict it."),
         "source": "advisory configuration + rules engine",
         "citation": "system:advisory-classes",
         "species": None, "bbox": COAST_BBOX},

        {"text": ("The sustainability index is a weighted sum of catch "
                  f"likelihood ({w.get('catch', 0.45)}), weather safety "
                  f"({w.get('weather', 0.25)}) and the ecological term "
                  f"({w.get('ecological', 0.30)}). It is monotonic in every "
                  "input, the weights are configuration owned by governance "
                  "rather than hidden constants, and a protected area or "
                  "closure overrides the score entirely."),
         "source": "advisory configuration + scoring engine",
         "citation": "system:sustainability-index",
         "species": None, "bbox": COAST_BBOX},

        {"text": ("Protected areas and seasonal closures are enforced as hard, "
                  "fail-closed constraints: if the registry is unreachable the "
                  "request is refused rather than cleared, so an outage can "
                  "never produce a permissive answer. This is why a STOP may "
                  "appear with the reason 'MPA registry unavailable' - it is "
                  "the conservation guard working as designed, not a fault."),
         "source": "rules engine (fail-closed guard)",
         "citation": "system:fail-closed",
         "species": None, "bbox": COAST_BBOX},

        {"text": ("What the assistant will and will not do: it summarises the "
                  "advisory in plain language, answers questions using the "
                  "advisory data plus retrieved passages and cites them, and "
                  "reads catch photos, satellite tiles and charts describing "
                  "only what is visible. It never overrules the advisory "
                  "class, never softens a STOP, refuses rather than invents "
                  "when it has no retrieved context, and always names the "
                  "backend and model that produced an answer."),
         "source": "assistant layer documentation",
         "citation": "system:assistant-guardrails",
         "species": None, "bbox": COAST_BBOX},

        {"text": ("Weather safety in the advisory is judged from live marine "
                  "and meteorological forecasts - wind speed and gusts, wave "
                  "height, wave period and direction - against the limits of "
                  "small boats. Calm conditions raise the safety component and "
                  "rough conditions lower it, so an advisory can be WAIT OR "
                  "MOVE even where fish are likely. Warnings apply to the "
                  "requested point, not to a whole district: conditions a few "
                  "kilometres offshore differ from the harbour, and they change "
                  "through the day."),
         "source": "advisory system documentation (weather-safety component)",
         "citation": "system:weather-safety",
         "species": None, "bbox": COAST_BBOX},

        {"text": ("Ecological risk in the advisory covers bycatch and habitat "
                  "harm: it rises near sensitive habitats such as seagrass, "
                  "coral and mangroves, and during juvenile recruitment "
                  "months, and it lowers the final class even when catch "
                  "likelihood is high. The rule the system encodes is that "
                  "catching the target fish does not justify damaging the "
                  "nursery grounds the next season depends on."),
         "source": "advisory system documentation (bycatch / ecological term)",
         "citation": "system:bycatch-risk",
         "species": None, "bbox": COAST_BBOX},
    ]


def news_docs(path: Path) -> list[dict]:
    """The seeded regional news corpus, which carries its own sources."""
    out = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                  # noqa: BLE001
        return out
    for item in data.get("items", []):
        text = (item.get("summary_en") or item.get("summary") or "").strip()
        title = (item.get("title_en") or item.get("title") or "").strip()
        if not text or not title:
            continue
        out.append({
            "text": f"{title}. {text}",
            "source": f"regional ocean news seed ({item.get('region', 'region')}; "
                      f"source: {item.get('source', 'n/a')})",
            "citation": f"news:{item.get('id', title[:24])}",
            "species": None, "bbox": COAST_BBOX,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "regulations.jsonl")
    ap.add_argument("--mpas", type=Path,
                    default=ROOT / "data" / "mpas_india_osm.geojson")
    ap.add_argument("--news", type=Path,
                    default=ROOT / "src" / "parasail" / "data" / "ocean_news.json")
    args = ap.parse_args()

    cfg = load_config()
    docs = (closure_docs(cfg) + mpa_docs(args.mpas)
            + system_docs(cfg) + news_docs(args.news))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    kinds = {"closure": 0, "mpa": 0, "system": 0, "news": 0}
    for d in docs:
        c = d["citation"]
        kinds["mpa" if c.startswith("mpa:") else
              "system" if c.startswith("system:") else
              "news" if c.startswith("news:") else "closure"] += 1
    print(f"wrote {len(docs)} documents -> {args.out.relative_to(ROOT)}")
    print("  " + ", ".join(f"{k}: {v}" for k, v in kinds.items()))
    print("  starter corpus from repository content only - no legal text "
          "invented; operators must replace it with official notifications.")


if __name__ == "__main__":
    main()

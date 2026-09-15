"""Seed the Qdrant text collection from a regulation corpus (phase P5).

Corpus format (JSONL), one document per line:
    {"text": "...", "source": "MPA authority bulletin",
     "citation": "Fisheries Department order 12/2024",
     "species": "Sardinella longiceps", "bbox": [73.0, 8.0, 78.5, 13.0],
     "date": "2024-05-01"}

Usage:
    python scripts/seed_regulations.py --corpus data/regulations.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config   # noqa: E402
from parasail.rag import RagService       # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True, type=Path)
    args = ap.parse_args()

    documents = [json.loads(line) for line in
                 args.corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not documents:
        raise SystemExit("corpus is empty")

    rag = RagService(load_config())
    n = rag.upsert_text_documents(documents)
    print(f"seeded {n} chunks from {len(documents)} documents into "
          f"'{load_config().rag['text_collection']}'")


if __name__ == "__main__":
    main()

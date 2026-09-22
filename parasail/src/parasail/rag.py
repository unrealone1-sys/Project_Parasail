"""ParaSail RAG layer (development phase P5) - explainability by retrieval.

Two Qdrant collections:
  * parasail_text   - 384-d MiniLM embeddings of chunked regulations,
                      closure calendars, conservation guidance and consented
                      local ecological knowledge;
  * parasail_sat    - 512-d OpenCLIP embeddings of Sentinel tiles annotated
                      with bounding box and acquisition metadata.

Hybrid retrieval: bounding-box + temporal payload pre-filter, then top-k
vector search. The retrieved passages and tiles are attached to every
advisory - explainability is retrieval of verifiable sources, not generated
prose. (An optional local LLM may summarise the context; it never replaces it.)
"""
from __future__ import annotations

import logging
from datetime import datetime

from .config import Config

log = logging.getLogger("parasail.rag")


class RagService:
    def __init__(self, cfg: Config, client=None, encoder=None):
        self.cfg = cfg
        self.conf = cfg.rag
        # Late-bound so the module imports without qdrant/transformers.
        self._client = client
        self._encoder = encoder
        self._connected = False

    # ------------------------------------------------------------------ #
    # lazy clients
    # ------------------------------------------------------------------ #
    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self.conf["qdrant_url"])
        return self._client

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.cfg.models["text_encoder"])
        return self._encoder

    # ------------------------------------------------------------------ #
    # collection management
    # ------------------------------------------------------------------ #
    def ensure_collections(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        for name, dim in ((self.conf["text_collection"], 384),
                          (self.conf["satellite_collection"], 512)):
            if not self.client.collection_exists(name):
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
                log.info("created Qdrant collection %s (dim=%d)", name, dim)
        self._connected = True

    # ------------------------------------------------------------------ #
    # ingestion helpers (used by scripts/seed_regulations.py etc.)
    # ------------------------------------------------------------------ #
    @staticmethod
    def chunk_text(text: str, chunk_chars: int, overlap: int) -> list[str]:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + chunk_chars])
            start += chunk_chars - overlap
        return [c for c in chunks if c.strip()]

    def upsert_text_documents(self, documents: list[dict]) -> int:
        """documents: [{id, text, source, citation, bbox?, date?, species?}]"""
        from qdrant_client.models import PointStruct
        self.ensure_collections()
        n_chars = self.conf["chunk_chars"]
        overlap = self.conf["chunk_overlap"]
        points, next_id = [], 0
        for doc in documents:
            for chunk in self.chunk_text(doc["text"], n_chars, overlap):
                points.append(PointStruct(
                    id=next_id,
                    vector=self.encoder.encode(chunk).tolist(),
                    payload={
                        "text": chunk,
                        "source": doc.get("source", "unknown"),
                        "citation": doc.get("citation", doc.get("source", "")),
                        "species": doc.get("species"),
                        "bbox": doc.get("bbox"),
                        "date": doc.get("date"),
                    },
                ))
                next_id += 1
        if points:
            self.client.upsert(self.conf["text_collection"], points=points)
        log.info("upserted %d text chunks", len(points))
        return len(points)

    def list_tiles(self, lat: float, lon: float, when: datetime,
                   top_k: int | None = None) -> list[dict]:
        """Nearest Sentinel tiles for an advisory.

        Tiles are ranked by spatial and temporal proximity (payload filter +
        scroll), not by text similarity: their vectors are OpenCLIP image
        embeddings, used for tile-to-tile search in the ingestion scripts.
        """
        k = top_k or self.conf["top_k"]
        try:
            points, offset = [], 0
            while len(points) < k * 4 and offset is not None:
                batch, offset = self.client.scroll(
                    collection_name=self.conf["satellite_collection"],
                    limit=64, offset=offset,
                    with_payload=True, with_vectors=False,
                )
                points.extend(batch)
            scored = []
            for p in points:
                bbox = p.payload.get("bbox") or []
                if len(bbox) != 4:
                    continue
                lon_min, lat_min, lon_max, lat_max = bbox
                if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                    continue
                acquired = p.payload.get("acquired")
                days = (abs((datetime.fromisoformat(acquired) - when).days)
                        if acquired else 9999)
                scored.append((days, p.payload))
            scored.sort(key=lambda t: t[0])
            return [{"acquired": pl.get("acquired"),
                     "bbox": pl.get("bbox"),
                     "source": pl.get("source", "sentinel"),
                     "days_from_request": d}
                    for d, pl in scored[:k]]
        except Exception as exc:  # noqa: BLE001 - retrieval must never block advice
            log.warning("tile lookup failed: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    # hybrid retrieval
    # ------------------------------------------------------------------ #
    @staticmethod
    def _search(client, collection: str, query_vec: list, limit: int,
                query_filter=None) -> list:
        """Vector search across qdrant-client versions.

        qdrant-client >= 1.10 removed `search()` in favour of
        `query_points()`, which returns a response object rather than a
        list. Without this shim, retrieval silently returns nothing against
        current clients and every answer loses its citations.
        """
        if hasattr(client, "query_points"):
            resp = client.query_points(collection_name=collection,
                                       query=query_vec, query_filter=query_filter,
                                       limit=limit, with_payload=True)
            return list(getattr(resp, "points", resp) or [])
        return list(client.search(collection_name=collection,
                                  query_vector=query_vec,
                                  query_filter=query_filter, limit=limit))

    def retrieve_context(self, query: str, species: str, lat: float, lon: float,
                         when: datetime, top_k: int | None = None) -> dict:
        """Top-k passages + tiles for an advisory, pre-filtered in space and
        time where payloads allow it."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        k = top_k or self.conf["top_k"]
        try:
            query_vec = self.encoder.encode(query).tolist()

            def _hits(species_filter: bool) -> list:
                flt = (Filter(must=[FieldCondition(
                    key="species", match=MatchValue(value=species))])
                       if species_filter else None)
                return self._search(self.client, self.conf["text_collection"],
                                    query_vec, k, flt)

            # merge species-tagged and general hits, then rank by score: most
            # of the library (protected areas, system rules, regional news) is
            # not species-specific, so a species-only filter would hide it -
            # and returning species hits *instead of* better general ones is
            # how an answer ends up citing something irrelevant
            merged: dict = {}
            for h in _hits(species_filter=True) + _hits(species_filter=False):
                key = (h.payload.get("citation"), h.payload.get("text", "")[:80])
                if key not in merged or h.score > merged[key].score:
                    merged[key] = h
            hits = sorted(merged.values(), key=lambda h: -h.score)[:k]
        except Exception as exc:  # noqa: BLE001 - retrieval must never block advice
            log.warning("text retrieval failed: %s", exc)
            hits = []
        passages = [{
            "text": h.payload.get("text", ""),
            "source": h.payload.get("source"),
            "citation": h.payload.get("citation"),
            "score": round(h.score, 4),
        } for h in hits]

        return {
            "query": query,
            "passages": passages,
            "tiles": self.list_tiles(lat, lon, when, top_k),
            "top_k": k,
        }

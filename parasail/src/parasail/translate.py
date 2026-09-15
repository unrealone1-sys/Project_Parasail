"""ParaSail in-site translation service.

Translates any interface text - static labels AND dynamically generated
advisory reasons - into the coastal-state languages of India. Two live
translation backends with graceful fallback:

  1. Google translate endpoint (gtx) - primary, best quality
  2. MyMemory translated.net API    - fallback

Results are cached in memory and persisted to disk, so each unique
(text, language) pair is translated once, ever, per deployment.
If every backend fails, the original English is returned - the interface
degrades to English rather than breaking.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx

log = logging.getLogger("parasail.translate")

GOOGLE_GTX = "https://translate.googleapis.com/translate_a/single"
MYMEMORY = "https://api.mymemory.translated.net/get"

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ml": "\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02",   # Malayalam
    "ta": "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd",           # Tamil
    "kn": "\u0c95\u0ca8\u0ccd\u0ca8\u0ca1",           # Kannada
    "te": "\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41",     # Telugu
    "mr": "\u092e\u0930\u093e\u0920\u0940",           # Marathi
    "gu": "\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0",  # Gujarati
    "bn": "\u09ac\u09be\u0982\u09b2\u09be",           # Bengali
    "or": "\u0b13\u0b21\u0b3c\u0b3f\u0b06",           # Odia
    "hi": "\u0939\u093f\u0928\u094d\u0926\u0940",     # Hindi
}


class TranslationService:
    def __init__(self, cache_path: str = ".cache/translations.json"):
        self.cache_path = cache_path
        parent = os.path.dirname(cache_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self._load_disk_cache()

    # ------------------------------------------------------------------ #
    # cache
    # ------------------------------------------------------------------ #
    @staticmethod
    def _key(text: str, target: str) -> str:
        return f"{target}||{text}"

    def _load_disk_cache(self) -> None:
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as fh:
                    self._cache = json.load(fh)
                log.info("loaded %d cached translations", len(self._cache))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("translation cache unreadable (%s); starting fresh", exc)
            self._cache = {}

    def _persist(self) -> None:
        try:
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump(self._cache, fh, ensure_ascii=False)
        except OSError as exc:
            log.warning("could not persist translation cache: %s", exc)

    # ------------------------------------------------------------------ #
    # backends
    # ------------------------------------------------------------------ #
    def _google(self, text: str, target: str) -> str | None:
        resp = httpx.get(
            GOOGLE_GTX,
            params={"client": "gtx", "sl": "en", "tl": target, "dt": "t", "q": text},
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ParaSail/1.0)"},
        )
        resp.raise_for_status()
        data = resp.json()
        segments = data[0] if data and isinstance(data[0], list) else []
        out = "".join(seg[0] for seg in segments if seg and seg[0])
        return out or None

    def _mymemory(self, text: str, target: str) -> str | None:
        resp = httpx.get(
            MYMEMORY,
            params={"q": text[:490], "langpair": f"en|{target}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        translated = resp.json().get("responseData", {}).get("translatedText")
        if translated and "MYMEMORY WARNING" not in translated.upper():
            return translated
        return None

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def translate(self, text: str, target: str) -> str:
        if target == "en" or not text or not text.strip():
            return text
        if target not in SUPPORTED_LANGUAGES:
            return text
        key = self._key(text, target)
        with self._lock:
            if key in self._cache:
                return self._cache[key]

        result = None
        for backend in (self._google, self._mymemory):
            try:
                result = backend(text, target)
            except Exception as exc:  # noqa: BLE001 - fall through to next backend
                log.warning("%s failed for %s->%s: %s",
                            backend.__name__, target, text[:40], exc)
            if result:
                break
        if not result:
            return text  # graceful degradation to English

        with self._lock:
            self._cache[key] = result
            self._persist()
        return result

    def translate_batch(self, texts: list[str], target: str,
                         workers: int = 8) -> list[str]:
        """Translate a batch, deduplicating and parallelising; order kept."""
        unique = list(dict.fromkeys(t for t in texts if t and t.strip()))
        if target == "en" or not unique:
            return list(texts)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            translated = dict(
                zip(unique, pool.map(lambda t: self.translate(t, target), unique)))
        return [translated.get(t, t) for t in texts]

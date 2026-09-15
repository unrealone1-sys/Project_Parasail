"""ParaSail grounded AI assistant layer (development phase P7).

A conversational, vision-capable assistant that sits on top of the advisory
engine and the retrieval layer to serve the public website:

  * plain-language summaries of advisories (decision-making analysis: which
    component drove the class, what to watch, how old the data is),
  * grounded question answering over the regulation / guidance / local
    knowledge corpus,
  * image understanding for catch photos, satellite tiles and charts via a
    small open-source vision-language model (VLM).

Design contract - the assistant explains, it never decides:
  * every answer is grounded in the advisory payload and numbered retrieved
    passages; unverifiable claims are refused rather than improvised,
  * the advisory class is authoritative; the assistant may not contradict
    or soften a DO NOT FISH verdict,
  * the deterministic template path produces the same response schema with
    no LLM at all, so the website keeps working on CPU-only deployments,
  * the VLM backend is configuration: Qwen2.5-VL-7B-Instruct-AWQ served by
    vLLM (8-12 GB VRAM profile) by default, Ollama as a local fallback.

See docs/AI_ASSISTANT.md and docs/PRODUCTION_HARDWARE.md for deployment.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import Config

log = logging.getLogger("parasail.assistant")

MODEL_PREFS_PATH = Path(".cache/assistant_model.json")

CLASS_WORDS = {
    "PROCEED": "GO",
    "PROCEED WITH CAUTION": "GO CAREFULLY",
    "DELAY OR RELOCATE": "WAIT OR MOVE",
    "DO NOT FISH": "STOP",
}

# Phrases a grounded assistant must never emit for a blocked advisory.
_ENCOURAGEMENT = re.compile(
    r"\b(safe to (?:fish|sail|go)|go ahead|good day to fish|fish anyway)\b",
    re.IGNORECASE)

SYSTEM_PROMPT = """You are the ParaSail Assistant, the AI helper of a fishing
advisory system used by fishers, fisheries officers and coastal communities.

Hard rules:
1. Answer ONLY from the ADVISORY DATA, CONTEXT PASSAGES and attached IMAGES
   provided in the conversation. Never invent facts, numbers or rules.
2. Cite every factual claim with the passage number it came from, like [1].
3. The ADVISORY CLASS is authoritative. Never contradict it, never soften a
   DO NOT FISH verdict, never encourage fishing in a blocked area or season.
4. If the provided data does not answer the question, say so plainly and
   suggest what the user can do instead (for example, ask the fisheries
   department or re-check closer to departure).
5. Describe images (catch photos, satellite tiles, charts) only from what is
   visible; do not guess species or conditions you cannot see clearly.
6. Keep answers short (under 150 words), plain and fisher-friendly. Explain
   any technical term you must use.
7. Reply in the requested language."""


class AssistantService:
    """Grounded summarisation + Q&A + image description, with graceful
    degradation to a deterministic template path when no model server is
    reachable (the website must never depend on a GPU being up).

    A model REGISTRY in config.yaml lists the switchable models; the runtime
    selection persists in .cache/assistant_model.json so users can scale
    quality against their hardware from the dashboard without config edits.
    """

    def __init__(self, cfg: Config, rag=None, translation=None):
        self.cfg = cfg
        self.conf = cfg.assistant
        self.rag = rag
        self.translation = translation
        self._registry: dict = self.conf.get("models") or {}
        self._active_key: str | None = self._load_model_pref()
        self._semaphore = threading.Semaphore(
            int(self.conf.get("max_concurrent_requests", 8)))
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()
        self._summary_cache: dict[tuple, tuple[float, dict]] = {}
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # model registry (runtime switching)
    # ------------------------------------------------------------------ #
    def _load_model_pref(self) -> str | None:
        """Persisted user selection wins, else the configured default; the
        key must exist in the registry (stale prefs fall back silently)."""
        default = self.conf.get("active_model")
        try:
            pref = json.loads(MODEL_PREFS_PATH.read_text(encoding="utf-8"))
            key = pref.get("model")
            if key and (not self._registry or key in self._registry):
                return key
        except Exception:  # noqa: BLE001 - missing/corrupt pref file
            pass
        if default and (not self._registry or default in self._registry):
            return default
        return None

    def _model_conf(self) -> dict:
        """Effective model settings: registry entry for the active key, or
        the legacy single-backend config when no registry is defined."""
        if self._active_key and self._active_key in self._registry:
            entry = dict(self._registry[self._active_key])
            entry["key"] = self._active_key
            return entry
        backend = self.conf.get("backend", "template")
        model = (self.conf.get(backend, {}) or {}).get("model") \
            if backend in ("vllm", "ollama") else None
        return {"key": None, "backend": backend, "model": model}

    def list_models(self) -> list[dict]:
        """Registry for the dashboard switcher: metadata + active flag."""
        out = []
        for key, m in self._registry.items():
            out.append({
                "key": key,
                "backend": m.get("backend", "template"),
                "model": m.get("model"),
                "vram_gb": m.get("vram_gb"),
                "download_gb": m.get("download_gb"),
                "description": m.get("description", ""),
                "active": key == self._active_key,
            })
        if not out:  # legacy config without a registry
            mc = self._model_conf()
            out.append({**mc, "vram_gb": None, "download_gb": None,
                        "description": "configured model", "active": True})
        return out

    def switch_model(self, key: str) -> dict:
        """Switch the active model at runtime and persist the choice."""
        if self._registry and key not in self._registry:
            raise ValueError(f"unknown model {key!r} - not in registry")
        self._active_key = key
        try:
            MODEL_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
            MODEL_PREFS_PATH.write_text(
                json.dumps({"model": key, "switched_at":
                            datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - persistence is best-effort
            log.warning("could not persist model choice: %s", exc)
        with self._client_lock:          # rebuild the HTTP client lazily
            if self._client is not None:
                self._client.close()
                self._client = None
        with self._cache_lock:           # summaries are model-specific
            self._summary_cache.clear()
        log.info("assistant model switched to %s", key)
        return self.status()

    # ------------------------------------------------------------------ #
    # backend plumbing
    # ------------------------------------------------------------------ #
    @property
    def backend_name(self) -> str:
        return self._model_conf().get("backend", "template")

    @property
    def model_name(self) -> str:
        return self._model_conf().get("model") or "deterministic-template"

    def _http(self) -> httpx.Client:
        if self.backend_name == "vllm":
            base = self.conf["vllm"]["base_url"]
            timeout = float(self.conf["vllm"].get("timeout_s", 30))
            headers = {"Authorization":
                       f"Bearer {self.conf['vllm'].get('api_key', 'EMPTY')}"}
        else:
            base = self.conf["ollama"]["base_url"]
            timeout = float(self.conf["ollama"].get("timeout_s", 60))
            headers = {}
        with self._client_lock:
            if self._client is None:
                self._client = httpx.Client(
                    base_url=base, timeout=timeout, headers=headers)
        return self._client

    def _chat(self, messages: list[dict]) -> str:
        """One completion against the configured backend. Raises on any
        transport / protocol failure; callers fall back to the template."""
        with self._semaphore:
            if self.backend_name == "vllm":
                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": float(self.conf.get("temperature", 0.2)),
                    "max_tokens": int(self.conf.get("max_output_tokens", 512)),
                }
                r = self._http().post("/chat/completions", json=payload)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
            # Ollama OpenAI-compatible endpoint
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": float(self.conf.get("temperature", 0.2)),
                    "num_predict": int(self.conf.get("max_output_tokens", 512)),
                },
            }
            r = self._http().post("/v1/chat/completions", json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    def status(self) -> dict:
        """Backend probe for /health and the dashboard status pill."""
        mc = self._model_conf()
        out = {"backend": self.backend_name, "model": self.model_name,
               "active_model": mc.get("key"), "available": False}
        if self.backend_name == "template":
            out["available"] = True
            return out
        try:
            if self.backend_name == "vllm":
                r = self._http().get("/models")
                out["available"] = r.status_code == 200
            else:
                r = self._http().get("/api/tags")
                out["available"] = (
                    r.status_code == 200
                    and any(m.get("name", "").startswith(self.model_name)
                            for m in r.json().get("models", [])))
        except Exception as exc:  # noqa: BLE001 - probe must never raise
            log.info("assistant backend probe failed: %s", exc)
        return out

    # ------------------------------------------------------------------ #
    # prompt assembly
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fingerprint(advisory: dict, language: str) -> tuple:
        """Cache key: everything that changes the summary text, bucketed so
        near-identical advisories (same class, same drivers, same day) share
        one generation."""
        comp = advisory.get("components") or {}
        q = advisory.get("data_quality") or {}
        return (
            advisory.get("class"), advisory.get("block_reason"),
            advisory.get("species", {}).get("scientific"),
            advisory.get("window", {}).get("start", "")[:10],
            round((comp.get("C") or 0) * 10), round((comp.get("W") or 0) * 10),
            round((comp.get("B") or 0) * 10), bool(q.get("degraded")),
            language,
        )

    def _grounded_messages(self, question: str, advisory: dict | None,
                           passages: list[dict], language: str,
                           image: dict | None = None) -> list[dict]:
        blocks = [f"LANGUAGE: Reply in language code '{language}'.\n"]
        if advisory:
            blocks.append("ADVISORY DATA (authoritative, do not contradict):\n"
                          + json.dumps(
                              {k: advisory.get(k) for k in (
                                  "class", "score", "components", "observed",
                                  "species", "block_reason", "citation",
                                  "data_quality")}
                              if advisory.get("allowed") else
                              {k: advisory.get(k) for k in (
                                  "class", "allowed", "block_reason",
                                  "citation", "species")},
                              default=str, indent=1) + "\n")
        if passages:
            numbered = "\n".join(
                f"[{i + 1}] {p.get('source', 'source')}: {p.get('text', '')}"
                for i, p in enumerate(passages))
            blocks.append("CONTEXT PASSAGES (cite as [n]):\n" + numbered + "\n")
        else:
            blocks.append("CONTEXT PASSAGES: none retrieved for this "
                          "question - say so if the answer needs them.\n")
        if image:
            blocks.append(f"An image is attached ({image.get('kind', 'photo')}"
                          "). Describe only what is visible.\n")
        blocks.append("QUESTION: " + question)
        content = [{"type": "text", "text": "".join(blocks)}]
        if image and image.get("data_base64"):
            content.append({"type": "image_url", "image_url": {
                "url": f"data:{image.get('mime', 'image/jpeg')};base64,"
                       + image["data_base64"]}})
        return [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content}]

    # ------------------------------------------------------------------ #
    # guardrails
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cited_indices(answer: str) -> set[int]:
        return {int(m) for m in re.findall(r"\[(\d{1,2})\]", answer)}

    def _check_grounded(self, answer: str, passages: list[dict]) -> bool:
        """Answers over retrieved context must cite at least one passage that
        actually exists; uncited claims are treated as unverified."""
        if not passages:
            return True  # nothing to ground on; template handles it
        cited = self._cited_indices(answer)
        return bool(cited) and cited <= set(range(1, len(passages) + 1))

    def _enforce_class_consistency(self, answer: str,
                                   advisory: dict | None) -> str:
        """The verdict line always accompanies the answer; the assistant can
        add nuance but never override the traffic light."""
        if not advisory:
            return answer
        cls = advisory.get("class")
        if not cls:
            return answer
        word = CLASS_WORDS.get(cls, cls)
        if advisory.get("allowed") is False:
            reason = advisory.get("block_reason") or "not allowed today"
            if _ENCOURAGEMENT.search(answer) or word.lower() not in answer.lower():
                answer = (f"STOP - {reason}.\n\n" + answer)
        elif word.lower() not in answer.lower() and cls == "PROCEED":
            pass  # summaries lead with the class; Q&A need not repeat it
        return answer

    # ------------------------------------------------------------------ #
    # localization (template path: same languages as the dashboard UI)
    # ------------------------------------------------------------------ #
    def _localize(self, text: str, language: str) -> str:
        if language == "en" or self.translation is None:
            return text
        try:
            out = self.translation.translate_batch([text], language)
            if out and out[0]:
                return out[0]
        except Exception:  # noqa: BLE001 - translation is best-effort
            pass
        return text

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def summarize_advisory(self, advisory: dict,
                           language: str = "en") -> dict:
        """Decision-support summary of one advisory: verdict, what drove it,
        what to watch, how old the data is. Cached; degrades to template."""
        key = self._fingerprint(advisory, language)
        ttl = int(self.conf.get("summary_cache_ttl_s", 900))
        now = time.monotonic()
        with self._cache_lock:
            hit = self._summary_cache.get(key)
            if hit and now - hit[0] < ttl:
                return {**hit[1], "cached": True}

        result = self._llm_summarize(advisory, language)
        if result is None:
            result = self._template_summary(advisory, language)
        with self._cache_lock:
            self._summary_cache[key] = (now, result)
            if len(self._summary_cache) > 256:  # bound the cache
                oldest = min(self._summary_cache.items(), key=lambda kv: kv[1][0])
                self._summary_cache.pop(oldest[0], None)
        return {**result, "cached": False}

    def _llm_summarize(self, advisory: dict, language: str) -> dict | None:
        if self.backend_name == "template":
            return None
        passages = (advisory.get("context") or {}).get("passages", [])
        question = ("Explain this fishing advisory to a fisher in plain "
                    "words: the verdict, the one or two things that drove "
                    "it, what to watch out for, and how old the data is.")
        try:
            answer = self._chat(self._grounded_messages(
                question, advisory, passages, language))
            if not self._check_grounded(answer, passages):
                log.warning("summary failed grounding check; using template")
                return None
            return {"summary": self._enforce_class_consistency(
                        answer, advisory),
                    "backend": self.backend_name,
                    "model": self.model_name,
                    "grounded": bool(passages)}
        except Exception as exc:  # noqa: BLE001 - never block the advisory
            log.warning("LLM summary failed (%s); template fallback", exc)
            return None

    def _template_summary(self, advisory: dict, language: str) -> dict:
        """Deterministic, zero-LLM summary - the same facts the dashboard
        renders, as text. Always available, including CPU-only deployments."""
        if not advisory.get("allowed"):
            text = (f"STOP - {advisory.get('block_reason', 'not allowed')}. "
                    f"This comes from {advisory.get('citation', 'the rules')}. "
                    "The system cannot advise fishing here now; the sea gets "
                    "a break and you avoid a fine.")
        else:
            c = advisory.get("components") or {}
            o = advisory.get("observed") or {}
            weather = ("calm seas" if c.get("W", 0) >= 0.66 else
                       "changing conditions" if c.get("W", 0) >= 0.33 else
                       "rough seas")
            fish = ("likely in this area" if c.get("C", 0) >= 0.6 else
                    "possibly in this area" if c.get("C", 0) >= 0.35 else
                    "unlikely in this area")
            risk = ("low" if c.get("B", 1) < 0.35 else
                    "some" if c.get("B", 1) < 0.6 else "high")
            details = []
            if o.get("wind_speed_ms") is not None:
                details.append(f"wind {o['wind_speed_ms'] * 3.6:.0f} km/h")
            if o.get("wave_height_m") is not None:
                details.append(f"waves {o['wave_height_m']:.1f} m")
            species = advisory.get("species", {}).get("common") or "your target"
            text = (f"{CLASS_WORDS.get(advisory['class'], advisory['class'])} - "
                    f"{weather} ({', '.join(details) or 'conditions measured at sea'})"
                    f", {species} {fish}, and {risk} risk of harm to young "
                    "fish and habitats.")
        q = advisory.get("data_quality") or {}
        if q.get("degraded"):
            text += (f" Note: some data is {q.get('max_age_hours')} hours old "
                     "(served from cache).")
        return {"summary": self._localize(text, language), "backend": "template",
                "model": "deterministic-template", "grounded": False}

    def answer_question(self, question: str, language: str = "en",
                        advisory: dict | None = None, species: str | None = None,
                        lat: float | None = None, lon: float | None = None,
                        when: datetime | None = None) -> dict:
        """Grounded Q&A: retrieve context, generate a cited answer, verify
        grounding and class consistency; degrade to a transparent fallback
        that surfaces the retrieved passages instead of improvising."""
        passages: list[dict] = []
        if self.rag is not None and (species or (lat is not None and lon is not None)):
            try:
                ctx = self.rag.retrieve_context(
                    question, species or "Sardinella longiceps",
                    lat if lat is not None else 9.93,
                    lon if lon is not None else 76.26,
                    when or datetime.now(timezone.utc),
                    top_k=int(self.conf.get("grounding", {})
                              .get("max_context_passages", 6)))
                passages = ctx.get("passages", [])
            except Exception as exc:  # noqa: BLE001 - retrieval must never block
                log.warning("assistant retrieval failed: %s", exc)

        answer, backend = None, self.backend_name
        if self.backend_name != "template":
            try:
                answer = self._chat(self._grounded_messages(
                    question, advisory, passages, language))
                if not self._check_grounded(answer, passages):
                    answer = None
            except Exception as exc:  # noqa: BLE001
                log.warning("assistant answer failed (%s); fallback", exc)

        if answer is None:
            backend = "template"
            answer = self._localize(
                self._template_answer(question, advisory, passages), language)

        return {
            "answer": self._enforce_class_consistency(answer, advisory),
            "backend": backend,
            "model": self.model_name if backend != "template"
                     else "deterministic-template",
            "grounded_passages": passages,
            "advisory_class": (advisory or {}).get("class"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _template_answer(question: str, advisory: dict | None,
                         passages: list[dict]) -> str:
        """No-LLM answer: the authoritative advisory line plus the top
        retrieved passages, quoted verbatim - transparency over fluency."""
        parts = []
        if advisory is not None:
            if advisory.get("allowed") is False:
                parts.append(f"The advisory for this request is DO NOT FISH: "
                             f"{advisory.get('block_reason')} "
                             f"({advisory.get('citation')}).")
            else:
                parts.append(
                    f"The current advisory is {advisory['class']} "
                    f"(score {advisory.get('score')}).")
        if passages:
            top = " ".join(p.get("text", "") for p in passages[:2]).strip()
            parts.append("From the reference library: " + (top[:400] or "…"))
            parts.append("The AI answer service is not reachable right now, "
                         "so these are the exact source passages.")
        else:
            parts.append("I do not have retrieved context for this question "
                         "right now. Please rephrase, or check with your "
                         "fisheries department for anything urgent.")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ #
    def describe_image(self, data_base64: str, kind: str = "catch",
                       question: str | None = None,
                       language: str = "en") -> dict:
        """Vision-language reading of a catch photo, satellite tile or chart.
        Requires the VLM backend; the template path cannot see images, and
        says so rather than guessing."""
        prompt = {
            "catch": "This is a photo of a fisher's catch. Describe what you "
                     "see: species shapes, approximate sizes, anything that "
                     "looks like juvenile fish or protected species. Only "
                     "report what is clearly visible.",
            "satellite": "This is a satellite tile of the sea. Describe "
                         "visible features: clouds, turbidity or plume "
                         "patterns, colour fronts. Only report what is "
                         "clearly visible.",
            "chart": "This is a chart or screenshot. Explain in plain words "
                     "what it shows.",
        }.get(kind, "Describe this image in plain words.")
        if question:
            prompt += f"\nThen answer: {question}"
        try:
            answer = self._chat(self._grounded_messages(
                prompt, None, [], language,
                image={"kind": kind, "data_base64": data_base64}))
            return {"description": answer, "backend": self.backend_name,
                    "model": self.model_name, "kind": kind}
        except Exception as exc:  # noqa: BLE001
            log.warning("image description failed: %s", exc)
            return {"description": "The image service is not available right "
                                   "now. Please try again later.",
                    "backend": "template", "model": "deterministic-template",
                    "kind": kind, "error": str(exc)}

    @staticmethod
    def encode_image(image_bytes: bytes, mime: str = "image/jpeg") -> str:
        return base64.b64encode(image_bytes).decode("ascii")

    @staticmethod
    def fingerprint_of(payload: dict) -> str:
        return hashlib.sha1(
            json.dumps(payload, sort_keys=True, default=str)
            .encode("utf-8")).hexdigest()[:12]

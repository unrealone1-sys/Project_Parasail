# The ParaSail AI Assistant

A **grounded, self-hosted, vision-capable assistant** integrated into the
ParaSail website (development phase P7). It gives fishers, officers and
coastal communities three things the advisory dashboard alone cannot:

1. **Plain-language advisory summaries** — decision-making analysis: the
   verdict, the one or two things that drove it, what to watch, and how
   old the data is.
2. **Question answering** — "Is it safe to take a small boat out tomorrow
   morning?" — answered from the live advisory and the retrieval corpus,
   with citations, in the user's language.
3. **Image understanding** — upload a catch photo, satellite tile or chart
   and get a plain description of what is visible.

Everything runs **locally**: one open-source vision-language model
(Qwen2.5-VL-7B-Instruct-AWQ, Apache 2.0) served by vLLM on a single GPU in
the 8–12 GB VRAM class. There are no external AI API calls, so unlimited
daily traffic creates no per-token costs. Hardware specifications:
[`PRODUCTION_HARDWARE.md`](PRODUCTION_HARDWARE.md).

## Design contract: the assistant explains, it never decides

| Guardrail | Enforcement |
|---|---|
| **Grounded answers only** | The prompt contains only the advisory payload and numbered retrieved passages; answers must cite them as `[n]`; a post-generation check rejects answers whose citations do not resolve to real passages |
| **Verdict is authoritative** | The advisory class (PROCEED … DO NOT FISH) is computed by the deterministic rules engine and scoring, never by the model; the class-consistency guard prepends the authoritative verdict when a blocked advisory would otherwise be softened |
| **Refusal over invention** | With no retrieved context the assistant says so instead of improvising |
| **Backend transparency** | Every response names the `backend` and `model` that produced it (asserted by validation family T5) |
| **Always available** | If the model server is down or absent, a deterministic template path produces the same response schema from the same data — the website keeps working on CPU-only deployments |
| **Bounded load** | A semaphore caps concurrent generations; near-identical advisories share one cached summary (TTL from config) |

## Architecture

```
                    ┌──────────────────────────────────────────────┐
 user question ────►│ AssistantService (src/parasail/assistant.py) │
 (chat, language,   │                                              │
  position, photo)  │ 1. retrieve: RagService (Qdrant text+sat)    │
                    │ 2. optional: AdvisoryEngine advisory payload  │
                    │ 3. build grounded prompt (system policy)     │
                    │ 4. generate: vLLM (Qwen2.5-VL-7B-AWQ, local) │
                    │    └─ Ollama fallback ── template fallback   │
                    │ 5. guardrails: citation + class consistency  │
                    └──────────────────────────────────────────────┘
                          ▼ cited answer + backend ID + verdict
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /assistant/summarize` | Advisory + plain-language summary (request body = same as `POST /advisory`) |
| `POST /assistant/ask` | Grounded Q&A; optional `lat/lon/species/start/hours` attach the live advisory so answers cannot contradict the verdict |
| `POST /assistant/describe-image` | Vision-language reading of a base64 image (`kind`: catch / satellite / chart) |
| `GET /assistant/status` | Backend probe for monitoring |

Examples:

```bash
# Plain-language explanation of tonight's advisory
curl -X POST http://localhost:8000/assistant/summarize \
  -H "Content-Type: application/json" \
  -d '{"lat": 9.93, "lon": 76.26, "species": "Sardinella longiceps",
       "start": "2026-09-14T04:00:00Z", "hours": 24}'

# Ask a question (grounded in the live advisory + rule library)
curl -X POST http://localhost:8000/assistant/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why should I not fish for sardine in June?",
       "language": "en", "species": "Sardinella longiceps",
       "lat": 9.93, "lon": 76.26, "start": "2026-06-20T04:00:00Z"}'
```

Response shape (`/assistant/ask`):

```json
{
  "answer": "STOP - spawning protection - monsoon fishing closure.\n\n...",
  "backend": "vllm",
  "model": "Qwen/Qwen2.5-VL-7B-Instruct-AWQ",
  "grounded_passages": [{"text": "...", "source": "regulations", "citation": "..."}],
  "advisory_class": "DO NOT FISH",
  "generated_at": "2026-09-13T..."
}
```

## Backends and configuration

Configured in `config.yaml` under `assistant:` (all values are data, not
code — swapping the model never touches source):

```yaml
assistant:
  enabled: true
  backend: vllm            # vllm | ollama | template
  vllm:
    base_url: http://localhost:8001/v1
    model: Qwen/Qwen2.5-VL-7B-Instruct-AWQ
  ollama:
    base_url: http://localhost:11434
    model: qwen2.5vl:7b
  max_concurrent_requests: 8
  temperature: 0.2
  summary_cache_ttl_s: 900
```

Environment overrides: `PARASAIL_VLLM_URL`, `PARASAIL_OLLAMA_URL` (used by
docker-compose).

Running the model server:

```bash
# vLLM (production): starts with the full stack
docker compose --profile gpu up -d

# or directly on the host
vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
  --quantization awq --max-model-len 16384 --max-num-seqs 32 --port 8001

# laptop profile (6 GB GPUs, e.g. RTX 4050): the 3B sibling via Ollama
ollama pull qwen2.5vl:3b
#   then in config.yaml:  backend: ollama / model: qwen2.5vl:3b /
#   max_concurrent_requests: 2   (details: PRODUCTION_HARDWARE.md, Tier L)
```

## Multilingual

The dashboard language selector (10 Indian coastal languages) is passed
through to the assistant; the VLM is instructed to reply in the requested
language. In template mode, deterministic answers are routed through the
existing `TranslationService`, so language coverage is identical with or
without a GPU.

## Validation (family T5)

`python scripts/run_validation.py` asserts: blocked summaries keep the
DO NOT FISH verdict and reason; scored summaries name the class and data
age; the cache engages for repeat advisories; the class-consistency guard
overrides encouragement; citation checks reject uncited or out-of-range
citations; no-context answers refuse instead of improvising; every answer
names its backend; and (when a model server is running) live answers land
inside the configured latency budget.

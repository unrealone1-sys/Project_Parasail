# ParaSail

**P**redictive **A**dvisory and **R**etrieval-**A**ugmented **S**ystem **A**dvancing **I**nformed **L**ivelihoods

A production-style, retrieval-augmented geospatial decision support system for
sustainable fishing, marine conservation and coastal livelihood resilience.
Companion reference implementation for the Experimental Paper
*ParaSail: A Retrieval-Augmented Geospatial Decision Support System for
Sustainable Fishing, Marine Conservation and Coastal Livelihood Resilience*
(26th Digital Blue Economy Summit; Anantha Krishnan AS, Naipunnya School of
Management, Cherthala, India).

---

## 1. What ParaSail does

Given a position, a target species and a time window, ParaSail returns one
advisory:

1. **Hard constraints first** — if the point falls inside an active marine
   protected area or a seasonal closure for that species, the advisory is
   `DO NOT FISH` with the blocking reason and citation. No score is computed.
2. **Otherwise, score** the trip on a transparent sustainability index

   `S = 0.45*C + 0.25*W + 0.30*(1 - B)`

   where `C` is a catch-likelihood composite, `W` a weather-safety component
   and `B` a bycatch / ecological-risk proxy, mapped to four classes:
   `PROCEED` (S >= 0.75), `PROCEED WITH CAUTION` (0.60–0.75),
   `DELAY OR RELOCATE` (0.40–0.60), `DO NOT FISH` (< 0.40).
3. **Explain by retrieval** — the advisory carries top-k retrieved passages
   (regulations, closure calendars, conservation guidance, local ecological
   knowledge) and satellite tiles drawn from a dual-collection Qdrant store.
4. **Explain in conversation** — a self-hosted, vision-capable AI assistant
   (phase P7) summarises every advisory in plain language for the website,
   answers users' questions in their own words and language with citations,
   and reads uploaded catch photos, satellite tiles and charts. It explains
   the decision; it never makes it. See `docs/AI_ASSISTANT.md`.

## 2. Architecture (six layers)

```
INGESTION        Open-Meteo - Copernicus - ERDDAP - GBIF/OBIS - FishBase/WoRMS - Sentinel-2/3
    |
PROCESSING       validation - taxonomy normalisation - common grid - features - quality gates
    |
PREDICTION       YOLOv8n - ViT-B/16+LoRA - LSTM(24-step) - random-forest habitat fallback
    |
RAG              Qdrant text collection + Qdrant satellite collection - hybrid top-k retrieval
    |
ADVISORY         rules engine (hard blocks) - scoring - 4 classes - FastAPI + dashboard
    |
ASSISTANT        grounded VLM (Qwen2.5-VL-7B AWQ on vLLM) - plain-language summaries -
                 cited Q&A - catch-photo / tile / chart reading - template fallback
```

Shared infrastructure: PostgreSQL + PostGIS, Qdrant, vLLM inference server,
Docker Compose, YAML-configured deployment (region, species, closures,
models, score weights and the assistant model are data, not code).

## 3. Selected models (and why)

| Task | Selected model | Rationale |
|---|---|---|
| Catch-image detection | `yolov8n.pt` (Ultralytics) | Real-time on modest hardware; mature toolchain |
| Species classification | `google/vit-base-patch16-224` + PEFT LoRA (r=8, query/value projections of all 12 blocks) | Fine-grained accuracy at under 1% trainable parameters (0.29M / 85.8M = 0.34%) |
| Movement tendency (24 h) | 2-layer LSTM, hidden size 128 | Short-horizon spatiotemporal sequences for data-rich species |
| Habitat suitability | scikit-learn `RandomForestClassifier` | Interpretable, robust fallback for data-poor taxa |
| Text embeddings (RAG) | `sentence-transformers/all-MiniLM-L6-v2` | Fast 384-d sentence embeddings over regulations and guidance |
| Satellite tile embeddings | OpenCLIP `ViT-B-32` (laion2b_s34b_b79k) | Similarity search over unlabelled Sentinel tiles |
| Conversational assistant, summaries, image understanding | `Qwen/Qwen2.5-VL-7B-Instruct-AWQ` served by vLLM (Apache 2.0) | One open-source vision-language model for all assistant jobs; ~6.9 GB 4-bit weights fit an 8–12 GB VRAM budget; strong document/chart/catch-photo understanding; continuous batching sustains high traffic locally — no per-token API costs |

Selection criterion throughout: **coastal deployability on mid-range
hardware, not leaderboard position.** The assistant runs fully self-hosted;
a deterministic template path keeps the website functional on CPU-only
deployments. Production hardware guidance (VRAM budgets, throughput,
recommended GPU tiers, cost model vs cloud APIs):
[`docs/PRODUCTION_HARDWARE.md`](docs/PRODUCTION_HARDWARE.md).

## 4. Development phases (from scratch)

| Phase | Focus | Acceptance gate |
|---|---|---|
| P1 | Governance, region selection, regulatory inventory | region + rules inventory signed off |
| P2 | Ingestion pipeline, database schema | live fetches validated; freshness audit passes |
| P3 | Baseline predictive models | baselines beat naive persistence |
| P4 | LoRA fine-tuning, custom data ingestion | training converges within GPU memory budget |
| P5 | RAG integration, advisory API | closure/MPA blocks exact; top-k retrieval relevant |
| P6 | Dashboard, pilot feedback loop | advisory schema legible to pilot users |
| P7 | Grounded AI assistant, production hardening | assistant answers grounded, cited and class-consistent; template fallback exact; latency within budget |

Every gate maps onto a validation test family (see `scripts/run_validation.py`):
T1 live fetch, T2 rule enforcement, T3 scoring behaviour, T4 retrieval
relevance, T5 assistant behaviour.

## 5. Repository layout

```
parasail/
├── README.md                  this file
├── requirements.txt           Python dependencies
├── config.yaml                region, species, closures, weights, models, assistant
├── models/                    (gitignored) the AI weights live HERE on this
│                              machine: OLLAMA_MODELS points at this folder
├── .env                       (gitignored) local secrets: tokens, credentials
├── docker-compose.yml         api + postgres/postgis + qdrant + vllm (gpu profile) + ollama
├── db/schema.sql              PostGIS schema
├── docs/
│   ├── AI_ASSISTANT.md        assistant architecture, API, guardrails
│   ├── PREDICTION.md          suggested-fish model: features, accuracy, retraining
│   └── PRODUCTION_HARDWARE.md model VRAM budget, throughput, GPU tiers, costs
├── src/parasail/
│   ├── config.py              YAML configuration loader
│   ├── ingestion.py           P2 - live sources with caching + offline fallback
│   ├── processing.py          P2 - validation, regridding, features, quality gates
│   ├── rules.py               P5 - MPA / closure hard constraints (PostGIS)
│   ├── rag.py                 P5 - Qdrant dual collections + hybrid retrieval
│   ├── advisory.py            P5 - scoring + advisory assembly
│   ├── assistant.py           P7 - grounded VLM assistant + guardrails + fallback
│   ├── api.py                 P6/P7 - FastAPI service + dashboard with AI chat
│   └── models/
│       ├── habitat.py         P3 - random-forest habitat suitability
│       ├── forecaster.py      P3 - LSTM movement-tendency model
│       ├── classifier.py      P4 - ViT + LoRA species classifier
│       └── detection.py       P3 - YOLOv8n catch detector
├── train/
│   ├── train_lora.py          P4 - LoRA fine-tuning loop
│   └── train_forecaster.py    P3 - LSTM training + persistence baseline gate
└── scripts/
    ├── seed_regulations.py    P5 - regulation corpus -> Qdrant text collection
    ├── embed_satellite_tiles.py  P5 - Sentinel tiles -> OpenCLIP -> Qdrant
    └── run_validation.py      T1-T5 evaluation suite
```

## 6. Quickstart

```bash
# 1. infrastructure (postgres+postgis, qdrant, api)
docker compose up -d
#    with the self-hosted AI assistant (needs an NVIDIA GPU, 12 GB+ VRAM,
#    and the NVIDIA container toolkit):
docker compose --profile gpu up -d
#    (the api container installs the slim requirements-api.txt; use
#     requirements.txt in a local environment for training and corpus seeding)

# 2. python environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. initialise schema and corpora
psql $DATABASE_URL -f db/schema.sql
python scripts/seed_regulations.py --corpus data/regulations.jsonl
python scripts/embed_satellite_tiles.py --tiles data/sentinel/

# 4. (optional) train / adapt models
python train/train_forecaster.py --config config.yaml
python train/train_lora.py --data data/species_images --epochs 10

# 5. run the validation suite (T1-T5)
python scripts/run_validation.py

# 6. serve
uvicorn parasail.api:app --reload --port 8000
```

Example advisory request:

```bash
curl -X POST http://localhost:8000/advisory \
  -H "Content-Type: application/json" \
  -d '{"lat": 9.93, "lon": 76.26, "species": "Sardinella longiceps",
       "start": "2026-09-14T04:00:00Z", "hours": 24}'
```

Example assistant requests:

```bash
# plain-language decision-support summary
curl -X POST http://localhost:8000/assistant/summarize \
  -H "Content-Type: application/json" \
  -d '{"lat": 9.93, "lon": 76.26, "species": "Sardinella longiceps",
       "start": "2026-09-14T04:00:00Z", "hours": 24}'

# ask a question in your own words (grounded, cited, multilingual)
curl -X POST http://localhost:8000/assistant/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why should I not fish for sardine in June?",
       "language": "en", "species": "Sardinella longiceps",
       "lat": 9.93, "lon": 76.26, "start": "2026-06-20T04:00:00Z"}'
```

Running the AI locally (no external AI API is ever called):

```bash
# production server: vLLM + Qwen2.5-VL-7B-Instruct-AWQ (~6.9 GB weights)
vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
  --quantization awq --max-model-len 16384 --max-num-seqs 32 --port 8001

# or a lighter local fallback
ollama pull qwen2.5vl:7b
```

### Mobile / remote testing (PWA + Tailscale)

The dashboard is an installable mobile web app (manifest, offline app-shell
service worker, touch-optimised layout). To test from phones and other
devices, host it on your tailnet:

```bash
uvicorn parasail.api:app --host 0.0.0.0 --port 8000   # all interfaces
tailscale serve --bg 8000                              # HTTPS on your tailnet
```

Full instructions: [`docs/REMOTE_ACCESS.md`](docs/REMOTE_ACCESS.md).

## 7. Ethics, licensing and governance

- All ingested sources are open-licensed or publicly documented.
- The AI stack is fully open source (Apache-2.0 model, open serving stack),
  runs locally, and sends no user data to third-party AI services; request
  volume therefore never generates per-token API costs.
- Local-knowledge ingestion is consent-gated and attributed at source.
- The optional AIS/VMS module is disabled by default (legal restrictions on
  vessel-effort data in many jurisdictions).
- ParaSail is advisory: it recommends, never commands, and every advisory
  displays the age of the data it was computed from. The AI assistant
  extends this principle: it explains decisions with citations, cannot
  contradict the authoritative advisory class, and names the backend that
  produced every answer.

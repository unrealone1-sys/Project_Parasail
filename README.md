# ParaSail

A self-hosted advisory system for small-scale fishers on the Indian coast. ParaSail fuses live weather and ocean conditions, Marine Protected Area (MPA) boundaries, species ecology and community knowledge into a transparent advisory — **PROCEED / CAUTION / DELAY OR RELOCATE / DO NOT FISH** — and explains it in plain language, in the fisher's own language, using a locally hosted open-source vision-language model. **No cloud AI, no per-question costs.**

---

## Repository Layout

| Path | Contents |
|------|----------|
| [`parasail/`](parasail/) | The application: FastAPI dashboard + advisory API, grounded AI assistant, deployment configs, docs |
| [`ParaSail_Paper/`](ParaSail_Paper/) | Research paper and both presentation decks — sources, figures, QA scripts and renders |

---

## Quick Start (5 minutes)

```bash
# 1. Clone
git clone https://github.com/unrealone1-sys/Parasail.git
cd Parasail/parasail

# 2. Python environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt && pip install -e .

# 3. Start databases (PostgreSQL + PostGIS, Qdrant)
docker compose up -d db qdrant

# 4. Generate YOUR admin API key (one-time)
python scripts/generate_api_key.py --name your-name --role admin
# → Copy the printed SHA-256 hash into config.yaml under security.api_keys
#   (or export PARASAIL_API_KEYS as a JSON env var — see SECURITY.md)

# 5. Start full stack (requires Administrator for Ollama model path)
#    This starts: Ollama (keeps model in VRAM 24/7), API, health checks
scripts/start_all.bat            # Windows (Run as Administrator)
# ./scripts/start_stack.ps1      # or PowerShell

# 6. Open dashboard
#    http://localhost:8000
#    → Click map, pick species/date, "Get my advice"
#    → "Ask ParaSail" chat panel for grounded Q&A
```

> **No GPU / no AI model?** The dashboard, advisory engine, and chat work out of the box — the assistant answers in deterministic template mode (cites the same rule library) and says which backend it used. Install the AI later via `parasail/docs/AI_SETUP.md`.

---

## Developer Onboarding

### Prerequisites
- Windows 10/11 (tested), or Linux/macOS with Docker
- Python 3.11+
- Docker Desktop (for PostgreSQL + Qdrant)
- NVIDIA GPU (RTX 3060 12 GB minimum for 7B model; RTX 4050 6 GB for 3B laptop model)

### Generate Your API Key
```bash
cd parasail
python scripts/generate_api_key.py --name alice --role admin
```
Output:
```
API key (store securely - shown once):
  xK9mN2pQ... (urlsafe, 43 chars)

Paste into config.yaml -> security.api_keys:
  api_keys:
    - name: alice
      key_hash: a1b2c3d4...   # SHA-256 hash, safe to commit
      role: admin
```
Add the hash to `config.yaml` **or** inject via environment (recommended for CI/production):
```bash
export PARASAIL_API_KEYS='[{"name":"alice","key_hash":"a1b2c3d4...","role":"admin"}]'
```

### Key Files to Know
| File | Purpose |
|------|---------|
| `config.yaml` | Single source of truth: region, species (12), advisory weights, model registry, ingestion freshness |
| `parasail/src/parasail/api.py` | All endpoints: `/advisory`, `/telemetry`, `/assistant/*`, `/admin/stats`, `/health` |
| `parasail/src/parasail/assistant.py` | Grounded VLM (Qwen2.5-VL), citation enforcement, class-consistency guard |
| `parasail/src/parasail/ingestion.py` | Live fetch with provenance (fetched_at, age_hours, stale flag) |
| `parasail/src/parasail/rules.py` | MPA fail-closed guard, seasonal closures |
| `parasail/scripts/start_all.bat` | 24/7 orchestration (admin check, hard kill, warmup) |
| `parasail/docs/AI_SETUP.md` | GPU model install, vLLM/Ollama, LoRA fine-tuning |
| `parasail/docs/PRODUCTION_HARDWARE.md` | 4 hardware tiers, cost model, capacity planning |

### Run Tests
```bash
# Full validation suite (45+ checks)
python scripts/run_validation.py

# Skip live network calls
python scripts/run_validation.py --skip-live
```

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (fisher)                            │
│  PWA dashboard (offline shell, Tailscale HTTPS, 10 languages)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   FastAPI (port 8000)   │
              │  /advisory /telemetry   │
              │  /assistant/ask,summarize│
              │  /fish-suggestions      │
              │  /alerts /admin/stats   │
              └───────────┬─────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐      ┌───────────┐      ┌──────────┐
   │PostgreSQL│      │  Qdrant   │      │  Ollama  │
   │+ PostGIS │      │ (2 coll.) │      │(qwen2.5vl)│
   │16 MPAs   │      │ parasail_ │      │keep_alive│
   │closures  │      │ text/sat  │      │=-1 (24/7)│
   └─────────┘      └───────────┘      └──────────┘
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [`parasail/README.md`](parasail/README.md) | Application guide, endpoints, configuration |
| [`parasail/docs/AI_SETUP.md`](parasail/docs/AI_SETUP.md) | GPU model install, vLLM/Ollama, LoRA fine-tuning |
| [`parasail/docs/PRODUCTION_HARDWARE.md`](parasail/docs/PRODUCTION_HARDWARE.md) | 4 hardware tiers, cost model, capacity planning |
| [`parasail/docs/SECURITY.md`](parasail/docs/SECURITY.md) | Rate limits, RBAC, API keys, hardening checklist |

---

## Presentations (26th Digital Blue Economy Summit)

| File | Slides | Purpose |
|------|--------|---------|
| `ParaSail_Presentation_TechnicalBackup (Ananthakrishnan AS).pptx` | 10 | Technical backup — architecture, scoring, constraints, AI, deployment |
| `ParaSail_Data_Sources_API_Architecture.pptx` | 12 | Data source docs — APIs, freshness contracts, provenance |
| `ParaSail_Speaker_Notes.docx` | — | **Print this** — presenter script for Technical Backup deck |

---

## License

MIT — see [LICENSE](LICENSE). MPA boundary data is derived from OpenStreetMap (© OpenStreetMap contributors, ODbL) and the WDPA; the `authority` property inside each GeoJSON records its source.

---

## Citation

> Anantha Krishnan AS, *ParaSail: Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods*, 26th Digital Blue Economy Summit (Experimental Paper), 2026.
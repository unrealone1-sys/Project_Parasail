# ParaSail AI — Complete Installation Guide

Every command and step needed to get the AI assistant running, tailored to
this machine (Windows 11 · Python 3.11.9 · Docker Desktop 29 with WSL2 ·
Hugging Face CLI 1.26 · NVIDIA RTX 4050 Laptop 6 GB). Copy-paste ready.

> Already verified present on this machine: Python, pip, Docker, WSL2,
> NVIDIA driver (`nvidia-smi` works), HF CLI. Missing: **Ollama** (Path A).
>
> Not needed for the AI: the database — but see §6 if advisories show
> "MPA registry unavailable".

---

## 0. The application itself (one-time, already done on this machine)

```powershell
cd C:\Users\ignun\.zcode\workspace\default\parasail
python -m venv .venv
.venv\Scripts\activate            # PowerShell / CMD
pip install -r requirements.txt
pip install -e .                  # makes `parasail` importable everywhere
uvicorn parasail.api:app --port 8000
```

Dashboard: http://127.0.0.1:8000 — works immediately in built-in template
mode (no AI model, CPU only). Everything below upgrades it to real AI.

---

## 1. PATH A — Ollama (recommended for the RTX 4050, 6 GB)

The 6 GB card cannot fit the 7B AWQ model (~6.9 GB weights alone); the 3B
quantised via Ollama (~2.5 GB) fits with room for the vision encoder.

### 1.1 Install Ollama

Download and run the Windows installer:
**https://ollama.com/download** (OllamaSetup.exe)

Verify (new terminal after install):
```powershell
ollama --version
```

### 1.2 Pull the model (~2.5 GB download, one time)

```powershell
ollama pull qwen2.5vl:3b
```
Files land in `C:\Users\ignun\.ollama\models` (managed by Ollama; never
hand-edit). Ollama runs as a background service on port 11434 — the pull
also warms it up.

### 1.3 Register + select it in ParaSail

The registry entry already exists (`config.yaml` → `assistant.models` →
`qwen2.5vl-3b-laptop`). Select it either way:

- **Dashboard:** open http://127.0.0.1:8000 → "Ask ParaSail" card → dropdown
  (top-right) → choose `qwen2.5vl-3b-laptop · 6 GB`. Persists across restarts.
- **Or via API:**
```powershell
curl.exe -X POST http://127.0.0.1:8000/assistant/model -H "Content-Type: application/json" -d "{\"model\":\"qwen2.5vl-3b-laptop\"}"
```

### 1.4 Restart the app and verify

```powershell
# stop the old server (Ctrl+C in its window), then:
cd C:\Users\ignun\.zcode\workspace\default\parasail
.venv\Scripts\activate
uvicorn parasail.api:app --port 8000
```
Verify:
```powershell
curl.exe http://127.0.0.1:8000/assistant/status
# expect: {"backend":"ollama","model":"qwen2.5vl:3b","active_model":"qwen2.5vl-3b-laptop","available":true,...}
```
In the dashboard, ask something in the chat — the answer line should say
`answer by local AI`.

### 1.5 (Optional) larger Ollama models when you have more VRAM

```powershell
ollama pull qwen2.5vl:7b        # ~6 GB, needs a 10 GB+ card
```
Registry key: `qwen2.5vl-7b-ollama` (already in the switcher).

---

## 2. PATH B — Hugging Face CLI + vLLM (needs 12 GB+ VRAM, or another machine)

Use this on the production/deployment GPU (RTX 4090 / L4 / A100), not the
6 GB laptop — the official 3B is bf16-only (~7.5 GB, too big for 6 GB).

### 2.1 Download the weights with the HF CLI (already installed)

```powershell
pip install -U huggingface_hub
hf download Qwen/Qwen2.5-VL-7B-Instruct-AWQ
```
Lands in `C:\Users\ignun\.cache\huggingface\hub` (~6.9 GB).

### 2.2 Serve with vLLM

vLLM has no native Windows build — run it through Docker (installed) or
WSL2:

```powershell
# Option 1: the ParaSail stack (pulls the model itself into a volume)
cd C:\Users\ignun\.zcode\workspace\default\parasail
docker compose --profile gpu up -d
docker compose logs -f vllm        # wait for "Application startup complete"

# Option 2: standalone, reusing the HF cache you downloaded in 2.1 (WSL2):
wsl
vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ --quantization awq --max-model-len 16384 --port 8001
```

The vLLM service answers on **http://localhost:8001/v1** (OpenAI-compatible).
ParaSail's default active model (`qwen2.5vl-7b-awq`) already points there —
select it in the dashboard dropdown if you switched away.

### 2.3 Verify

```powershell
curl.exe http://127.0.0.1:8000/assistant/status
# expect: backend "vllm", available true
```

---

## 3. Managing models (switcher, registry, offline bundling)

| Task | Command / where |
|---|---|
| List registry | dashboard dropdown, or `curl.exe http://127.0.0.1:8000/assistant/models` |
| Switch model | dashboard dropdown, or `POST /assistant/model {"model":"<key>"}` |
| Add a new model | edit `parasail/config.yaml` → `assistant.models:` (backend/model/vram_gb/description) — appears in the dropdown after page refresh |
| Your current choice | `parasail/.cache/assistant_model.json` |
| Bundle model files for offline deployment | `python scripts/export_model.py --list` then `--model <key>` (copies HF weights into `parasail/models/<key>/`; prints the Ollama store copy command for Ollama models) |
| Import a GGUF you downloaded | `ollama create <name> -f Modelfile` (FROM ./file.gguf), then register with `backend: ollama` |

Registry entry template:
```yaml
assistant:
  models:
    my-new-model:
      backend: ollama        # or vllm
      model: qwen2.5vl:3b    # ollama tag, or HF repo id for vllm
      vram_gb: 6
      download_gb: 2.5
      description: "what shows in the dropdown"
```

---

## 4. Full-stack alternative (database + vectors + AI in one command)

```powershell
cd C:\Users\ignun\.zcode\workspace\default\parasail
docker compose --profile gpu up -d      # db + qdrant + vllm + api
```
Requires the NVIDIA container toolkit (Docker Desktop → Settings →
"Use the WSL 2 based engine" is usually enough on Windows).

---

## 5. Verification checklist (run after any install)

```powershell
# 1. backend is up and visible to the app
curl.exe http://127.0.0.1:8000/assistant/status          # "available": true

# 2. a real AI answer (grounded, names its backend)
curl.exe -X POST http://127.0.0.1:8000/assistant/ask -H "Content-Type: application/json" -d "{\"question\":\"Is it safe to fish tomorrow morning?\",\"language\":\"en\"}"

# 3. the full validation suite (T5 activates its live-backend latency check)
cd C:\Users\ignun\.zcode\workspace\default\parasail
python scripts/run_validation.py
```
On the dashboard: chat answers should end with `answer by local AI`, and the
advisory card's plain-language summary should read fluently (AI) rather than
the formulaic template text.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Chat says "answer by built-in mode" | No model backend reachable. `curl http://127.0.0.1:8000/assistant/status` → check `available`; start Ollama (it autostarts after install) or the vLLM container |
| `ollama: command not found` | New terminal needed after install, or Ollama not on PATH — reopen PowerShell |
| Model switch accepted but still template answers | Ollama service down (`ollama serve`) or the pull didn't finish (`ollama list`) |
| vLLM container exits immediately | GPU too small for the model (7B AWQ needs 12 GB) or NVIDIA runtime disabled in Docker settings |
| Advisories all say "MPA registry unavailable" | That's the fail-closed guard without PostGIS — not an AI issue. `docker compose up -d db qdrant` |
| Port 8000 already in use | Stale server: `netstat -ano | findstr :8000` then `taskkill /PID <pid> /F` |
| Slow first answer | Model warm-up / first inference — subsequent answers are fast |

---

## 7. What runs where (quick reference)

| Component | Port | Process |
|---|---|---|
| ParaSail dashboard + API | 8000 | `uvicorn parasail.api:app` |
| Ollama model server | 11434 | Ollama background service (native Windows) |
| vLLM model server | 8001 | Docker `--profile gpu` or WSL2 |
| PostGIS / Qdrant | 5432 / 6333 | Docker (optional, for full advisory + retrieval) |

Model files never live inside the project: Ollama manages
`~\.ollama\models`, vLLM uses the HF cache / Docker volume, and
`parasail\models\` is only for deliberately bundled offline copies.

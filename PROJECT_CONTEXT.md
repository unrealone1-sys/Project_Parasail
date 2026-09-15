# ParaSail — Project Context & Session Handoff

> **Purpose of this file:** complete, self-contained record of the AI-integration
> work session (September 2026) so any future session/person can resume without
> re-reading the original conversation. Read this first.
>
> **One-line status:** The grounded, self-hosted AI assistant layer (phase P7) is
> implemented, validated, and reflected in the research paper, both decks, the
> figures and all documentation. A dashboard-breaking JS bug found during local
> testing was fixed (see §7). The app runs locally; PostGIS + Ollama are needed
> for full behaviour (see §8).

---

## 1. Original requirements (from the project owner)

1. **Add an AI integration** to ParaSail for: decision-making analysis,
   summarising advisory data in plain language for people on the website, and
   answering their questions (conversational layer).
2. **Reflect the change in all paperwork**: research paper (docx/pdf) and both
   PowerPoint decks (general + technical backup).
3. Must use **open-source vision models** that run in **8–12 GB VRAM**.
4. Must **handle high traffic**.
5. Include **documentation on recommended production hardware**.
6. **The AI must run locally** (self-hosted) — no external AI APIs, so thousands
   of requests/day never pile up per-token costs.
7. Include an **RTX 4050 laptop GPU (6 GB) tier** so the owner can run it locally.
8. The web application must have **decent animations** for visual effects.
9. Dashboard layout follows the owner's mockup (header, controls, map left,
   verdict + telemetry right, likely spots, **"Ask ParaSail" chat at bottom**).
10. Keep this context file so future sessions don't hit context-cache limits.

## 2. Key architecture decisions (verified against primary sources)

| Decision | Choice | Why |
|---|---|---|
| Assistant model | **Qwen2.5-VL-7B-Instruct-AWQ** (Apache 2.0, 8.29B params, 4-bit ≈ 6.9 GB weights) | Fits 8–12 GB VRAM with vision encoder + KV cache; one model does summaries + Q&A + image reading; official AWQ build; first-class vLLM support; DocVQA 95.7 / ChartQA 87.3 (catch photos, tiles, scanned rules) |
| Laptop variant | **Qwen2.5-VL-3B** (~3.75B, Q4 via Ollama ≈ 2.5 GB) | The 7B does NOT fit a 6 GB RTX 4050; the 3B does (total ≈ 4.5–5.5 GB) |
| Serving stack | **vLLM** (PagedAttention, continuous batching) + AWQ | High throughput on one GPU; Kwon et al. SOSP 2023; Lin et al. MLSys 2024 |
| Fallback chain | vllm → ollama → **deterministic template** | Website never depends on a GPU being up; template mode is CPU-only, zero cost |
| Guardrails | Enforced **in code**, not prompts | Citations must resolve to retrieved passages; advisory class is authoritative (AI can never soften DO NOT FISH); refusal over invention; backend named on every answer |
| Multilingual | Model replies in requested language; template path uses existing TranslationService | 10 Indian coastal languages |

**Where the AI model files live (answered):** there is **no model file in the
repository** — models are downloaded on demand:
- Ollama route: `ollama pull qwen2.5vl:3b` (or `:7b`) → stored in
  `C:\Users\<user>\.ollama\models` (~2.5 GB / ~5–6 GB).
- vLLM/Docker route: pulled from Hugging Face into the `hfcache` Docker volume
  (host path: Docker volume; manual runs → `C:\Users\<user>\.cache\huggingface`).

## 3. Code changes (`parasail/`)

| File | Change |
|---|---|
| `src/parasail/assistant.py` | **NEW** — `AssistantService`: grounded summarisation, cited Q&A, image description; backends vllm/ollama/template; guardrails (citation check, class-consistency, refusal, backend transparency); TTL summary cache; concurrency semaphore; `status()` probe |
| `src/parasail/api.py` | New endpoints `POST /assistant/summarize`, `/assistant/ask`, `/assistant/describe-image`, `GET /assistant/status`; dashboard: AI summary block in verdict card + **"Ask ParaSail" chat panel** (bubbles, sources line, animated typing dots); **animations** (fadeUp/popIn/ringPulse/blink/spin keyframes, staggered reveals, hover states, `prefers-reduced-motion` support); **local Leaflet** via `/static` + guarded map init (map failure can never kill species/chat); fixed the `\n` JS bug (see §7) |
| `src/parasail/config.py` | `assistant` config property; `PARASAIL_VLLM_URL` / `PARASAIL_OLLAMA_URL` env overrides |
| `config.yaml` | New `assistant:` section (backend, vllm/ollama endpoints+models, timeouts, concurrency, cache TTL, grounding rules) + commented **RTX 4050 laptop profile**; removed obsolete `models.explanation_llm` |
| `docker-compose.yml` | New `vllm` service (profile `gpu`: Qwen2.5-VL-7B-AWQ, awq, 16k ctx, 32 seqs) and `ollama` service (profile `ollama`); `PARASAIL_VLLM_URL` wired into api; volumes `hfcache`, `ollamadata` |
| `scripts/run_validation.py` | **New T5 test family** (9 checks: backend config, blocked summary keeps verdict+reason, scored summary names class+data age, cache engagement, class-consistency guard, citation grounding, no-context refusal, backend naming, live latency budget) |
| `src/parasail/static/` | **NEW** — `leaflet.js` (147 KB) + `leaflet.css` (15 KB), Leaflet 1.9.4, served locally (no CDN dependency for app functionality; only map tiles need internet) |
| `requirements*.txt` | Unchanged — assistant needs only `httpx` (already present) |

## 4. Documentation (`parasail/docs/` — NEW)

- **`PRODUCTION_HARDWARE.md`** — the required hardware documentation: model
  selection + verified alternatives (Qwen3-VL-8B, InternVL3-8B MIT, MiniCPM-V
  4.5), VRAM budget breakdown table, vLLM/AWQ serving stack, throughput &
  capacity table, **hardware tiers**:
  - **Tier L laptop**: RTX 4050 6 GB → Qwen2.5-VL-3B via Ollama, 6k ctx, 1–2 concurrent
  - **Tier 1 pilot**: 12 GB (RTX 3060/4070) → 7B AWQ, 8k ctx, 8 concurrent
  - **Tier 2 recommended**: 24 GB (RTX 4090 / L4) → 7B AWQ, 16k ctx, 32–64 concurrent
  - **Tier 3 regional**: 2–4× L4/A10G + LB, or A100
  - Cost model: self-hosted ≈ $2k once + ~$315/yr power vs $16k–55k/yr at
    per-token API rates (10k requests/day); ops/runbook, coastal environment notes
- **`AI_ASSISTANT.md`** — assistant architecture, guardrails table, API
  reference with curl examples, backends/config, laptop quickstart, T5 summary
- `README.md` — six-layer architecture, assistant row in model table, P7/T5,
  new repo layout, quickstart with `--profile gpu`, assistant examples,
  ethics section updated (local AI, no data leaves premises)

## 5. Paperwork (`ParaSail_Paper/`)

**Research paper** (`generate_paper.js` → docx → pdf, now 13 pages):
- Abstract & keywords (added vision-language models), §1.2 problem statement,
  **RQ5**, contributions **C7/C8**, objective **RO9**
- §2.4 related work extended (VLMs + vLLM + AWQ)
- Architecture: **five → six layers**; new **§4.7 Grounded AI Assistant Layer**;
  §4.8 deployment + **new Table 8 (hardware tiers)**; SDG table → Table 9
- Table 3 model row: Qwen2.5-VL-7B (AWQ) on vLLM (replaces "optional LLM")
- Table 5 phase **P7**; §5.2 test family **T5**; Table 7 + new **§7.6 results**
- Limitations/future-scope/conclusion/Q3/Q5 updated; refs **[33] Qwen2.5-VL**,
  **[34] PagedAttention (SOSP 2023)**, **[35] AWQ (MLSys 2024)**

**General deck** (`build_deck.js`, 15 → **16 slides**): S8 features mention AI;
**new S11 "Ask it anything — in your own words"** (chat mockup + "free for
everyone, always" + "The AI explains the advice — it never overrules it");
slides renumbered 12–16; `qa_deck.py` anchors updated.

**Technical deck** (`build_deck_technical.js`, 15 → **17 slides**): 4 title
chips; six-layer fig1; model-table row; **new S11 (assistant architecture +
guardrails)**; **new S12 (hardware tiers + $0-per-question economics)**; T1–T5
chips; 5 findings incl. "Assistant guarded"; closing Q&A updated; AR values
refreshed.

**Figures** (both `figures/` and `deck_figures/`): `fig1_architecture.png` now
**six layers** (gold "6 ASSISTANT" column; vLLM in infrastructure bar);
`fig3_phases.png` now **seven phases** with P7 + gate G6. Regenerated; content
bounds verified within canvas (no clipping).

**Root copies refreshed:** `ParaSail_Research_Paper.docx`,
`ParaSail_Presentation.pptx`.

## 6. Verification status

- **Assistant self-tests + T5**: all pass (`python scripts/run_validation.py
  --skip-live`). T1–T3, T5 PASS. **T4 fails only in the dev environment**
  (needs `qdrant_client` + a seeded Qdrant corpus — pre-existing, unrelated).
- **Live server test (port 8000)**: page serves; `/static/leaflet.js|css` 200;
  `/species` returns 12; `/assistant/ask` + `/assistant/summarize` return
  grounded template-mode answers with correct verdicts; `/health` OK.
- **Inline JS**: extracted from the served page and `node --check` — **syntax
  valid** (this is the check that caught the §7 bug; keep using it after any
  UI_PAGE edit).
- **Paper QA** (`qa_paper.py`): CLEAN, 13 pages. **Deck QA** (`qa_deck.py`):
  CLEAN, 16 slides. Two checker bugs were fixed in `qa_paper.py`: (a) "NaN"
  substring check false-positived on "gover**nan**ce"/"domi**nan**t" → now a
  case-sensitive word-boundary regex; (b) block-level overlap check false-
  positived on wrapped table cells / tight reference leading → now line-level
  with a 35%-of-line-height threshold.
- **Full-content acceptance**: anchors verified present in all three PDFs
  (paper, both decks); tables 1–9 sequential; no out-of-bounds text; no
  text-over-figure collisions.
- **Visual review caveat:** pixel-level image review was NOT possible — file
  Reads of PNGs return CDN upload URLs in that session (both for the main
  agent and judge subagents). Geometric + text-extraction QA was the
  substitute. Eyeball the PDFs once when convenient.

## 7. Bug found & fixed during local testing (important lesson)

**Symptom:** map blank, species dropdown stuck on "loading…", chat not
responding — i.e. the whole page script dead.

**Root cause:** in `UI_PAGE` (a **non-raw** Python triple-quoted string), the
JS line `…(cite.length?'\n':'')…` contained the Python escape `\n`, which
Python rendered as a **real line break inside a JS string literal** →
`SyntaxError: Invalid or unexpected token` → the entire `<script>` block
failed to parse → nothing initialised. One bug, all three symptoms.

**Fixes applied:**
1. `'\n'` → `'\\n'` in the Python source (JS now receives the two-character
   escape). When editing `UI_PAGE` in the future: any `\n`, `\t`, `\r` meant
   for JS must be written `\\n`, `\\t`, `\\r`; `\uXXXX` is safe (Python emits
   the literal character, valid in JS).
2. **Hardening:** Leaflet is now served locally from `/static` (no CDN
   dependency for app functionality — only map tiles need internet), and map
   initialisation is wrapped in try/catch with `if(map)`/`if(locM)`/
   `if(spotLayer)` guards throughout, so a map failure shows a friendly
   message while species/chat/advice keep working.
3. Also installed the package properly: `pip install -e .` from `parasail/`
   (the bare `uvicorn parasail.api:app` was failing with ModuleNotFoundError
   before that).

**Port-8000 note during that session:** multiple stale uvicorn instances were
listening (127.0.0.1 + 0.0.0.0 + [::1]); they were killed and one clean
instance started. If the page misbehaves, check
`netstat -ano | grep :8000` for duplicate listeners first.

## 8. How to run (current, verified instructions)

```bash
# 0. one-time setup
cd parasail
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
pip install -e .                                  # makes `parasail` importable

# 1. database + vector store (else every advisory is blocked by the
#    MPA fail-closed guard: "MPA registry unavailable")
docker compose up -d db qdrant

# 2. the API + dashboard
uvicorn parasail.api:app --port 8000
# → open http://127.0.0.1:8000  (map, species, chat all work without any AI
#   model — the assistant answers in deterministic template mode)

# 3. the AI (local, no cloud):
#    laptop (RTX 4050, 6 GB):
ollama pull qwen2.5vl:3b
#      then in config.yaml: assistant.backend: ollama,
#      assistant.ollama.model: qwen2.5vl:3b, max_concurrent_requests: 2
#    production (12 GB+ GPU, NVIDIA container toolkit):
docker compose --profile gpu up -d     # vLLM + Qwen2.5-VL-7B-AWQ on :8001
```

**Known behaviours (by design, not bugs):**
- Without PostGIS running, advisories return `DO NOT FISH` with
  "MPA registry unavailable — request cannot be cleared" (fail-closed
  conservation guard; run `docker compose up -d db` to clear points properly).
- Without a model server, the chat answers in template mode and labels every
  answer "built-in mode" / names its backend — transparency, never silence.
- T4 of the validation suite needs a seeded Qdrant corpus
  (`scripts/seed_regulations.py --corpus data/regulations.jsonl`).

## 9. File map of everything touched this session

```
workspace root
├── PROJECT_CONTEXT.md                  ← this file
├── ParaSail_Research_Paper.docx        ← refreshed (root copy)
├── ParaSail_Presentation.pptx          ← refreshed (root copy)
├── parasail/
│   ├── README.md                       ← six layers, P7, T5, assistant docs
│   ├── config.yaml                     ← assistant: section + laptop profile
│   ├── docker-compose.yml              ← vllm (gpu) + ollama profiles
│   ├── docs/AI_ASSISTANT.md            ← NEW
│   ├── docs/PRODUCTION_HARDWARE.md     ← NEW (tiers, VRAM, costs)
│   ├── docs/AI_SETUP.md                ← NEW (full install guide, all commands)
│   ├── scripts/export_model.py         ← NEW (bundle models for offline use)
│   ├── scripts/run_validation.py       ← T5 family
│   └── src/parasail/
│       ├── assistant.py                ← NEW (the AI layer)
│       ├── api.py                      ← endpoints + chat UI + animations +
│       │                                  local Leaflet + guarded map + \n fix
│       ├── config.py                   ← assistant property + env overrides
│       └── static/leaflet.js|css       ← NEW (local map library)
└── ParaSail_Paper/
    ├── generate_paper.js               ← paper content (13 pages now)
    ├── build_deck.js                   ← general deck (16 slides)
    ├── build_deck_technical.js         ← technical deck (17 slides)
    ├── make_figures.py / make_deck_figures.py ← fig1 six layers, fig3 P7
    ├── qa_paper.py / qa_deck.py        ← QA (paper checker fixed+recalibrated)
    ├── ParaSail_Research_Paper.docx/.pdf
    ├── ParaSail_Presentation.pptx/.pdf
    ├── ParaSail_Presentation_TechnicalBackup.pptx/.pdf
    ├── figures/ , deck_figures/        ← regenerated
    └── render_paper/ , render_deck/ , render_deck_technical/  ← QA renders
```

## 10. Telemetry expansion (session update 2 — from `ocean_telemetry_parameters.csv`)

The owner supplied a CSV defining the required station telemetry parameter set
(`C:\Users\ignun\Downloads\ocean_telemetry_parameters.csv`, 13 parameters in 3
categories). All are now live on the dashboard and in the API:

| CSV category | Parameter | Source / field | Status |
|---|---|---|---|
| Meteorological | Wind Speed & Direction (incl. gusts) | Open-Meteo `wind_speed_10m`, `wind_gusts_10m`, `wind_direction_10m` | live |
| Meteorological | Barometric Pressure | `surface_pressure` (hPa) | live |
| Meteorological | Air Temperature | `temperature_2m` (°C) | live |
| Meteorological | Relative Humidity | `relative_humidity_2m` (%) | live |
| Oceanographic | Sea Surface Temperature | `sea_surface_temperature` (°C) | live |
| Oceanographic | Significant Wave Height | `wave_height` (m) | live |
| Oceanographic | Wave Period & Direction | `wave_period` (s), `wave_direction` (°) | live |
| Oceanographic | Ocean Current Velocity & Direction | `ocean_current_velocity` (km/h), `ocean_current_direction` (°) | live |
| Oceanographic | Salinity | none wired (Open-Meteo has no salinity) | shown as "–" with tooltip; needs Copernicus/ERDDAP source |
| Positional & System Health | GPS Coordinates | picked position (lat, lon) | live |
| Positional & System Health | Battery Voltage & Solar Output | optional `station.status_url` in config.yaml | honest "shore / external power" when not instrumented — never fabricated |
| Positional & System Health | Time Stamp (UTC) | `observed_at` | live |

Implementation notes:
- `ingestion.py`: `OpenMeteoSource` now requests **four independent variable
  groups** (core weather / extended weather / core marine / extended marine)
  so an unsupported variable or endpoint error degrades only that group.
  Variable names + units were verified against the live APIs (marine:
  wave_period s, wave_direction °, ocean_current_velocity **km/h**,
  ocean_current_direction °; weather: wind_direction_10m °, surface_pressure
  hPa, temperature_2m °C, relative_humidity_2m %). The advisory scoring path
  (`fetch_point`) is unchanged — extended variables are telemetry-only.
- `api.py`: `/telemetry` returns the full parameter set + `station` block
  (`name`, `battery_voltage_v`, `solar_output_w`, `power_source`); new module
  helper `_station_status(cfg)` fetches the optional configured node.
- Dashboard: telemetry card is now three labelled groups (**Weather / Sea /
  Station**) with 13 tiles, compass labels (N/NNE/…), animated direction
  arrows (CSS-rotated, smooth transition), sub-lines for gusts/directions,
  staggered pop-in animations extended to 5 tiles per group.
- `config.yaml`: new optional `station:` section (`name`, `status_url`).
- Verified live: `/telemetry` at Kochi returns real values for every wired
  parameter; page contains all tiles; inline JS passes `node --check`.
- **Standing instruction from the owner:** update PROJECT_CONTEXT.md after
  every change session (this section is that update).

## 11. Session update 3 — model registry/switcher, map markers, provenance, newsletter, Lora font, i18n fix

Owner request: export/bundle models with the app; add a model switcher for
scaling by preference; add/remove map markers; show where the data comes from
(station location); a newsletter area in the selected language; fix that
language selection did not translate the important dynamic data; change the
English typeface to **Lora** (Olga Karpushina & Alexei Vanyashi, Cyreal
Fonts, SIL OFL).

### Model registry + switcher + export
- `config.yaml`: `assistant.models` registry (key → backend, model, vram_gb,
  download_gb, description): `qwen2.5vl-3b-laptop` (Ollama, 6 GB),
  `qwen2.5vl-7b-awq` (vLLM, 12 GB, default), `qwen2.5vl-7b-ollama`,
  `qwen2.5vl-72b-awq` (datacenter tier). `active_model` is the default.
- `assistant.py`: `list_models()` / `switch_model(key)` — runtime switching,
  choice persisted in `.cache/assistant_model.json` (config stays pristine);
  per-model backend routing (vLLM vs Ollama endpoints), HTTP client rebuilt
  and summary cache cleared on switch; legacy single-model configs still work.
- API: `GET /assistant/models`, `POST /assistant/model` (404 on unknown key).
  Dashboard chat card has a model dropdown (key · VRAM) — switch any time.
- `scripts/export_model.py` (**NEW**): bundles models with the app — HF
  `snapshot_download` into `models/<key>/` for vLLM (offline `vllm serve
  models/<key>`), or prints/runs the Ollama store copy for Ollama models.
  `--list` shows the registry. Keep `models/` out of git.

### Map markers
- "Add marker" toggle button: in marker mode, map clicks prompt for a name
  and save a persistent marker (teal, `localStorage: parasail_marks`);
  each marker popup offers "use as my location" / "remove"; "Remove all
  markers" clears them. Markers survive reloads.

### Data provenance / station location
- `config.yaml` `station.position` → the station appears on the map (gold
  marker, "data source for this dashboard").
- `/telemetry` now returns `sources`: per-group provider + served field
  counts (Open-Meteo forecast/marine), salinity note, station identity and
  position. Telemetry card has a "Where the data comes from" panel with a
  "show on map" link that pans to the station marker.

### Newsletter (localized by language and area)
- `POST /newsletter/briefing` {language, lat, lon, species, start} → title +
  items: advisory summary (assistant, localized), live conditions headline
  (universal numbers), closure calendar (active vs upcoming, localized
  server-side via the translation service). **Verified in Malayalam.**
- `POST /newsletter/subscribe` {email, language, city} → appends to
  `data/newsletter_subscribers.json` with dedupe + email validation (422).
  Mount a volume on `/app/data` in Docker for persistence.
- Dashboard: "Today's briefing" card below the chat; auto-refreshes on load,
  language change and city change; email subscribe row.

### i18n fix (important data now follows the language)
Root cause of the English-in-Malayalam-UI screenshot: the AI/plain-language
summary was set via `textContent` and never entered the translation flow.
Fixes: `/assistant/summarize` accepts `language` (template path localizes
server-side; LLM path instructs the language); new client `localize()`
helper translates any dynamically-set string through `/translate`; the
summary source line is localized; `applyLanguage` now also reloads the
server-localized briefing after a language change.

### Lora typeface
- Downloaded Lora variable woff2 (latin + latin-ext, normal + italic,
  ~116 KB) into `src/parasail/static/fonts/` — served locally, no font CDN.
  All English text (body, headings, verdict, telemetry values) now renders
  in Lora; Indic scripts fall back to the system font (Lora is Latin-only).
  Footer carries the attribution (Cyreal Fonts, SIL OFL).

### Verification (all passed)
- `node --check` on the served inline JS — **caught a second raw-`\n`-in-JS-
  string bug in the new newsletter code (same class as §7); fixed to `\\n`
  and re-scanned the whole template for control-char escapes (none left).**
- Cross-checks: every `getElementById` target exists in the HTML; every
  onclick/onchange handler is defined; all four font files 200; page contains
  all new components.
- Live tests: model registry lists 4 models; switch → laptop tier and back
  (persisted to `.cache/assistant_model.json`; unknown key → 404);
  Malayalam briefing fully localized; subscribe + dedupe + 422 on bad email;
  telemetry sources (6 weather + 6 sea fields) + station position served.

## 12. Session update 4 — AI installation guide

Owner asked for a markdown file with every command/step to install all the
AI pieces. Environment probed on this machine: Windows 11, Python 3.11.9,
pip 26.2.1, Docker 29.7.2 (WSL2 docker-desktop), NVIDIA RTX 4050 Laptop
6141 MiB (driver working), HF CLI 1.26 installed, **Ollama NOT installed**.

**NEW FILE: `parasail/docs/AI_SETUP.md`** — the complete, machine-tailored
installation guide: app setup, Path A (Ollama — recommended for the 6 GB
4050: install from ollama.com, `ollama pull qwen2.5vl:3b`, select
`qwen2.5vl-3b-laptop` in the dashboard dropdown or via
`POST /assistant/model`), Path B (HF CLI `hf download
Qwen/Qwen2.5-VL-7B-Instruct-AWQ` + vLLM via Docker `--profile gpu` or WSL2
— needs 12 GB+ VRAM), model management (registry/switch/bundle/import),
full-stack compose, verification checklist (`/assistant/status`,
`/assistant/ask`, `run_validation.py`), troubleshooting table (template
mode, port conflicts, MPA fail-closed, vLLM OOM), and a ports/processes
reference. Repo layout in §9 now includes `docs/AI_SETUP.md`.

## 13. Session update 5 — production security layer (rate limiting, RBAC, hardening)

Owner request: rate limiting, other necessary security features, and
role-based access for developing ParaSail into a professional website.

**NEW `src/parasail/security.py`** (no external dependencies):
- **Rate limiting** — thread-safe sliding-window per client (first
  X-Forwarded-For hop behind a proxy) and per bucket; `X-RateLimit-*`
  headers, `Retry-After` on 429. Buckets: default 120/min, advisory 30/min,
  assistant 20/min, image 10/min, translate 60/min, subscribe 5/5min,
  admin 10/min — all data in `config.yaml` → `security.rate_limits`.
- **Security headers** on every response: CSP tuned to the local-asset
  dashboard (self + OSM tiles only), `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy.
- **Body-size cap** (10 MB, 413) via Content-Length check.
- **RBAC** — `X-API-Key` credential, roles public < officer < admin; keys
  in `security.api_keys` as SHA-256 hashes (plaintext `key` accepted for
  dev). 401 missing/invalid, 403 insufficient role; with no keys configured
  privileged endpoints stay locked with a pointer to docs/SECURITY.md
  (secure by default).
- **CORS** locked to `security.cors_origins` (no wildcards); `/docs`
  hideable via `security.public_docs`.
- **Audit log** (`parasail.audit` logger): model_switch,
  newsletter_subscribe, newsletter_subscribers_read, rate_limit_exceeded.

**api.py:** `create_app(cfg=None)` now accepts an injected config (enables
isolated test apps); SecurityMiddleware + CORS wired; `POST /assistant/model`
requires admin; **NEW `GET /newsletter/subscribers`** (admin-only, audited);
dashboard model-switcher prompts for the admin key once on 401/403 and
remembers it in localStorage.

**Also:** `scripts/generate_api_key.py` (key + sha256 for config),
`docs/SECURITY.md` (roles table, limits table, hardening checklist, and an
explicit "not done here" list: TLS/reverse proxy, end-user accounts via
IdP, distributed limiting, secret stores). **T6 security family** added to
`run_validation.py` (9 checks: limiter unit behaviour, bucket mapping,
401/401/403/200 RBAC matrix, officer blocked from model switch, headers,
rate headers, 413, public endpoints unaffected, no-keys-locked).

**Local admin key generated and registered** (plaintext dev entry
`local-admin` in config.yaml; the key is in the owner's chat log —
`<rotated-out-key-1>`).

**Environment change during this session:** the owner installed Ollama
0.34.0, pulled `qwen2.5vl:3b` (3.2 GB), and switched the active model via
the dashboard (persisted pref: `qwen2.5vl-3b-laptop`). **The live AI now
answers in ~1 s.** T5 was adjusted: deterministic checks run against an
isolated template-mode config; the live-latency check uses the real service.

**Verification (all live):** T5 9/9 + T6 9/9 pass (31/35 total; only
pre-existing T4 fails — needs seeded Qdrant); security headers + rate
headers on `/`; model switch 401 without key, 200 with admin key; subscribe
bucket 200×5 then 429; real AI answer via Ollama coherent and backend-named;
test subscribers cleaned from the list. The running server includes all of
this (restarted by the agent; restart your own terminal instance to take
ownership).

## 14. Session update 6 — Tailscale hosting + installable mobile web app (PWA)

Owner request: test the app via Tailscale on mobile/other devices; add a
web-based mobile app.

**PWA layer (all served locally, no CDN):**
- `scripts/make_icons.py` (**NEW**) — draws the brand mark (coral sail +
  teal waves on deep-ocean) with Pillow → `static/icons/`: icon-192/512,
  maskable-512 (safe-zone padded), apple-touch-icon (180), favicon-32.
- `static/manifest.webmanifest` (**NEW**) — standalone display, theme
  colour #0A2E3C, maskable icon; `static/sw.js` (**NEW**) — service worker:
  cache-first app shell (page, Leaflet, Lora fonts, icons), data APIs never
  cached (advisories stay fresh); served via **`GET /sw.js`** route (root
  path so SW scope covers `/`; a /static path would scope wrongly).
- Dashboard: manifest + theme-color + apple metas + icons in `<head>`;
  green **"Install app"** button (appears on `beforeinstallprompt`,
  Android); SW registration guarded to secure contexts (https/localhost —
  plain http://100.x tailscale IP browses fine but cannot install; use
  `tailscale serve` for HTTPS); mobile CSS (@media ≤600px: full-width
  fields/buttons, 300px map, wrapped chat row, 94% bubbles, 88px telemetry
  tiles, iOS safe-area padding); `viewport-fit=cover`.

**Tailscale:** server restarted bound to **0.0.0.0:8000** (tailnet
reachable). Tailscale v1.102.3 installed on this machine (agent shell
cannot read the IP; `tailscale ip -4` in the owner's terminal works).
**`docs/REMOTE_ACCESS.md` (NEW)**: tailnet hosting steps + Windows firewall
rule, PWA install on Android/iOS, the HTTPS caveat, `tailscale serve --bg
8000` (recommended — HTTPS + installable), `tailscale funnel` warning with
SECURITY.md checklist, remote-use notes (same-origin dashboard → CORS/CSP
unchanged). README gained a "Mobile / remote testing" section.

**Verified live:** manifest 200 (`application/manifest+json`), sw.js 200
(`application/javascript`), icons 200, page contains all PWA links;
`node --check` passes for both the inline page script and sw.js; manifest
JSON valid; server listening on 0.0.0.0:8000.

**Tailscale (live):** server bound to **0.0.0.0:8000**; `tailscale serve
--bg 8000` active → the tailnet HTTPS URL (URL, tailnet IP and machine
name are recorded in the gitignored `LOCAL_SECRETS.md`, never in the
public repo; Tailscale v1.102.3). Verified over HTTPS: dashboard 200,
health OK, sw.js 200 (PWA install works on this origin). **Note:** the
root serve replaced the owner's previous root mount for their other local
AI platform — documented the multi-app pattern (one `serve --bg <port>` per
project = one HTTPS link per port; `--set-path /x <port>` alternative;
`serve status` / `reset`) in docs/REMOTE_ACCESS.md §4 at the owner's
request.

**Species names in the local language (owner request):** new
`local_names` map per species in `config.yaml` — **curated vernacular
names, never machine-translated** (MT would transliterate: "ഇന്ത്യൻ ഓയിൽ
സാർഡൈൻ" instead of the real "ചാള"). Kerala-first curation: ചാള (oil
sardine), അയൽ (mackerel), നെയ്മീൻ (seer), നെത്തോലി (anchovy), വാൽ
(ribbonfish), ചെമ്പല്ലി (snapper), കടുവ ചെമ്മീൻ / വെള്ള ചെമ്മീൻ (prawns),
ചൂർ (tunas) + selected Tamil/Hindi; `Thunnus tonggol` and `Decapterus
russelli` intentionally empty (no confident vernacular) → English fallback.
`/species` exposes `local_names`; the dashboard rebuilds the species
dropdown ("ചാള · Sardinella longiceps") and the "Likely spots" title on
language switch (`buildSpeciesSelect`/`localNameFor`; no markTr on these
options so MT cannot touch them). Ops note: a stale uvicorn on port 8000
served old code — kill ALL listeners (`for PID in $(netstat -ano | grep
:8000 …)`) before restarting; verified live: /species carries local_names,
dashboard + tailnet HTTPS 200.

**Session update 7 (Problem/Answer + regional ocean news, newsletter
removed):**
- **Problem/Answer blocks**: `PROBLEM_ANSWERS` mapping in api.py — known
  block reasons (MPA registry unavailable/unreachable, seasonal closure,
  inside MPA, species not in registry) get a plain-language
  {"problem","answer"} localized into the request language, attached to
  `/advisory` and `/assistant/summarize` responses as `problem_answer`;
  the verdict card renders a coral "Problem: … / Answer: …" box (labels
  data-tr; content server-localized). Answers the owner's question about
  the "MPA registry unavailable" STOP: it is the fail-closed guard, now
  explained in-language.
- **Newsletter REMOVED** (endpoints, subscribe UI, subscribers file,
  SECURITY.md/T6 references) per owner request; T6 RBAC now tests
  `/assistant/model` (with a pref-file snapshot/restore so tests don't
  clobber the operator's model choice).
- **Regional ocean news** (NEW): `POST /news {language}` serves 8 seeded
  items from `src/parasail/data/ocean_news.json` (Kerala/ml,
  Tamil Nadu/ta, West Bengal/hi, India/Indian Ocean/Global/en; sources
  CMFRI, Gulf of Mannar BR, mangrove initiative, INCOIS, IOTC, NOAA/WMO,
  UNEP, FAO — thematic, no fabricated specifics; operators replace with
  live feeds per deployment). **Translation pivots through English**
  (`title_en`/`summary_en` reference editions ship with the corpus):
  direct Indic→Indic MT garbled; en→target is reliable. origin==target →
  original; target==en → reference edition; else en→target via
  translate_batch. Items flagged `translated` + `origin_language`.
  Dashboard: "Regional ocean news" card (region chip, title, summary,
  "translated from X · source"), reloads on language change; `/news` sits
  in the `translate` rate bucket.
- Verified live: advisory problem_answer (EN + ML), news in ML (all 8,
  cross-language items correct via pivot), news in TA (Malayalam-origin
  item correct), full validation suite 31/35 (only pre-existing T4).

**Session update 8 (paperwork rewrite):** paper + both decks regenerated to
cover everything from sessions 4-7 (telemetry expansion, model
registry/switcher, security/RBAC, PWA/mobile, vernacular species names,
Problem/Answer, ocean news, Lora, Tailscale). Paper (now **15 pages**):
abstract extended; C7/C8 broadened; §4.7 gains a second paragraph (registry,
vernacular names, Problem/Answer, news with English pivot, full telemetry
set + provenance); §4.8 gains a hardening paragraph (rate limits, RBAC
roles, headers, audit, PWA/offline shell, Lora, tailnet, registry↔Table 8
tiers mapping); §5.2 + Table 5 gate + Table 7 row + §7.6 second paragraph
add **T6 security behaviour**; §8/§10 (mobile PWA delivered, voice remains
future)/RO7/Q3/Q4/Q5 updated. General deck: S12 gains "Now a phone app"
bullet (+ model-switching phrasing on the ordinary-computers bullet); S16
closing updated (PWA today, voice next) keeping the "works offline" QA
anchor. Technical deck: S11 multilingual→"Multilingual and scalable" +
registry + T5/T6 assert line; S12 srcLine → hardening/PWA/tailnet; S15
chips now **T1-T6**; S16 six findings (+ "Service hardened"); S17 Q3
extended. **Preserved untouched** (owner's "do not edit this part"
precaution — additive-only edits elsewhere): title block, equations,
scoring/thresholds, all existing table rows, case study, references,
summit-question structure, general deck slides 1-11/13-15, technical deck
slides 1-10/13-14. Verified: qa_paper CLEAN (15pp), qa_deck CLEAN (16s),
all new-content anchors present in all three PDFs, root copies synced.

**Ops fix (post-rewrite):** "news is not showing up" root-caused to two
issues: (a) the background uvicorn had died (no listener on 8000) and
(b) the v1 service worker served the app shell CACHE-FIRST, so the
browser kept showing the pre-news page and its removed
`/newsletter/briefing` calls 404'd. Fix: sw.js rewritten - **network-first
for `/`** (cache only as offline fallback), cache-first only for
`/static/*`, CACHE bumped to `parasail-shell-v2` (activates by deleting
all older caches). Lesson: after any dashboard change, the SW version must
bump OR rely on the new network-first policy; after THIS fix users need
one or two refreshes for v2 to take control. Server restarted; /news (8
items) and tailnet HTTPS verified live.

**MPA registry data (owner question):** the Dataful dataset 1342 (MoEFCC/
ENVIS inventory, 132 rows: names/types/areas/years, NO geometry, no stated
license) is the attribute half of the registry, not the registry - the
fail-closed guard needs polygons (ST_Contains). Recipe: WDPA/Protected
Planet India subset (geometry, clear terms) cross-validated against the
Dataful inventory -> `scripts/load_mpas.py --geojson <file>` (**NEW**;
upserts into mpa_polygons by name, --truncate to replace, skips
non-polygon features) -> `docker compose up -d db` -> advisories clear
points against real boundaries.

**MPA registry LIVE (session update 9):** 16 real Indian MPA boundary
polygons fetched from OpenStreetMap via Nominatim polygon lookup
(`data/mpas_india_osm.geojson`, (c) OSM contributors, ODbL; Overpass was
504ing) - Gulf of Mannar MNP, Marine (Gulf of Kachchh) NP, Mahatma Gandhi
MNP, Rani Jhansi MNP, Gahirmatha (Marine) WLS, Malvan Marine Sanctuary,
Point Calimere WLS, Bhitarkanika NP, Galathea, Campbell Bay, N/S/Middle
Button, Saddle Peak, Pirotan, Pitti Island. Loaded with
`python scripts/load_mpas.py --geojson data/mpas_india_osm.geojson
--truncate` (Docker Desktop must be running; container `parasail-db-1`,
psycopg installed in the system python, API restarted so the engine
rebuilds its DB factory). **Verified live:** Kochi advisory now SCORES
(DELAY OR RELOCATE 0.4811 from real weather) instead of failing closed;
point inside Gulf of Mannar MNP (9.1703, 78.8283) blocks with the park
name + Problem/Answer. Test gotcha: for multi-island MPAs the CENTROID
falls in open sea - use ST_PointOnSurface for inside-tests. Known gaps:
Sundarbans NP + a few small reserves have no standalone OSM polygon -
fill from WDPA later (cross-check vs Dataful 1342 inventory). Known issue
noted for T4 seeding: newer qdrant-client renamed `.search` -> rag.py
needs a compat shim when Qdrant is actually running (degrades gracefully
today).

**Admin key rotated (session update 10):** key rotated and hash pasted into config.yaml by the agent; old key verified rejected (401), new key verified working (200). The current key value lives only in the owner's chat log - never in files.

**Admin key activated + hardened:** the local-admin API key (value in the
owner's chat log; the key prefix is recorded in the gitignored
`LOCAL_SECRETS.md`) verified live (401 no/bad key, 200 with key on
`POST /assistant/model`), then converted from the plaintext
dev entry to a **SHA-256 `key_hash`** in config.yaml (same key value keeps
working; `scripts/generate_api_key.py` for new ones). Verified again after
restart. Also: three stale uvicorn listeners had accumulated on :8000 -
killed all before the clean restart (repeat the kill-all loop if the port
acts up).

**Session update 11 (public GitHub repo + local-only secrets):** the whole
project is now published at `github.com/unrealone1-sys/Parasail` (155
tracked files; model weights, .venv, caches and node_modules are
gitignored; MIT LICENSE preserved from repo creation; a root README was
added). Internal identifiers — the tailnet URL/IP/machine name and the
admin-key prefix — were redacted from all public files AND from the git
history (commit amended + force-pushed). They live in `LOCAL_SECRETS.md`
at the workspace root, which is **gitignored and must never be committed
or published**. `docs/REMOTE_ACCESS.md` examples now use a placeholder
tailnet URL. The local repo's `origin` points at the GitHub repo — normal
`git push` from here on. Future sessions: keep new secrets/identifiers in
LOCAL_SECRETS.md, not in this file.

## 15. Suggested next steps (not yet done)

- Seed the Qdrant corpus so T4 passes and chat answers carry real citations.
- Load-test `POST /assistant/ask` (k6/locust) at 2× expected peak before any
  public pilot; confirm the summary-cache hit rate and rate-limit behaviour
  under load.
- Before public launch: replace the plaintext dev admin key with a
  `key_hash` from `scripts/generate_api_key.py`, set `public_docs: false`,
  add the real origin to `cors_origins`, terminate TLS at a reverse proxy,
  and route the `parasail.audit` logger to persistent storage
  (docs/SECURITY.md §7 checklist).
- Eyeball the three PDFs once (visual channel was unavailable to the agent).
- Optional: wire a salinity source (Copernicus Marine `global-reanalysis-phy`
  or an ERDDAP salinity dataset) into `environmental_fields` and populate
  `salinity_psu`; wire a real buoy/shore-node `station.status_url`.
- Optional: run `scripts/export_model.py --run` to bundle the laptop model
  into `models/` for fully offline deployments (keep out of git).
- Optional: dialogue-style fine-tuning data collection from consented fisher
  conversations (paper §10 future scope).

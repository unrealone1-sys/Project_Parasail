# ParaSail AI Assistant — Production Hardware & Deployment Guide

This document specifies the hardware required to run the ParaSail AI
assistant **in production, fully self-hosted**, within the project's
design budget of **8–12 GB of GPU VRAM**, and explains how the serving
stack sustains high traffic (thousands of requests per day) on that
budget.

The defining constraint is economic: the assistant must run on hardware
you own or rent at a fixed price, with **zero per-request AI API costs**.
Every component below is open-source (Apache-2.0 licensed models, open
serving stack) and runs locally.

---

## 1. Selected model

| Property | Value |
|---|---|
| Model | **Qwen2.5-VL-7B-Instruct-AWQ** (Alibaba Qwen, Apache 2.0) |
| Size | 8.29 B parameters, 4-bit AWQ quantised ≈ **6.9 GB** weights |
| Modality | Vision + language (images/video + text in, text out) |
| Context | 32,768 tokens (limited to 8–16 k in production configs) |
| Strengths | Document/chart understanding (DocVQA 95.7, ChartQA 87.3), OCR, object localisation — directly relevant to reading catch photos, satellite tiles and scanned regulations |
| License | Apache 2.0 — commercial use, modification and redistribution permitted |
| Small sibling | **Qwen2.5-VL-3B** (~3.75 B, same Apache 2.0 family) for 6 GB laptop GPUs — see Tier L below |

Why this model:

1. **It fits the budget.** At 4-bit AWQ the weights are ~6.9 GB; the full
   serving footprint (weights + vision encoder + KV cache + activations)
   fits comfortably inside a 12 GB GPU, and inside 10 GB with a reduced
   context window.
2. **It is vision-capable.** One model serves all three assistant jobs —
   plain-language advisory summaries, grounded Q&A, and image
   understanding (catch photos, satellite tiles, charts). No separate
   OCR or captioning model is needed.
3. **It is served efficiently.** An official AWQ build exists and is a
   first-class citizen in vLLM, the serving stack used in production.
4. **It is genuinely open.** Apache 2.0 with official weights on Hugging
   Face — no usage restrictions, no phone-home, no per-token billing.

**Verified alternatives** (drop-in swaps via `config.yaml`, same VRAM
class):

| Model | Params | License | Notes |
|---|---|---|---|
| Qwen3-VL-8B-Instruct | 8.8 B | Apache 2.0 | Newer generation; 256 k context; 32-language OCR (incl. Hindi) |
| InternVL3-8B | 8 B | MIT | Strong general VLM baseline |
| MiniCPM-V 4.5 | 8 B | Apache 2.0 | Optimised for edge/low-power GPUs |
| Llama 3.2 Vision 11B | 11 B | *Llama Community License* | Capable, but licence is not OSI-approved open source |

---

## 2. VRAM budget (8–12 GB profile)

Breakdown for `Qwen/Qwen2.5-VL-7B-Instruct-AWQ` served by vLLM:

| Component | VRAM (approx.) | Notes |
|---|---|---|
| LLM weights (4-bit AWQ) | 6.9 GB | Fixed |
| Vision encoder (ViT, fp16) | 1.2–1.5 GB | Activated per image request |
| KV cache | 0.4–1.5 GB | GQA (4 KV heads) ≈ 56 KB/token; PagedAttention allocates on demand |
| Activations / CUDA graphs | 0.8–1.2 GB | |
| **Total (8 k context, 8 seqs)** | **≈ 9–10 GB** | Fits a 12 GB card |
| **Total (16 k context, 32 seqs)** | **≈ 12 GB+** | Needs headroom — see tiers below |

Practical vLLM flags for the 12 GB profile:

```bash
vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 8192 \
  --max-num-seqs 8 \
  --gpu-memory-utilization 0.92 \
  --port 8001
```

---

## 3. Serving stack for high traffic

| Layer | Component | Role |
|---|---|---|
| Inference server | **vLLM** (PagedAttention, continuous batching) | Batches concurrent requests into one GPU pass; the reason a single 24 GB GPU serves a whole community |
| Quantisation | **AWQ 4-bit** | Halves-plus memory vs fp16 with <1 pt benchmark regression |
| Application cache | Assistant summary cache (TTL 15 min, config `summary_cache_ttl_s`) | Near-identical advisories (same class/drivers/day/language) share one generation |
| Concurrency control | Semaphore, config `max_concurrent_requests` | Protects small GPUs; excess requests queue instead of failing |
| Degradation | Deterministic template path | Website stays fully functional with no GPU at all |

Capacity planning (engineering estimates for ~300-token answers +
~800-token prompts, AWQ, batched; validate on your own hardware):

| GPU | Concurrent streams | Aggregate throughput | Capacity @ 10 k req/day |
|---|---|---|---|
| 12 GB consumer (RTX 3060/4070) | 8 | ~150–400 tok/s out | Fine for pilots (≈3–4 k peak-hours requests) |
| 24 GB (RTX 4090 / L4 / A10G) | 32–64 | ~600–1,500 tok/s out | Comfortable headroom |
| 2× 24 GB behind LB | 64–128 | ~1,200–3,000 tok/s out | Regional deployment |

With the summary cache absorbing 30–60 % of repeat traffic in practice, a
single 24 GB GPU sustains tens of thousands of assistant interactions per
day — far beyond the pilot's requirement.

---

## 4. Recommended production hardware

### Tier 0 — CPU-only / degraded (always available)
Any 4-core, 8 GB RAM machine. The assistant runs in **template mode**
(deterministic summaries + verbatim retrieved passages, no generation).
No GPU, no model download, zero cost. The website never goes dark.

### Tier L — Laptop / personal AI, 6 GB VRAM (e.g. RTX 4050 Laptop)
For running one instance locally on a gaming laptop. The 7B AWQ model
(~6.9 GB weights) does **not** fit a 6 GB card; swap to the 3B variant of
the same family — a configuration change, no code:

| Property | Value |
|---|---|
| GPU | **NVIDIA RTX 4050 Laptop (6 GB)** — also RTX 3050 6 GB / 2060 6 GB |
| Model | **Qwen2.5-VL-3B** (~3.75 B params, Apache 2.0), Ollama Q4 ≈ **2.5 GB** weights |
| Serving | Ollama (native on Windows; vLLM also works under WSL2) |
| Profile | `num_ctx 6144`, 1–2 concurrent requests |
| VRAM breakdown | 2.5 GB weights + ~0.7 GB vision encoder + ~1 GB KV/activations ≈ **4.5–5.5 GB total** |
| Capacity | Personal use / demos / development (a few requests per minute) |
| Trade-off | The 3B trails the 7B slightly on fine-grained vision tasks (e.g. TextVQA 79.3 vs 84.3) but matches the previous-generation 7B overall; guardrails, grounding and the template fallback are identical |

```bash
# on the laptop (Windows or Linux):
ollama pull qwen2.5vl:3b
ollama serve                       # if not already running
```

```yaml
# config.yaml — laptop profile (the only change needed):
assistant:
  backend: ollama
  ollama:
    base_url: http://localhost:11434
    model: qwen2.5vl:3b
  max_concurrent_requests: 2
```

Quality note: summaries and Q&A remain grounded and cited exactly as with
the 7B — the smaller model affects fluency and fine image detail, never
the guardrails (those are enforced in code, not by the model).

### Tier 1 — Minimum AI, 8–12 GB VRAM (single site / pilot)
| Part | Recommendation |
|---|---|
| GPU | **NVIDIA RTX 3060 12 GB / RTX 4070 12 GB / RTX 4060 Ti 16 GB** (any 12 GB+ card) |
| Serving profile | `--max-model-len 8192 --max-num-seqs 8` |
| CPU | 6+ cores (x86-64) |
| RAM | 32 GB |
| Storage | 100 GB NVMe (OS + Docker + ~7 GB model + PostGIS + Qdrant + HF cache) |
| Network | 50 Mbps symmetric |
| Indicative cost | $300–450 (GPU) / $800–1,200 (whole node) |

Suits: a single cooperative or harbour office serving hundreds of users.

### Tier 2 — Recommended production, 24 GB VRAM (district / state deployment)
| Part | Recommendation |
|---|---|
| GPU | **NVIDIA L4 24 GB** (cloud) or **RTX 4090 24 GB** (on-prem); A10G equivalent |
| Serving profile | `--max-model-len 16384 --max-num-seqs 32` |
| CPU | 16 cores |
| RAM | 64 GB ECC |
| Storage | 500 GB NVMe |
| Network | 200+ Mbps, public TLS endpoint |
| Indicative cost | L4 cloud ≈ $0.80–1.20/hr (≈ $700–1,050/yr at 8 h/day); RTX 4090 on-prem ≈ $2,000 capex + ~$315/yr electricity at 300 W |
| PSU / power (on-prem) | 850 W 80+ Gold; ~350–450 W wall under load |

Suits: the reference production profile for the case-study region.

### Tier 3 — High traffic / regional (millions of requests per year)
| Part | Recommendation |
|---|---|
| GPUs | **2–4× L4 / A10G** behind a round-robin or least-connections load balancer (vLLM replicas are stateless); or 1× A100 40 GB / H100 with large batches |
| Extras | Optional semantic cache (embedding similarity over past Q&A stored in Qdrant) to absorb repeated questions |
| Orchestration | Docker Compose today; Kubernetes + HPA on GPU metrics for multi-node |
| Indicative cost | $1.60–4.80/hr cloud, or 2–4 on-prem nodes |

### Environment notes for coastal deployments
- **Humidity/salt air**: on-prem nodes should sit in a ventilated, filtered
  cabinet; consumer GPUs tolerate it poorly without airflow management.
- **Power quality**: a modest UPS (1 kVA) covers grid dips; the assistant
  degrades to template mode on GPU loss, and the advisory stack itself is
  unaffected.
- **Connectivity**: after first boot everything runs locally; only the open
  environmental APIs (Open-Meteo etc.) need the internet, and those already
  degrade to cache offline.

---

## 5. Cost model: self-hosted vs per-token cloud APIs

Assume 10,000 assistant interactions/day × ~1,500 tokens each
(prompt + completion) ≈ **5.5 B tokens/year**:

| Option | Cost | Notes |
|---|---|---|
| Commercial VLM API, ~$3 / 1M tokens blended | ≈ **$16,400 / year** | Recurring, usage-priced, data leaves the premises |
| Commercial VLM API, ~$10 / 1M tokens | ≈ **$54,700 / year** | Frontier-class models |
| **Self-hosted RTX 4090 (Tier 2)** | **≈ $2,000 once + ~$315/yr power** | Break-even in ~3–6 weeks; marginal cost per request ≈ electricity |
| **Self-hosted cloud L4, 8 h/day** | ≈ $700–1,050 / year | No capex; scale to zero outside advisory hours |
| Template mode | $0 | Always-on fallback |

At ParaSail's traffic profile the self-hosted design pays for itself within
the first months and caps worst-case cost at a known fixed number — which
is the whole point of the 8–12 GB budget.

---

## 6. Operations

```bash
# Full stack with the local AI (needs NVIDIA container toolkit):
docker compose --profile gpu up -d

# API only (template assistant, CPU):
docker compose up -d api db qdrant

# Lighter local model via Ollama instead of vLLM:
docker compose --profile ollama up -d
docker compose exec ollama ollama pull qwen2.5vl:7b
```

Health and monitoring:

- `GET /assistant/status` — backend name, model, availability probe.
- Every assistant response carries `backend` and `model` fields, so logs
  show exactly what produced each answer (T5 asserts this).
- Watch vLLM metrics (`/metrics`, Prometheus format) for queue depth and
  token throughput; scale by adding replicas when p95 latency drifts.

Capacity checklist before go-live:

1. Run `python scripts/run_validation.py` — all T5 gates must pass.
2. Load-test with realistic Q&A (`k6` or `locust` against
   `POST /assistant/ask`) at 2× expected peak.
3. Confirm the summary cache hit rate on the dashboard telemetry.
4. Verify template-mode failover by stopping the vLLM container mid-test —
   the website must keep answering.

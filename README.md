# ParaSail

A self-hosted advisory system for small-scale fishers on the Indian coast.
ParaSail fuses live weather and ocean conditions, Marine Protected Area (MPA)
boundaries, species ecology and community knowledge into a transparent
advisory — PROCEED / CAUTION / DELAY OR RELOCATE / DO NOT FISH — and explains
it in plain language, in the fisher's own language, using a locally hosted
open-source vision-language model. No cloud AI, no per-question costs.

## Repository layout

| Path | Contents |
|---|---|
| [`parasail/`](parasail/) | The application: FastAPI dashboard + advisory API, grounded AI assistant, deployment configs, docs |
| [`ParaSail_Paper/`](ParaSail_Paper/) | Research paper and both presentation decks — sources, figures, QA scripts and renders |
| [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) | Development log and session handoff |

## Start here

- Application guide — [`parasail/README.md`](parasail/README.md)
- Full AI installation guide — [`parasail/docs/AI_SETUP.md`](parasail/docs/AI_SETUP.md)
- Production hardware tiers & self-hosting economics — [`parasail/docs/PRODUCTION_HARDWARE.md`](parasail/docs/PRODUCTION_HARDWARE.md)
- Security model (rate limits, RBAC, hardening) — [`parasail/docs/SECURITY.md`](parasail/docs/SECURITY.md)
- Research paper (PDF) — [`ParaSail_Paper/ParaSail_Research_Paper.pdf`](ParaSail_Paper/ParaSail_Research_Paper.pdf)

## Quick start

```bash
cd parasail
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt && pip install -e .
docker compose up -d db qdrant
uvicorn parasail.api:app --port 8000             # open http://127.0.0.1:8000
```

The dashboard, advisory API and chat work without any AI model installed
(the assistant answers in deterministic template mode and says which backend
it used). To run the real AI locally, follow
[`parasail/docs/AI_SETUP.md`](parasail/docs/AI_SETUP.md).

## License

MIT — see [LICENSE](LICENSE). MPA boundary data in `parasail/data/` is
derived from OpenStreetMap (© OpenStreetMap contributors, ODbL) and the
WDPA; attribution for each file is noted in `PROJECT_CONTEXT.md`.

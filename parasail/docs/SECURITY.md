# ParaSail Security

Production security for a public-facing deployment: what is implemented,
how to configure it, and what belongs to the surrounding infrastructure.
Implementation: `src/parasail/security.py` (no external dependencies).
Validated by test family **T6** (`python scripts/run_validation.py`).

## 1. Roles and access control (RBAC)

Credential: the `X-API-Key` header. Keys live in `config.yaml` →
`security.api_keys` as `{name, key_hash, role}` entries (SHA-256 hashes; a
plaintext `key` field is accepted **for local development only**).

| Role | Level | Can do |
|---|---|---|
| public | 0 | everything the dashboard needs: advisory, telemetry, chat, news, translations |
| officer | 1 | privileged reads (monitoring data) |
| admin | 2 | officer + switch the AI model (`POST /assistant/model`) |

Behaviour: **401** missing/invalid key, **403** valid key with insufficient
role, **403 with a hint** when no keys are configured at all (privileged
endpoints stay locked — secure by default).

Create a key:
```bash
python scripts/generate_api_key.py --name ops --role admin
# paste the printed key_hash into config.yaml, then:
curl -H "X-API-Key: <the key>" -X POST http://127.0.0.1:8000/assistant/model \n  -H "Content-Type: application/json" -d '{"model":"qwen2.5vl-7b-awq"}'
```
The dashboard's model switcher prompts for the admin key once and remembers
it in `localStorage`.

## 2. Rate limiting

Sliding window, per client (first `X-Forwarded-For` hop behind a proxy, else
socket peer), per endpoint class. Responses carry `X-RateLimit-Limit`,
`X-RateLimit-Remaining` and, on the 429, `Retry-After`.

| Bucket | Endpoints | Default limit |
|---|---|---|
| default | pages, reads (`/health`, `/species`, `/telemetry`, …) | 120/min |
| advisory | `/advisory`, `/fish-suggestions` | 30/min |
| assistant | `POST /assistant/*` (AI generation) | 20/min |
| image | `/assistant/describe-image` | 10/min |
| translate | `/translate` | 60/min |
| admin | privileged endpoints | 10/min |

All values are data in `config.yaml` → `security.rate_limits`. Exceeding a
limit returns `429 {"detail": "too many requests - please slow down"}` and
is written to the audit log.

## 3. Transport and browser security

- **Content-Security-Policy** tuned to the app: assets are same-origin
  (`/static`), map tiles from OpenStreetMap only, `frame-ancestors 'none'`.
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`.
- **CORS** restricted to `security.cors_origins` (no wildcards); methods
  GET/POST; headers `Content-Type`, `X-API-Key`.
- **Request body cap** (`security.max_body_bytes`, default 10 MB; images
  are additionally capped at 6 MB by the application) → `413`.
- **API docs** (`/docs`) can be disabled for production:
  `security.public_docs: false`.

## 4. Input validation and privacy

- Every endpoint validates through Pydantic models: coordinate bounds,
  enum patterns (languages, image kinds), string length caps (questions
  ≤600 chars, emails ≤120, API keys ≤80).
- No user accounts, no passwords, no tracking; the service stores no
  personal data.
- The assistant's grounding guardrails (citations must resolve; verdict
  authority; refusal over invention) are enforced in code — see
  `docs/AI_ASSISTANT.md`.

## 5. Audit log

Privileged and security-relevant events are emitted on the
`parasail.audit` logger as JSON: `model_switch`, `rate_limit_exceeded`. Route this logger to
a file or SIEM in production, e.g.:

```yaml
# uvicorn logging config or your process manager
loggers:
  parasail.audit:
    handlers: [audit_file]
    level: INFO
```

## 6. What this layer deliberately does NOT do

Professional deployments add these around the app, not inside it:

- **HTTPS/TLS** — terminate at a reverse proxy (Caddy/Nginx/traefik); the
  app speaks plain HTTP on the internal network.
- **End-user accounts and sessions** — when fisher accounts are needed,
  front the app with an identity provider (OAuth2/OIDC) and map tokens to
  the roles above; do not grow a password database inside ParaSail.
- **Distributed rate limiting** — the limiter is per-process; for multiple
  API replicas move the counters to Redis or the proxy.
- **Secrets management** — key hashes belong in a secret store, not in a
  committed config; `config.yaml` here is the local-dev convention.

## 7. Hardening checklist before going public

1. Generate admin/officer keys (`scripts/generate_api_key.py`), store
   hashes in config (or a secret store), never commit the keys.
2. Set `public_docs: false` and `cors_origins` to your real origin.
3. Put the app behind TLS via a reverse proxy; forward
   `X-Forwarded-For` correctly so rate limiting sees real clients.
4. Route the `parasail.audit` logger to persistent storage.
5. Re-run `python scripts/run_validation.py` — all six families,
   including T6, must pass.

## Injecting API keys from the environment

`security.api_keys` in config.yaml works for a single-operator deployment,
but production keys belong in a secret manager. The same entries can be
injected through the environment instead, or alongside the config:

```bash
export PARASAIL_API_KEYS='[{"name":"ops","key_hash":"<sha256>","role":"admin"}]'
```

Entries from the environment are appended to the configured ones, so you can
keep non-secret placeholders in config and the real keys outside the
repository (no key material — not even a hash — then lives in version
control). Malformed JSON is ignored with a warning and the config keys keep
working: a bad secret inject must not become an outage, and it must not fail
open either. T6 asserts both behaviours.

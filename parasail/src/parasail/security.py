"""ParaSail security layer (production hardening).

Everything a public-facing deployment needs, configuration-driven and with
no external dependencies:

  * sliding-window RATE LIMITING per client and per endpoint class,
    with X-RateLimit-* headers and 429 responses,
  * SECURITY HEADERS (CSP tuned to the local-asset dashboard, nosniff,
    frame denial, referrer policy, permissions policy),
  * a REQUEST BODY SIZE LIMIT,
  * ROLE-BASED ACCESS CONTROL on a X-API-Key credential: roles
    public < officer < admin; keys are stored as SHA-256 hashes in
    config.yaml (a plaintext `key` field is accepted for development),
  * an AUDIT LOG (parasail.audit logger) for privileged actions,
  * CORS restricted to configured origins.

What this deliberately does NOT do (see docs/SECURITY.md): end-user
accounts, sessions, password flows - those belong to a reverse proxy /
identity provider in a full production stack.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Config

log = logging.getLogger("parasail.security")
audit_log = logging.getLogger("parasail.audit")

ROLE_LEVELS = {"public": 0, "officer": 1, "admin": 2}

# Content-Security-Policy for the single-file dashboard: assets are served
# locally (/static), map tiles come from OpenStreetMap, and the page uses
# inline <style>/<script> blocks by design (no build tooling).
CSP = ("default-src 'self'; "
       "img-src 'self' data: https://tile.openstreetmap.org "
       "https://*.tile.openstreetmap.org; "
       "script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; "
       "connect-src 'self'; "
       "frame-ancestors 'none'; "
       "base-uri 'self'; "
       "form-action 'self'")


def audit(event: str, **fields) -> None:
    """Structured audit trail for privileged actions (model switches,
    subscriptions, admin reads). Route the `parasail.audit` logger to a
    file or SIEM in production."""
    audit_log.info("%s %s", event, json.dumps(fields, default=str))


# --------------------------------------------------------------------------- #
# rate limiting (sliding window, per client, per bucket)
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Thread-safe sliding-window limiter. Buckets and limits come from
    config (security.rate_limits); unknown buckets fall back to `default`."""

    def __init__(self, rules: dict | None):
        self.rules = rules or {}
        self._hits: dict[tuple[str, str], deque] = {}
        self._lock = threading.Lock()

    def _rule(self, bucket: str) -> dict:
        r = self.rules.get(bucket)
        if not r:
            r = self.rules.get("default") or {"limit": 120, "window_s": 60}
        return {"limit": int(r["limit"]), "window_s": float(r["window_s"])}

    def check(self, bucket: str, client: str) -> tuple[bool, dict[str, str]]:
        """Returns (allowed, headers). On denial the headers carry
        Retry-After so well-behaved clients back off."""
        rule = self._rule(bucket)
        now = time.monotonic()
        with self._lock:
            # opportunistic cleanup keeps memory bounded under address churn
            if len(self._hits) > 50_000:
                stale = now - max(rule["window_s"], 600.0)
                for k in [k for k, v in self._hits.items()
                          if not v or v[-1] <= stale]:
                    self._hits.pop(k, None)
            dq = self._hits.setdefault((bucket, client), deque())
            horizon = now - rule["window_s"]
            while dq and dq[0] <= horizon:
                dq.popleft()
            if len(dq) >= rule["limit"]:
                retry = max(1.0, rule["window_s"] - (now - dq[0]))
                return False, {
                    "X-RateLimit-Limit": str(rule["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(int(retry) + 1),
                }
            dq.append(now)
            return True, {
                "X-RateLimit-Limit": str(rule["limit"]),
                "X-RateLimit-Remaining": str(rule["limit"] - len(dq)),
            }


def client_ip(request: Request) -> str:
    """Client identity for rate limiting: first hop of X-Forwarded-For when
    behind a trusted reverse proxy, else the socket peer."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def bucket_for(path: str, method: str) -> str:
    """Map a request to a rate-limit bucket. Costly endpoints (live fetches,
    model inference, image uploads, subscriptions) and privileged endpoints
    get their own budgets."""
    p = path.rstrip("/")
    if p in ("/assistant/model",):
        return "admin"
    if p == "/assistant/describe-image":
        return "image"
    if p.startswith("/assistant"):
        return "assistant" if method == "POST" else "default"
    if p in ("/advisory", "/fish-suggestions"):
        return "advisory"
    if p == "/news":
        return "translate"       # may hit the translation backends on cache miss
    if p == "/translate":
        return "translate"
    return "default"


# --------------------------------------------------------------------------- #
# ASGI middleware: rate limit, security headers, body size
# --------------------------------------------------------------------------- #
class SecurityMiddleware:
    """One pass, three jobs: per-bucket rate limiting (429 + standard
    headers), fixed security headers on every response, and a request body
    size cap (413) checked via Content-Length."""

    def __init__(self, app, cfg: Config, limiter: RateLimiter):
        self.app = app
        self.limiter = limiter
        sec = cfg.raw.get("security", {}) or {}
        self.max_body = int(sec.get("max_body_bytes", 10 * 1024 * 1024))
        self.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": CSP,
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        # body size cap (Content-Length check; rejects before reading)
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.max_body:
                        response = JSONResponse(
                            {"detail": f"request body exceeds "
                                       f"{self.max_body // 1048576} MB limit"},
                            status_code=413)
                        await response(scope, receive, send)
                        return
                except ValueError:
                    pass
        # rate limit
        headers = {k.decode(): v.decode()
                   for k, v in scope.get("headers", [])}
        ip = headers.get("x-forwarded-for", "").split(",")[0].strip() \
            or (scope.get("client") or ("unknown",))[0]
        allowed, rl_headers = self.limiter.check(
            bucket_for(path, method), ip)
        if not allowed:
            audit("rate_limit_exceeded", path=path, client=ip,
                  bucket=bucket_for(path, method))
            response = JSONResponse(
                {"detail": "too many requests - please slow down"},
                status_code=429, headers=rl_headers)
            await response(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                for k, v in self.headers.items():
                    message["headers"].append((k.encode(), v.encode()))
                for k, v in rl_headers.items():
                    message["headers"].append((k.encode(), v.encode()))
            await send(message)

        await self.app(scope, receive, send_with_headers)


def add_cors(app, cfg: Config) -> None:
    """CORS locked to the configured origins - no wildcard in production."""
    sec = cfg.raw.get("security", {}) or {}
    origins = sec.get("cors_origins") or ["http://localhost:8000",
                                          "http://127.0.0.1:8000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
        max_age=600,
    )


# --------------------------------------------------------------------------- #
# role-based access control (X-API-Key)
# --------------------------------------------------------------------------- #
def _key_matches(provided: str, entry: dict) -> bool:
    if entry.get("key") and provided == entry["key"]:
        return True                                    # dev convenience
    wanted = entry.get("key_hash")
    if wanted:
        return hashlib.sha256(provided.encode()).hexdigest() == wanted
    return False


def configured_api_keys(cfg: Config) -> list[dict]:
    """API-key entries from config plus any injected through the
    PARASAIL_API_KEYS environment variable (JSON list; same entry shape).
    Malformed environment JSON is ignored with a warning rather than
    taking the service down - a bad secret inject must not become an
    outage, and the config keys (if any) keep working."""
    sec = cfg.raw.get("security", {}) or {}
    keys = list(sec.get("api_keys") or [])
    raw = os.environ.get("PARASAIL_API_KEYS", "").strip()
    if not raw:
        return keys
    try:
        extra = json.loads(raw)
        if isinstance(extra, dict):
            extra = [extra]
        if not isinstance(extra, list):
            raise ValueError("expected a JSON list or object")
        added = [e for e in extra if isinstance(e, dict)]
        log.info("PARASAIL_API_KEYS injected %d key entr(ies)", len(added))
        return keys + added
    except Exception as exc:  # noqa: BLE001 - never fail closed on parse
        log.warning("PARASAIL_API_KEYS ignored (invalid JSON: %s)", exc)
        return keys


def require_role(cfg: Config, minimum: str):
    """FastAPI dependency factory: enforces the minimum role for an
    endpoint. Credentials: X-API-Key header, validated against
    security.api_keys in config.yaml (SHA-256 hashes recommended).

    401 = missing/invalid credentials, 403 = valid credentials,
    insufficient role. With no keys configured, privileged endpoints are
    locked (secure by default) with a pointer to docs/SECURITY.md.

    Keys come from `security.api_keys` in config.yaml, optionally extended
    by the PARASAIL_API_KEYS environment variable (a JSON list of entries in
    the same shape). A production deployment should keep them in a secret
    manager and inject via the environment, so no key material - not even a
    hash - lives in the repository config.
    """
    keys = configured_api_keys(cfg)

    def dependency(
        x_api_key: str | None = Header(None, alias="X-API-Key"),
    ) -> str:
        if not keys:
            raise HTTPException(
                status_code=403,
                detail="privileged endpoints are locked: no API keys "
                       "configured - see docs/SECURITY.md")
        if not x_api_key:
            raise HTTPException(
                status_code=401, detail="API key required (X-API-Key)")
        role = None
        for entry in keys:
            if _key_matches(x_api_key, entry):
                role = entry.get("role", "public")
                break
        if role is None:
            raise HTTPException(status_code=401, detail="invalid API key")
        if ROLE_LEVELS.get(role, 0) < ROLE_LEVELS[minimum]:
            raise HTTPException(
                status_code=403,
                detail=f"requires {minimum} role (you have {role})")
        return role

    return dependency

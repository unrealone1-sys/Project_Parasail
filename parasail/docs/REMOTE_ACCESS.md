# Remote Access — Tailscale Hosting + Mobile Web App (PWA)

How to test ParaSail from your phone and other devices over Tailscale, and
how the installable mobile web app works.

## 1. Host over Tailscale (your private network)

Tailscale gives every device you own a private address (100.x.y.z) on your
tailnet; devices reach each other as if on one LAN, encrypted, no port
forwarding.

1. **Install Tailscale** and sign in on the server machine and on your
   phone (same account): https://tailscale.com/download
   (Already installed on the server: v1.102.3.)
2. **Run ParaSail bound to all interfaces** (already running this way):
   ```powershell
   cd C:\Users\ignun\.zcode\workspace\default\parasail
   .venv\Scripts\activate
   uvicorn parasail.api:app --host 0.0.0.0 --port 8000
   ```
3. **Find the server's tailnet address** (in your own terminal):
   ```powershell
   tailscale ip -4          # e.g. 100.101.102.103
   ```
4. **Open on any device** on your tailnet:
   `http://100.101.102.103:8000` — phone, tablet, another PC.

Windows Firewall note: if the page does not load from your phone, allow
inbound port 8000 once:
```powershell
New-NetFirewallRule -DisplayName "ParaSail 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

## 2. The installable mobile web app (PWA)

The dashboard is a full PWA:

- **manifest** (`/static/manifest.webmanifest`) — name, brand icons
  (including a maskable icon for Android adaptive launchers), standalone
  display, theme colour.
- **service worker** (`/sw.js`) — caches the app shell (page, Leaflet,
  Lora fonts, icons) so it opens even with no connectivity; live data APIs
  are never cached (advisories must stay fresh, and the app already shows
  data-age flags when offline).
- **mobile layout** — touch-sized controls, full-width buttons and inputs,
  shorter map, iOS safe-area padding.
- **Install app** button appears (green, header) on Android Chrome when the
  browser offers installation.

### Installing on your phone

**Android (Chrome):** open the app → menu ⋮ → *Install app* (or tap the
green *Install app* button). It lands on the home screen and opens
full-screen like a native app.

**iOS (Safari):** open the app → Share → *Add to Home Screen*.

> **HTTPS and installability:** browsers only allow service-worker
> registration and PWA install on secure origins (https or localhost).
> Plain `http://100.x.y.z:8000` works for browsing but not for install.
> Use Tailscale Serve (below) to get automatic HTTPS on your tailnet.

## 3. Tailscale Serve — HTTPS on your tailnet (recommended)

One command proxies ParaSail with a valid TLS certificate on your tailnet:

```powershell
tailscale serve --bg 8000
```

Now open `https://<your-machine>.<your-tailnet>.ts.net` on any device:
- HTTPS (service worker + PWA install work),
- no port in the URL,
- `--bg` keeps the proxy running in the background.

Remove it later with `tailscale serve --bg off` (or `tailscale serve reset`).

### Going public (optional, later)

`tailscale funnel` can expose the app to the public internet through the
same command. Before doing that, work through the hardening checklist in
[`SECURITY.md`](SECURITY.md) §7: hashed API keys, `public_docs: false`,
real CORS origin, and remember the rate limiter is per-process.

## 4. Serving multiple apps on the same machine (different links)

One Tailscale node can serve any number of local projects, each on **its
own link** — one `serve` entry per port. This is the recommended pattern
when you run more than one local platform (e.g., ParaSail plus another
local AI platform):

```powershell
# ParaSail -> the root link
tailscale serve --bg 8000
#   https://<your-machine>.<your-tailnet>.ts.net          -> localhost:8000

# your other platform -> its own link (use its real port)
tailscale serve --bg 3000
#   https://<your-machine>.<your-tailnet>.ts.net:3000     -> localhost:3000
```

Each entry gets HTTPS automatically, and every device on the tailnet sees
both links in the same Tailscale app. Verify the full mapping any time:

```powershell
tailscale serve status
```

Important gotcha: **a `serve` command for the root path (`/`) replaces the
previous root mount** — if another project "used to run on the link", a new
root serve took it over. Re-add it on its own port as shown above (or move
one of them to a subpath, below) and the old link's content returns under
its new address.

Alternative — mount an app under a **subpath** of the same link instead of
a separate port:

```powershell
tailscale serve --bg --set-path /ai 3000
#   https://<your-machine>.<your-tailnet>.ts.net/ai       -> localhost:3000
```

Only do this if that app works under a path prefix (many web apps assume
they are served at `/` and their asset links break). The separate-port
pattern above avoids this entirely.

Removing / resetting:

```powershell
tailscale serve --bg off 8000     # remove one entry
tailscale serve reset             # remove everything, start clean
```

If the other project runs on a **different machine**, run `tailscale serve`
on that machine — each machine has its own
`<machine>.<tailnet>.ts.net` hostname, so the links never collide.

## 5. Notes for remote/mobile use

- The dashboard is same-origin (all fetches are relative), so CORS and the
  CSP (`connect-src 'self'`) work unchanged on any host you serve it from.
- If you call the API cross-origin (another frontend), add that origin to
  `security.cors_origins` in `config.yaml`.
- The AI (Ollama on this machine) answers on any interface the API is
  reachable from; nothing extra is needed for mobile clients.
- Offline behaviour: with no connectivity the cached shell opens, telemetry
  and advisories show their unavailable/degraded states, and the chat falls
  back to the built-in mode — by design, never a blank screen.

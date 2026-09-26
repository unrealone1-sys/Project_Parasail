"""ParaSail FastAPI service (development phases P6-P7).

Endpoints:
  GET  /                       - visual advisory dashboard (map location picking,
                                live telemetry, traffic-light verdict, likely
                                fish spots with landmarks and distances,
                                in-site translation to Indian coastal languages,
                                grounded AI assistant for summaries and Q&A)
  POST /advisory               - the core recommendation (position, species, window)
  POST /assistant/summarize    - plain-language decision-support summary of an
                                advisory (grounded VLM, template fallback)
  POST /assistant/ask          - grounded Q&A over the corpus + live advisory
                                (cited answers; never contradicts the verdict)
  POST /assistant/describe-image - vision-language reading of catch photos,
                                satellite tiles and charts
  GET  /assistant/status       - assistant backend probe (model, availability)
  GET  /telemetry              - current conditions at a point (wind, gusts, waves, SST)
  GET  /fish-suggestions       - approximate fish locations with landmark + distance
  POST /translate              - translate arbitrary interface text (batched)
  GET  /languages              - supported translation languages
  GET  /species                - the configured registry
  GET  /closures               - active closure calendar entries
  GET  /mpas                   - protected-area boundaries (GeoJSON; what the
                                fail-closed guard enforces + the map overlay)
  GET  /health                 - liveness + configuration fingerprint
  GET  /docs                   - interactive API documentation (FastAPI/Swagger)

Run:  uvicorn parasail.api:app --reload --port 8000
"""
from __future__ import annotations

import functools
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .advisory import AdvisoryEngine
from .assistant import AssistantService, ModelUnavailableError
from .config import Config, load_config
from .ingestion import IngestionService, TelemetryField, AlertItem
from .rag import RagService
from .rules import RulesEngine
from .security import (RateLimiter, SecurityMiddleware, add_cors, audit,
                       require_role)
from .suggestions import fish_suggestions
from .translate import SUPPORTED_LANGUAGES, TranslationService

log = logging.getLogger("parasail.api")

# Problem/Answer explanations for known system states, shown in the
# dashboard verdict card (localized into the requested language). The
# patterns match advisory block reasons; unmatched reasons get no block.
PROBLEM_ANSWERS = [
    ("MPA registry unavailable",
     "Why does ParaSail say STOP when the sea looks fine?",
     "The protected-areas registry - the map of marine parks and reserves - "
     "is not connected right now, so your spot cannot be checked against "
     "it. ParaSail refuses to advise rather than risk pointing you into a "
     "protected zone; conservation comes before convenience. Your operator "
     "can restore the registry by starting the database "
     "(docker compose up -d db)."),
    ("MPA registry unreachable",
     "Why does ParaSail say STOP when the sea looks fine?",
     "The protected-areas registry cannot be reached at the moment. ParaSail "
     "refuses to advise rather than risk pointing you into a protected "
     "zone, and keeps trying in the background. Try again shortly."),
    ("seasonal closure",
     "Why is fishing closed for this fish right now?",
     "A seasonal closure is active for this species to protect spawning. "
     "The advisory's citation shows the exact rule; fishing reopens when "
     "the closed season ends."),
    ("inside marine protected area",
     "Why is this place always STOP?",
     "This position falls inside a marine protected area, where fishing is "
     "not allowed at any time of year. The reserve's boundaries are "
     "enforced ahead of any scoring, whatever the weather or the fish."),
    ("not in registry",
     "Why can't ParaSail advise on this species?",
     "This species is not in this deployment's registry. The operator adds "
     "species through configuration - no code changes - together with "
     "their closures and habitat profiles."),
]


def _problem_answer_for(advisory: dict, language: str,
                        translations: TranslationService) -> dict | None:
    """Attach a localized Problem/Answer explanation for known block
    reasons; returns None for ordinary advisories."""
    reason = advisory.get("block_reason") or ""
    for pattern, problem, answer in PROBLEM_ANSWERS:
        if pattern.lower() in reason.lower():
            if language != "en":
                problem, answer = translations.translate_batch(
                    [problem, answer], language)
            return {"problem": problem, "answer": answer}
    return None


# --------------------------------------------------------------------------- #
# request / response models
# --------------------------------------------------------------------------- #
class AdvisoryRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="latitude")
    lon: float = Field(..., ge=-180, le=180, description="longitude")
    species: str = Field(..., description="scientific name from the registry")
    start: datetime = Field(..., description="trip start (ISO-8601, UTC)")
    hours: int = Field(24, ge=1, le=72, description="advisory horizon")
    language: str = Field("en", pattern="^(en|ml|ta|kn|te|mr|gu|bn|or|hi)$",
                          description="language for plain-language summaries")


class TranslateRequest(BaseModel):
    texts: list[str] = Field(..., max_length=50,
                             description="English strings to translate")
    target: str = Field(..., pattern="^(en|ml|ta|kn|te|mr|gu|bn|or|hi)$",
                        description="target language code")


class AssistantAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=600,
                          description="the user's question, any phrasing")
    language: str = Field("en", pattern="^(en|ml|ta|kn|te|mr|gu|bn|or|hi)$",
                          description="reply language")
    # Optional advisory context: when provided, the answer is grounded in the
    # live advisory so it can never contradict the authoritative verdict.
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    species: str | None = Field(None, description="scientific name")
    start: datetime | None = Field(None, description="trip start (ISO-8601, UTC)")
    hours: int = Field(24, ge=1, le=72)


class AssistantImageRequest(BaseModel):
    image_base64: str = Field(..., min_length=64,
                              description="base64-encoded image (jpeg/png/webp)")
    mime: str = Field("image/jpeg", pattern="^image/(jpeg|png|webp)$")
    kind: str = Field("catch", pattern="^(catch|satellite|chart|other)$",
                      description="what the image shows; tunes the prompt")
    question: str | None = Field(None, max_length=400,
                                 description="optional follow-up question")
    language: str = Field("en", pattern="^(en|ml|ta|kn|te|mr|gu|bn|or|hi)$")


class AssistantModelRequest(BaseModel):
    model: str = Field(..., max_length=80,
                       description="registry key from GET /assistant/models")
    force: bool = Field(
        False, description="switch even when the model is not downloaded "
        "yet; the assistant then answers in built-in mode until it is "
        "installed (the response says so)")


class NewsRequest(BaseModel):
    language: str = Field("en", pattern="^(en|ml|ta|kn|te|mr|gu|bn|or|hi)$",
                          description="news is translated into this language")


# --------------------------------------------------------------------------- #
# visual advisory dashboard (single self-contained page, no build tooling)
# --------------------------------------------------------------------------- #
UI_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ParaSail - fishing advisory</title>
<link rel="stylesheet" href="/static/leaflet.css">
<link rel="manifest" href="/static/manifest.webmanifest">
<meta name="theme-color" content="#0A2E3C">
<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/favicon-32.png">
<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ParaSail">
<style>
 /* Lora by Olga Karpushina & Alexei Vanyashi (Cyreal Fonts), SIL OFL 1.1 -
    served locally so the app has no font-CDN dependency. Indic scripts fall
    back to the system font (Lora covers Latin only). */
 @font-face{font-family:'Lora';font-style:normal;font-weight:400 700;font-display:swap;src:url(/static/fonts/lora-normal-latin-ext.woff2) format('woff2');unicode-range:U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
 @font-face{font-family:'Lora';font-style:normal;font-weight:400 700;font-display:swap;src:url(/static/fonts/lora-normal-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
 @font-face{font-family:'Lora';font-style:italic;font-weight:400 700;font-display:swap;src:url(/static/fonts/lora-italic-latin-ext.woff2) format('woff2');unicode-range:U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
 @font-face{font-family:'Lora';font-style:italic;font-weight:400 700;font-display:swap;src:url(/static/fonts/lora-italic-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
 *{box-sizing:border-box}
 body{font-family:'Lora','Nirmala UI','Segoe UI',Arial,serif;background:#0A2E3C;color:#F2F8F9;margin:0;padding:22px;display:flex;justify-content:center;min-height:100vh}
 .wrap{width:100%;max-width:1180px}
 header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:18px;flex-wrap:wrap}
 h1{font-family:'Lora',Georgia,serif;font-size:36px;margin:0;color:#fff}
 .tag{color:#9DB8C0;margin:6px 0 0;font-size:15px}
 .hright{display:flex;gap:10px;align-items:center;margin-top:6px;flex-wrap:wrap}
 .pill{background:#12455A;border:1px solid #2A5A6E;color:#D9EAED;border-radius:999px;padding:7px 16px;font-size:12.5px;font-weight:600;display:flex;align-items:center;gap:8px}
 .dot{width:9px;height:9px;border-radius:50%;background:#4C9A57;display:inline-block}
 #lang{background:#12455A;border:1px solid #2A5A6E;color:#F2F8F9;border-radius:999px;padding:7px 12px;font-size:13.5px;cursor:pointer}
 #installbtn{background:#4C9A57;color:#fff;border:0;border-radius:999px;padding:7px 16px;font-size:13px;font-weight:700;cursor:pointer;transition:transform .12s,background .15s}
 #installbtn:hover{background:#3E8A4A;transform:translateY(-1px)}
 .card{background:#fff;color:#16323D;border-radius:14px;padding:22px 26px;box-shadow:0 10px 30px rgba(0,0,0,.35);margin-bottom:18px}
 .controls{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end}
 .field{flex:1;min-width:170px}
 label{display:block;font-size:11.5px;font-weight:700;color:#0E4A54;margin-bottom:6px;letter-spacing:.5px;text-transform:uppercase}
 select,input{width:100%;padding:10px 12px;border:1.5px solid #C7D8DD;border-radius:8px;font-size:15px;color:#16323D;background:#fff}
 button.go{background:#E76F51;color:#fff;border:0;border-radius:9px;padding:12px 28px;font-size:15.5px;font-weight:700;cursor:pointer;min-width:170px}
 button.go:disabled{opacity:.6;cursor:wait}
 .main{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;align-items:start;grid-auto-rows:auto}
 @media(max-width:900px){.main{grid-template-columns:1fr}}
 /* The map card is sized by JS to match the live-telemetry card exactly
    (syncMapHeight): equal heights, and the map never grows or shrinks when
    the advice result card appears. The fixed height below is the pre-JS
    fallback. */
 .mapcard{padding:12px;align-self:start;min-height:0;display:flex;flex-direction:column;overflow:hidden}
 #map{flex:1 1 auto;min-height:260px;height:430px;border-radius:10px;z-index:1}
 .coords{font-size:12.5px;color:#6B8290;text-align:center;padding:9px 4px 2px}
 .sectitle{font-family:'Lora',Georgia,serif;font-size:17px;font-weight:700;color:#0E4A54;margin-bottom:12px}
 .verdict{display:flex;align-items:center;gap:20px;padding:4px 2px}
 .light{width:88px;height:88px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;text-align:center;box-shadow:0 6px 16px rgba(0,0,0,.28)}
 .vword{font-family:'Lora',Georgia,serif;font-size:27px;font-weight:700}
 .vsub{color:#6B8290;font-size:13.5px;margin-top:3px}
 ul.why{list-style:none;padding:0;margin:14px 0 0}
 ul.why li{padding:10px 0 10px 34px;border-bottom:1px solid #E3EFF1;position:relative;font-size:14px}
 ul.why li:last-child{border-bottom:0}
 ul.why li:before{content:'';position:absolute;left:4px;top:13px;width:17px;height:17px;border-radius:50%}
 li.w-ok:before{background:#4C9A57}
 li.w-mid:before{background:#D9A62E}
 li.w-bad:before{background:#C94F4F}
 .note{font-size:12px;color:#6B8290;margin-top:12px}
 details{margin-top:12px}
 summary{cursor:pointer;color:#14707C;font-weight:600;font-size:13px}
 pre{background:#0A2E3C;color:#D9EAED;border-radius:10px;padding:13px;overflow:auto;font-size:11.5px;max-height:280px;margin-top:9px}
 .tgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:10px}
 .tgrid+.tgroup{margin-top:14px}
 .tgroup{font-size:10.5px;font-weight:700;color:#6B8290;letter-spacing:.9px;text-transform:uppercase;margin:0 0 7px}
 .t{background:#E3EFF1;border-radius:10px;padding:13px 8px;text-align:center;animation:popIn .4s ease both}
 .t.wide .tv{font-size:15px}
 .tv{font-family:'Lora',Georgia,serif;font-size:21px;font-weight:700;color:#0E4A54}
 .ts{font-size:10.5px;color:#6B8290;margin-top:2px;min-height:0}
 .tl{font-size:11px;color:#6B8290;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-top:3px}
 .dirarrow{display:inline-block;font-size:12px;transition:transform .6s cubic-bezier(.2,.9,.3,1.1);color:#14707C}
 .spotrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
 .spot{background:#E3EFF1;border-radius:11px;padding:15px 17px;cursor:pointer;transition:transform .12s}
 .spot:hover{transform:translateY(-2px)}
 .spot .rank{display:inline-block;background:#14707C;color:#fff;border-radius:6px;font-size:11.5px;font-weight:700;padding:2px 9px}
 .spot .dist{font-family:'Lora',Georgia,serif;font-size:17.5px;font-weight:700;color:#0E4A54;margin:8px 0 2px}
 .spot .lm{font-size:13px;color:#16323D;margin-bottom:9px}
 .bar{height:7px;background:#C7D8DD;border-radius:99px;overflow:hidden}
 .bar i{display:block;height:100%;border-radius:99px}
 .spot .m{font-size:11.5px;color:#6B8290;margin-top:6px}
 .aisum{background:#F4F8F9;border:1px solid #D8E2E6;border-left:4px solid #14707C;border-radius:9px;padding:13px 16px;margin-top:14px;font-size:14px;line-height:1.55;animation:fadeUp .45s ease both}
 .pa{background:#FDF3EF;border:1px solid #F0C9BC;border-left:4px solid #E76F51;border-radius:9px;padding:12px 15px;margin-top:14px;animation:fadeUp .45s ease both}
 .paq{font-weight:700;color:#B3553D;font-size:13px;margin-bottom:5px}
 .paa{font-size:13.5px;line-height:1.6}
 .ntag{display:inline-block;background:#14707C;color:#fff;border-radius:5px;font-size:10px;padding:2px 8px;margin-right:8px;font-weight:600;vertical-align:1px}
 .nsrc{font-size:11px;color:#6B8290;margin-top:5px}
 .aisum .tagline{font-size:11px;font-weight:700;color:#14707C;letter-spacing:.6px;text-transform:uppercase;margin-bottom:5px}
 .aisum .pts{margin:4px 0 0;padding:0}
 .aisum .pts div{position:relative;padding:3px 0 3px 22px;animation:fadeUp .4s ease both}
 .aisum .pts div:before{content:'';position:absolute;left:3px;top:10px;width:8px;height:8px;border-radius:2px;background:#14707C;transform:rotate(45deg)}
 .aisum .pts div:nth-child(2){animation-delay:.07s}
 .aisum .pts div:nth-child(3){animation-delay:.14s}
 .aisum .pts div:nth-child(4){animation-delay:.21s}
 .aisum .pts div:nth-child(5){animation-delay:.28s}
 .aisum .src{font-size:11px;color:#6B8290;margin-top:8px}
 #chatlog{max-height:300px;overflow-y:auto;margin:12px 0 6px;display:flex;flex-direction:column;gap:9px;scroll-behavior:smooth}
 .bub{max-width:86%;border-radius:13px;padding:10px 14px;font-size:14px;line-height:1.5;white-space:pre-wrap;animation:bubIn .28s cubic-bezier(.2,.9,.3,1.2) both}
 .bub.user{align-self:flex-end;background:#14707C;color:#fff;border-bottom-right-radius:4px}
 .bub.ai{align-self:flex-start;background:#E3EFF1;color:#16323D;border-bottom-left-radius:4px}
 .bub.ai .cite{display:block;font-size:11.5px;color:#4A6B75;margin-top:7px;border-top:1px solid #C7D8DD;padding-top:6px}
 .bub.ai.wait{opacity:.75;font-style:italic}
 .dots i{display:inline-block;width:5px;height:5px;border-radius:50%;background:#6B8290;margin-left:3px;animation:blink 1.2s infinite}
 .dots i:nth-child(2){animation-delay:.2s}
 .dots i:nth-child(3){animation-delay:.4s}
 .chatrow{display:flex;gap:9px}
 #chatin{flex:1;padding:11px 14px;border:1.5px solid #C7D8DD;border-radius:9px;font-size:14.5px;transition:border-color .18s,box-shadow .18s}
 #chatin:focus{outline:none;border-color:#14707C;box-shadow:0 0 0 3px rgba(20,112,124,.14)}
 #chatsend{background:#14707C;color:#fff;border:0;border-radius:9px;padding:11px 22px;font-size:14.5px;font-weight:700;cursor:pointer;transition:background .18s,transform .12s}
 #chatsend:hover{background:#0E5A66}
 #chatsend:disabled{opacity:.6;cursor:wait}
 .chathint{font-size:12.5px;color:#6B8290;margin:-6px 0 2px}
 .chattop{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
 /* ---- model picker: chip button + modal panel with honest availability ---- */
 .modelbtn{display:inline-flex;align-items:center;gap:8px;background:#E3EFF1;border:1.5px solid #C7D8DD;color:#16323D;border-radius:999px;padding:7px 14px;font-size:12.5px;font-weight:700;cursor:pointer;max-width:260px;font-family:inherit;transition:border-color .18s,background .15s,transform .12s}
 .modelbtn:hover{border-color:#14707C;background:#D9E9ED;transform:translateY(-1px)}
 .modelbtn .mdot{width:9px;height:9px;border-radius:50%;background:#9DB4BC;flex:none;transition:background .3s}
 .modelbtn .mdot.ok{background:#4C9A57;animation:pulseDot 2.4s ease-out infinite}
 .modelbtn .mdot.bad{background:#C94F4F}
 .modelbtn .mchev{font-size:10px;color:#4A6B75}
 .modalov{position:fixed;inset:0;background:rgba(10,32,42,.55);backdrop-filter:blur(3px);z-index:1200;display:none;align-items:center;justify-content:center;padding:18px}
 .modalov.open{display:flex;animation:fadeUp .18s ease both}
 .mpanel{background:#F6FAFB;border-radius:16px;box-shadow:0 18px 50px rgba(6,35,45,.35);width:min(560px,100%);max-height:86vh;overflow-y:auto;padding:20px 22px;animation:bubIn .24s cubic-bezier(.2,.9,.3,1.15) both}
 .mphead{display:flex;justify-content:space-between;align-items:center;gap:10px}
 .mpx{background:none;border:0;font-size:26px;line-height:1;color:#4A6B75;cursor:pointer;padding:2px 10px;border-radius:8px;transition:background .15s,color .15s}
 .mpx:hover{background:#E3EFF1;color:#0E4A54}
 .mpsub{font-size:12.5px;color:#6B8290;margin:6px 0 14px;line-height:1.5}
 .mcard{background:#fff;border:1.5px solid #D5E3E8;border-radius:12px;padding:13px 15px;margin-bottom:10px;cursor:pointer;transition:border-color .18s,box-shadow .18s,transform .12s;animation:fadeUp .3s ease both}
 .mcard:hover{border-color:#14707C;transform:translateY(-1px);box-shadow:0 6px 18px rgba(14,74,84,.10)}
 .mcard.active{border-color:#14707C;box-shadow:0 0 0 3px rgba(20,112,124,.12);cursor:default}
 .mcard.active:hover{transform:none;box-shadow:0 0 0 3px rgba(20,112,124,.12)}
 .mtop{display:flex;justify-content:space-between;align-items:center;gap:8px}
 .mname{font-family:ui-monospace,'Cascadia Mono',Consolas,monospace;font-weight:700;font-size:13px;color:#0E4A54}
 .mchip{font-size:10.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;border-radius:999px;padding:3px 10px;white-space:nowrap}
 .mchip.live{background:#E2F1E4;color:#2E7D3A}
 .mchip.down{background:#F7E3E0;color:#A83E33}
 .mdesc{font-size:12.5px;color:#4A6B75;margin:6px 0 9px;line-height:1.5}
 .mmeta{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
 .mtag{font-size:11px;font-weight:700;color:#0E4A54;background:#E3EFF1;border-radius:7px;padding:3px 9px}
 .minstall{display:none;margin-top:10px;background:#FBF3EE;border:1px solid #EAD3C8;border-radius:9px;padding:10px 12px;animation:fadeUp .25s ease both}
 .mcard.showinstall .minstall{display:block}
 .minstall .mt2{font-size:12px;font-weight:700;color:#8A3B2E;margin-bottom:5px}
 .minstall .cmd{font-family:ui-monospace,'Cascadia Mono',Consolas,monospace;font-size:12px;color:#8A3B2E;word-break:break-all;display:block;margin-bottom:8px}
 .minstall .still{background:none;border:1.5px solid #C94F4F;color:#A83E33;border-radius:8px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;transition:background .15s}
 .minstall .still:hover{background:#F7E3E0}
 .mpkey{display:none;margin-top:12px;background:#E3EFF1;border-radius:10px;padding:12px 14px;animation:fadeUp .25s ease both}
 .mpkey.open{display:block}
 .mpkey .kt{font-size:12.5px;font-weight:700;color:#0E4A54;margin-bottom:8px}
 .mpkey .krow{display:flex;gap:8px}
 .mpkey input{flex:1;padding:9px 12px;border:1.5px solid #C7D8DD;border-radius:8px;font-size:13px;font-family:inherit}
 .mpkey input:focus{outline:none;border-color:#14707C}
 .mpkey button{background:#14707C;color:#fff;border:0;border-radius:8px;padding:9px 16px;font-weight:700;font-size:13px;cursor:pointer;font-family:inherit;transition:background .15s}
 .mpkey button:hover{background:#0E5A66}
 .mpfoot{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:6px}
 .mpnote{font-size:12px;color:#6B8290}
 .mpghost{background:none;border:1.5px solid #C7D8DD;color:#0E4A54;border-radius:8px;padding:7px 14px;font-size:12.5px;font-weight:700;cursor:pointer;font-family:inherit;transition:border-color .15s,background .15s;white-space:nowrap}
 .mpghost:hover{border-color:#14707C;background:#E3EFF1}
 /* admin panel */
 .admingrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:10px}
 .admcard{background:#fff;border:1.5px solid #D5E3E8;border-radius:12px;padding:14px 16px;animation:fadeUp .3s ease both}
 .admcard h4{margin:0 0 8px;font-size:13px;font-weight:700;color:#0E4A54;border-bottom:1px solid #E3EFF1;padding-bottom:8px}
 .admrow{display:flex;justify-content:space-between;padding:4px 0;font-size:12.5px}
 .admrow .k{color:#4A6B75}
 .admrow .v{color:#16323D;font-weight:600}
 .admrow .v.ok{color:#4C9A57}
 .admrow .v.warn{color:#D9A62E}
 .admrow .v.bad{color:#C94F4F}
 .admgrid.single{grid-template-columns:1fr}
 .maptools{display:flex;gap:8px;justify-content:center;padding:2px 2px 10px;flex-wrap:wrap}
 .maptools button{background:#E3EFF1;color:#0E4A54;border:0;border-radius:8px;padding:7px 15px;font-size:12.5px;font-weight:700;cursor:pointer;transition:background .15s,transform .12s}
 .maptools button:hover{background:#D2E4E8;transform:translateY(-1px)}
 .maptools button.on{background:#14707C;color:#fff}
 .srcdetails{margin-top:12px}
 .srcinfo div{font-size:12px;color:#16323D;padding:3px 0;line-height:1.5}
 .srcinfo a{color:#14707C;font-weight:600}
 .newsitem{background:#E3EFF1;border-radius:10px;padding:13px 16px;margin-bottom:9px;animation:fadeUp .4s ease both}
 .newsitem .nh{font-size:11.5px;font-weight:700;color:#0E4A54;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px}
 .newsitem .nb{font-size:13.5px;line-height:1.6;white-space:pre-line}
 .hidden{display:none}
 /* ---- motion: reveals, pulses, spinners (reduced-motion safe) ---- */
 @keyframes fadeUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
 @keyframes bubIn{from{opacity:0;transform:translateY(8px) scale(.96)}to{opacity:1;transform:none}}
 @keyframes popIn{from{opacity:0;transform:scale(.72)}to{opacity:1;transform:scale(1)}}
 @keyframes pulseDot{0%,100%{box-shadow:0 0 0 0 rgba(76,154,87,.5)}50%{box-shadow:0 0 0 9px rgba(76,154,87,0)}}
 @keyframes ringPulse{0%{box-shadow:0 6px 16px rgba(0,0,0,.28),0 0 0 0 rgba(255,255,255,.55)}100%{box-shadow:0 6px 16px rgba(0,0,0,.28),0 0 0 16px rgba(255,255,255,0)}}
 @keyframes blink{0%,80%,100%{opacity:.25}40%{opacity:1}}
 @keyframes spin{to{transform:rotate(360deg)}}
 .reveal{animation:fadeUp .5s ease both}
 .pill .dot{animation:pulseDot 2.4s ease-out infinite}
 #vlight{transition:background .4s ease}
 #vlight.pop{animation:ringPulse .9s ease-out 1,popIn .35s cubic-bezier(.2,.9,.3,1.25) both}
 .t{animation:popIn .4s ease both}
 .t:nth-child(2){animation-delay:.07s}.t:nth-child(3){animation-delay:.14s}
 .t:nth-child(4){animation-delay:.21s}.t:nth-child(5){animation-delay:.28s}
 .spot{animation:fadeUp .45s ease both}
 .spot:nth-child(2){animation-delay:.08s}.spot:nth-child(3){animation-delay:.16s}.spot:nth-child(4){animation-delay:.24s}
 button.go{transition:transform .12s ease,box-shadow .18s ease,opacity .18s}
 button.go:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 5px 14px rgba(231,111,81,.38)}
 button.go:active:not(:disabled){transform:translateY(0)}
 button.go .spin{display:none;width:14px;height:14px;border:2px solid rgba(255,255,255,.45);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;vertical-align:-2px;margin-right:8px}
 button.go:disabled .spin{display:inline-block}
 /* loading indicator beside the advice button: ocean-wave bars + hint */
 .gorow{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
 .loadhint{display:inline-flex;align-items:center;gap:9px;font-size:13px;font-weight:700;color:#0E4A54;animation:fadeUp .25s ease both}
 .loadhint.hidden{display:none}
 .loadhint .waves{display:inline-flex;align-items:flex-end;gap:3px;height:18px;flex:none}
 .loadhint .waves i{width:4px;height:16px;border-radius:2px;background:#14707C;transform-origin:bottom;animation:wavebars 1.05s ease-in-out infinite}
 .loadhint .waves i:nth-child(2){animation-delay:.14s}
 .loadhint .waves i:nth-child(3){animation-delay:.28s}
 .loadhint .waves i:nth-child(4){animation-delay:.42s}
 @keyframes wavebars{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}
 .why li{animation:fadeUp .4s ease both}
 .why li:nth-child(2){animation-delay:.08s}.why li:nth-child(3){animation-delay:.16s}
 @media (prefers-reduced-motion: reduce){
  *,*:before,*:after{animation:none !important;transition:none !important;scroll-behavior:auto !important}
 }
 /* ---- mobile web app: touch-sized controls, safe areas, full-width actions ---- */
 @media(max-width:600px){
  body{padding:12px 12px calc(16px + env(safe-area-inset-bottom))}
  h1{font-size:27px}
  .hright{width:100%;justify-content:space-between}
  .controls .field{min-width:100%}
  button.go{width:100%}
  #map{height:300px}
  .chatrow{flex-wrap:wrap}
  #chatin{min-width:100%}
  #chatsend{width:100%}
  .bub{max-width:94%}
  .tgrid{grid-template-columns:repeat(auto-fit,minmax(88px,1fr))}
  .main{grid-template-columns:1fr}
  .modalov{padding:0;align-items:flex-end}
  .mpanel{max-height:88vh;border-radius:16px 16px 0 0;padding:16px 14px}
  .modelbtn{max-width:100%}
 }
 footer{color:#9DB8C0;font-size:12px;text-align:center;margin:4px 0 10px;line-height:1.8}
 footer a{color:#9DB8C0}
 .leaflet-container{font-family:'Lora','Nirmala UI','Segoe UI',serif}
</style></head>
<body><div class="wrap">
 <header>
  <div>
   <h1>ParaSail</h1>
   <p class="tag" data-tr>A smart guide for safer fishing &mdash; is it safe, are the fish there, is it allowed?</p>
  </div>
<div class="hright">
     <select id="lang" onchange="applyLanguage()" title="Language">
      <option value="en">English</option>
      <option value="ml">മലയാളം</option>
      <option value="ta">தமிழ்</option>
      <option value="kn">ಕನ್ನಡ</option>
      <option value="te">తెలుగు</option>
      <option value="mr">मराठी</option>
      <option value="gu">ગુજરાતી</option>
      <option value="bn">বাংলা</option>
      <option value="or">ଓଡ଼ିଆ</option>
      <option value="hi">हिन्दी</option>
     </select>
     <button id="installbtn" class="hidden" data-tr onclick="installApp()">Install app</button>
     <button id="adminbtn" class="pill" onclick="openAdminPanel()" style="background:#12455A;border:1px solid #2A5A6E;color:#D9EAED;border-radius:999px;padding:7px 16px;font-size:12.5px;font-weight:600;display:flex;align-items:center;gap:8px" data-tr title="Admin dashboard (requires API key)">Admin <span class="dot" style="background:#C94F4F"></span></button>
     <div class="pill"><span class="dot"></span><span id="pilltext">checking...</span></div>
    </div>
 </header>

 <div class="card controls">
  <div class="field"><label data-tr>Where will you fish?</label><select id="city" onchange="cityChange()">__CITY_OPTIONS__</select></div>
  <div class="field"><label data-tr>What are you catching?</label><select id="species"><option>loading...</option></select></div>
  <div class="field"><label data-tr>Which day?</label><input type="date" id="date"></div>
  <div class="gorow">
   <button class="go" id="go" onclick="getAdvice()"><span class="spin"></span><span id="golabel" data-tr>Get my advice</span></button>
   <span class="loadhint hidden" id="loadhint"><span class="waves"><i></i><i></i><i></i><i></i></span><span data-tr>Reading the sea...</span></span>
  </div>
 </div>

 <div class="main">
  <div class="card mapcard">
   <div class="maptools">
    <button id="mpabtn" data-tr onclick="toggleMPAs()">Protected areas</button>
    <button id="addmark" data-tr onclick="toggleMarkerMode()">Add marker</button>
    <button id="clearmarks" data-tr onclick="clearMarkers()">Remove all markers</button>
   </div>
   <div id="map"></div>
   <div class="coords" id="coords">click anywhere on the sea to set your location</div>
  </div>
  <div>
   <div class="card hidden" id="result">
    <div class="verdict">
     <div class="light" id="vlight">GO</div>
     <div><div class="vword" id="vword">GO</div><div class="vsub" id="vsub"></div></div>
    </div>
    <ul class="why" id="why"></ul>
    <div class="pa hidden" id="pa">
     <div class="paq"><span data-tr>Problem:</span> <span id="pa_problem"></span></div>
     <div class="paa"><span data-tr>Answer:</span> <span id="pa_answer"></span></div>
    </div>
    <div class="aisum hidden" id="aisum">
     <div class="tagline" data-tr>Plain-language explanation</div>
     <div id="aisum_text"></div>
     <div class="src" id="aisum_src"></div>
    </div>
    <div class="note" id="note"></div>
    <details><summary data-tr>Full data (JSON)</summary><pre id="raw"></pre></details>
   </div>
   <div class="card" id="telemcard">
    <div class="sectitle" data-tr>Live telemetry</div>
    <div class="tgroup" data-tr>Weather</div>
    <div class="tgrid">
     <div class="t"><div class="tv" id="t_wind">&ndash;</div><div class="ts" id="t_wind_s"></div><div class="tl" data-tr>wind &amp; gusts</div></div>
     <div class="t"><div class="tv" id="t_press">&ndash;</div><div class="tl" data-tr>pressure</div></div>
     <div class="t"><div class="tv" id="t_air">&ndash;</div><div class="tl" data-tr>air temp</div></div>
     <div class="t"><div class="tv" id="t_hum">&ndash;</div><div class="tl" data-tr>humidity</div></div>
    </div>
    <div class="tgroup" data-tr>Sea</div>
    <div class="tgrid">
     <div class="t"><div class="tv" id="t_sst">&ndash;</div><div class="tl" data-tr>sea temp</div></div>
     <div class="t"><div class="tv" id="t_wave">&ndash;</div><div class="ts" id="t_wave_s"></div><div class="tl" data-tr>waves</div></div>
     <div class="t"><div class="tv" id="t_period">&ndash;</div><div class="ts" id="t_period_s"></div><div class="tl" data-tr>wave period</div></div>
     <div class="t"><div class="tv" id="t_current">&ndash;</div><div class="ts" id="t_current_s"></div><div class="tl" data-tr>current</div></div>
     <div class="t" title="requires an instrumented salinity source (e.g. Copernicus) - not yet wired"><div class="tv">&ndash;</div><div class="tl" data-tr>salinity</div></div>
    </div>
    <div class="tgroup" data-tr>Station</div>
    <div class="tgrid">
     <div class="t wide"><div class="tv" id="t_gps">&ndash;</div><div class="tl" data-tr>gps</div></div>
     <div class="t wide"><div class="tv" id="t_utc">&ndash;</div><div class="tl" data-tr>time (utc)</div></div>
     <div class="t wide"><div class="tv" id="t_power">&ndash;</div><div class="ts" id="t_power_s"></div><div class="tl" data-tr>power</div></div>
    </div>
<details class="srcdetails"><summary data-tr>Where the data comes from</summary><div class="srcinfo" id="srcinfo"></div></details>
    <div class="note" id="t_note">pick a location to see live conditions</div>
   </div>
  </div>
 </div>

<div class="card hidden" id="alertscard">
  <div class="chattop">
   <div class="sectitle" style="margin-bottom:0" data-tr>Security Alerts</div>
   <span id="alertscount" class="note"></span>
  </div>
  <div id="alertslist"></div>
  <div class="note" id="alertsnote" data-tr>Official alerts from IMD, INCOIS, NDMA, CAP India, SAC. Auto-refreshes every 5 minutes.</div>
 </div>

<div class="card spots hidden" id="spots">
  <div class="sectitle" id="spots_title">Likely spots</div>
  <div class="spotrow" id="spotrow"></div>
  <div class="note" id="spots_note"></div>
 </div>

 <div class="card" id="chatcard">
  <div class="chattop">
   <div class="sectitle" style="margin-bottom:0" data-tr>Ask ParaSail</div>
   <button id="modelbtn" class="modelbtn" onclick="openModelPanel()" title="Choose the AI model">
    <span class="mdot" id="modeldot"></span><span id="modelbtnlabel">AI model</span><span class="mchev">&#9662;</span>
   </button>
  </div>
  <div class="chathint" data-tr>Ask anything about safety, fish or the rules - in your own words. Answers come from the same live data and the rule library, and cite their sources. Runs on our own computer, not a paid cloud service.</div>
  <div id="chatlog"></div>
  <div class="chatrow">
   <input id="chatin" placeholder="e.g. Is it safe to take a small boat out tomorrow morning?" onkeydown="if(event.key==='Enter')sendChat()">
   <button id="chatsend" data-tr onclick="sendChat()">Ask</button>
  </div>
 </div>

 <div class="card" id="newscard">
  <div class="sectitle" data-tr>Regional ocean news</div>
  <div id="newsitems"></div>
  <div class="note" id="newsnote" data-tr>News follows your language. Items from other regions are translated for you.</div>
 </div>

 <div id="modelov" class="modalov" onclick="if(event.target===this)closeModelPanel()">
  <div class="mpanel" role="dialog" aria-modal="true" aria-label="Choose the AI model">
   <div class="mphead">
    <div class="sectitle" style="margin-bottom:0" data-tr>AI model</div>
    <button class="mpx" onclick="closeModelPanel()" aria-label="Close">&#215;</button>
   </div>
   <div class="mpsub" data-tr>Everything runs on our own computer - never a paid cloud service. Pick the model that matches the hardware; the status tells you honestly whether it is installed.</div>
   <div id="modellist"></div>
   <div class="mpkey" id="mpkey">
    <div class="kt" data-tr>Admin key required to switch models</div>
    <div class="krow">
     <input id="mpkeyin" type="password" placeholder="X-API-Key" onkeydown="if(event.key==='Enter')document.getElementById('mpkeybtn').click()">
     <button id="mpkeybtn" data-tr>Unlock</button>
    </div>
   </div>
   <div class="mpfoot">
    <span class="mpnote" id="modelnote"></span>
    <button class="mpghost" onclick="refreshModels()" data-tr>Re-check status</button>
   </div>
  </div>
</div>

<div id="adminov" class="modalov" onclick="if(event.target===this)closeAdminPanel()">
 <div class="mpanel" role="dialog" aria-modal="true" aria-label="Admin dashboard">
  <div class="mphead">
   <div class="sectitle" style="margin-bottom:0" data-tr>Admin Dashboard</div>
   <button class="mpx" onclick="closeAdminPanel()" aria-label="Close">&#215;</button>
  </div>
  <div class="mpsub" data-tr>System health, service status, and request statistics. Requires admin API key.</div>
  <div id="admincontent"></div>
  <div class="mpfoot">
   <span class="mpnote" id="adminnote"></span>
   <button class="mpghost" onclick="refreshAdminStats()" data-tr>Refresh</button>
  </div>
 </div>
</div>

 <footer>Anantha Krishnan AS &middot; Naipunnya School of Management, Cherthala, India<br>
 26th Digital Blue Economy Summit &middot; <a href="/docs">API documentation</a> &middot; <a href="/health">service status</a> &middot; map &copy; OpenStreetMap contributors<br>
 Protected-area boundaries: WDPCA (UNEP-WCMC & IUCN) &middot; OpenStreetMap contributors (ODbL)<br>
 Typeface: Lora by Olga Karpushina & Alexei Vanyashi, Cyreal Fonts (SIL Open Font License)</footer>
</div>
<script src="/static/leaflet.js"></script>
<script>
const CITIES=__CITIES_JSON__;
const VERDICTS={
 'PROCEED':              {word:'GO',           color:'#4C9A57',sub:'Good conditions - safe to sail.'},
 'PROCEED WITH CAUTION': {word:'GO CAREFULLY', color:'#D9A62E',sub:'Fishing is possible - but watch the conditions.'},
 'DELAY OR RELOCATE':    {word:'WAIT OR MOVE', color:'#D97E35',sub:'Better to wait, or try another spot.'},
 'DO NOT FISH':          {word:'STOP',         color:'#C94F4F',sub:'Not safe, or not allowed today.'}
};
const state={lat:9.93,lon:76.26};
let LANG='en';

/* map init is guarded: if Leaflet or tiles fail, the advice, species and
   chat must keep working - the map is an input convenience, not a dependency */
var map=null,locM=null,spotLayer=null,spotMarkers=[];
var userLayer=null,userMarks=[],markMode=false,stationMk=null;
try{
 map=L.map('map').setView([14.2,78.5],5);
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
 locM=L.circleMarker([9.93,76.26],{radius:9,color:'#fff',weight:2,fillColor:'#E76F51',fillOpacity:.95}).addTo(map);
 spotLayer=L.layerGroup().addTo(map);
 userLayer=L.layerGroup().addTo(map);
 map.on('click',function(e){
  if(markMode){addUserMarker(e.latlng.lat,e.latlng.lng);return;}
  setLoc(e.latlng.lat,e.latlng.lng,null);refreshTelemetry();
 });
}catch(e){
 document.getElementById('coords').textContent='map unavailable - choose a city above; everything else works';
}

/* ---- map card height follows the live-telemetry card ----
   The two cards then end on the same line (clean two-column look), and the
   map keeps that height when the advice result card is revealed: only the
   right column grows. Below 900px the grid stacks, so the sync is disabled
   and the map falls back to its CSS height. */
var _mapSyncT=null;
function syncMapHeight(){
 if(_mapSyncT){clearTimeout(_mapSyncT);}
 _mapSyncT=setTimeout(function(){
  var mc=document.querySelector('.mapcard'),tc=document.getElementById('telemcard');
  if(!mc||!tc)return;
  if(window.innerWidth<=900){mc.style.height='';if(map)map.invalidateSize();return;}
  var h=tc.getBoundingClientRect().height;
  if(h<200)return;                       /* telemetry not laid out yet */
  mc.style.height=Math.round(h)+'px';
  if(map)map.invalidateSize();
 },60);
}
window.addEventListener('resize',syncMapHeight);

/* ---- user markers: save places on the map (persisted per browser) ---- */
function toggleMarkerMode(){
 markMode=!markMode;
 document.getElementById('addmark').classList.toggle('on',markMode);
 document.getElementById('coords').textContent=markMode
  ?'marker mode: click the map to save a place'
  :'click anywhere on the sea to set your location';
}
function saveMarks(){
 try{localStorage.setItem('parasail_marks',JSON.stringify(userMarks));}catch(e){}
}
function loadMarkers(){
 try{
  (JSON.parse(localStorage.getItem('parasail_marks')||'[]')||[])
   .forEach(function(m){addUserMarker(m.lat,m.lon,m.label,true);});
 }catch(e){}
}
function addUserMarker(lat,lon,label,silent){
 if(!userLayer)return;
 if(!silent){
  label=prompt('Name this place:','My spot '+(userMarks.length+1));
  if(!label)return;
 }
 var i=userMarks.length;
 userMarks.push({lat:lat,lon:lon,label:label});
 var mk=L.circleMarker([lat,lon],{radius:7,color:'#fff',weight:2,fillColor:'#7AADA0',fillOpacity:.95}).addTo(userLayer)
  .bindPopup('<b>'+label+'</b><br>'+lat.toFixed(3)+', '+lon.toFixed(3)
   +'<br><a href="#" onclick="useMarker('+i+');return false;">use as my location</a>'
   +' &middot; <a href="#" onclick="removeMarker('+i+');return false;">remove</a>');
 if(!silent){mk.openPopup();saveMarks();}
}
function useMarker(i){
 var m=userMarks[i];if(!m)return;
 setLoc(m.lat,m.lon,m.label);
 refreshTelemetry();loadNews();
}
function removeMarker(i){
 userMarks.splice(i,1);
 if(userLayer)userLayer.clearLayers();
 var keep=userMarks.slice();userMarks=[];
 keep.forEach(function(m){addUserMarker(m.lat,m.lon,m.label,true);});
 saveMarks();
}
function clearMarkers(){
 userMarks=[];
 if(userLayer)userLayer.clearLayers();
 saveMarks();
}
/* the configured station: shows WHERE the dashboard data comes from */
function ensureStationMarker(st){
 if(!map||!st||!st.position||stationMk)return;
 stationMk=L.circleMarker([st.position.lat,st.position.lon],
  {radius:8,color:'#fff',weight:2,fillColor:'#C8B87C',fillOpacity:.95}).addTo(map)
  .bindPopup('<b>'+(st.provider||'data station')+'</b><br>data source for this dashboard<br>'
   +st.position.lat.toFixed(3)+', '+st.position.lon.toFixed(3));
}
function showStation(){
 if(!map||!stationMk)return;
 map.flyTo([stationMk.getLatLng().lat,stationMk.getLatLng().lng],10);
 stationMk.openPopup();
}

/* ---- protected areas: the boundaries the DO-NOT-FISH guard enforces ---- */
var mpaLayer=null,mpaOn=false,mpaLoaded=false;
function toggleMPAs(){
 if(!map)return;
 mpaOn=!mpaOn;
 document.getElementById('mpabtn').classList.toggle('on',mpaOn);
 if(mpaOn){
  if(!mpaLoaded){loadMPAs();return;}
  if(mpaLayer)mpaLayer.addTo(map);
 }else if(mpaLayer){map.removeLayer(mpaLayer);}
}
function loadMPAs(){
 fetch('/mpas').then(function(r){return r.json();}).then(function(d){
  mpaLoaded=true;
  if(!d.available||!d.features||!d.features.length){
   mpaOn=false;
   document.getElementById('mpabtn').classList.remove('on');
   document.getElementById('coords').textContent='protected-area registry unavailable right now';
   return;
  }
  mpaLayer=L.geoJSON(d,{
   style:{color:'#C94F4F',weight:2,fillColor:'#C94F4F',fillOpacity:.12,dashArray:'5 4'},
   onEachFeature:function(f,lyr){
    var p=f.properties||{},lines=['<b>'+p.name+'</b>'];
    if(p.desig)lines.push(p.desig);
    if(p.authority)lines.push(p.authority);
    lines.push('fishing is not allowed inside this boundary');
    lyr.bindPopup(lines.join('<br>'));
    if(p.name)lyr.bindTooltip(p.name,{sticky:true});
   }
  });
  if(mpaOn)mpaLayer.addTo(map);
 }).catch(function(){
  mpaLoaded=false;mpaOn=false;
  document.getElementById('mpabtn').classList.remove('on');
  document.getElementById('coords').textContent='protected-area layer failed to load';
 });
}

function setLoc(lat,lon,label){
 state.lat=+lat.toFixed(4);state.lon=+lon.toFixed(4);
 if(locM)locM.setLatLng([state.lat,state.lon]);
 document.getElementById('coords').textContent=state.lat.toFixed(3)+'\u00B0N, '+state.lon.toFixed(3)+'\u00B0E - '+(label||'custom (picked on map)');
 if(!label)document.getElementById('city').value='custom';
 refreshTelemetry();
 loadNews();
 loadAlerts();
}
function cityChange(){
 const c=CITIES[document.getElementById('city').value];
 if(!c)return;
 setLoc(c.lat,c.lon,c.name+' ('+c.state+')');
 if(map)map.panTo([c.lat,c.lon]);
 refreshTelemetry();
 loadNews();
 loadAlerts();
}

/* ---- translation: every visible string flows through the in-site translator ---- */
function markTr(el,text){el.setAttribute('data-tr','1');el.dataset.orig=text;el.textContent=text;}
async function applyLanguage(restore){
 if(restore!==false)restore=true;
 LANG=document.getElementById('lang').value;
 try{localStorage.setItem('parasail_lang',LANG);}catch(e){}
 const els=[...document.querySelectorAll('[data-tr]')];
 if(restore)els.forEach(function(el){if(el.dataset.orig)el.textContent=el.dataset.orig;});
 if(LANG==='en')return;
 const pairs=els.filter(function(el){return el.dataset.orig;}).map(function(el){return {el:el,t:el.dataset.orig};});
 if(!pairs.length)return;
 try{
  const r=await fetch('/translate',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({texts:pairs.map(function(p){return p.t;}),target:LANG})});
  const d=await r.json();
  if(d.translations)pairs.forEach(function(p,i){if(d.translations[i])p.el.textContent=d.translations[i];});
 }catch(e){/* stay in English */}
 buildSpeciesSelect();   /* vernacular species names follow the language */
 loadNews();   /* the briefing is server-localized per language */
 syncMapHeight();   /* translated labels can change the telemetry card height */
}
async function setText(el,en){
 markTr(el,en);
 if(LANG==='en')return;
 try{
  const r=await fetch('/translate',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({texts:[en],target:LANG})});
  const d=await r.json();
  if(d.translations&&d.translations[0])el.textContent=d.translations[0];
 }catch(e){}
}

/* ---- species names in the local language: curated vernacular names from
   the registry (config.yaml local_names); English fallback; never machine-
   translated (transliterations would be wrong) ---- */
var SPECIES=[];
function speciesLabel(s){
 var local=(s.local_names||{})[LANG];
 return (local?local:s.common_name)+' \u00B7 '+s.scientific_name;
}
function localNameFor(sci){
 for(var i=0;i<SPECIES.length;i++){
  if(SPECIES[i].scientific_name===sci){
   return (SPECIES[i].local_names||{})[LANG]||SPECIES[i].common_name;
  }
 }
 return null;
}
function buildSpeciesSelect(){
 var sel=document.getElementById('species');
 var cur=sel.value;
 sel.innerHTML='';
 SPECIES.forEach(function(s){
  var o=document.createElement('option');
  o.value=s.scientific_name;
  o.textContent=speciesLabel(s);   /* already localized - no markTr */
  sel.appendChild(o);
 });
 /* clearing innerHTML leaves selectedIndex at -1, so the select would hand
    an EMPTY species to the advisory (-> "not in registry" STOP). Restore the
    previous choice, else select the first species explicitly. */
 var keep=SPECIES.some(function(s){return s.scientific_name===cur;});
 if(keep){sel.value=cur;}
 else if(SPECIES.length){sel.selectedIndex=0;}
}
function loadSpecies(){
 fetch('/species').then(function(r){return r.json();}).then(function(list){
  SPECIES=list||[];
  buildSpeciesSelect();
 }).catch(function(){document.getElementById('species').innerHTML='<option>unavailable</option>';});
}

window.onload=function(){
 document.querySelectorAll('[data-tr]').forEach(function(el){if(!el.dataset.orig)el.dataset.orig=el.textContent;});
 document.getElementById('date').value=new Date(Date.now()+24*3600*1000).toISOString().slice(0,10);
 fetch('/health').then(function(r){return r.json();}).then(function(h){
  document.getElementById('pilltext').textContent='live \u00B7 '+h.species_count+' species';
 }).catch(function(){document.getElementById('pilltext').textContent='offline';});
 loadSpecies();
 if(map)map.whenReady(function(){setTimeout(function(){map.invalidateSize();},150);});
 loadMarkers();
 loadModels();
 refreshTelemetry();
 syncMapHeight();
 loadNews();
 loadAlerts();
 // Auto-refresh alerts every 5 minutes
 setInterval(loadAlerts, 5*60*1000);
 try{const saved=localStorage.getItem('parasail_lang');
  if(saved&&saved!=='en'){document.getElementById('lang').value=saved;applyLanguage();}}catch(e){}
};

/* ---- telemetry: full station parameter set, compass + animated arrows ---- */
function degToCompass(d){
 if(d==null)return '';
 const dirs=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
 return dirs[Math.round(((d%360)+360)%360/22.5)%16];
}
function arrow(deg,flow){          /* flow=true: rotate to where it moves */
 if(deg==null)return '';
 const a=((deg+(flow?180:0))%360+360)%360;
 return ' <span class="dirarrow" style="transform:rotate('+a+'deg)">\u2191</span>';
}
function setV(id,txt){const el=document.getElementById(id);if(el)el.textContent=txt;}
function setS(id,html){const el=document.getElementById(id);if(el)el.innerHTML=html||'';}
async function refreshTelemetry(){
 ['t_wind','t_press','t_air','t_hum','t_sst','t_wave','t_period','t_current','t_gps','t_utc','t_power'].forEach(setDash);
 function setDash(id){setV(id,'\u2013');}
 setS('t_wind_s','');setS('t_wave_s','');setS('t_period_s','');setS('t_current_s','');setS('t_power_s','');
 setV('t_note','contacting...');
 try{
  const r=await fetch('/telemetry?lat='+state.lat+'&lon='+state.lon);
  const d=await r.json();
  /* weather */
  setV('t_wind',d.wind_speed_ms!=null?(d.wind_speed_ms*3.6).toFixed(0)+' km/h':'\u2013');
  setS('t_wind_s',(d.wind_gusts_ms!=null?'gusts '+(d.wind_gusts_ms*3.6).toFixed(0)+' km/h':'')
   +(d.wind_direction_deg!=null?' \u00B7 from '+degToCompass(d.wind_direction_deg)+arrow(d.wind_direction_deg,true):''));
  setV('t_press',d.surface_pressure_hpa!=null?d.surface_pressure_hpa.toFixed(0)+' hPa':'\u2013');
  setV('t_air',d.air_temperature_c!=null?d.air_temperature_c.toFixed(1)+'\u00B0C':'\u2013');
  setV('t_hum',d.relative_humidity_pct!=null?d.relative_humidity_pct.toFixed(0)+' %':'\u2013');
  /* sea */
  setV('t_sst',d.sea_surface_temperature_c!=null?d.sea_surface_temperature_c.toFixed(1)+'\u00B0C':'\u2013');
  setV('t_wave',d.wave_height_m!=null?d.wave_height_m.toFixed(1)+' m':'\u2013');
  setS('t_wave_s',d.wave_direction_deg!=null?'from '+degToCompass(d.wave_direction_deg)+arrow(d.wave_direction_deg,true):'');
  setV('t_period',d.wave_period_s!=null?d.wave_period_s.toFixed(1)+' s':'\u2013');
  setS('t_period_s',d.wave_direction_deg!=null?'from '+degToCompass(d.wave_direction_deg)+arrow(d.wave_direction_deg,true):'');
  setV('t_current',d.ocean_current_velocity_kmh!=null?d.ocean_current_velocity_kmh.toFixed(1)+' km/h':'\u2013');
  setS('t_current_s',d.ocean_current_direction_deg!=null?'toward '+degToCompass(d.ocean_current_direction_deg)+arrow(d.ocean_current_direction_deg,false):'');
  /* station */
  setV('t_gps',state.lat.toFixed(3)+'\u00B0, '+state.lon.toFixed(3)+'\u00B0');
  setV('t_utc',d.observed_at?d.observed_at.slice(11,19):new Date().toISOString().slice(11,19));
  const st=d.station||{};
  if(st.battery_voltage_v!=null){
   setV('t_power',st.battery_voltage_v.toFixed(1)+' V');
   setS('t_power_s',(st.solar_output_w!=null?'solar '+st.solar_output_w.toFixed(0)+' W':'')+(st.power_source?' \u00B7 '+st.power_source:''));
  }else{
   setV('t_power',st.power_source==='external'?'shore':'\u2013');
   setS('t_power_s',st.power_source==='external'?'external power':'');
  }
  /* provenance: where the data comes from + the station on the map */
  if(d.sources){
   ensureStationMarker(d.sources.station);
   var s=d.sources,sh='';
   if(s.weather&&s.weather.served&&s.weather.served.length)
    sh+='<div><b>'+s.weather.provider+'</b> \u00B7 weather ('+s.weather.served.length+' fields)</div>';
   if(s.sea&&s.sea.served&&s.sea.served.length)
    sh+='<div><b>'+s.sea.provider+'</b> \u00B7 sea state ('+s.sea.served.length+' fields)</div>';
   if(s.station){
    sh+='<div><b>'+s.station.provider+'</b> \u00B7 station health'
     +(s.station.position?' \u00B7 <a href="#" onclick="showStation();return false;">show on map</a>':'')+'</div>';
   }
   if(s.salinity&&!s.salinity.provider)
    sh+='<div>salinity: '+s.salinity.note+'</div>';
   document.getElementById('srcinfo').innerHTML=sh;
  }
  setV('t_note','live readings at your point ('+new Date().toLocaleTimeString()+')');
 }catch(e){
  setV('t_note','telemetry unavailable - check the connection');
 }
 syncMapHeight();
}

/* ---- security alerts: IMD cyclones, INCOIS tsunami, NDMA, CAP, SAC ---- */
async function loadAlerts(){
 const card=document.getElementById('alertscard');
 const list=document.getElementById('alertslist');
 const count=document.getElementById('alertscount');
 try{
  const r=await fetch('/alerts?lat='+state.lat+'&lon='+state.lon);
  const d=await r.json();
  if(d.count>0){
   card.classList.remove('hidden');
   count.textContent=d.count+' alert'+(d.count>1?'s':'')+' \u00B7 updated '+new Date(d.retrieved_at).toLocaleTimeString();
   list.innerHTML='';
   d.alerts.forEach(function(a){
    const sevColors={'extreme':'#C94F4F','severe':'#D97E35','moderate':'#D9A62E','minor':'#14707C','info':'#4A6B75'};
    const sevColor=sevColors[a.severity]||'#6B8290';
    const div=document.createElement('div');
    div.className='newsitem';
    div.style.borderLeftColor=sevColor;
    const issued=new Date(a.issued_at);
    const expires=a.expires_at?new Date(a.expires_at):null;
    const now=new Date();
    let timeLeft='';
    if(expires && expires > now){
     const diff=expires - now;
     const hrs=Math.floor(diff/3600000);
     const mins=Math.floor((diff%3600000)/60000);
     timeLeft=' <span style="color:'+sevColor+'">expires in '+(hrs>0?hrs+'h ':'')+mins+'m</span>';
    }
    var h=document.createElement('div');
    h.className='nh';
    var tag=document.createElement('span');
    tag.className='ntag';
    tag.style.background=sevColor;
    tag.textContent=a.severity.toUpperCase()+' \u00B7 '+a.event_type.toUpperCase();
    h.appendChild(tag);
    h.appendChild(document.createTextNode(' '+a.title+timeLeft));
    var b=document.createElement('div');
    b.className='nb';
    b.textContent=a.description;
    var areas=a.areas&&a.areas.length?('Areas: '+a.areas.join(', ')):'';
    var s=document.createElement('div');
    s.className='nsrc';
    s.textContent=areas+' | '+a.source+(a.source_url?' \u00B7 <a href="'+a.source_url+'" target="_blank">source</a>':'')+(a.languages&&a.languages.hi?' | \u0939\u093f\u0928\u094d\u0926\u0940: '+a.languages.hi:'');
    div.appendChild(h);div.appendChild(b);div.appendChild(s);
    list.appendChild(div);
   });
  }else{
   card.classList.add('hidden');
  }
 }catch(e){
  card.classList.add('hidden');
 }
}

async function getAdvice(){
 const btn=document.getElementById('go');
 const label=document.getElementById('golabel');
 const hint=document.getElementById('loadhint');
 /* the label is a nested span: setText targets IT, never the button, so
    the in-button spinner survives the text update */
 setText(label,'Checking the sea...');btn.disabled=true;
 hint.classList.remove('hidden');
 /* telemetry FIRST: the live-conditions card updates before the verdict
    and the AI summary appear, and the assistant is fed the same station
    data server-side (advisory.telemetry) - what you see is what it
    analysed */
 try{await refreshTelemetry();}catch(e){}
 const start=document.getElementById('date').value+'T05:00:00Z';
 const species=document.getElementById('species').value;
 const body={lat:state.lat,lon:state.lon,species:species,start:start,hours:24,language:LANG};
 const results=await Promise.allSettled([
  fetch('/advisory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json().then(function(d){return {status:r.status,data:d};});}),
  fetch('/fish-suggestions?species='+encodeURIComponent(species)+'&lat='+state.lat+'&lon='+state.lon).then(function(r){return r.json();}),
  fetch('/assistant/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json();})
 ]);
 try{
  const a=results[0];
  if(a.status==='fulfilled'&&a.value.status===200){renderVerdict(a.value.data);}
  else if(a.status==='fulfilled'){showError(typeof a.value.data.detail==='string'?a.value.data.detail:'request rejected');}
  else{showError('advisory request failed');}
 }catch(e){showError('could not reach the service: '+e);}
 renderSpots(results[1].status==='fulfilled'?results[1].value:null);
 renderAiSummary(results[2].status==='fulfilled'?results[2].value:null);
 /* restore the label BEFORE the language pass so re-translation picks up
    "Get my advice", not a stale "Checking the sea..." */
 btn.disabled=false;setText(label,'Get my advice');
 hint.classList.add('hidden');
 if(LANG!=='en')applyLanguage(false);
}

function renderAiSummary(d){
 const box=document.getElementById('aisum');
 if(!d||!d.summary){box.classList.add('hidden');return;}
 box.classList.remove('hidden');
 const s=d.summary;
 const host=document.getElementById('aisum_text');host.innerHTML='';
 /* structured: one point per line (server sends points; older responses
    fall back to splitting a newline-separated summary; a single paragraph
    renders as-is) */
 let pts=(Array.isArray(s.points)&&s.points.length)?s.points.slice(0,6):null;
 if(!pts&&s.summary.indexOf('\\n')>=0)pts=s.summary.split(/\\n+/);
 if(pts&&pts.length>1){
  const list=document.createElement('div');list.className='pts';
  pts.forEach(function(p){p=(p||'').trim();if(!p)return;
   const li=document.createElement('div');li.textContent=p;list.appendChild(li);});
  if(list.childNodes.length>1)host.appendChild(list);
  else host.textContent=s.summary;
 }else{host.textContent=s.summary;}
 localize(document.getElementById('aisum_src'),
  s.backend==='template'
   ?'plain-language advisory from the rules engine'
   :('AI summary \u00B7 '+(s.model||'').split('/').pop()+(s.cached?' \u00B7 cached':'')+' \u00B7 runs locally, no cloud API'));
}

/* ---- grounded AI chat: same live data + rule library, cited answers ---- */
async function sendChat(){
 const inp=document.getElementById('chatin'),btn=document.getElementById('chatsend');
 const q=inp.value.trim();
 if(!q)return;
 inp.value='';btn.disabled=true;
 addBubble('user',q);
 const wait=addBubble('ai wait','');
 wait.appendChild(document.createTextNode('checking the sea and the rule library'));
 const dots=document.createElement('span');dots.className='dots';
 dots.innerHTML='<i></i><i></i><i></i>';
 wait.appendChild(dots);
 const payload={question:q,language:LANG,lat:state.lat,lon:state.lon,
  species:document.getElementById('species').value,
  start:document.getElementById('date').value+'T05:00:00Z',hours:24};
 try{
  const r=await fetch('/assistant/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await r.json();
  wait.classList.remove('wait');
  const cite=[];
  if(d.grounded_passages&&d.grounded_passages.length){
   cite.push('sources: '+d.grounded_passages.slice(0,3).map(function(p){return p.source||'library';}).join(', '));
  }
  if(d.backend) cite.push('answer by '+(d.backend==='template'?'built-in mode':'local AI'));
  wait.textContent=d.answer+(cite.length?'\\n':'')+(cite.length?cite.join(' \u00B7 '):'');
 }catch(e){
  wait.classList.remove('wait');
  wait.textContent='Sorry - the answer service is not reachable right now. Please try again.';
 }
 document.getElementById('chatlog').scrollTop=9e9;
 btn.disabled=false;
}
/* ---- model switcher: chip button + polished picker panel. Availability
   is HONEST: a model that is not downloaded shows a red status chip, the
   exact install command, and refuses to pretend (switch is blocked unless
   you explicitly choose "Switch anyway") ---- */
let MODELS=[];
function activeModel(){
 let m=null;(MODELS||[]).forEach(function(x){if(x.active)m=x;});
 return m;
}
function renderModelBtn(){
	 const m=activeModel();const dot=document.getElementById('modeldot');
	 const lbl=document.getElementById('modelbtnlabel');const btn=document.getElementById('modelbtn');
	 if(!m){lbl.textContent='AI: built-in';dot.className='mdot';btn.title='The assistant runs in built-in mode';return;}
	 const displayName=m.label||m.key;
	 lbl.textContent='AI: '+displayName;
	 dot.className='mdot '+(m.available?'ok':'bad');
	 btn.title=m.available?('AI model: '+displayName+' - ready')
	  :('AI model: '+displayName+' - NOT installed; answers fall back to built-in mode');
	}
async function loadModels(refresh){
 try{
  const r=await fetch('/assistant/models'+(refresh?'?refresh=true':''));
  const d=await r.json();MODELS=d.models||[];
  renderModelBtn();
  if(document.getElementById('modelov').classList.contains('open'))renderModelList();
 }catch(e){
  MODELS=[];renderModelBtn();
 }
}
function refreshModels(){modelNote('re-checking status...');loadModels(true);}
function openModelPanel(){
 document.getElementById('modelov').classList.add('open');
 renderModelList();loadModels(true);
}
function closeModelPanel(){
 document.getElementById('modelov').classList.remove('open');
 hideKeyRow();modelNote('');
}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModelPanel();});
function modelNote(t){document.getElementById('modelnote').textContent=t||'';}
function mtag(t){const s=document.createElement('span');s.className='mtag';s.textContent=t;return s;}
function renderModelList(){
 const box=document.getElementById('modellist');box.innerHTML='';
 if(!(MODELS||[]).length){
  const d=document.createElement('div');d.className='mpsub';
  d.textContent='No model registry is configured - the assistant runs in built-in (template) mode.';
  box.appendChild(d);return;
 }
 MODELS.forEach(function(m,i){
  const c=document.createElement('div');
  c.className='mcard'+(m.active?' active':'');
  c.style.animationDelay=(i*0.06)+'s';c.id='mcard-'+m.key;
  const top=document.createElement('div');top.className='mtop';
  /* product name in front, machine key underneath: operators need the
     identifier, everyone else reads the name */
  const names=document.createElement('div');
  const nm=document.createElement('div');nm.className='mname';
  nm.textContent=(m.label||m.key);
  names.appendChild(nm);
  if(m.label){const sub=document.createElement('div');sub.className='mkey';
   sub.textContent=m.key;names.appendChild(sub);}
  top.appendChild(names);
  const chip=document.createElement('span');
  if(m.active&&m.available){chip.className='mchip live';chip.textContent='ACTIVE';}
  else if(m.active){chip.className='mchip down';chip.textContent='ACTIVE \u00B7 NOT INSTALLED';}
  else if(m.available){chip.className='mchip live';chip.textContent='READY';}
  else{chip.className='mchip down';chip.textContent='NOT DOWNLOADED';}
  top.appendChild(chip);c.appendChild(top);
  const de=document.createElement('div');de.className='mdesc';
  de.textContent=m.description||'';c.appendChild(de);
  const meta=document.createElement('div');meta.className='mmeta';
  if(m.vram_gb)meta.appendChild(mtag(m.vram_gb+' GB VRAM'));
  if(m.download_gb)meta.appendChild(mtag(m.download_gb+' GB download'));
  if(m.backend)meta.appendChild(mtag(m.backend));
  c.appendChild(meta);
  if(!m.available){
   const ins=document.createElement('div');ins.className='minstall';
   const t=document.createElement('div');t.className='mt2';
   t.textContent='Not on this machine yet. Install it with:';
   const cmd=document.createElement('code');cmd.className='cmd';
   cmd.textContent=m.install_command||'see docs/AI_SETUP.md';
   const still=document.createElement('button');still.className='still';
   still.textContent='Switch anyway';
   still.onclick=function(ev){ev.stopPropagation();switchModel(m.key,true);};
   ins.appendChild(t);ins.appendChild(cmd);ins.appendChild(still);
   c.appendChild(ins);
   c.onclick=function(){c.classList.toggle('showinstall');};
  }else if(!m.active){
   c.onclick=function(){modelNote('');switchModel(m.key,false);};
  }
  box.appendChild(c);
 });
}
async function switchModel(key,force,withKey){
 const headers={'Content-Type':'application/json'};
 const k=withKey||apiKey();if(k)headers['X-API-Key']=k;
 modelNote('switching...');
 let r;
 try{
  r=await fetch('/assistant/model',{method:'POST',headers:headers,body:JSON.stringify({model:key,force:!!force})});
 }catch(e){modelNote('network error - could not reach the server');return;}
 if(r.status===401||r.status===403){showKeyRow(key,force);return;}
 let d={};try{d=await r.json();}catch(e){}
 if(r.ok){
  document.getElementById('modelov').classList.remove('open');
  hideKeyRow();
  if(d.available===false){
   addBubble('ai','Switched to '+key+', but it is NOT installed yet. Answers will come from built-in mode until you run: '+(d.install_command||'see docs/AI_SETUP.md'));
  }else{
   addBubble('ai','AI model switched to '+key+'. The next answers use it.');
  }
  document.getElementById('chatlog').scrollTop=9e9;
  loadModels(false);
 }else if(r.status===409){
  modelNote('That model is not installed yet - see the install steps on its card.');
  const card=document.getElementById('mcard-'+key);
  if(card){card.classList.add('showinstall');
   if(card.scrollIntoView)card.scrollIntoView({block:'nearest'});}
 }else{
  modelNote('Could not switch ('+r.status+'). The current model keeps serving.');
 }
}
function showKeyRow(key,force){
 const row=document.getElementById('mpkey');row.classList.add('open');
 const inp=document.getElementById('mpkeyin');inp.value='';inp.focus();
 document.getElementById('mpkeybtn').onclick=function(){
  const k=inp.value.trim();if(!k)return;
  localStorage.setItem('parasail_api_key',k);
  row.classList.remove('open');
  switchModel(key,force,k);
 };
}
function hideKeyRow(){const row=document.getElementById('mpkey');if(row)row.classList.remove('open');}
function apiKey(){
 try{return localStorage.getItem('parasail_api_key')||'';}catch(e){return '';}
}

/* ---- regional ocean news: follows the selected language; items from
   other regions arrive translated (server-side) and are flagged ---- */
async function loadNews(){
 try{
  const r=await fetch('/news',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({language:LANG})});
  const d=await r.json();
  var el=document.getElementById('newsitems');el.innerHTML='';
  (d.items||[]).forEach(function(it){
   var div=document.createElement('div');div.className='newsitem';
   var h=document.createElement('div');h.className='nh';
   var tag=document.createElement('span');tag.className='ntag';tag.textContent=it.region||'';
   h.appendChild(tag);
   h.appendChild(document.createTextNode(it.title||''));
   var b=document.createElement('div');b.className='nb';b.textContent=it.summary||'';
   var s=document.createElement('div');s.className='nsrc';
   s.textContent=(it.translated?'translated from '+(it.origin_language||'')+' \u00B7 ':'')
    +(it.source||'');
   div.appendChild(h);div.appendChild(b);div.appendChild(s);
   el.appendChild(div);
  });
 }catch(e){document.getElementById('newsitems').innerHTML='';}
}

/* ---- dynamic-content localization: important data must follow the
   selected language, not just the static interface labels ---- */
async function localize(el,en){
 if(!el)return;
 el.removeAttribute('data-tr');
 el.dataset.orig=en;
 el.textContent=en;
 if(LANG==='en')return;
 try{
  const r=await fetch('/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texts:[en],target:LANG})});
  const d=await r.json();
  if(d.translations&&d.translations[0])el.textContent=d.translations[0];
 }catch(e){/* keep English */}
}

/* ---- PWA: install prompt + offline app shell (secure contexts only) ---- */
var deferredPrompt=null;
window.addEventListener('beforeinstallprompt',function(e){
 e.preventDefault();deferredPrompt=e;
 var b=document.getElementById('installbtn');if(b)b.classList.remove('hidden');
});
function installApp(){
 if(!deferredPrompt)return;
 deferredPrompt.prompt();
 deferredPrompt.userChoice.then(function(){
  deferredPrompt=null;
  var b=document.getElementById('installbtn');if(b)b.classList.add('hidden');
 });
}
if('serviceWorker' in navigator&&(location.protocol==='https:'||['localhost','127.0.0.1'].indexOf(location.hostname)>=0)){
 window.addEventListener('load',function(){
  navigator.serviceWorker.register('/sw.js').catch(function(){});
 });
}

function addBubble(cls,text){
 const log=document.getElementById('chatlog');
 const el=document.createElement('div');el.className='bub '+cls;el.textContent=text;
 log.appendChild(el);log.scrollTop=9e9;
 return el;
}

function reveal(el){
 el.classList.remove('hidden','reveal');
 void el.offsetWidth;              /* restart the fadeUp animation */
 el.classList.add('reveal');
}

function renderVerdict(d){
 reveal(document.getElementById('result'));
 const m=VERDICTS[d.class]||VERDICTS['DO NOT FISH'];
 const L=document.getElementById('vlight');
 L.style.background=m.color;
 L.style.fontSize=(m.word.length>9?'12px':(m.word.length>5?'14px':'21px'));
 L.classList.remove('pop');void L.offsetWidth;L.classList.add('pop');
 markTr(L,m.word);
 markTr(document.getElementById('vword'),m.word);
 document.getElementById('vword').style.color=m.color;
 markTr(document.getElementById('vsub'),d.allowed?m.sub:(d.block_reason||m.sub));
 const why=document.getElementById('why');why.innerHTML='';
 if(!d.allowed){
  addWhy('w-bad',d.block_reason||'Not allowed today.');
  addWhy('w-ok','The sea gets a break - and you avoid a fine.');
 }else{
  const o=d.observed||{},c=d.components||{};
  const det=[];
  if(o.wind_speed_ms!=null)det.push('wind '+(o.wind_speed_ms*3.6).toFixed(0)+' km/h');
  if(o.wave_height_m!=null)det.push('waves '+o.wave_height_m.toFixed(1)+' m');
  addWhy(c.W>=0.66?'w-ok':(c.W>=0.33?'w-mid':'w-bad'),
   'Weather - '+(c.W>=0.66?'calm seas':(c.W>=0.33?'changing conditions':'rough seas'))
   +(det.length?' ('+det.join(', ')+')':'')+', safety '+(c.W*100).toFixed(0)+'/100');
  addWhy(c.C>=0.6?'w-ok':(c.C>=0.35?'w-mid':'w-bad'),
   'Fish - '+(c.C>=0.6?'likely in this area':(c.C>=0.35?'possibly in this area':'unlikely in this area'))
   +', likelihood '+(c.C*100).toFixed(0)+'/100');
  addWhy(c.B<0.35?'w-ok':(c.B<0.6?'w-mid':'w-bad'),
   'Young fish and habitats - '+(c.B<0.35?'low risk':(c.B<0.6?'some risk':'high risk'))+' of harm');
 }
 const q=d.data_quality||{};
 markTr(document.getElementById('note'),q.degraded
  ?('Note: some data is '+q.max_age_hours+' hours old (served from cache).')
  :('Live data - '+(q.max_age_hours!=null?q.max_age_hours:0)+' hours old.'));
 /* Problem / Answer: plain-language explanation for blocked advisories,
    already localized server-side into the selected language */
 var pabox=document.getElementById('pa');
 if(d.problem_answer&&d.problem_answer.problem){
  pabox.classList.remove('hidden');
  document.getElementById('pa_problem').textContent=d.problem_answer.problem;
  document.getElementById('pa_answer').textContent=d.problem_answer.answer;
 }else{pabox.classList.add('hidden');}
 document.getElementById('raw').textContent=JSON.stringify(d,null,2);
}

function renderSpots(s){
 const card=document.getElementById('spots');
 if(!s||!s.suggestions||!s.suggestions.length){
  card.classList.add('hidden');
  if(spotLayer){spotLayer.clearLayers();spotMarkers=[];}
  return;
 }
 reveal(card);
 if(spotLayer){spotLayer.clearLayers();spotMarkers=[];}
 markTr(document.getElementById('spots_title'),
  'Likely spots - '+(localNameFor(document.getElementById('species').value)||s.common_name));
 markTr(document.getElementById('spots_note'),s.note);
 const row=document.getElementById('spotrow');row.innerHTML='';
 /* Likely-fish PERIMETER: drawn like the MPA zones (border + translucent
    fill + dashed outline), teal instead of coral. Replaces the old dots. */
 if(spotLayer&&typeof L!=='undefined'&&s.zone){
  L.geoJSON(s.zone,{style:{color:'#2F9E8F',weight:2,fillColor:'#2F9E8F',fillOpacity:.18,dashArray:'5 4'},
   onEachFeature:function(f,lyr){
    /* the popup names the scorer that produced the zone: a trained model
       reports its threshold and training-record count, the untrained
       envelope says so plainly (the API decides, not this code) */
    const trained=(s.training_records!=null);
    const basisString=trained
      ?('trained habitat model \u00B7 '+(s.zone_threshold*100).toFixed(0)+'% threshold \u00B7 '+s.training_records+' presences')
      :('live sea-temperature match \u2265 '+(s.zone_threshold!=null?(s.zone_threshold*100).toFixed(0):50)+'%');
    lyr.bindPopup('<b>Likely area</b> - '+(localNameFor(document.getElementById('species').value)||s.common_name)
     +'<br>'+basisString
     +'<br>'+(s.zone_cells||0)+' sea cells \u00B7 '
     +(trained?'habitat estimate, not a catch forecast':'indicative hint, not a trained prediction'));
    lyr.bindTooltip('likely fish area',{sticky:true});
   }}).addTo(spotLayer);
 }
 s.suggestions.forEach(function(sp,i){
  const suit=sp.suitability!=null?sp.suitability:0;
  const col=suit>=0.66?'#4C9A57':(suit>=0.33?'#D9A62E':'#D97E35');
  const dist=sp.distance_km<1.5?'right at your location':sp.distance_km+' km '+sp.bearing+' of you';
  const lm=sp.landmark?('near '+sp.landmark+(sp.landmark_distance_km!=null?' ('+sp.landmark_distance_km+' km '+sp.landmark_direction+')':'')):'';
  /* specific spot dots ride along with the perimeter zone */
  var mk=null;
  if(spotLayer&&typeof L!=='undefined'){
   mk=L.circleMarker([sp.lat,sp.lon],{radius:6+6*suit,color:'#fff',weight:2,fillColor:col,fillOpacity:.95}).addTo(spotLayer)
    .bindPopup('<b>'+dist+'</b><br>'+(lm?lm+'<br>':'')+'Sea '+(sp.sst_c!=null?sp.sst_c+'\u00B0C':'-')+' \u00B7 match '+(suit*100).toFixed(0)+'%');
   spotMarkers.push(mk);
  }
  const el=document.createElement('div');el.className='spot';
  el.innerHTML='<span class="rank">#'+(i+1)+'</span><div class="dist"></div><div class="lm"></div>'
   +'<div class="bar"><i style="width:'+(suit*100).toFixed(0)+'%;background:'+col+'"></i></div><div class="m"></div>';
  markTr(el.querySelector('.dist'),dist);
  markTr(el.querySelector('.lm'),lm||'\u2013');
  markTr(el.querySelector('.m'),'sea '+(sp.sst_c!=null?sp.sst_c+'\u00B0C':'-')+' \u00B7 match '+(suit*100).toFixed(0)+'%');
  el.onclick=function(){if(map)map.flyTo([sp.lat,sp.lon],10);if(mk)mk.openPopup();};
  row.appendChild(el);
 });
 if(map)map.flyTo([s.center.lat,s.center.lon],8);
}

function addWhy(cls,text){
 const li=document.createElement('li');li.className=cls;markTr(li,text);
 document.getElementById('why').appendChild(li);
}
function showError(msg){
 reveal(document.getElementById('result'));
 const L=document.getElementById('vlight');L.textContent='!';L.style.background='#C94F4F';L.style.fontSize='34px';L.removeAttribute('data-tr');
 L.classList.remove('pop');void L.offsetWidth;L.classList.add('pop');
 const w=document.getElementById('vword');w.textContent='Cannot advise';w.style.color='#C94F4F';w.removeAttribute('data-tr');
 markTr(document.getElementById('vsub'),msg);
 document.getElementById('why').innerHTML='';
 document.getElementById('note').textContent='';
 document.getElementById('aisum').classList.add('hidden');
 document.getElementById('pa').classList.add('hidden');
 document.getElementById('raw').textContent='';
}

/* ---- admin panel: site health & statistics ---- */
function openAdminPanel(){
 const key=apiKey();
 if(!key){alert('Admin API key required. Enter it in the model panel first.');openModelPanel();return;}
 document.getElementById('adminov').classList.add('open');
 loadAdminStats();
}
function closeAdminPanel(){
 document.getElementById('adminov').classList.remove('open');
 document.getElementById('adminnote').textContent='';
}
async function loadAdminStats(){
 const box=document.getElementById('admincontent');
 box.innerHTML='<div class="loadhint" style="justify-content:center"><span class="waves"><i></i><i></i><i></i><i></i></span><span data-tr>Loading...</span></div>';
 const key=apiKey();
 try{
  const r=await fetch('/admin/stats',{headers:key?{'X-API-Key':key}:{}});
  if(r.status===401||r.status===403){
   box.innerHTML='<div class="mpsub" style="color:#C94F4F">Admin key required or invalid.</div>';
   return;
  }
  const d=await r.json();
  renderAdminStats(d);
 }catch(e){
  box.innerHTML='<div class="mpsub" style="color:#C94F4F">Failed to load: '+e+'</div>';
 }
}
function refreshAdminStats(){loadAdminStats();}
function adminNote(t){document.getElementById('adminnote').textContent=t||'';}
function renderAdminStats(d){
 const box=document.getElementById('admincontent');
 box.innerHTML='';
 /* API overview */
 const api=d.api||{};
 addAdminCard(box,'API',[
  {k:'Version',v:api.version||'-'},
  {k:'Region',v:api.region||'-'},
  {k:'Species',v:api.species_count||'-'},
  {k:'Uptime',v:api.uptime_human||'-'},
 ]);
 /* Services */
 const svc=d.services||{};
 const svcRows=[];
 for(const [name,info] of Object.entries(svc)){
  if(name==='docker')continue;
  const v=typeof info==='object'?info.status:info;
  const cls=v==='running'||v==='connected'?'ok':(v==='error'?'bad':'warn');
  svcRows.push({k:name.charAt(0).toUpperCase()+name.slice(1),v:v||'-',cls});
  if(name==='ollama'&&info.models&&info.models.length){
   svcRows.push({k:'  Models',v:info.models.join(', '),cls:''});
  }
 }
 addAdminCard(box,'Services',svcRows);
 /* Docker */
 if(svc.docker){
  const dockerRows=[];
  for(const [name,info] of Object.entries(svc.docker)){
   if(typeof info==='object'){
    const cls=info.status==='running'?'ok':(info.status==='exited'?'warn':'');
    dockerRows.push({k:name,v:info.status+' ('+(info.image||'')+')',cls});
   }
  }
  if(dockerRows.length)addAdminCard(box,'Docker',dockerRows);
 }
 /* System */
 const sys=d.system||{};
 addAdminCard(box,'System',[
  {k:'CPU',v:sys.cpu_percent!==undefined?sys.cpu_percent+'%':'-'},
  {k:'Memory',v:sys.memory?sys.memory.used_percent+'% ('+sys.memory.available_gb+' GB free)':'-'},
  {k:'Disk',v:sys.disk?sys.disk.used_percent+'% ('+sys.disk.free_gb+' GB free)':'-'},
 ]);
 /* Rate limits */
 const rl=d.rate_limits||{};
 if(Object.keys(rl).length){
  const rlRows=[];
  for(const [bucket,stats] of Object.entries(rl)){
   rlRows.push({k:bucket,v:stats.clients+' clients, '+stats.total_hits+' hits',cls:''});
  }
  addAdminCard(box,'Rate Limits (current window)',rlRows);
 }
 /* Assistant */
 const asst=d.assistant||{};
 addAdminCard(box,'AI Assistant',[
  {k:'Active Model',v:asst.active_model||'-'},
  {k:'Backend',v:asst.backend||'-'},
  {k:'Available',v:asst.available? 'yes':'no',cls:asst.available?'ok':'bad'},
  {k:'Models Configured',v:asst.models_count!=null?asst.models_count:'-'},
 ]);
 /* Config */
 const cfg=d.config||{};
 addAdminCard(box,'Config',[
  {k:'Rate Limit Buckets',v:(cfg.rate_limit_buckets||[]).join(', ')}
 ]);
}
function addAdminCard(host,title,rows){
 const card=document.createElement('div');card.className='admcard';
 const h=document.createElement('h4');h.textContent=title;card.appendChild(h);
 rows.forEach(function(r){
  const row=document.createElement('div');row.className='admrow';
  const k=document.createElement('span');k.className='k';k.textContent=r.k;
  const v=document.createElement('span');v.className='v '+(r.cls||'');v.textContent=r.v;
  row.appendChild(k);row.appendChild(v);card.appendChild(row);
 });
 host.appendChild(card);
}
</script></body></html>"""


def _telemetry_snapshot(eng, lat: float, lon: float) -> dict:
    """Compact live-conditions block (the GET /telemetry parameter set)
    attached to advisories so the AI assistant analyses the FULL station
    data - pressure, humidity, wave period, currents - not just the
    scoring inputs. None values are dropped to keep prompts lean."""
    from .ingestion import TelemetryField
    data = eng.ingestion.open_meteo.fetch_points([(lat, lon)], hours=24)
    env = data.get((lat, lon), {})

    def get_val(key: str):
        """Extract value from TelemetryField or raw value (backward compat)."""
        v = env.get(key)
        if isinstance(v, TelemetryField):
            return v.value
        return v

    def rnd(key: str, digits: int = 1):
        v = get_val(key)
        return round(v, digits) if v is not None else None

    snapshot = {
        "wind_speed_ms": get_val("wind_speed_10m"),
        "wind_gusts_ms": get_val("wind_gusts_10m"),
        "wind_direction_deg": rnd("wind_direction_10m", 0),
        "surface_pressure_hpa": rnd("surface_pressure"),
        "air_temperature_c": rnd("temperature_2m"),
        "relative_humidity_pct": rnd("relative_humidity_2m", 0),
        "sea_surface_temperature_c": rnd("sea_surface_temperature"),
        "wave_height_m": rnd("wave_height", 2),
        "wave_period_s": rnd("wave_period"),
        "wave_direction_deg": rnd("wave_direction", 0),
        "ocean_current_velocity_kmh": rnd("ocean_current_velocity", 2),
        "ocean_current_direction_deg": rnd("ocean_current_direction", 0),
    }
    return {k: v for k, v in snapshot.items() if v is not None}


def _station_status(cfg) -> dict:
    """Optional instrumented-station health (buoy / solar shore node).

    When no status_url is configured the dashboard honestly reports the
    service node on external power - battery/solar values are never
    fabricated. When configured, the endpoint should return JSON like
    {"battery_voltage_v": 12.4, "solar_output_w": 38.1}.
    """
    conf = cfg.raw.get("station") or {}
    out = {"name": conf.get("name", "parasail-node"),
           "battery_voltage_v": None, "solar_output_w": None,
           "power_source": "external"}
    url = conf.get("status_url")
    if url:
        try:
            r = httpx.get(url, timeout=3.0)
            r.raise_for_status()
            data = r.json()
            out.update({k: data.get(k) for k in
                        ("battery_voltage_v", "solar_output_w")})
            if out["battery_voltage_v"] is not None:
                out["power_source"] = "battery+solar"
        except Exception:  # noqa: BLE001 - station health is best-effort
            out["power_source"] = "unreachable"
    return out


# --------------------------------------------------------------------------- #
# application factory (lazy singletons so imports stay dependency-light)
# --------------------------------------------------------------------------- #
def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    _START_TIME = time.monotonic()   # process start, for the admin uptime
    api_cfg = cfg.raw.get("api", {})
    translations = TranslationService()
    sec_cfg = cfg.raw.get("security", {}) or {}

    app = FastAPI(
        title=api_cfg.get("title", "ParaSail Advisory API"),
        version=api_cfg.get("version", "1.0.0"),
        docs_url="/docs" if sec_cfg.get("public_docs", True) else None,
        redoc_url=None if not sec_cfg.get("public_docs", True) else "/redoc",
        description=(
            "Sustainability-scored, explainable fishing advisories with "
            "marine protected areas and seasonal closures enforced as hard "
            "constraints. Predictive Advisory and Retrieval-Augmented System "
            "Advancing Informed Livelihoods."),
    )

    # Security: rate limiting + headers + body cap, then CORS lockdown.
    limiter = RateLimiter(sec_cfg.get("rate_limits"))
    app.state.rate_limiter = limiter
    app.add_middleware(SecurityMiddleware, cfg=cfg, limiter=limiter)
    add_cors(app, cfg)

    # Local Leaflet assets: the dashboard must render without any CDN
    # (field/offline resilience); only the map TILES still need internet.
    from pathlib import Path as _Path
    _static_dir = _Path(__file__).resolve().parent / "static"
    if _static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static_dir)),
                  name="static")

    @app.api_route("/sw.js", methods=["GET", "HEAD"])
    def service_worker() -> FileResponse:
        """PWA service worker, served from the app root so its scope covers
        '/' (a /static/... path would scope it to /static/ only)."""
        sw = _static_dir / "sw.js"
        if not sw.exists():
            raise HTTPException(status_code=404, detail="no service worker")
        return FileResponse(sw, media_type="application/javascript",
                            headers={"Cache-Control": "no-cache"})

    def _db_factory():
        import psycopg
        dsn = cfg.database_url.replace("postgresql+psycopg://", "postgresql://")
        # short connect timeout: a down registry must not stall the request
        return psycopg.connect(dsn, connect_timeout=3)

    @functools.lru_cache(maxsize=1)
    def engine() -> AdvisoryEngine:
        try:
            import psycopg  # noqa: F401 - present in the API container
            db_factory = _db_factory
        except ImportError:
            db_factory = None  # no PostGIS driver: MPA checks fail closed
        ingestion = IngestionService(cfg)
        rules = RulesEngine(cfg, db_connection_factory=db_factory)
        rag = RagService(cfg)
        return AdvisoryEngine(cfg, ingestion, rules, rag)

    @functools.lru_cache(maxsize=1)
    def assistant() -> AssistantService:
        # Shares the engine's retrieval layer; the translation service
        # localises deterministic template answers on CPU-only deployments.
        return AssistantService(cfg, rag=engine().rag,
                                translation=translations)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        groups = cfg.region.get("locations", [])
        flat: list[dict] = []
        parts = ['<option value="custom" disabled>pick on the map...</option>']
        for g in groups:
            parts.append(f'<optgroup label="{g["state"]}">')
            for p in g.get("places", []):
                idx = len(flat)
                flat.append({"name": p["name"], "state": g["state"],
                             "lat": p["lat"], "lon": p["lon"]})
                parts.append(f'<option value="{idx}">{p["name"]}</option>')
            parts.append("</optgroup>")
        return (UI_PAGE
                .replace("__CITY_OPTIONS__", "".join(parts))
                .replace("__CITIES_JSON__", json.dumps(flat)))

    @app.post("/advisory")
    def advise(req: AdvisoryRequest) -> dict:
        try:
            advisory = engine().advise(req.lat, req.lon, req.species,
                                       req.start, req.hours)
        except ValueError as exc:          # quality gates
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        advisory["problem_answer"] = _problem_answer_for(
            advisory, req.language, translations)
        return advisory

    # ------------------------------------------------------------------ #
    # grounded AI assistant (phase P7) - explains, never decides
    # ------------------------------------------------------------------ #
    @app.post("/assistant/summarize")
    def assistant_summarize(req: AdvisoryRequest) -> dict:
        """Advisory + plain-language decision-support summary (verdict, what
        drove it, what to watch, data age), in the requested language.
        Grounded in the retrieved context; deterministic template fallback
        keeps this working without a GPU."""
        try:
            advisory = engine().advise(req.lat, req.lon, req.species,
                                       req.start, req.hours)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        advisory["problem_answer"] = _problem_answer_for(
            advisory, req.language, translations)
        # full live telemetry rides along so the active AI model analyses
        # the complete station parameter set, not just the scoring inputs
        advisory["telemetry"] = _telemetry_snapshot(
            engine(), req.lat, req.lon)
        return {"advisory": advisory,
                "summary": assistant().summarize_advisory(
                    advisory, req.language)}

    @app.post("/assistant/ask")
    def assistant_ask(req: AssistantAskRequest) -> dict:
        """Grounded question answering: retrieved passages + live advisory
        context in, cited plain-language answer out. The advisory class is
        authoritative; the assistant never contradicts a DO NOT FISH."""
        advisory = None
        if (req.lat is not None and req.lon is not None and req.species
                and req.start is not None):
            try:
                advisory = engine().advise(req.lat, req.lon, req.species,
                                           req.start, req.hours)
            except ValueError as exc:
                raise HTTPException(status_code=422,
                                    detail=str(exc)) from exc
        if advisory is not None:
            advisory["telemetry"] = _telemetry_snapshot(
                engine(), req.lat, req.lon)
        return assistant().answer_question(
            req.question, language=req.language, advisory=advisory,
            species=req.species, lat=req.lat, lon=req.lon, when=req.start)

    @app.post("/assistant/describe-image")
    def assistant_describe_image(req: AssistantImageRequest) -> dict:
        """Vision-language reading of a catch photo, satellite tile or chart
        (open-source VLM, 8-12 GB VRAM profile; see
        docs/PRODUCTION_HARDWARE.md)."""
        import base64 as _b64

        max_bytes = int(cfg.assistant.get("max_image_bytes", 6291456))
        try:
            raw = _b64.b64decode(req.image_base64, validate=True)
        except Exception as exc:
            raise HTTPException(status_code=422,
                                detail="image_base64 is not valid base64"
                                ) from exc
        if len(raw) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"image exceeds {max_bytes // 1048576} MB cap")
        return assistant().describe_image(req.image_base64, kind=req.kind,
                                          question=req.question,
                                          language=req.language)

    @app.get("/assistant/status")
    def assistant_status() -> dict:
        return assistant().status()

    @app.get("/assistant/models")
    def assistant_models(refresh: bool = False) -> dict:
        """The model registry for the dashboard switcher: backend, VRAM
        class and HONEST per-model availability (probed against the backend,
        20 s cache; ?refresh=true re-probes now)."""
        return {"active_model": assistant().status().get("active_model"),
                "models": assistant().list_models(refresh=refresh)}

    @app.post("/assistant/model")
    def assistant_switch_model(req: AssistantModelRequest,
                               role: str = Depends(
                                   require_role(cfg, "admin"))) -> dict:
        """Switch the active assistant model at runtime (scaling by user
        preference / hardware). The choice persists across restarts.
        Refused with 409 + the install command when the model is not
        downloaded/served unless force=true. Requires the ADMIN role
        (X-API-Key)."""
        try:
            result = assistant().switch_model(req.model, force=req.force)
            audit("model_switch", model=req.model, by_role=role)
            return result
        except ModelUnavailableError as exc:
            raise HTTPException(status_code=409, detail={
                "error": str(exc), "model": exc.key,
                "backend": exc.backend,
                "install_command": exc.install_command}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/telemetry")
    def telemetry(lat: float = Query(...), lon: float = Query(...)) -> dict:
        """Full current-conditions telemetry at a point, mirroring the
        station parameter set: meteorological (wind speed/gusts/direction,
        pressure, air temperature, humidity), oceanographic (SST, significant
        wave height, wave period/direction, surface current velocity/
        direction, salinity when a source provides it) and station health
        (GPS, UTC, battery/solar when an instrumented node is configured).

        Each field now includes provenance: fetched_at (when we retrieved it),
        age_hours (hours since fetch), and stale (served from cache)."""
        data = engine().ingestion.open_meteo.fetch_points([(lat, lon)],
                                                          hours=24)
        env = data.get((lat, lon), {})

        def get_val(key: str):
            """Extract value from TelemetryField or raw value (backward compat)."""
            v = env.get(key)
            if isinstance(v, TelemetryField):
                return v.value
            return v

        def get_age(key: str):
            """Extract age_hours from TelemetryField."""
            v = env.get(key)
            if isinstance(v, TelemetryField):
                return round(v.age_hours, 2)
            return None

        def get_stale(key: str):
            """Extract stale flag from TelemetryField."""
            v = env.get(key)
            if isinstance(v, TelemetryField):
                return v.stale
            return None

        def get_fetched_at(key: str):
            """Extract fetched_at from TelemetryField."""
            v = env.get(key)
            if isinstance(v, TelemetryField):
                return v.fetched_at
            return None

        def rnd(key: str, digits: int = 1):
            v = get_val(key)
            return round(v, digits) if v is not None else None

        # Build per-field provenance info
        field_provenance = {}
        for key in ("wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
                    "surface_pressure", "temperature_2m", "relative_humidity_2m",
                    "sea_surface_temperature", "wave_height", "wave_period",
                    "wave_direction", "ocean_current_velocity", "ocean_current_direction"):
            v = env.get(key)
            if isinstance(v, TelemetryField):
                field_provenance[key] = {
                    "fetched_at": v.fetched_at,
                    "age_hours": round(v.age_hours, 2),
                    "stale": v.stale,
                }

        # per-group provenance: which provider served what, and what is
        # missing, so the dashboard can show where the data comes from
        sources = {
            "weather": {
                "provider": "Open-Meteo forecast API",
                "served": [k for k in ("wind_speed_10m", "wind_gusts_10m",
                                       "wind_direction_10m",
                                       "surface_pressure", "temperature_2m",
                                       "relative_humidity_2m")
                           if get_val(k) is not None],
            },
            "sea": {
                "provider": "Open-Meteo marine API",
                "served": [k for k in ("sea_surface_temperature", "wave_height",
                                       "wave_period", "wave_direction",
                                       "ocean_current_velocity",
                                       "ocean_current_direction")
                           if get_val(k) is not None],
            },
            "salinity": {
                "provider": None,   # not wired: Copernicus/ERDDAP source
                "note": "no open salinity source configured yet",
            },
            "station": {
                "provider": cfg.raw.get("station", {}).get("name",
                                                           "parasail-node"),
                "position": cfg.raw.get("station", {}).get("position"),
            },
        }
        retrieved_at = datetime.now(timezone.utc).isoformat()
        return {
            "position": {"lat": lat, "lon": lon},
            # meteorological
            "wind_speed_ms": get_val("wind_speed_10m"),
            "wind_gusts_ms": get_val("wind_gusts_10m"),
            "wind_direction_deg": rnd("wind_direction_10m", 0),
            "surface_pressure_hpa": rnd("surface_pressure"),
            "air_temperature_c": rnd("temperature_2m"),
            "relative_humidity_pct": rnd("relative_humidity_2m", 0),
            # oceanographic
            "sea_surface_temperature_c": rnd("sea_surface_temperature"),
            "wave_height_m": rnd("wave_height", 2),
            "wave_period_s": rnd("wave_period"),
            "wave_direction_deg": rnd("wave_direction", 0),
            "ocean_current_velocity_kmh": rnd("ocean_current_velocity", 2),
            "ocean_current_direction_deg": rnd("ocean_current_direction", 0),
            "salinity_psu": None,  # no open source wired yet; shown as n/a
            # provenance (when we actually fetched the data)
            "retrieved_at": retrieved_at,
            "field_provenance": field_provenance,
            # station health + provenance
            "station": _station_status(cfg),
            "sources": sources,
            "observed_at": retrieved_at,
        }

    @app.get("/alerts")
    def alerts(lat: float = Query(...), lon: float = Query(...),
               radius_km: float = Query(200, ge=1, le=1000)) -> dict:
        """Security/disaster alerts for a location (IMD cyclones, INCOIS tsunami,
        NDMA multi-hazard, CAP India, SAC satellite alerts).

        Returns alerts sorted by severity and urgency (most critical first).
        Each alert includes: id, title, description, severity, urgency,
        certainty, event_type, affected areas, issued_at, expires_at, source,
        source_url, and localised languages."""
        alert_items = engine().ingestion.alerts_for_location(lat, lon, radius_km)
        return {
            "position": {"lat": lat, "lon": lon},
            "radius_km": radius_km,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "count": len(alert_items),
            "alerts": [
                {
                    "id": a.id,
                    "title": a.title,
                    "description": a.description,
                    "severity": a.severity,
                    "urgency": a.urgency,
                    "certainty": a.certainty,
                    "event_type": a.event_type,
                    "areas": a.areas,
                    "issued_at": a.issued_at,
                    "expires_at": a.expires_at,
                    "source": a.source,
                    "source_url": a.source_url,
                    "languages": a.languages,
                }
                for a in alert_items
            ],
        }

    @app.get("/fish-suggestions")
    def suggest(species: str = Query(...), lat: float = Query(...),
                lon: float = Query(...)) -> dict:
        """Approximate fish locations around a point, with the nearest
        landmark and distance - habitat-envelope estimate on live SST."""
        try:
            return fish_suggestions(cfg, engine().ingestion, species, lat, lon)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/translate")
    def translate(payload: TranslateRequest) -> dict:
        """Translate interface text (static labels and dynamic advisory
        content) into a supported Indian coastal language."""
        return {
            "target": payload.target,
            "translations": translations.translate_batch(
                payload.texts[:50], payload.target),
        }

    @app.get("/languages")
    def languages() -> dict:
        return {"supported": SUPPORTED_LANGUAGES}

    @app.get("/species")
    def species() -> list[dict]:
        return [
            {"scientific_name": s["scientific_name"],
             "common_name": s["common_name"],
             "modelling_path": s["modelling_path"],
             "local_names": s.get("local_names", {}),
             "closures": s.get("closures", [])}
            for s in cfg.species
        ]

    @app.get("/closures")
    def closures() -> list[dict]:
        out = []
        for s in cfg.species:
            for c in s.get("closures", []):
                out.append({"species": s["scientific_name"],
                            "common_name": s["common_name"],
                            "months": c["months"],
                            "reason": c["reason"],
                            "citation": c["citation"]})
        return out

    # ------------------------------------------------------------------ #
    # marine protected areas: the boundaries the fail-closed guard enforces
    # ------------------------------------------------------------------ #
    _mpa_cache: dict = {"ts": 0.0, "payload": None}

    @app.get("/mpas")
    def mpas() -> dict:
        """Protected-area registry as a GeoJSON FeatureCollection (EPSG:4326)
        - exactly what the advisory guard checks with PostGIS ST_Contains.
        Serves the dashboard overlay and external analysis. Cached in-process
        for 5 minutes so a registry reload is picked up without a restart.
        The PostGIS registry is the single source of truth; when it is
        unreachable the map shows nothing rather than stale boundaries."""
        import time as _time
        now = _time.time()
        if _mpa_cache["payload"] is not None and now - _mpa_cache["ts"] < 300:
            return _mpa_cache["payload"]
        try:
            with _db_factory() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT name, authority, desig, iucn_cat, no_take, source,
                           ST_AsGeoJSON(ST_Force2D(geometry), 6) AS geom
                    FROM   mpa_polygons
                    WHERE (valid_from IS NULL OR valid_from <= CURRENT_DATE)
                      AND (valid_to   IS NULL OR valid_to   >= CURRENT_DATE)
                    """)
                rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001 - registry down: honest empty
            log.warning("MPA registry unreadable: %s", exc)
            return {"type": "FeatureCollection", "count": 0,
                    "available": False,
                    "note": "MPA registry unreachable - boundaries unavailable",
                    "features": []}
        features = []
        for name, authority, desig, iucn, no_take, source, geom in rows:
            features.append({
                "type": "Feature",
                "geometry": json.loads(geom),
                "properties": {"name": name, "authority": authority,
                               "desig": desig, "iucn_cat": iucn,
                               "no_take": no_take, "source": source}})
        payload = {"type": "FeatureCollection", "count": len(features),
                   "available": True, "features": features}
        _mpa_cache.update(ts=now, payload=payload)
        return payload

    # ------------------------------------------------------------------ #
    # regional ocean news: every item shown in the reader's language
    # ------------------------------------------------------------------ #
    @app.post("/news")
    def news(req: NewsRequest) -> dict:
        """Regional ocean news from the seeded corpus
        (src/parasail/data/ocean_news.json), translated into the requested
        language. Items originating in other languages are translated for
        the reader (flagged `translated`); translation failures fall back
        to the original text, never to an error."""
        from pathlib import Path as _P
        import json as _json
        path = _P(__file__).resolve().parent / "data" / "ocean_news.json"
        try:
            corpus = _json.loads(path.read_text(encoding="utf-8"))
            items = corpus.get("items", [])
        except Exception as exc:  # noqa: BLE001 - unreadable corpus
            log.warning("news corpus unreadable: %s", exc)
            items = []

        out: list[dict] = []
        to_translate: list[tuple[int, str, str]] = []  # (idx, field, text)
        for i, it in enumerate(items):
            origin = it.get("origin_language", "en")
            # Translation pivots through the reference English edition
            # (title_en/summary_en): Indic->Indic machine translation is
            # unreliable, en->target is the strong pair for both backends.
            if req.language == origin:
                title, summary = it.get("title", ""), it.get("summary", "")
                translated_flag = False
            elif req.language == "en":
                title = it.get("title_en") or it.get("title", "")
                summary = it.get("summary_en") or it.get("summary", "")
                translated_flag = origin != "en"
            else:
                title = it.get("title_en") or it.get("title", "")
                summary = it.get("summary_en") or it.get("summary", "")
                translated_flag = True
                to_translate.append((i, "title", title))
                to_translate.append((i, "summary", summary))
            out.append({"id": it.get("id"), "region": it.get("region"),
                        "source": it.get("source"),
                        "origin_language": origin,
                        "title": title, "summary": summary,
                        "translated": translated_flag})

        if to_translate:
            texts = [t for _, _, t in to_translate if t]
            translated = translations.translate_batch(texts, req.language)
            lookup = {t: n for t, n in zip(texts, translated)}
            for i, field, original in to_translate:
                new = lookup.get(original)
                if new and new != original:
                    out[i][field] = new
                    out[i]["translated"] = True

        return {"language": req.language, "count": len(out), "items": out,
                "generated_at": datetime.now(timezone.utc).isoformat()}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "region": cfg.region["name"],
                "species_count": len(cfg.species)}

    # ------------------------------------------------------------------ #
    # admin dashboard: site health & statistics (requires admin role)
    # ------------------------------------------------------------------ #
    _admin_cache: dict = {"ts": 0.0, "payload": None, "uptime": 0.0}

    @app.get("/admin/stats")
    def admin_stats(role: str = Depends(require_role(cfg, "admin"))) -> dict:
        """System health and statistics for administrators.
        Requires X-API-Key with admin role. Probes are cached for 15 s so
        repeated dashboard opens do not re-hit every backend."""
        import time

        # API uptime
        api_uptime_s = time.monotonic() - _START_TIME
        now = time.monotonic()
        cached = _admin_cache["payload"]
        if (cached is not None and now - _admin_cache["ts"] < 15.0):
            out = json.loads(json.dumps(cached))       # shallow copy
            out["api"]["uptime_seconds"] = round(api_uptime_s)
            out["api"]["uptime_human"] = _human_uptime(api_uptime_s)
            out["cached"] = True
            return out

        def _tcp_open(host: str, port: int, timeout: float = 0.6) -> bool:
            """Fast reachability pre-check: avoids psycopg's multi-address
            connect retries (localhost -> ::1 then 127.0.0.1, ~15 s) when
            the container is simply not running."""
            import socket
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except OSError:
                return False

        # Ollama status
        ollama_status = "unknown"
        ollama_models = []
        try:
            with httpx.Client(timeout=3.0) as client:
                r = client.get("http://127.0.0.1:11434/api/tags")
                if r.status_code == 200:
                    ollama_status = "running"
                    ollama_models = [m.get("name", "") for m in r.json().get("models", [])]
                else:
                    ollama_status = "error"
        except Exception:
            ollama_status = "unreachable"

        # Database status
        db_status = "unreachable" if not _tcp_open("127.0.0.1", 5432) else "unknown"
        if db_status == "unknown":
            try:
                with _db_factory() as conn, conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                    db_status = "connected"
            except Exception as exc:
                db_status = "unreachable"
                log.info("admin probe: db unavailable (%s)", exc)

        # Qdrant status (TCP pre-check first: "localhost" would otherwise
        # burn ~4 s on the IPv6 connect before falling back to IPv4)
        qdrant_status = "unreachable" if not _tcp_open("127.0.0.1", 6333) else "unknown"
        qdrant_collections = []
        if qdrant_status == "unknown":
            try:
                with httpx.Client(timeout=3.0) as client:
                    r = client.get("http://127.0.0.1:6333/collections")
                    if r.status_code == 200:
                        qdrant_status = "running"
                        qdrant_collections = [c.get("name", "") for c in r.json().get("result", {}).get("collections", [])]
                    else:
                        qdrant_status = "error"
            except Exception:
                qdrant_status = "unreachable"

        # Docker container status via the CLI (no extra Python dependency;
        # fails fast when Docker Desktop is not running)
        docker_containers = {}
        try:
            import subprocess
            out = subprocess.run(
                ["docker", "ps", "-a", "--format",
                 "{{.Names}}|{{.State}}|{{.Image}}"],
                capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                for line in out.stdout.strip().splitlines():
                    parts = line.split("|")
                    if len(parts) >= 2:
                        docker_containers[parts[0]] = {
                            "status": parts[1],
                            "image": parts[2] if len(parts) > 2 else "unknown",
                        }
            else:
                docker_containers = {"note": "docker CLI unavailable"}
        except Exception:
            docker_containers = {"note": "Docker not running"}

        # Rate limiter stats
        rate_limit_stats = {}
        _lim = app.state.rate_limiter
        if hasattr(_lim, '_hits'):
            for (bucket, _client), hits in _lim._hits.items():
                if bucket not in rate_limit_stats:
                    rate_limit_stats[bucket] = {"clients": 0, "total_hits": 0}
                rate_limit_stats[bucket]["clients"] += 1
                rate_limit_stats[bucket]["total_hits"] += len(hits)

        # System resources (optional: requires psutil)
        system = {}
        try:
            import psutil
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu_pct = psutil.cpu_percent(interval=0.1)
            system = {
                "cpu_percent": cpu_pct,
                "memory": {
                    "total_gb": round(mem.total / 1024**3, 1),
                    "available_gb": round(mem.available / 1024**3, 1),
                    "used_percent": mem.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / 1024**3, 1),
                    "free_gb": round(disk.free / 1024**3, 1),
                    "used_percent": round(disk.used / disk.total * 100, 1),
                },
            }
        except ImportError:
            system = {"note": "psutil not installed - system metrics unavailable"}

        # Assistant status
        assistant_status = assistant().status()

        payload = {
            "api": {
                "uptime_seconds": round(api_uptime_s),
                "uptime_human": _human_uptime(api_uptime_s),
                "version": cfg.raw.get("api", {}).get("version", "1.0.0"),
                "region": cfg.region["name"],
                "species_count": len(cfg.species),
            },
            "services": {
                "ollama": {"status": ollama_status, "models": ollama_models},
                "database": {"status": db_status},
                "qdrant": {"status": qdrant_status, "collections": qdrant_collections},
                "docker": docker_containers,
            },
            "system": system,
            "rate_limits": rate_limit_stats,
            "assistant": dict(assistant_status,
                              models_count=len(
                                  cfg.raw.get("assistant", {}).get("models", {})),
                              registry=list(
                                  cfg.raw.get("assistant", {}).get("models", {}).keys())),
            "config": {
                "active_model": assistant_status.get("active_model"),
                "rate_limit_buckets": list(cfg.raw.get("security", {}).get("rate_limits", {}).keys()),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }
        _admin_cache.update(ts=now, payload=payload)
        return payload

    def _human_uptime(seconds: float) -> str:
        """Format uptime as human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        parts = []
        if days: parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    return app


app = create_app()

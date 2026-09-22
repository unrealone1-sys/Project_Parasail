# -*- coding: utf-8 -*-
"""Pick a cover variant that passes two objective checks:
  (1) no text span extends past the page edges, and
  (2) no two distinct text spans overlap.
Renders each candidate, checks it, and reports pass/fail per template.
"""
import os
import sys

import pymupdf

PDF_SKILL_DIR = (r"C:\Users\ignun\.zcode\cli\plugins\cache\zcode-plugins-official"
                 r"\pdf\0.1.7\skills\pdf")
sys.path.insert(0, os.path.join(PDF_SKILL_DIR, "scripts"))
from cover_render import render_cover  # noqa: E402

PALETTE = {"primary": "#3e5059", "secondary": "#457993", "text": "#232627",
           "muted": "#767d80", "bg": "#f6f7f7"}
W, H = 595.28, 841.89
TOL = 2.0

CANDIDATES = {
    "02": {
        "kicker": "SESSION SUMMARY  \u00b7  APPLICATION CHANGES",
        "hero": "ParaSail",
        "summary": ("Honest model availability, a rebuilt model switcher, a loading "
                    "animation and structured explanations. Both presentation decks "
                    "rebuilt to ten slides, animated and interactive."),
        "meta": "Anantha Krishnan AS  \u00b7  Naipunnya School of Management",
        "footer": "PARASAIL  \u00b7  SEPTEMBER 2026",
        "year": "2026", "word": "SUMMARY",
    },
    "01": {
        "kicker": "SESSION SUMMARY  \u00b7  APPLICATION CHANGES",
        "hero": "ParaSail",
        "summary": ("Honest model availability, a rebuilt model switcher, a loading "
                    "animation and structured explanations. Both decks rebuilt to ten "
                    "slides, animated and interactive."),
        "meta": "Ananthakrishnan AS  \u00b7  Naipunnya School of Management",
        "footer": "PARASAIL  \u00b7  SEPTEMBER 2026",
        "year": "2026", "word": "SUMMARY",
    },
    "03": {
        "kicker": "SESSION SUMMARY",
        "hero": "ParaSail",
        "summary": ("Honest model availability, a rebuilt model switcher, a loading "
                    "animation and structured explanations. Both presentation decks "
                    "rebuilt to ten slides, animated and interactive."),
        "meta": "Ananthakrishnan AS  \u00b7  Naipunnya School of Management",
        "footer": "PARASAIL  \u00b7  SEPTEMBER 2026",
        "year": "2026", "word": "SUMMARY",
    },
    "05": {
        "kicker": "SESSION SUMMARY  \u00b7  APPLICATION CHANGES",
        "hero": "ParaSail",
        "summary": ("Honest model availability, a rebuilt model switcher, a loading "
                    "animation and structured explanations. Both decks rebuilt to ten "
                    "slides, animated and interactive."),
        "meta": "Ananthakrishnan AS  \u00b7  Naipunnya School of Management",
        "footer": "PARASAIL  \u00b7  SEPTEMBER 2026",
        "year": "2026", "word": "SUMMARY",
    },
}


def spans(pdf):
    """Distinct text spans: dedupe the faux-bold copies drawn at the same spot."""
    out = {}
    for b in pymupdf.open(pdf)[0].get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for sp in line["spans"]:
                t = sp["text"].strip()
                if not t:
                    continue
                key = (round(sp["bbox"][0]), round(sp["bbox"][1]), t)
                out[key] = sp["bbox"]
    return list(out.items())


def check(pdf):
    issues = []
    items = spans(pdf)
    for (x0, y0, t), bb in items:
        if bb[0] < -TOL or bb[2] > W + TOL or bb[1] < -TOL or bb[3] > H + TOL:
            issues.append(f"outside page: {t[:44]!r} bbox={tuple(round(v) for v in bb)}")
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            ix = min(a[2], b[2]) - max(a[0], b[0])
            iy = min(a[3], b[3]) - max(a[1], b[1])
            if ix > 4 and iy > 4 and items[i][0][2] != items[j][0][2]:
                # same-text overlaps are the engine's faux-bold double-draw
                issues.append(f"overlap: {items[i][0][2][:30]!r} <-> {items[j][0][2][:30]!r}")
    return issues, len(items)


results = {}
for tpl, content in CANDIDATES.items():
    out = f"_cover_test_{tpl}.pdf"
    render_cover(tpl, content, out, palette=PALETTE)
    issues, n = check(out)
    results[tpl] = (issues, n)
    print(f"template {tpl}: {n} spans, {len(issues)} issue(s)")
    for it in issues[:4]:
        print("    -", it)
ok = [t for t, (i, _) in results.items() if not i]
print("\nclean templates:", ok or "none")

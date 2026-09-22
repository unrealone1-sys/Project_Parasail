# -*- coding: utf-8 -*-
"""Geometric QA over a rendered deck PDF (slide-bounds, collisions, anchors).
Text-over-figure is checked ONLY against the matplotlib figure rectangles;
rounded cards rasterize in PDF export and legitimately carry their own text.

Usage:  python qa_deck.py [ParaSail_Presentation.pdf]  # deck auto-detected
"""
import pymupdf, re, sys

PDF = sys.argv[1] if len(sys.argv) > 1 else "ParaSail_Presentation.pdf"
TECH = "TechnicalBackup" in PDF
W_PT, H_PT = 960.0, 540.0
TOL = 2.0
IN = 72.0

# figure placements in inches: slide -> [(x, y, w, h)] (from the build scripts)
FIGS = ({
    4: [(0.5, 1.5, 8.0, 8.0 / (2601 / 1153))],
    6: [(0.5, 1.85, 6.2, 6.2 / (1600 / 1000))],
} if TECH else {})

def norm(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())

ANCHORS = {
    "general": {
        1: ["ParaSail", "smart guide for safer fishing", "Anantha Krishnan AS"],
        2: ["What we will cover", "The problem", "Conclusion", "The honest map"],
        3: ["Why fishing needs help", "1 in 3", "Fish are moving", "Rules are hard to check"],
        4: ["Meet ParaSail", "GO CAREFULLY", "WAIT OR MOVE", "STOP"],
        5: ["What you actually see", "PLAIN-LANGUAGE EXPLANATION", "Reading the sea"],
        6: ["shows where", "Follows the real coastline", "Protected areas, for real", "backwater"],
        7: ["Ask it anything", "qwen2.5vl-3b-laptop", "Shows its sources", "Honest about the hardware"],
        8: ["It worked", "Closed seasons were always respected", "The map stayed over water"],
        9: ["Everyone on the coast wins", "Made for your coast", "Authorities"],
        10: ["Thank you", "Fish smarter", "Anantha Krishnan AS"],
    },
    "technical": {
        1: ["ParaSail", "geospatial decision support", "Anantha Krishnan AS"],
        2: ["What this deck covers", "Geospatial constraints", "Conclusion"],
        3: ["gap is architectural", "35.5", "ParaSail (this work)"],
        4: ["Six layers, one advisory", "Open data in", "Station telemetry"],
        5: ["Every advisory carries its own justification", "S = 0.45", "Hard rule"],
        6: ["Constraints with real geometry", "Ocean mask", "Real protected boundaries"],
        7: ["grounded local assistant", "Guardrails (in code)", "Honest availability"],
        8: ["Validated end to end", "Zones never over land", "Service hardened"],
        9: ["Local AI on one GPU", "Tier", "per question"],
        10: ["Thank you", "Q5", "Life Below Water"],
    },
}
anchors = ANCHORS["technical" if TECH else "general"]

doc = pymupdf.open(PDF)
problems = []

for pno, page in enumerate(doc, start=1):
    d = page.get_text("dict")
    lines = []
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if txt:
                lines.append((l["bbox"], txt))
    # 1. text outside slide bounds
    for bb, txt in lines:
        if bb[0] < -TOL or bb[2] > W_PT + TOL or bb[1] < -TOL or bb[3] > H_PT + TOL:
            problems.append(f"s{pno}: text outside bounds bbox={tuple(round(v,1) for v in bb)} {txt[:40]!r}")
    # 2. line-level text collisions
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a, c = lines[i][0], lines[j][0]
            ix = min(a[2], c[2]) - max(a[0], c[0])
            iy = min(a[3], c[3]) - max(a[1], c[1])
            if ix > 3 and iy > 2.5:
                problems.append(f"s{pno}: TEXT COLLISION {lines[i][1][:28]!r} <-> {lines[j][1][:28]!r}")
    # 3. text overlapping the matplotlib figure rectangles
    for fr in FIGS.get(pno, []):
        fx, fy, fw, fh = (v * IN for v in fr)
        fr_pt = (fx, fy, fx + fw, fy + fh)
        for bb, txt in lines:
            ix = min(bb[2], fr_pt[2]) - max(bb[0], fr_pt[0])
            iy = min(bb[3], fr_pt[3]) - max(bb[1], fr_pt[1])
            if ix > 8 and iy > 6:
                problems.append(f"s{pno}: text over FIGURE {txt[:36]!r}")
    # 4. anchors
    page_norm = norm(page.get_text())
    for anc in anchors.get(pno, []):
        if norm(anc) not in page_norm:
            problems.append(f"s{pno}: missing anchor {anc!r}")

full = "".join(p.get_text() for p in doc)
for bad in ["undefined", "[object", "TODO", "lorem", "[insert", "Click to add"]:
    if bad in full:
        problems.append(f"garbled text: {bad}")
if "BlueAdvisor" in full:
    problems.append("old name present")

print(f"{PDF}: slides {len(doc)}")
if problems:
    print("PROBLEMS (%d):" % len(problems))
    for pr in problems:
        print(" -", pr)
    sys.exit(1)
print("DECK QA CLEAN: bounds ok, no collisions, no text-on-figures, anchors ok")

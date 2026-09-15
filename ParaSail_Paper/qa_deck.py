# -*- coding: utf-8 -*-
"""Geometric QA over the rendered deck PDF (slide-bounds, collisions, anchors).
Text-over-image is checked ONLY against the six matplotlib figure rectangles;
rounded cards rasterize in PDF export and legitimately carry their own text."""
import pymupdf, re, sys

PDF = "ParaSail_Presentation.pdf"
W_PT, H_PT = 960.0, 540.0
TOL = 2.0
IN = 72.0

def rect(x, y, w, h):
    return (x * IN, y * IN, (x + w) * IN, (y + h) * IN)

# figure placements from build_deck.js: slide -> list of (x, y, w, h) inches
# (problem-led deck embeds no matplotlib figures - all visuals are native)
FIGS = {}

def norm(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())

anchors = {
    1: ["ParaSail", "smart guide for safer fishing", "Anantha Krishnan AS"],
    2: ["1 in 3", "The sea is changing"],
    3: ["The fish are moving away", "Yesterday's spots are empty"],
    4: ["The ocean needs a break", "Spawning grounds"],
    5: ["Going to sea is dangerous", "Warnings are too general"],
    6: ["Information is everywhere", "THE RULEBOOK", "Nothing connects them"],
    7: ["What is at stake", "Livelihoods"],
    8: ["Like a weather app", "Meet ParaSail", "Ask it anything"],
    9: ["traffic light", "GO CAREFULLY", "STOP"],
    10: ["What you actually see", "JUNE 15"],
    11: ["Ask it anything", "small boat", "sources: marine forecast", "Free for everyone, always"],
    12: ["shows its homework", "THE HOMEWORK", "Built to grow"],
    13: ["Your coast. Your fish. Your rules."],
    14: ["what we found", "Closed seasons were always respected"],
    15: ["Everyone on the coast", "Communities"],
    16: ["Thank you", "Fish smarter", "Anantha Krishnan AS", "works offline"],
}

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
            problems.append(f"s{pno}: text outside slide bounds bbox={tuple(round(v,1) for v in bb)} {txt[:40]!r}")
    # 2. line-level text collisions
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a, c = lines[i][0], lines[j][0]
            ix = min(a[2], c[2]) - max(a[0], c[0])
            iy = min(a[3], c[3]) - max(a[1], c[1])
            if ix > 3 and iy > 2.5:
                problems.append(f"s{pno}: TEXT COLLISION {lines[i][1][:28]!r} <-> {lines[j][1][:28]!r}")
    # 3. text overlapping the matplotlib figures (not cards)
    for fr in FIGS.get(pno, []):
        for bb, txt in lines:
            ix = min(bb[2], fr[2]) - max(bb[0], fr[0])
            iy = min(bb[3], fr[3]) - max(bb[1], fr[1])
            if ix > 8 and iy > 6:
                problems.append(f"s{pno}: text over FIGURE {txt[:36]!r} fig={tuple(round(v,0) for v in fr)}")
    # 4. anchors (whitespace-normalised; charSpacing splits extracted text)
    page_norm = norm(page.get_text())
    for anc in anchors.get(pno, []):
        if norm(anc) not in page_norm:
            problems.append(f"s{pno}: missing anchor {anc!r}")

full = "".join(p.get_text() for p in doc)
for bad in ["undefined", "[object", "TODO", "lorem", "[insert"]:
    if bad in full:
        problems.append(f"garbled text: {bad}")
if "BlueAdvisor" in full:
    problems.append("old name present")

print("slides:", len(doc))
if problems:
    print("PROBLEMS (%d):" % len(problems))
    for pr in problems:
        print(" -", pr)
    sys.exit(1)
print("DECK QA CLEAN: bounds ok, no collisions, no text-on-figures, anchors ok")

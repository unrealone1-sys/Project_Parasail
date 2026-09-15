# -*- coding: utf-8 -*-
"""Geometric + content QA over the rendered paper PDF (visual-proxy checks)."""
import pymupdf, re, sys

PDF = "ParaSail_Research_Paper.pdf"
PAGE_W, PAGE_H = 11906 / 20, 16838 / 20  # pt
M_L, M_R, M_T, M_B = 1440 / 20, 1240 / 20, 1180 / 20, 1180 / 20  # pt margins
TOL = 3.0  # pt tolerance

doc = pymupdf.open(PDF)
problems = []
all_fonts = set()

for pno, page in enumerate(doc, start=1):
    d = page.get_text("dict")
    blocks = [b for b in d["blocks"] if b["type"] == 0]
    # 1. margin overflow (ignore header/footer bands which sit inside margins by design)
    for b in blocks:
        x0, y0, x1, y1 = b["bbox"]
        if x0 < M_L - TOL - 14 or x1 > PAGE_W - M_R + TOL + 14:
            snippet = " ".join(s["text"] for l in b["lines"] for s in l["spans"])[:60]
            problems.append(f"p{pno}: horizontal overflow bbox=({x0:.1f},{x1:.1f}) text={snippet!r}")
        if y1 > PAGE_H - 40:  # below bottom margin area (footer zone is ~57pt+)
            snippet = " ".join(s["text"] for l in b["lines"] for s in l["spans"])[:60]
            if "Digital Blue Economy Summit" not in snippet and not re.fullmatch(r"\s*\d+\s*", snippet):
                problems.append(f"p{pno}: block in footer zone text={snippet!r}")
    # 2. overlapping text lines (line level: table-cell blocks interleave
    #    benignly in pymupdf, actual glyph collisions happen at line level).
    #    A true collision overlaps a large fraction of the line height; tight
    #    leading (references) padding overlaps ~25% and is not a collision.
    lines = []
    for b in blocks:
        for l in b["lines"]:
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if txt:
                lines.append((l["bbox"], txt))
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a, c = lines[i][0], lines[j][0]
            ix = min(a[2], c[2]) - max(a[0], c[0])
            iy = min(a[3], c[3]) - max(a[1], c[1])
            if ix > 4 and iy > max(3.0, 0.35 * min(a[3] - a[1], c[3] - c[1])):
                problems.append(f"p{pno}: line overlap {lines[i][1][:40]!r} <-> {lines[j][1][:40]!r}")
    # 3. fonts
    for b in blocks:
        for l in b["lines"]:
            for s in l["spans"]:
                all_fonts.add(s["font"])
    # 4. header present (top band) except none expected missing
    top_text = page.get_text("text", clip=pymupdf.Rect(0, 0, PAGE_W, 60)).strip()
    if "ParaSail" not in top_text:
        problems.append(f"p{pno}: running header missing")
    # 5. footer page number
    bot_text = page.get_text("text", clip=pymupdf.Rect(0, PAGE_H - 55, PAGE_W, PAGE_H)).strip()
    if not re.search(rf"(?<!\d){pno}(?!\d)", bot_text):
        problems.append(f"p{pno}: footer page number not found ({bot_text!r})")

# 6. garbled / placeholder text ("NaN" case-sensitive on word boundary:
#    a case-insensitive substring would false-positive on "governance")
full_text = "\n".join(pg.get_text() for pg in doc)
for bad in ["undefined", "[object", "TODO", "lorem", "[insert", "TBD"]:
    if bad.lower() in full_text.lower():
        problems.append(f"garbled/placeholder text found: {bad}")
if re.search(r"\bNaN\b", full_text):
    problems.append("garbled/placeholder text found: NaN")

# 7. structural anchors
for anchor in ["Abstract", "1. Introduction", "12. The Five Mandatory Summit Questions",
               "References", "Table 1", "Table 8", "(1)", "(2)", "(3)",
               "S = 0.45C + 0.25W + 0.30(1 \u2212 B)", "[32] CSA Department"]:
    if anchor not in full_text:
        problems.append(f"missing anchor: {anchor!r}")

print("fonts used:", sorted(all_fonts))
print("pages:", len(doc))
if problems:
    print("PROBLEMS (%d):" % len(problems))
    for pr in problems:
        print(" -", pr)
    sys.exit(1)
print("QA CLEAN: no overflow, no overlaps, headers/footers ok, anchors ok, no placeholders")

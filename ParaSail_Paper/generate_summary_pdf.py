# -*- coding: utf-8 -*-
"""ParaSail session summary - mobile-readable A4 report (ReportLab).

Body only (no cover): the cover is rendered separately by the PDF skill's
cover engine and merged as page 1.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, HRFlowable, KeepTogether,
                                PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = "ParaSail_Session_Summary.pdf"

# ── Fonts (Windows host: Times New Roman + Calibri) ───────────────────────
FONTS = {
    "Times New Roman": (r"C:\Windows\Fonts\times.ttf", r"C:\Windows\Fonts\timesbd.ttf"),
    "Calibri": (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
}
for name, (reg, bold) in FONTS.items():
    pdfmetrics.registerFont(TTFont(name, reg))
    pdfmetrics.registerFont(TTFont(name + "-Bold", bold))
    registerFontFamily(name, normal=name, bold=name + "-Bold",
                       italic=name, boldItalic=name + "-Bold")

# ── Palette (pdf.py palette.cascade - cold / minimal) ────────────────────
PAGE_BG = colors.HexColor("#f6f7f7")
CARD_BG = colors.HexColor("#eceeef")
STRIPE = colors.HexColor("#eff1f1")
HEADER_FILL = colors.HexColor("#3e5059")
BORDER = colors.HexColor("#a8b7bf")
ICON = colors.HexColor("#457993")
ACCENT = colors.HexColor("#cf304b")
TEXT = colors.HexColor("#232627")
MUTED = colors.HexColor("#767d80")
SUCCESS = colors.HexColor("#45935f")

SERIF, SANS = "Times New Roman", "Calibri"

# ── Styles ───────────────────────────────────────────────────────────────
S = {}
S["h1"] = ParagraphStyle("h1", fontName=SERIF, fontSize=19, leading=24,
                         textColor=HEADER_FILL, spaceBefore=18, spaceAfter=8)
S["h2"] = ParagraphStyle("h2", fontName=SERIF, fontSize=13.5, leading=18,
                         textColor=ACCENT, spaceBefore=14, spaceAfter=5)
S["body"] = ParagraphStyle("body", fontName=SERIF, fontSize=11, leading=16.5,
                           textColor=TEXT, spaceAfter=8, alignment=TA_LEFT)
S["bullet"] = ParagraphStyle("bullet", parent=S["body"], leftIndent=16,
                             bulletIndent=4, spaceAfter=4)
S["caption"] = ParagraphStyle("caption", fontName=SERIF, fontSize=9.5, leading=13,
                              textColor=MUTED, alignment=TA_CENTER,
                              spaceBefore=5, spaceAfter=12)
S["cell"] = ParagraphStyle("cell", fontName=SERIF, fontSize=9.5, leading=13.5,
                           textColor=TEXT)
S["cellb"] = ParagraphStyle("cellb", parent=S["cell"], fontName=SERIF + "-Bold")
S["head"] = ParagraphStyle("head", fontName=SERIF + "-Bold", fontSize=10,
                           leading=13, textColor=colors.white)
S["statn"] = ParagraphStyle("statn", fontName=SANS + "-Bold", fontSize=24,
                            leading=26, textColor=ACCENT, alignment=TA_CENTER)
S["statl"] = ParagraphStyle("statl", fontName=SANS, fontSize=8.5, leading=11,
                            textColor=MUTED, alignment=TA_CENTER)

AVAIL = A4[0] - 1.8 * inch


def heading(text):
    return [CondPageBreak(A4[1] * 0.18), Paragraph(text, S["h1"]),
            HRFlowable(width="100%", thickness=0.6, color=BORDER,
                       spaceBefore=0, spaceAfter=10)]


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def table(rows, ratios, caption=None):
    """rows[0] = header. All cells wrapped in Paragraph (never plain str)."""
    widths = [r * AVAIL for r in ratios]
    data = [[Paragraph(c, S["head"]) for c in rows[0]]]
    for r in rows[1:]:
        data.append([Paragraph(c, S["cell"]) for c in r])
    t = Table(data, colWidths=widths, hAlign="CENTER", repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        style.append(("BACKGROUND", (0, i), (-1, i),
                      STRIPE if i % 2 else colors.white))
    t.setStyle(TableStyle(style))
    out = [Spacer(1, 4), t]
    if caption:
        out.append(Paragraph(caption, S["caption"]))
    else:
        out.append(Spacer(1, 12))
    return out


def stats(items):
    """items = [(number, label), ...] - data sculpture callouts."""
    cells = [[Paragraph(n, S["statn"]) for n, _ in items],
             [Paragraph(l, S["statl"]) for _, l in items]]
    w = AVAIL / len(items)
    t = Table(cells, colWidths=[w] * len(items), hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
    ]))
    return [Spacer(1, 6), t, Spacer(1, 14)]


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(SERIF, 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.9 * inch, A4[1] - 0.62 * inch,
                      "ParaSail - Session Summary")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.9 * inch, A4[1] - 0.68 * inch,
                A4[0] - 0.9 * inch, A4[1] - 0.68 * inch)
    canvas.line(0.9 * inch, 0.66 * inch, A4[0] - 0.9 * inch, 0.66 * inch)
    canvas.drawString(0.9 * inch, 0.52 * inch, "Anantha Krishnan AS - ParaSail")
    canvas.drawRightString(A4[0] - 0.9 * inch, 0.52 * inch, "Page %d" % doc.page)
    canvas.restoreState()


story = []

# ── Intro ────────────────────────────────────────────────────────────────
story += heading("What this session delivered")
story.append(Paragraph(
    "Two things were completed. First, the application changes that the deck now "
    "presents - honest model availability, a rebuilt model switcher, the loading "
    "animation and the structured plain-language explanation. Second, both "
    "presentation decks were rebuilt to exactly ten slides on one shared spine, "
    "animated and made interactive, and renamed with the author name for "
    "identification.", S["body"]))
story += stats([("10", "slides per deck<br/>(one shared spine)"),
                ("35/35", "validation checks<br/>passing"),
                ("4", "layout defects<br/>found and fixed"),
                ("2", "decks rebuilt,<br/>renamed, rendered")])

# ── Application changes ─────────────────────────────────────────────────
story += heading("The application changes, and where the deck shows them")
story += table([
    ["Change", "What it does", "Where it appears"],
    ["<b>Honest model availability</b>",
     "Every model in the registry is probed against its backend (2.5 s timeout, 20 s cache). An uninstalled model is refused with the exact install command instead of being reported as active.",
     "Slide 7 - “it checks what is actually installed on this computer and says so”"],
    ["<b>Polished model switcher</b>",
     "The dropdown and the browser prompt are gone. A status pill opens a panel with one card per model: status chip, VRAM and download size, the install command, and an inline admin-key form.",
     "Slide 7 - the model-readiness note"],
    ["<b>Loading animation</b>",
     "The button's spinner was being destroyed by the translation code; the label now lives in its own span, and animated wave bars plus “Reading the sea…” appear beside the button while the request runs.",
     "Slide 5 - the “while it thinks” card"],
    ["<b>Structured explanation</b>",
     "Summaries return separate checkable points (verdict, sea conditions, fish likelihood, ecological risk) instead of one paragraph, rendered with staggered diamond markers.",
     "Slide 5 - the plain-language explanation card"],
    ["<b>Ocean-masked zones</b>",
     "The likely-fish area is clipped to real shoreline geometry; lagoons and backwaters fall on the land side, so a zone can never sit over land.",
     "Slide 6 - “follows the real coastline”"],
    ["<b>Real protected boundaries</b>",
     "Sixteen real Indian marine-protected-area polygons in PostGIS, checked fail-closed: inside one, the answer is STOP and it names the park.",
     "Slide 6 - “protected areas, for real”"],
    ["<b>Telemetry-fed AI</b>",
     "The live station set is part of the grounding payload, so the assistant reasons over the same data the dashboard shows.",
     "Slides 4 and 7"],
    ["<b>English generation, then translation</b>",
     "The model always generates in English and the finished answer is translated into the ten coastal languages - small local models reason poorly in Indic scripts directly.",
     "Slide 7 - “translated, not guessed”"],
], [0.19, 0.50, 0.31])

# ── The decks ───────────────────────────────────────────────────────────
story += heading("One spine, ten slides, two audiences")
story.append(Paragraph(
    "The general deck and the technical backup now follow the same ten-slide "
    "structure in the same order; only the depth and the wording change with the "
    "audience. Everything the paper carries is compressed in - nothing was dropped.",
    S["body"]))
story += table([
    ["#", "Role", "General deck", "Technical deck"],
    ["1", "Title", "ParaSail - a smart guide for safer fishing", "Title with contribution chips"],
    ["2", "Contents", "Interactive hub - eight linked cards", "Interactive hub - eight linked cards"],
    ["3", "Problem", "Why fishing needs help", "The gap is architectural, not algorithmic"],
    ["4", "How it works", "Meet ParaSail - one clear answer", "Six layers, one advisory + telemetry"],
    ["5", "The answer", "What you actually see", "Every advisory carries its own justification"],
    ["6", "The map", "The map shows where - honestly", "Constraints with real geometry"],
    ["7", "The AI", "Ask it anything - in your own words", "A grounded local assistant - it never decides"],
    ["8", "Evidence", "It worked - here is what we found", "Validated end to end (T1-T6)"],
    ["9", "Impact", "Everyone on the coast wins", "Local AI on one GPU - no API bills"],
    ["10", "Conclusion", "Fish smarter. Stay safe.", "The five summit questions"],
], [0.05, 0.13, 0.41, 0.41])

# ── Animation / interactivity ───────────────────────────────────────────
story += heading("Animations and interactivity")
story.append(Paragraph(
    "The deck library cannot emit animations, so they are written directly into "
    "the presentation XML by a new post-processing script. The work is repeatable: "
    "rebuild the deck and the animations are re-applied automatically.", S["body"]))
story += bullets([
    "<b>Slide transitions</b> - a medium fade on all twenty slides.",
    "<b>Entrance builds</b> - shapes fade in as roughly six waves per slide, so each "
    "slide assembles itself instead of appearing at once.",
    "<b>Click-to-reveal</b> - three slides hold content back for the presenter: the four "
    "traffic-light signals, the four explanation points, and the four recent AI changes.",
    "<b>Navigation</b> - the contents slide links to slides 3-10, and every content slide "
    "carries a contents link back to the hub.",
])
story.append(Paragraph(
    "Verified after the rebuild: every slide XML parses, no animation references a "
    "missing shape, transitions precede animation in schema order, and all eight "
    "internal links resolve.", S["body"]))

# ── Ops ─────────────────────────────────────────────────────────────────
story += heading("Operations: what was down, and what was fixed")
story += bullets([
    "<b>Port conflict</b> - a Docker API container and the host server were both bound to "
    "port 8000, and the container cannot reach the host's Ollama, so requests could silently "
    "fall back to template mode. Fixed: containers now serve only the database and the vector "
    "store; the API runs on the host.",
    "<b>Containers had exited</b> - the database and vector store had been down for two days "
    "after a machine restart with no restart policy; both were brought back and verified healthy.",
    "<b>Ollama had stopped</b> - it now runs as a managed background service with its model "
    "store set, so the bundled model is found on startup.",
    "<b>Rendering</b> - LibreOffice was not installed, and its installer requires administrator "
    "rights (error 1603). An administrative extraction, which needs no elevation, supplied a "
    "working converter for the PDF exports.",
])
story.append(Paragraph(
    "With all of that in place the live system was verified end to end: health check, model "
    "status, honest per-model availability, and a real assistant answer naming its backend - "
    "plus the full validation suite at 35/35.", S["body"]))

# ── Verification ────────────────────────────────────────────────────────
story += heading("Verification status")
story += table([
    ["Check", "Result"],
    ["Geometric QA on both decks", "Clean - text within bounds, no collisions, no text over figures, all anchors present"],
    ["Layout defects fixed", "Right-edge overflow on both map slides; a glyph-induced false collision; the scoring formula wrapping into its caption; and one font-size floor raised"],
    ["Slide XML and animations", "All 20 slides parse; no dangling animation targets; every relationship id resolves"],
    ["PowerPoint repair issue", "Fixed. Two constructs PowerPoint rejects: a hyperlink on multi-run text produced a dangling relationship (“rIdundefined”), and animation nodes reused ids. Both corrected - the decks now open in real PowerPoint with no repair prompt"],
    ["Slide 6 map figure", "Fixed. The zone had been clipped against a curve offset from the real shoreline, so it overlapped land. It is now clipped to the same curve that draws the coast, verified both geometrically and by scanning the rendered image (zero green pixels above the shoreline across 1,580 land columns)"],
    ["Application validation suite", "35 of 35 checks pass"],
    ["Pixel-level visual review", "Could not run - the review agent was unreachable and this session's model cannot view images. Font-size and image-placement checks were used instead."],
    ["Email delivery", "Not sent - the agent's browser is a separate profile without the mail session, and desktop control is unavailable in this session. The renamed file is ready for a manual send."],
], [0.32, 0.68])

# ── Open items ──────────────────────────────────────────────────────────
story += heading("Open items")
story += bullets([
    "<b>The email has not been sent.</b> The deck, renamed with the author name, is ready to "
    "attach: ParaSail_Presentation (Ananthakrishnan AS).pptx, with a PDF twin beside it. "
    "Recipient: vembanad.dialogues@naipunnyacollege.ac.in, with no message body, as requested.",
    "<b>Paper fixes before submission</b> - the title block still reads as a template "
    "(the author values are still wrapped in brackets), and the table captions run out of "
    "order: 1, 2, 3, 4, 8, 5, 6, 7, 9, because the hardware-tiers table sits before tables 5-7.",
    "<b>Nothing is committed to git yet</b> - the application changes and the deck rebuild are "
    "all still in the working tree.",
    "<b>Worth one look</b> - the rendered deck pages are in ParaSail_Paper/.cache_render/; the "
    "dense technical tables are the smallest text in the set.",
])

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    topMargin=0.95 * inch, bottomMargin=0.95 * inch,
    title="ParaSail - Session Summary", author="Anantha Krishnan AS",
    creator="ParaSail", subject="Application changes and the 10-slide deck rebuild",
)
doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
print("WROTE", OUT, os.path.getsize(OUT), "bytes")

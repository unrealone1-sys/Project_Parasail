# -*- coding: utf-8 -*-
"""Render the summary report cover (ReportLab cover engine, template 02) and
merge it as page 1 of the body PDF -> one final A4 PDF."""
import os
import sys

PDF_SKILL_DIR = (r"C:\Users\ignun\.zcode\cli\plugins\cache\zcode-plugins-official"
                 r"\pdf\0.1.7\skills\pdf")
sys.path.insert(0, os.path.join(PDF_SKILL_DIR, "scripts"))

from pypdf import PdfReader, PdfWriter, Transformation  # noqa: E402
from cover_render import render_cover  # noqa: E402

BODY = "ParaSail_Session_Summary.pdf"
COVER = "ParaSail_Session_Summary_cover.pdf"
FINAL = "ParaSail_Session_Summary.pdf"
A4_W, A4_H = 595.28, 841.89

content = {
    "kicker": "SESSION SUMMARY  ·  APPLICATION CHANGES",
    "hero": "ParaSail",
    "summary": ("Honest model availability, a rebuilt model switcher, a loading "
                "animation and structured explanations. Both presentation decks "
                "rebuilt to ten slides, animated and interactive."),
    "meta": "Ananthakrishnan AS  ·  Naipunnya School of Management",
    "footer": "PARASAIL  \u00b7  SESSION SUMMARY  \u00b7  SEPTEMBER 2026",
    "year": "2026",
    "word": "SUMMARY",
}
palette = {"primary": "#3e5059", "secondary": "#457993", "text": "#232627",
           "muted": "#767d80", "bg": "#f6f7f7"}

render_cover("02", content, COVER, palette=palette)
print("cover:", COVER, os.path.getsize(COVER))


def norm(page):
    b = page.mediabox
    w, h = float(b.width), float(b.height)
    if abs(w - A4_W) > 2 or abs(h - A4_H) > 2:
        page.add_transformation(Transformation().scale(sx=A4_W / w, sy=A4_H / h))
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (A4_W, A4_H)
    return page


writer = PdfWriter()
writer.add_page(norm(PdfReader(COVER).pages[0]))
for p in PdfReader(BODY).pages:
    writer.add_page(norm(p))
writer.add_metadata({
    "/Title": "ParaSail - Session Summary",
    "/Author": "Anantha Krishnan AS",
    "/Creator": "ParaSail",
    "/Subject": "Application changes and the 10-slide deck rebuild",
})
writer.write(FINAL + ".tmp")
os.replace(FINAL + ".tmp", FINAL)
print("merged:", FINAL, os.path.getsize(FINAL), "bytes,",
      len(PdfReader(FINAL).pages), "pages")

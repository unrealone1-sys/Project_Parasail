# -*- coding: utf-8 -*-
"""Add interactivity to a pptxgenjs-built deck, in place.

pptxgenjs cannot emit animations or transitions, so this post-processor edits
the OOXML directly:

  * <p:transition> - a medium fade on every slide
  * <p:timing>     - an entrance build: shapes fade in as a short cascade of
                     "waves" (a few shapes per wave, each wave after the
                     previous), except on slides listed in CLICK, where the
                     shapes inside declared regions are held back and revealed
                     one region per click ("clickEffect") for a presenter-led
                     reveal.

Schema order matters: transition must precede timing inside <p:sld>.
Usage:  python add_interactivity.py <deck.pptx> [<deck2.pptx> ...]
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from itertools import count
from pathlib import Path

EMU = 914400.0
FADE_MS = 400          # per-shape fade duration
WAVES = 6              # target number of auto "waves" per slide
FADE_XML = """<p:transition spd="med" advClick="1"><p:fade/></p:transition>"""

# Click-reveal regions per deck (1-based slide number -> list of regions).
# A shape belongs to the first region whose box contains its top-left corner;
# shapes in a region are revealed together on one click, regions in order.
CLICK = {
    "ParaSail_Presentation (Ananthakrishnan AS).pptx": {
        # S4 - the four traffic-light signals
        4: [{"x0": 5.6, "x1": 13.0, "y0": 1.90, "y1": 2.99},
            {"x0": 5.6, "x1": 13.0, "y0": 2.99, "y1": 4.08},
            {"x0": 5.6, "x1": 13.0, "y0": 4.08, "y1": 5.17},
            {"x0": 5.6, "x1": 13.0, "y0": 5.17, "y1": 6.30}],
        # S5 - the four plain-language points of the explanation
        5: [{"x0": 0.8, "x1": 6.30, "y0": 3.70, "y1": 4.28},
            {"x0": 0.8, "x1": 6.30, "y0": 4.28, "y1": 4.86},
            {"x0": 0.8, "x1": 6.30, "y0": 4.86, "y1": 5.44},
            {"x0": 0.8, "x1": 6.30, "y0": 5.44, "y1": 5.95}],
    },
    "ParaSail_Presentation_TechnicalBackup (Ananthakrishnan AS).pptx": {
        # S7 - the four "what changed recently" columns
        7: [{"x0": 0.45, "x1": 3.60, "y0": 5.05, "y1": 6.60},
            {"x0": 3.60, "x1": 6.74, "y0": 5.05, "y1": 6.60},
            {"x0": 6.74, "x1": 9.88, "y0": 5.05, "y1": 6.60},
            {"x0": 9.88, "x1": 13.0, "y0": 5.05, "y1": 6.60}],
    },
}

SHAPE_RE = re.compile(r'<p:cNvPr id="(\d+)"')
OFF_RE = re.compile(r'<a:off x="(-?\d+)" y="(-?\d+)"')


def shapes_in_order(xml: str) -> list[dict]:
    """[(spid, x_in, y_in)] in document order (= z-order, background first)."""
    out = []
    hits = list(SHAPE_RE.finditer(xml))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(xml)
        seg = xml[m.end():end]
        off = OFF_RE.search(seg)
        if not off:
            continue                       # group/placeholder without xfrm
        out.append({"id": int(m.group(1)),
                    "x": int(off.group(1)) / EMU,
                    "y": int(off.group(2)) / EMU})
    return out


def effect(spid: int, nid, node_type: str) -> str:
    """One fade-in effect targeting a shape (set visibility, then fade).

    Each cTn node needs its own id: PowerPoint rejects duplicated animation
    ids with a "needs repair" prompt (LibreOffice tolerates them), so every
    id comes from one monotonic allocator.
    """
    set_id, vis_id, anim_id = next(nid), next(nid), next(nid)
    return (
        f'<p:par><p:cTn id="{set_id}" presetID="10" presetClass="entr" '
        f'presetSubtype="0" fill="hold" grpId="0" nodeType="{node_type}">'
        f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        f'<p:set><p:cBhvr><p:cTn id="{vis_id}" dur="1" fill="hold">'
        f'<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
        f'<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
        f'</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
        f'<p:animEffect transition="in" filter="fade"><p:cBhvr>'
        f'<p:cTn id="{anim_id}" dur="{FADE_MS}"/>'
        f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
        f'</p:cBhvr></p:animEffect>'
        f'</p:childTnLst></p:cTn></p:par>')


def group(effects: list[str], nid, click: bool) -> str:
    """Wrap effects in a click- or auto-triggered group."""
    outer, inner = next(nid), next(nid)
    delay = "indefinite" if click else "0"
    return (
        f'<p:par><p:cTn id="{outer}" fill="hold">'
        f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>'
        f'<p:par><p:cTn id="{inner}" fill="hold">'
        f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        + "".join(effects) +
        f'</p:childTnLst></p:cTn></p:par>'
        f'</p:childTnLst></p:cTn></p:par>')


def build_timing(xml: str, slide_no: int, deck: str) -> str:
    shapes = shapes_in_order(xml)
    if not shapes:
        return ""
    regions = CLICK.get(deck, {}).get(slide_no, [])
    click_groups: list[list[dict]] = [[] for _ in regions]
    auto: list[dict] = []
    for sh in shapes:
        for gi, rg in enumerate(regions):
            if (rg["x0"] <= sh["x"] < rg["x1"]
                    and rg["y0"] <= sh["y"] < rg["y1"]):
                click_groups[gi].append(sh)
                break
        else:
            auto.append(sh)

    nid = count(3)                      # ids 1 (root) and 2 (mainSeq) are taken
    chunk = max(1, round(len(auto) / WAVES)) if auto else 0
    parts: list[str] = []
    # --- auto cascade -----------------------------------------------------
    for i in range(0, len(auto), max(chunk, 1)):
        wave = auto[i:i + max(chunk, 1)]
        fx = [effect(s["id"], nid, "withEffect" if j else "afterEffect")
              for j, s in enumerate(wave)]
        parts.append(group(fx, nid, click=False))
    # --- click reveals ----------------------------------------------------
    for cg in click_groups:
        if not cg:
            continue
        fx = [effect(s["id"], nid, "withEffect" if j else "clickEffect")
              for j, s in enumerate(cg)]
        parts.append(group(fx, nid, click=True))
    if not parts:
        return ""
    timing = (
        '<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" '
        'restart="never" nodeType="tmRoot"><p:childTnLst>'
        '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" '
        'nodeType="mainSeq"><p:childTnLst>' + "".join(parts) +
        '</p:childTnLst></p:cTn>'
        '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl>'
        '<p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl>'
        '<p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
        '</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>')
    # guard: duplicate animation ids make PowerPoint refuse the file
    ids = re.findall(r'<p:cTn id="(\d+)"', timing)
    assert len(ids) == len(set(ids)), \
        f"slide {slide_no}: duplicate animation ids {sorted({i for i in ids if ids.count(i) > 1})}"
    return timing


def process(path: Path) -> None:
    deck = path.name
    tmp = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(path) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        names = zin.namelist()
        slide_names = sorted(
            (n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"(\d+)", n.split("/")[-1]).group(1)))
        for item in names:
            data = zin.read(item)
            if item in slide_names:
                no = int(re.search(r"(\d+)", item.split("/")[-1]).group(1))
                xml = data.decode("utf-8")
                if "<p:timing>" in xml or "<p:transition" in xml:
                    xml = re.sub(r"<p:transition.*?</p:transition>|<p:transition[^>]*/>", "", xml, flags=re.S)
                    xml = re.sub(r"<p:timing>.*</p:timing>", "", xml, flags=re.S)
                timing = build_timing(xml, no, deck)
                if timing:
                    xml = xml.replace("</p:sld>", FADE_XML + timing + "</p:sld>")
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)
    print(f"  interactivity added: {deck}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        f = Path(p)
        if not f.exists():
            print(f"  MISSING: {p}")
            continue
        process(f)

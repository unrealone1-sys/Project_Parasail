/* ParaSail - 10-slide TECHNICAL deck (pptxgenjs, 13.33x7.5in).
 * Same 10-slide spine as the general deck (build_deck.js): title, contents
 * hub, problem, how it works, the answer, the map, ask the AI, evidence,
 * deployment, conclusion - with the engineering depth compressed in.
 * Interactive: linked contents grid + "contents" home link; transitions,
 * entrance builds and click reveals are added by add_interactivity.py. */
const pptxgen = require("pptxgenjs");

const W = 13.33, H = 7.5, M = 0.5;
const BG_DARK = "0A2E3C", CARD_DK = "12455A";
const PRIMARY = "14707C", PRIMARY_DK = "0E4A54", PRIMARY_LT = "E3EFF1";
const ACCENT = "E76F51", TEXT = "16323D", MUTED = "6B8290";
const LIGHT = "F2F8F9", LMUT = "9DB8C0";
const TL = { go: "4C9A57", careful: "D9A62E", wait: "D97E35", stop: "C94F4F" };
const SERIF = "Georgia", SANS = "Segoe UI";
const AR = { f1: 2601 / 1153, f7: 1600 / 1000 };

const CONTENTS_SLIDE = 2;
const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 2, angle: 45, opacity: 0.14 });
const bu = () => ({ code: "2022", indent: 12 });
const link = (n) => ({ slide: n });

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Anantha Krishnan AS";
pres.title = "ParaSail - Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods";

function kicker(s, t, dark) {
  s.addText(t.toUpperCase(), { x: M, y: 0.42, w: 8.5, h: 0.32, fontSize: 11,
    color: dark ? LMUT : PRIMARY, charSpacing: 3, fontFace: SANS, bold: true, margin: 0 });
}
function title(s, t, dark) {
  s.addText(t, { x: M, y: 0.70, w: W - 2 * M, h: 0.66, fontSize: 28,
    color: dark ? LIGHT : TEXT, fontFace: SERIF, bold: true, margin: 0 });
}
function pageNum(s, n, dark) {
  s.addText(String(n).padStart(2, "0"), { x: W - 0.95, y: H - 0.44, w: 0.45, h: 0.3,
    fontSize: 10, color: dark ? LMUT : MUTED, fontFace: SANS, align: "right", margin: 0 });
}
function srcLine(s, t, dark) {
  s.addText(t, { x: M, y: H - 0.44, w: 9.9, h: 0.3, fontSize: 10,
    color: dark ? LMUT : MUTED, fontFace: SANS, margin: 0 });
}
function homeLink(s, dark) {
  s.addText("\u2630  CONTENTS", { x: W - 2.35, y: 0.42, w: 1.85, h: 0.32, fontSize: 10,
    color: dark ? LMUT : PRIMARY, fontFace: SANS, bold: true, align: "right",
    charSpacing: 1, margin: 0, hyperlink: link(CONTENTS_SLIDE) });
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07,
    fill: { color: fill }, line: { color: "FFFFFF", width: 0 }, shadow: shadow() });
}
function outlineCard(s, x, y, w, h, border) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07,
    fill: { color: "FFFFFF" }, line: { color: border || "D8E2E6", width: 1.25 }, shadow: shadow() });
}
function img(s, file, ar, w, x, y) {
  const h = w / ar;
  s.addImage({ path: "deck_figures/" + file, x, y, w, h });
  return h;
}
function numRow(s, n, lead, desc, y, x, w, leadSize, descSize, h) {
  s.addShape(pres.shapes.OVAL, { x, y: y + 0.04, w: 0.56, h: 0.56,
    fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
  s.addText(n, { x, y: y + 0.04, w: 0.56, h: 0.56, fontSize: 14, bold: true,
    color: "FFFFFF", fontFace: SANS, align: "center", valign: "middle", margin: 0 });
  s.addText([
    { text: lead, options: { fontSize: leadSize, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: desc, options: { fontSize: descSize, color: TEXT } },
  ], { x: x + 0.9, y, w, h: h || 1.15, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 3 });
}

/* ============ S1 - Title (dark) ============ */
let s = pres.addSlide();
s.background = { color: BG_DARK };
s.addText("26TH DIGITAL BLUE ECONOMY SUMMIT  \u00B7  EXPERIMENTAL PAPER", {
  x: 0.9, y: 1.30, w: 11.5, h: 0.34, fontSize: 12, color: LMUT, charSpacing: 3,
  fontFace: SANS, bold: true, margin: 0 });
s.addText("ParaSail", { x: 0.9, y: 1.72, w: 11.5, h: 1.5, fontSize: 76,
  color: LIGHT, fontFace: SERIF, bold: true, margin: 0 });
s.addText("Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods", {
  x: 0.9, y: 3.28, w: 11.0, h: 0.42, fontSize: 15, italic: true, color: LMUT,
  fontFace: SERIF, margin: 0 });
s.addText("A geospatial decision support system for sustainable fishing, marine conservation and coastal livelihood resilience", {
  x: 0.9, y: 3.86, w: 10.6, h: 0.75, fontSize: 16, color: LIGHT, fontFace: SANS, margin: 0 });
const chips = ["Hard conservation constraints", "Explainable by retrieval", "Adaptable by LoRA fine-tuning", "Grounded AI assistant (local)"];
chips.forEach((c, i) => {
  const cx = 0.9 + i * 2.93;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 5.05, w: 2.78, h: 0.56,
    rectRadius: 0.28, fill: { color: CARD_DK }, line: { color: "2A5A6E", width: 1 } });
  s.addText(c, { x: cx, y: 5.05, w: 2.78, h: 0.56, fontSize: 11, color: LIGHT,
    fontFace: SANS, align: "center", valign: "middle", margin: 0 });
});
s.addText("Anantha Krishnan AS  \u00B7  Naipunnya School of Management, Cherthala, India  \u00B7  September 2026", {
  x: 0.9, y: 6.55, w: 11.5, h: 0.35, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
s.addNotes("ParaSail fuses live ocean data, species models and conservation rules into one explainable advisory. Interactive deck: the contents slide links to every section; \u2630 CONTENTS returns to it from any slide.");

/* ============ S2 - Contents (interactive hub) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Contents");
title(s, "What this deck covers");
const toc = [
  ["Problem, gap, objectives", "The information gap is architectural, not algorithmic", 3],
  ["Architecture and data", "Six layers, open inputs, telemetry, resilient ingestion", 4],
  ["The advisory engine", "Dual-collection retrieval, scoring under hard constraints", 5],
  ["Geospatial constraints", "Ocean-masked zones and real protected-area boundaries", 6],
  ["Grounded AI assistant", "Local VLM, guardrails in code, honest availability", 7],
  ["Validation", "Six test families, gates G1-G6, end-to-end evidence", 8],
  ["Deployment and impact", "Hardware tiers, zero marginal cost, who benefits", 9],
  ["Conclusion", "The five summit questions in one pass", 10],
];
toc.forEach((t, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.38, y = 1.72 + row * 1.12;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.95, h: 0.98, rectRadius: 0.07,
    fill: { color: PRIMARY_LT }, line: { color: "FFFFFF", width: 0 }, shadow: shadow(),
    hyperlink: link(t[2]) });
  s.addText(String(i + 1), { x: x + 0.22, y: y + 0.14, w: 0.62, h: 0.7, fontSize: 22,
    bold: true, color: PRIMARY, fontFace: SERIF, margin: 0, valign: "middle",
    hyperlink: link(t[2]) });
  /* single-run boxes, NOT a rich-text array: pptxgenjs writes a dangling
     r:id ("rIdundefined") when a hyperlink sits on a multi-run paragraph,
     which makes PowerPoint demand a repair */
  s.addText(t[0], { x: x + 0.95, y: y + 0.13, w: 4.85, h: 0.36, fontSize: 13.5,
    bold: true, color: PRIMARY_DK, fontFace: SANS, margin: 0, valign: "middle",
    hyperlink: link(t[2]) });
  s.addText(t[1], { x: x + 0.95, y: y + 0.49, w: 4.85, h: 0.36, fontSize: 10.5,
    color: TEXT, fontFace: SANS, margin: 0, valign: "middle",
    hyperlink: link(t[2]) });
});
s.addText("Tap any card to jump to that section; the CONTENTS link on each slide returns here.", {
  x: M, y: 6.32, w: 12.33, h: 0.4, fontSize: 11.5, italic: true, color: MUTED,
  fontFace: SERIF, margin: 0 });
s.addNotes("Interactive contents - each card is a hyperlink to its slide. Use it to jump during Q&A.");

/* ============ S3 - Problem, gap, objectives ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem");
title(s, "The gap is architectural, not algorithmic");
homeLink(s);
const stats = [
  ["35.5%", "of assessed stocks fished beyond sustainable levels", "FAO SOFIA 2023"],
  ["11 Mt", "of plastic entering the ocean every year", "UNEP 2023"],
  ["~3\u00D7", "projected growth of plastic flows by 2040", "UNEP 2023"],
  ["~492 M", "people supported by small-scale fisheries", "FAO 2023"],
];
stats.forEach((st, i) => {
  const x = M + i * 3.14;
  s.addText(st[0], { x, y: 1.52, w: 2.9, h: 0.85, fontSize: 38, bold: true,
    color: ACCENT, fontFace: SERIF, margin: 0 });
  s.addText(st[1], { x, y: 2.38, w: 2.9, h: 0.72, fontSize: 11.5, bold: true,
    color: TEXT, fontFace: SANS, margin: 0 });
  s.addText(st[2], { x, y: 3.06, w: 2.9, h: 0.32, fontSize: 10, color: MUTED,
    fontFace: SANS, margin: 0 });
});
const th = { fill: { color: PRIMARY }, color: "FFFFFF", bold: true, fontFace: SANS, fontSize: 10, align: "center", valign: "middle" };
const td = { fontFace: SANS, fontSize: 10, color: TEXT, valign: "middle" };
const tdC = { ...td, align: "center" };
const NO = { ...tdC, color: "B8C4CA" };
const YES = { ...tdC, color: PRIMARY_DK, bold: true };
const gapRows = [
  [{ text: "Tool class", options: { ...th, align: "left" } }, { text: "Weather", options: th }, { text: "Fish context", options: th }, { text: "Legality", options: th }, { text: "Explainability", options: th }],
  [{ text: "Weather applications", options: td }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "PFZ-style advisories", options: td }, { text: "\u2013", options: NO }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "Habitat / SDM studies", options: td }, { text: "\u2013", options: NO }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "Static regulations", options: td }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }],
  [{ text: "ParaSail (this work)", options: { ...td, bold: true, color: PRIMARY_DK, fill: { color: PRIMARY_LT } } },
   ...["\u2713", "\u2713", "\u2713", "\u2713"].map(t => ({ text: t, options: { ...YES, color: ACCENT, fill: { color: PRIMARY_LT } } }))],
];
s.addTable(gapRows, { x: M, y: 3.42, w: 12.33, colW: [3.63, 1.85, 2.2, 1.85, 2.8],
  border: { pt: 0.5, color: "D8E2E6" }, rowH: 0.36, margin: 0.05 });
s.addText([
  { text: "Objectives RO1-RO9: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "fuse live open data \u00B7 model movement with habitat fallback \u00B7 enforce MPAs and closures as hard constraints \u00B7 attach regulations to every advisory \u00B7 adapt locally via LoRA \u00B7 expose API + dashboard \u00B7 validate every layer \u00B7 align with blue-economy principles \u00B7 ground a conversational layer.", options: { color: TEXT } },
], { x: M, y: 5.62, w: 12.33, h: 0.95, fontSize: 11, fontFace: SANS, margin: 0, valign: "top" });
srcLine(s, "Sources: FAO SOFIA 2023; UNEP Turning off the Tap 2023; OECD 2022. PFZ: INCOIS potential fishing zone advisories.");
pageNum(s, 3);
s.addNotes("No existing tool class covers more than one column. ParaSail occupies all four - constraints before scores, and the justification attached to the output. The gap is architectural: nobody has fused these sources.");

/* ============ S4 - Architecture and data ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 architecture and data");
title(s, "Six layers, one advisory");
homeLink(s);
const h1 = img(s, "fig1_architecture.png", AR.f1, 8.0, M, 1.5);
s.addText("Every layer independently replaceable; region, species, closures and weights are YAML configuration, not code.", {
  x: M, y: 1.52 + h1 + 0.08, w: 8.0, h: 0.4, fontSize: 11.5, italic: true,
  color: MUTED, fontFace: SANS, margin: 0 });
card(s, 8.75, 1.5, 4.08, 2.6, PRIMARY_LT);
s.addText("Open data in", { x: 9.0, y: 1.68, w: 3.6, h: 0.35, fontSize: 13, bold: true,
  color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Open-Meteo \u2014 hourly met + marine forecasts", options: { bullet: bu(), breakLine: true } },
  { text: "Copernicus Marine \u2014 daily SST and currents", options: { bullet: bu(), breakLine: true } },
  { text: "NASA ERDDAP \u2014 SST, chlorophyll-a fields", options: { bullet: bu(), breakLine: true } },
  { text: "GBIF / OBIS \u2014 historical occurrences", options: { bullet: bu(), breakLine: true } },
  { text: "FishBase / WoRMS \u2014 taxonomy and traits", options: { bullet: bu(), breakLine: true } },
  { text: "Sentinel-2 / 3 \u2014 multispectral tiles", options: { bullet: bu() } },
], { x: 9.0, y: 2.05, w: 3.6, h: 1.95, fontSize: 9.5, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 5, margin: 0, valign: "top" });
card(s, 8.75, 4.25, 4.08, 1.75, PRIMARY_LT);
s.addText("Resilience by design", { x: 9.0, y: 4.42, w: 3.6, h: 0.35, fontSize: 13, bold: true,
  color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Freshness contracts per source", options: { bullet: bu(), breakLine: true } },
  { text: "Caching with explicit age flags", options: { bullet: bu(), breakLine: true } },
  { text: "Offline contingency \u2014 advisories continue from cached fields", options: { bullet: bu(), breakLine: true } },
  { text: "Quality gates, WoRMS normalisation", options: { bullet: bu() } },
], { x: 9.0, y: 4.78, w: 3.6, h: 1.15, fontSize: 9.5, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 4, margin: 0, valign: "top" });
s.addText([
  { text: "Station telemetry: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "13 parameters in three groups (weather \u00B7 sea \u00B7 station health), fetched in independent groups so one unsupported variable degrades only its own group - and the same live set is what the assistant analyses.", options: { color: TEXT } },
], { x: M, y: 6.05, w: 12.33, h: 0.75, fontSize: 11, fontFace: SANS, margin: 0, valign: "top" });
srcLine(s, "All sources open-licensed or publicly documented; operating cost negligible at pilot volumes.");
pageNum(s, 4);
s.addNotes("Walk the six layers, then the two boxes: what comes in (six open sources) and how it survives outages (contracts, caching, age flags). The telemetry strip matters - the assistant reasons over the full live station set, not just the scoring inputs.");

/* ============ S5 - The advisory engine ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 retrieval and scoring");
title(s, "Every advisory carries its own justification");
homeLink(s);
const chain = [
  [M, 3.35, "Collections (Qdrant)", "Regulations, closure calendars, guidance and local knowledge; OpenCLIP embeddings of satellite tiles with spatial metadata."],
  [4.35, 4.3, "Hybrid top-k retrieval", "Bounding-box + temporal pre-filter, then vector search - so context is relevant to this place and this day."],
  [9.15, 3.68, "Advisory + cited context", "Passages and tiles attached to every recommendation and shown next to the score."],
];
chain.forEach((c, i) => {
  outlineCard(s, c[0], 1.72, c[1], 1.5, i === 2 ? PRIMARY : null);
  s.addText([
    { text: c[2], options: { fontSize: 12.5, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: c[3], options: { fontSize: 10, color: TEXT } },
  ], { x: c[0] + 0.22, y: 1.86, w: c[1] - 0.44, h: 1.25, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 3 });
});
s.addShape(pres.shapes.LINE, { x: 3.85, y: 2.47, w: 0.4, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
s.addShape(pres.shapes.LINE, { x: 8.75, y: 2.47, w: 0.3, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
outlineCard(s, M, 3.45, 4.95, 1.45);
s.addText("S = 0.45\u00B7C + 0.25\u00B7W + 0.30\u00B7(1 \u2212 B)", {
  x: 0.75, y: 3.58, w: 4.5, h: 0.5, fontSize: 16, bold: true, color: PRIMARY_DK,
  fontFace: SERIF, margin: 0 });
s.addText("C catch likelihood \u00B7 W weather safety \u00B7 B bycatch risk \u2014 monotonic in every input, weights owned by governance.", {
  x: 0.75, y: 4.05, w: 4.5, h: 0.7, fontSize: 9.5, color: MUTED, fontFace: SANS,
  margin: 0, valign: "top" });
const classes = [
  ["PROCEED", "S \u2265 0.75", PRIMARY_LT, PRIMARY_DK],
  ["PROCEED WITH CAUTION", "0.60 \u2264 S < 0.75", PRIMARY_LT, PRIMARY_DK],
  ["DELAY OR RELOCATE", "0.40 \u2264 S < 0.60", PRIMARY_LT, PRIMARY_DK],
  ["DO NOT FISH", "S < 0.40", ACCENT, "FFFFFF"],
];
classes.forEach((cl, i) => {
  const y = 3.5 + i * 0.42;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.7, y, w: 3.15, h: 0.36, rectRadius: 0.08,
    fill: { color: cl[2] }, line: { color: "FFFFFF", width: 0 } });
  s.addText(cl[0], { x: 5.7, y, w: 3.15, h: 0.36, fontSize: 9.5, bold: true,
    color: cl[3], fontFace: SANS, align: "center", valign: "middle", margin: 0 });
  s.addText(cl[1], { x: 8.98, y, w: 2.4, h: 0.36, fontSize: 10, color: TEXT,
    fontFace: SANS, valign: "middle", margin: 0 });
  });
s.addText([
  { text: "Hard rule: ", options: { bold: true, color: ACCENT } },
  { text: "constraints run before scoring. Inside an active MPA or seasonal closure the advisory is DO NOT FISH regardless of score - no weight configuration can legalise an illegal trip.", options: { color: TEXT } },
], { x: M, y: 5.2, w: 12.33, h: 0.55, fontSize: 12, fontFace: SANS, margin: 0, valign: "top" });
s.addText("Explainability is the retrieval of verifiable sources - not generated prose. New sources plug in as chunked documents; the corpus grows per region and no model is retrained.", {
  x: M, y: 5.85, w: 12.33, h: 0.5, fontSize: 11.5, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, margin: 0, valign: "top" });
s.addText("Scalable by design: adding a regulation, a guidance note, a satellite pass or a whole regional corpus is an ingestion job - not a re-training project.", {
  x: M, y: 6.42, w: 12.33, h: 0.5, fontSize: 11, color: TEXT, fontFace: SANS,
  margin: 0, valign: "top" });
pageNum(s, 5);
s.addNotes("Dual-collection retrieval over rules and satellite tiles, hybrid pre-filtering, and citations attached to the output. Scoring is a weighted sum - but constraints run first, so the legality guarantee does not depend on weights. Adding knowledge is an ingestion job, not retraining.");

/* ============ S6 - Geospatial constraints ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 geospatial constraints");
title(s, "Constraints with real geometry");
homeLink(s);
const hz = img(s, "fig7_zones.png", AR.f7, 6.2, M, 1.85);
s.addText("Illustrative schematic: blocky advisory cells clipped to the sea side, and a protected area that forces STOP.", {
  x: M, y: 1.88 + hz, w: 6.2, h: 0.4, fontSize: 10, italic: true, color: MUTED,
  fontFace: SANS, margin: 0 });
numRow(s, "1", "Ocean mask (GSHHG)",
  "Shoreline data unioned over the India box; a grid cell counts as sea only where the mask and the marine model agree. Lagoons and backwaters fall on the land side, so a zone can never sit over land.", 1.85, 7.05, 4.85, 13.5, 10.5, 1.5);
numRow(s, "2", "Real protected boundaries",
  "16 real Indian MPA polygons loaded into PostGIS. The guard is ST_Contains and fail-closed: an unreachable registry blocks the request instead of clearing it.", 3.55, 7.05, 4.85, 13.5, 10.5, 1.5);
numRow(s, "3", "Fine grid, honest fallback",
  "0.03\u00B0 cells (about 3.3 km) traced into boundary polygons. The fallback chain is strictly sea-only, and if nothing qualifies there is no zone rather than a guess.", 5.25, 7.05, 4.85, 13.5, 10.5, 1.5);
srcLine(s, "Shoreline: GSHHG (Wessel & Smith, public domain) \u00B7 Protected areas: OpenStreetMap contributors (ODbL) \u00B7 Satellite embeddings: OpenCLIP.");
pageNum(s, 6);
s.addNotes("The geometry is the point. Zones are clipped by a real ocean mask so they cannot cover land or lagoons; protected areas use real boundaries; and the conservation guard fails closed - if the registry is unreachable, nothing is cleared.");

/* ============ S7 - Grounded AI assistant ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 conversational layer (P7)");
title(s, "A grounded local assistant - it never decides");
homeLink(s);
const boxes = [
  [M, "Inputs (grounding only)", "Advisory JSON with live telemetry \u00B7 top-k retrieved passages \u00B7 optional image (catch photo, tile, chart) \u00B7 question + language", "FFFFFF", PRIMARY],
  [4.62, "Local VLM + registry", "Qwen2.5-VL on vLLM (7B AWQ \u2248 6.9 GB, Apache 2.0) or Ollama (3B laptop tier). A runtime registry switches quality to hardware, 3B \u2192 72B, probed for what is actually installed.", PRIMARY_LT, null],
  [8.74, "Guardrails (in code)", "Citations must resolve to retrieved passages \u00B7 the advisory class is authoritative \u00B7 refusal over invention \u00B7 backend named on every answer", "FFFFFF", ACCENT],
];
boxes.forEach(b => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: b[0], y: 1.7, w: 3.9, h: 2.0, rectRadius: 0.07,
    fill: { color: b[3] }, line: { color: b[4] || "D8E2E6", width: 1.25 }, shadow: shadow() });
  s.addText([
    { text: b[1], options: { fontSize: 12.5, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: b[2], options: { fontSize: 9.5, color: TEXT } },
  ], { x: b[0] + 0.22, y: 1.85, w: 3.46, h: 1.75, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 5 });
});
s.addShape(pres.shapes.LINE, { x: 4.42, y: 2.7, w: 0.16, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
s.addShape(pres.shapes.LINE, { x: 8.54, y: 2.7, w: 0.16, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
card(s, M, 3.85, 12.33, 1.05, PRIMARY_LT);
s.addText([
  { text: "Output: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "structured plain-language explanations (separate checkable points), cited answers, image readings - generated in English and pivoted through translation into ten coastal languages with vernacular fish names. If the GPU is down, a deterministic template assembles the same schema from the same data.", options: { color: TEXT } },
], { x: 0.78, y: 3.85, w: 11.75, h: 1.05, fontSize: 11, fontFace: SANS, valign: "middle", margin: 0 });
const recent = [
  ["Structured output", "Summaries return separate points, not a paragraph"],
  ["Honest availability", "Every registry model is probed; an uninstalled one is refused with the exact install command"],
  ["Telemetry-fed", "The live station set is part of the grounding payload"],
  ["Translated, not guessed", "One English generation, then a translation pivot - small models reason better in English"],
];
recent.forEach((r, i) => {
  const x = M + i * 3.14;
  s.addText(r[0], { x, y: 5.1, w: 2.95, h: 0.38, fontSize: 12.5, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(r[1], { x, y: 5.5, w: 2.95, h: 1.0, fontSize: 9.5, color: TEXT,
    fontFace: SANS, margin: 0, valign: "top" });
});
srcLine(s, "T5 asserts class consistency, citation integrity, cache, fallback and backend naming; T6 asserts rate limits, 401/403 role gates, headers and body caps.");
pageNum(s, 7);
s.addNotes("One self-hosted VLM serves summaries, grounded Q&A and image reading. Guardrails are code: citations must resolve, the verdict is authoritative, refusal beats invention, the backend is always named. The four recent additions: structured points, honest model availability, telemetry in the grounding payload, and an English-generation + translation pivot.");

/* ============ S8 - Validation ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Validation");
title(s, "Validated end to end");
homeLink(s);
const tests = [
  ["T1", "Live fetch"], ["T2", "Rule enforcement"], ["T3", "Scoring behaviour"],
  ["T4", "Retrieval relevance"], ["T5", "Assistant behaviour"], ["T6", "Security behaviour"],
];
tests.forEach((t, i) => {
  const x = M + i * 2.09;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.68, w: 1.94, h: 0.56, rectRadius: 0.1,
    fill: { color: PRIMARY_LT }, line: { color: "FFFFFF", width: 0 } });
  s.addText([
    { text: t[0] + "  ", options: { bold: true, color: ACCENT } },
    { text: t[1], options: { color: PRIMARY_DK, bold: true } },
  ], { x, y: 1.68, w: 1.94, h: 0.56, fontSize: 9.5, fontFace: SANS, align: "center",
    valign: "middle", margin: 0 });
});
const results = [
  ["Live fetches reliable", "Graceful degradation under outage, with explicit age flags"],
  ["Closure blocks exact", "June sardine request returns DO NOT FISH with the reason"],
  ["Scoring monotonic", "In every input; class thresholds land exactly as configured"],
  ["Retrieval relevant", "Top-k context attached to every advisory on the dashboard"],
  ["Zones never over land", "Ocean-masked zones stayed at sea at Kochi, Chennai and Mangaluru"],
  ["Assistant guarded", "Citations resolve; verdicts hold; template fallback exact; availability honest"],
  ["Service hardened", "Rate limits 429; 401/403 role gates; security headers on every response"],
  ["Pilot-ready", "Installable PWA, offline shell, documented hardware tiers and cost model"],
];
results.forEach((r, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.38, y = 2.45 + row * 1.06;
  card(s, x, y, 5.95, 0.94, PRIMARY_LT);
  s.addText("\u2713", { x: x + 0.2, y: y + 0.2, w: 0.4, h: 0.5, fontSize: 15, bold: true,
    color: TL.go, fontFace: SANS, margin: 0 });
  s.addText([
    { text: r[0], options: { fontSize: 11.5, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: r[1], options: { fontSize: 9.5, color: TEXT } },
  ], { x: x + 0.68, y: y + 0.14, w: 5.1, h: 0.72, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 2 });
});
srcLine(s, "Test families map one-to-one onto phase gates G1-G6; the suite runs offline (--skip-live) and against live services.");
pageNum(s, 8);
s.addNotes("Six test families, six gates, and the eight findings on the right. Every capability claim in this deck is tied to a test - including the assistant's grounding (T5) and the service's security posture (T6).");

/* ============ S9 - Deployment and impact ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Deployment and impact");
title(s, "Local AI on one GPU - no API bills");
homeLink(s);
const th9 = { fill: { color: PRIMARY }, color: "FFFFFF", bold: true, fontFace: SANS, fontSize: 10, valign: "middle", align: "left" };
const td9 = { fontFace: SANS, fontSize: 10, color: TEXT, valign: "middle" };
const tiers = [
  [{ text: "Tier", options: th9 }, { text: "Hardware", options: th9 }, { text: "Model / profile", options: th9 }, { text: "Sustains", options: th9 }],
  [{ text: "L \u00B7 laptop", options: td9 }, { text: "RTX 4050 Laptop, 6 GB", options: td9 }, { text: "Qwen2.5-VL-3B, Q4 \u00B7 6 k ctx \u00B7 1-2 concurrent", options: td9 }, { text: "Personal use, demos", options: td9 }],
  [{ text: "1 \u00B7 pilot", options: td9 }, { text: "RTX 3060/4070, 12 GB", options: td9 }, { text: "7B AWQ \u00B7 8 k ctx \u00B7 8 concurrent", options: td9 }, { text: "Thousands of requests/day", options: td9 }],
  [{ text: "2 \u00B7 recommended", options: { ...td9, bold: true, color: PRIMARY_DK, fill: { color: PRIMARY_LT } } }, { text: "RTX 4090 / NVIDIA L4, 24 GB", options: { ...td9, fill: { color: PRIMARY_LT } } }, { text: "7B AWQ \u00B7 16 k ctx \u00B7 32-64 concurrent", options: { ...td9, fill: { color: PRIMARY_LT } } }, { text: "Tens of thousands/day", options: { ...td9, fill: { color: PRIMARY_LT } } }],
  [{ text: "3 \u00B7 regional", options: td9 }, { text: "2-4\u00D7 L4/A10G + LB, or A100 40 GB", options: td9 }, { text: "7B AWQ replicas + semantic cache", options: td9 }, { text: "Millions of requests/year", options: td9 }],
];
s.addTable(tiers, { x: M, y: 1.68, w: 12.33, colW: [1.9, 3.4, 4.23, 2.8],
  border: { pt: 0.5, color: "D8E2E6" }, rowH: 0.46, margin: 0.05 });
const econ = [
  ["$0 per question", "Self-hosted inference: the marginal cost of an answer is electricity."],
  ["~$16-55k/yr avoided", "Per-token billing for 10k questions/day at commercial API rates."],
  ["~$2k once + $315/yr", "The recommended 24 GB tier: one GPU plus power, owned outright."],
];
econ.forEach((e, i) => {
  const x = M + i * 4.2;
  card(s, x, 4.28, 3.9, 1.45, PRIMARY_LT);
  s.addText([
    { text: e[0], options: { fontSize: 15, bold: true, color: PRIMARY_DK, breakLine: true, fontFace: SERIF } },
    { text: e[1], options: { fontSize: 10, color: TEXT } },
  ], { x: x + 0.25, y: 4.44, w: 3.4, h: 1.15, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 4 });
});
s.addText([
  { text: "Who benefits: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "fishers save fuel and avoid fines \u00B7 the ocean gets its closures respected automatically \u00B7 communities keep their knowledge in a lasting library \u00B7 authorities get decisions anyone can audit.", options: { color: TEXT } },
], { x: M, y: 5.85, w: 12.33, h: 0.7, fontSize: 11, fontFace: SANS, margin: 0, valign: "top" });
srcLine(s, "Hardened for public traffic: rate limits, API-key RBAC, security headers, audit log; ships as an installable PWA with an offline app shell.");
pageNum(s, 9);
s.addNotes("Four hardware tiers, from a 6 GB laptop to multi-GPU regional deployments, and the economics that justify self-hosting: at 10,000 questions a day, commercial per-token APIs would cost 16-55k a year against a 2,000-dollar GPU plus power.");

/* ============ S10 - Conclusion (dark) ============ */
s = pres.addSlide();
s.background = { color: BG_DARK };
kicker(s, "Conclusion", true);
homeLink(s, true);
s.addText("Conservation, legality and safety are built into the objective function - ParaSail cannot recommend an illegal trip under any configuration.", {
  x: M, y: 0.95, w: 12.33, h: 1.1, fontSize: 22, bold: true, color: LIGHT,
  fontFace: SERIF, margin: 0 });
s.addText("Primary alignment: SDG 14 (Life Below Water)  \u00B7  supporting: SDG 2 \u00B7 8 \u00B7 9 \u00B7 13", {
  x: M, y: 2.05, w: 12.33, h: 0.35, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
s.addText("The five mandatory summit questions", { x: M, y: 2.55, w: 12.33, h: 0.35,
  fontSize: 13.5, bold: true, color: LIGHT, fontFace: SERIF, margin: 0 });
const qa = [
  ["Q1 \u00B7 Problem", "No real-time, integrated, explainable advisory system for sustainable fishing in data-poor regions."],
  ["Q2 \u00B7 Importance", "Livelihoods, food security, marine conservation and safety meet at one information gap."],
  ["Q3 \u00B7 Technology", "Geospatial AI (YOLOv8, ViT + LoRA, LSTM, random forest), dual-collection RAG, a self-hosted Qwen2.5-VL assistant on vLLM with a runtime model registry, open live APIs, FastAPI + PostGIS + Qdrant; hardened with rate limiting and RBAC, shipped as a PWA."],
  ["Q4 \u00B7 Evidence", "Open environmental, biodiversity and satellite data; regulation datasets; a working system validated by six test families across six gates."],
  ["Q5 \u00B7 Contribution", "A production-grade platform issuing sustainability-scored, explainable, conversational advisories with conservation enforced as a hard constraint - on local AI, at zero marginal cost."],
];
qa.forEach((q, i) => {
  const y = 2.98 + i * 0.68;
  s.addText([
    { text: q[0] + "   ", options: { bold: true, color: ACCENT } },
    { text: q[1], options: { color: LIGHT } },
  ], { x: M, y, w: 12.33, h: 0.62, fontSize: 11, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("Thank you  \u00B7  Anantha Krishnan AS  \u00B7  Naipunnya School of Management, Cherthala, India  \u00B7  26th Digital Blue Economy Summit", {
  x: M, y: 6.6, w: 12.33, h: 0.4, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
pageNum(s, 10, true);
s.addNotes("Close on the normative claim - constraints inside the objective function - then the five mandatory questions in one pass, and invite questions. \u2630 CONTENTS jumps back to the hub.");

pres.writeFile({ fileName: "ParaSail_Presentation_TechnicalBackup (Ananthakrishnan AS).pptx" }).then(() => console.log("WROTE ParaSail_Presentation_TechnicalBackup (Ananthakrishnan AS).pptx (10 slides, technical)"));

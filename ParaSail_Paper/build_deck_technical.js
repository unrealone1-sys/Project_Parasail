/* ParaSail — 17-slide professional deck (pptxgenjs, 13.33x7.5in)
 * Palette: deep-ocean dark + white content + marine teal primary + coral accent.
 * Fonts: Georgia (titles/statements) + Segoe UI (body/labels). */
const pptxgen = require("pptxgenjs");

const W = 13.33, H = 7.5, M = 0.5;
const BG_DARK = "0A2E3C", CARD_DK = "12455A";
const PRIMARY = "14707C", PRIMARY_DK = "0E4A54", PRIMARY_LT = "E3EFF1";
const ACCENT = "E76F51", TEXT = "16323D", MUTED = "6B8290";
const LIGHT = "F2F8F9", LMUT = "9DB8C0";
const SERIF = "Georgia", SANS = "Segoe UI";
const AR = { f1: 2601 / 1153, f2: 1670 / 1120, f3: 2593 / 953, f4: 1837 / 997, f5: 1646 / 1068, f6: 2399 / 872 };

const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 2, angle: 45, opacity: 0.14 });
const bu = () => ({ code: "2022", indent: 12 });

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Anantha Krishnan AS";
pres.title = "ParaSail - Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods";

function kicker(s, t, dark) {
  s.addText(t.toUpperCase(), { x: M, y: 0.42, w: W - 2 * M, h: 0.32, fontSize: 11,
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
  s.addText(t, { x: M, y: H - 0.44, w: 10.5, h: 0.3, fontSize: 10,
    color: dark ? LMUT : MUTED, fontFace: SANS, margin: 0 });
}
function img(s, file, ar, w, x, y) {
  const h = w / ar;
  s.addImage({ path: "deck_figures/" + file, x, y, w, h });
  return h;
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07,
    fill: { color: fill }, line: { color: "FFFFFF", width: 0 }, shadow: shadow() });
}

/* ============ S1 — Title (dark) ============ */
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
s.addNotes("ParaSail - one system fusing live ocean data, species models and conservation rules into a single explainable advisory. The name is a backronym: Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods.");

/* ============ S2 — Crisis stats ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem \u00B7 context");
title(s, "The blue economy under pressure");
const stats = [
  ["35.5%", "of assessed stocks fished beyond sustainable levels", "FAO, State of World Fisheries 2023"],
  ["11 Mt", "of plastic entering the ocean every year", "UNEP, Turning off the Tap 2023"],
  ["~3\u00D7", "projected growth of plastic flows by 2040", "UNEP, Turning off the Tap 2023"],
  ["~492 M", "people supported by small-scale fisheries", "FAO, Illuminating Hidden Harvests 2023"],
];
stats.forEach((st, i) => {
  const x = M + i * 3.14;
  s.addText(st[0], { x, y: 1.85, w: 2.9, h: 1.05, fontSize: 52, bold: true,
    color: ACCENT, fontFace: SERIF, margin: 0 });
  s.addText(st[1], { x, y: 2.98, w: 2.85, h: 0.85, fontSize: 13, bold: true,
    color: TEXT, fontFace: SANS, margin: 0 });
  s.addText(st[2], { x, y: 3.85, w: 2.85, h: 0.55, fontSize: 10.5,
    color: MUTED, fontFace: SANS, margin: 0 });
});
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.85, w: W, h: 1.55, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText("Rebuilding stocks under sound management pays; what is missing is the real-time information infrastructure for coastal actors to act on it.", {
  x: 0.7, y: 4.85, w: 11.9, h: 1.55, fontSize: 16, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, valign: "middle", margin: 0 });
srcLine(s, "Sources: FAO SOFIA 2023; UNEP 2023; OECD Global Plastics Outlook 2022; Cheung et al. 2010.");
pageNum(s, 2);
s.addNotes("Frame the crisis: overfishing share at record high, plastic flows tripling by 2040, half a billion livelihoods at stake. Land on the gap: information infrastructure, not willingness.");

/* ============ S3 — Four harms ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem \u00B7 consequences");
title(s, "Four harms of planning fishing blind");
const harms = [
  ["01", "Economic", "Fuel, time and labour wasted on blind search for shifting fish distributions."],
  ["02", "Ecological", "Fishing pressure concentrates on spawning grounds, sensitive habitats and protected zones."],
  ["03", "Safety", "Small vessels put to sea without granular marine wind and wave guidance."],
  ["04", "Institutional", "Weather apps, habitat studies, AIS analytics and regulations never speak to one another."],
];
harms.forEach((hm, i) => {
  const y = 1.78 + i * 1.28;
  s.addShape(pres.shapes.OVAL, { x: 0.62, y: y + 0.08, w: 0.66, h: 0.66, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
  s.addText(hm[0], { x: 0.62, y: y + 0.08, w: 0.66, h: 0.66, fontSize: 16, bold: true, color: "FFFFFF", fontFace: SANS, align: "center", valign: "middle", margin: 0 });
  s.addText([
    { text: hm[1], options: { fontSize: 16, bold: true, color: TEXT, breakLine: true } },
    { text: hm[2], options: { fontSize: 13, color: MUTED } },
  ], { x: 1.62, y, w: 11.0, h: 1.1, fontFace: SANS, margin: 0, valign: "top" });
});
pageNum(s, 3);
s.addNotes("Four harms of the status quo: economic waste, ecological concentration of effort, avoidable safety risk, and institutional fragmentation. The fourth is the root cause of the first three.");

/* ============ S4 — Fragmented tools matrix ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The gap");
title(s, "Existing tools are fragmented");
const th = { fill: { color: PRIMARY }, color: "FFFFFF", bold: true, fontFace: SANS, fontSize: 11, align: "center", valign: "middle" };
const td = { fontFace: SANS, fontSize: 11, color: TEXT, valign: "middle" };
const tdC = { ...td, align: "center" };
const NO = { ...tdC, color: "B8C4CA" };
const YES = { ...tdC, color: PRIMARY_DK, bold: true };
const rows4 = [
  [{ text: "Tool class", options: { ...th, align: "left" } }, { text: "Weather", options: th }, { text: "Fish context", options: th }, { text: "Legality", options: th }, { text: "Explainability", options: th }],
  [{ text: "Weather applications", options: td }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "PFZ-style advisories", options: td }, { text: "\u2013", options: NO }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "Habitat / SDM studies", options: td }, { text: "\u2013", options: NO }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "AIS fleet analytics", options: td }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }],
  [{ text: "Static regulations", options: td }, { text: "\u2013", options: NO }, { text: "\u2013", options: NO }, { text: "\u2713", options: YES }, { text: "\u2013", options: NO }],
  [{ text: "ParaSail (this work)", options: { ...td, bold: true, color: PRIMARY_DK, fill: { color: PRIMARY_LT } } },
   ...["\u2713", "\u2713", "\u2713", "\u2713"].map(t => ({ text: t, options: { ...YES, color: ACCENT, fill: { color: PRIMARY_LT } } }))],
];
s.addTable(rows4, { x: M, y: 1.75, w: 12.33, colW: [4.23, 1.9, 2.0, 1.9, 2.3],
  border: { pt: 0.5, color: "D8E2E6" }, rowH: 0.52, margin: 0.06 });
s.addText("No existing tool class fuses weather, fish context, legality and explanation \u2014 the gap is architectural, not algorithmic.", {
  x: M, y: 5.85, w: 12.33, h: 0.7, fontSize: 14.5, italic: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
srcLine(s, "PFZ: Potential Fishing Zone advisories (INCOIS). SDM: species distribution models.");
pageNum(s, 4);
s.addNotes("Each existing tool class covers one column at most. ParaSail is the first to occupy all four: constraints before scores, explanations attached to outputs.");

/* ============ S5 — Objectives ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Objectives");
title(s, "What ParaSail sets out to do");
card(s, M, 1.75, 4.15, 4.9, PRIMARY_LT);
s.addText("\u201CRecommend safe, legal and ecologically responsible fishing windows \u2014 with the justification attached.\u201D", {
  x: 0.85, y: 2.05, w: 3.5, h: 2.6, fontSize: 19, italic: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText("Eight objectives, each mapped to a validation test family (T1\u2013T4).", {
  x: 0.85, y: 5.35, w: 3.5, h: 1.0, fontSize: 12, color: MUTED, fontFace: SANS, margin: 0 });
const ros = [
  ["RO1", "Fuse live open data into one quality-controlled geospatial model"],
  ["RO2", "Model aggregation and movement tendency, with habitat fallback"],
  ["RO3", "Enforce MPAs and closures as hard constraints"],
  ["RO4", "Attach regulations, guidance and local knowledge to every advisory"],
  ["RO5", "Adapt locally via custom ingestion and LoRA fine-tuning"],
  ["RO6", "Expose a production-style API and visual dashboard"],
  ["RO7", "Evaluate via live-fetch, rule, scoring and retrieval tests"],
  ["RO8", "Align with blue-economy principles end to end"],
];
ros.forEach((ro, i) => {
  const col = Math.floor(i / 4), row = i % 4;
  const x = 5.15 + col * 3.95, y = 1.85 + row * 1.22;
  s.addText([
    { text: ro[0], options: { fontSize: 13, bold: true, color: PRIMARY, breakLine: true } },
    { text: ro[1], options: { fontSize: 11.5, color: TEXT } },
  ], { x, y, w: 3.75, h: 1.1, fontFace: SANS, margin: 0, valign: "top" });
});
pageNum(s, 5);
s.addNotes("Primary objective decomposed into eight verifiable objectives. The mission statement on the left is the one-line version used with pilot communities.");

/* ============ S6 — Architecture (fig1) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 architecture");
title(s, "Six layers, one advisory");
const h6 = img(s, "fig1_architecture.png", AR.f1, 11.9, 0.72, 1.55);
s.addText("Every layer is independently replaceable and configured through YAML \u2014 region, species, closures, models and score weights are data, not code.", {
  x: 0.72, y: 1.62 + h6 + 0.10, w: 11.9, h: 0.42, fontSize: 12.5, italic: true,
  color: MUTED, fontFace: SANS, align: "center", margin: 0 });
pageNum(s, 6);
s.addNotes("Walk left to right: ingest open APIs and satellite archives, normalise onto a common grid, predict with mixed model families, retrieve regulations and local knowledge, then apply constraints before scoring.");

/* ============ S7 — Ingestion ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 ingestion and processing");
title(s, "Live open data, normalised and audited");
const th7 = { fill: { color: PRIMARY }, color: "FFFFFF", bold: true, fontFace: SANS, fontSize: 10.5, valign: "middle" };
const td7 = { fontFace: SANS, fontSize: 10.5, color: TEXT, valign: "middle" };
const rows7 = [
  [{ text: "Source", options: { ...th7, align: "left" } }, { text: "Content", options: { ...th7, align: "left" } }, { text: "Cadence", options: th7 }],
  [{ text: "Open-Meteo", options: td7 }, { text: "Hourly meteorological and marine forecasts", options: td7 }, { text: "Hourly", options: { ...td7, align: "center" } }],
  [{ text: "Copernicus Marine", options: td7 }, { text: "Near-real-time ocean analysis (SST, currents)", options: td7 }, { text: "Daily", options: { ...td7, align: "center" } }],
  [{ text: "NASA ERDDAP", options: td7 }, { text: "SST and chlorophyll-a fields", options: td7 }, { text: "Daily", options: { ...td7, align: "center" } }],
  [{ text: "GBIF / OBIS", options: td7 }, { text: "Historical species occurrences", options: td7 }, { text: "Corpus", options: { ...td7, align: "center" } }],
  [{ text: "FishBase / WoRMS", options: td7 }, { text: "Taxonomy, traits, seasonality", options: td7 }, { text: "Corpus", options: { ...td7, align: "center" } }],
  [{ text: "Sentinel-2 / Sentinel-3", options: td7 }, { text: "Multispectral satellite tiles", options: td7 }, { text: "Per pass", options: { ...td7, align: "center" } }],
];
s.addTable(rows7, { x: M, y: 1.8, w: 8.1, colW: [2.15, 4.45, 1.5],
  border: { pt: 0.5, color: "D8E2E6" }, rowH: 0.55, margin: 0.06 });
card(s, 9.0, 1.8, 3.83, 4.35, PRIMARY_LT);
s.addText("Resilience by design", { x: 9.3, y: 2.05, w: 3.3, h: 0.4, fontSize: 15, bold: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Freshness contracts per source", options: { bullet: bu(), breakLine: true } },
  { text: "Response caching with age tracking", options: { bullet: bu(), breakLine: true } },
  { text: "Offline contingency: advisories continue from cached fields, with explicit age flags", options: { bullet: bu(), breakLine: true } },
  { text: "Quality gates and taxonomy normalisation (WoRMS identifiers)", options: { bullet: bu() } },
], { x: 9.3, y: 2.55, w: 3.3, h: 3.4, fontSize: 11.5, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 10, margin: 0, valign: "top" });
srcLine(s, "All sources open-licensed or publicly documented; operating cost negligible at pilot volumes.");
pageNum(s, 7);
s.addNotes("Ingestion wraps every provider behind one interface with freshness contracts. Under outage the system degrades gracefully: cached fields plus age flags, never silence.");

/* ============ S8 — Model selection ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 prediction");
title(s, "Model selection: mixed families, deliberate trade-offs");
const th8 = { fill: { color: PRIMARY }, color: "FFFFFF", bold: true, fontFace: SANS, fontSize: 10.5, valign: "middle", align: "left" };
const td8 = { fontFace: SANS, fontSize: 10.5, color: TEXT, valign: "middle" };
const rows8 = [
  [{ text: "Task", options: th8 }, { text: "Selected model", options: th8 }, { text: "Why this one", options: th8 }],
  [{ text: "Catch-image detection", options: td8 }, { text: "YOLOv8n (Ultralytics)", options: td8 }, { text: "Real-time on modest hardware; mature toolchain", options: td8 }],
  [{ text: "Species classification", options: td8 }, { text: "ViT-B/16 + LoRA (r = 8)", options: td8 }, { text: "Fine-grained accuracy at under 1% trainable parameters", options: td8 }],
  [{ text: "Movement tendency (24 h)", options: td8 }, { text: "Two-layer LSTM (hidden 128)", options: td8 }, { text: "Short-horizon sequences for data-rich species", options: td8 }],
  [{ text: "Habitat suitability", options: td8 }, { text: "Random forest", options: td8 }, { text: "Interpretable fallback for data-poor taxa", options: td8 }],
  [{ text: "Text embeddings", options: td8 }, { text: "all-MiniLM-L6-v2", options: td8 }, { text: "Fast 384-dimensional sentence embeddings", options: td8 }],
  [{ text: "Satellite tile embeddings", options: td8 }, { text: "OpenCLIP ViT-B/32", options: td8 }, { text: "Similarity search over unlabelled tiles", options: td8 }],
  [{ text: "Assistant: summaries, Q&A, image reading", options: td8 }, { text: "Qwen2.5-VL-7B (AWQ 4-bit) on vLLM", options: td8 }, { text: "One open-source VLM for all assistant jobs; 8-12 GB VRAM; batched local serving \u2014 no per-token API costs", options: td8 }],
];
s.addTable(rows8, { x: M, y: 1.75, w: 12.33, colW: [3.0, 3.9, 5.43],
  border: { pt: 0.5, color: "D8E2E6" }, rowH: 0.5, margin: 0.06 });
s.addText("Selection criterion is coastal deployability, not leaderboard position \u2014 every model runs on mid-range hardware.", {
  x: M, y: 6.35, w: 12.33, h: 0.45, fontSize: 13, italic: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
pageNum(s, 8);
s.addNotes("One representative per family: detector, fine-grained classifier, sequence model, tabular baseline, plus the embedding models that power retrieval. The optional LLM only summarises retrieved context.");

/* ============ S9 — LoRA (fig5) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 fine-tuning");
title(s, "Local adaptation at 0.34% of the parameters");
img(s, "fig5_lora.png", AR.f5, 6.9, M, 1.85);
s.addText("W = W\u2080 + BA", { x: 7.9, y: 2.0, w: 4.9, h: 0.7, fontSize: 26, bold: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Rank r = 8 updates on the query and value projections of all 12 encoder blocks", options: { bullet: bu(), breakLine: true } },
  { text: "0.29 M of 85.8 M parameters trainable (0.34%) on ViT-B/16", options: { bullet: bu(), breakLine: true } },
  { text: "Training converges within mid-range GPU memory", options: { bullet: bu(), breakLine: true } },
  { text: "New regions and species adapted through configuration and lightweight fine-tunes \u2014 no code edits", options: { bullet: bu() } },
], { x: 7.9, y: 2.85, w: 4.9, h: 3.4, fontSize: 13, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 12, margin: 0, valign: "top" });
srcLine(s, "Trainable-parameter counts derived from the ViT-B/16 architecture; LoRA per Hu et al., ICLR 2022.");
pageNum(s, 9);
s.addNotes("LoRA freezes pretrained weights and learns low-rank additive updates. Under one percent trainable keeps adaptation within a mid-range GPU budget - the difference between a lab artifact and a deployable regional system.");

/* ============ S10 — RAG diagram ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 retrieval-augmented explanation");
title(s, "Every advisory carries its own justification");
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.85, w: 4.15, h: 1.85, rectRadius: 0.07,
  fill: { color: "FFFFFF" }, line: { color: PRIMARY, width: 1.25 }, shadow: shadow() });
s.addText([
  { text: "Text collection (Qdrant)", options: { fontSize: 13.5, bold: true, color: PRIMARY_DK, breakLine: true } },
  { text: "Regulations, closure calendars, conservation guidance, local ecological knowledge", options: { fontSize: 11.5, color: TEXT } },
], { x: 0.75, y: 2.0, w: 3.7, h: 1.6, fontFace: SANS, margin: 0, valign: "top" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 4.15, w: 4.15, h: 1.85, rectRadius: 0.07,
  fill: { color: "FFFFFF" }, line: { color: PRIMARY, width: 1.25 }, shadow: shadow() });
s.addText([
  { text: "Satellite collection (Qdrant)", options: { fontSize: 13.5, bold: true, color: PRIMARY_DK, breakLine: true } },
  { text: "OpenCLIP tile embeddings with bounding-box and acquisition metadata", options: { fontSize: 11.5, color: TEXT } },
], { x: 0.75, y: 4.3, w: 3.7, h: 1.6, fontFace: SANS, margin: 0, valign: "top" });
s.addShape(pres.shapes.LINE, { x: 4.72, y: 2.95, w: 0.82, h: 0.62, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
s.addShape(pres.shapes.LINE, { x: 4.72, y: 4.30, w: 0.82, h: 0.62, flipV: true, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
card(s, 5.65, 3.05, 3.0, 1.75, PRIMARY_LT);
s.addText([
  { text: "Hybrid top-k retrieval", options: { fontSize: 13.5, bold: true, color: PRIMARY_DK, breakLine: true } },
  { text: "Bounding-box + temporal pre-filter, then vector search", options: { fontSize: 11, color: TEXT } },
], { x: 5.9, y: 3.2, w: 2.5, h: 1.5, fontFace: SANS, margin: 0, valign: "top" });
s.addShape(pres.shapes.LINE, { x: 8.75, y: 3.93, w: 0.55, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
card(s, 9.45, 2.85, 3.38, 2.15, BG_DARK);
s.addText([
  { text: "Advisory + cited context", options: { fontSize: 14, bold: true, color: LIGHT, breakLine: true } },
  { text: "Passages and tiles attached to every recommendation \u2014 the dashboard shows them next to the score", options: { fontSize: 11.5, color: LMUT } },
], { x: 9.7, y: 3.02, w: 2.9, h: 1.85, fontFace: SANS, margin: 0, valign: "top" });
s.addText([
  { text: "Explainability is the retrieval of verifiable sources \u2014 not generated prose.", options: { breakLine: true } },
  { text: "Scalable by design: new sources plug in as chunked documents \u2014 no model retraining; the corpus grows per region.", options: {} },
], { x: M, y: 6.2, w: 12.33, h: 0.8, fontSize: 13.5, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, margin: 0 });
pageNum(s, 10);
s.addNotes("Two Qdrant collections: text (rules and knowledge) and satellite tiles. Hybrid retrieval pre-filters by space and time, then ranks by similarity. The output is an advisory with its citations attached. Scalability: new regulations, guidance, satellite passes and whole regional corpora are added by chunking, embedding and upserting - knowledge lives in the corpus, not the weights, so no model retraining is ever needed.");

/* ============ S11 — Grounded AI assistant ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 conversational layer (P7)");
title(s, "A grounded AI assistant explains - it never decides");
const boxes11 = [
  [M, 1.85, "Inputs (grounding only)", "Live advisory JSON \u00B7 top-k retrieved passages \u00B7 optional image (catch photo, tile, chart) \u00B7 user question + language", "FFFFFF", PRIMARY],
  [4.62, 1.85, "Qwen2.5-VL-7B (AWQ)", "Single open-source VLM, Apache 2.0 \u00B7 4-bit weights \u2248 6.9 GB \u00B7 served locally on vLLM with continuous batching", PRIMARY_LT, null],
  [8.74, 1.85, "Guardrails (in code)", "Citations must resolve to retrieved passages \u00B7 verdict is authoritative \u00B7 refusal over invention \u00B7 backend named on every answer", "FFFFFF", ACCENT],
];
boxes11.forEach(b => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: b[0], y: b[1], w: 3.9, h: 2.15, rectRadius: 0.07,
    fill: { color: b[4] }, line: { color: b[5] || "D8E2E6", width: 1.25 }, shadow: shadow() });
  s.addText([
    { text: b[2], options: { fontSize: 13.5, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: b[3], options: { fontSize: 11, color: TEXT } },
  ], { x: b[0] + 0.25, y: b[1] + 0.2, w: 3.4, h: 1.8, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 6 });
});
s.addShape(pres.shapes.LINE, { x: 4.45, y: 2.9, w: 0.12, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
s.addShape(pres.shapes.LINE, { x: 8.57, y: 2.9, w: 0.12, h: 0, line: { color: PRIMARY, width: 2.2, endArrowType: "triangle" } });
card(s, M, 4.35, 12.33, 1.35, PRIMARY_LT);
s.addText([
  { text: "Output: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "plain-language summary or cited answer + backend ID + authoritative verdict. If the GPU is down, a deterministic template path assembles the same schema from the same data \u2014 the website never goes dark.", options: { color: TEXT } },
], { x: 0.8, y: 4.35, w: 11.7, h: 1.35, fontSize: 13, fontFace: SANS, valign: "middle", margin: 0 });
s.addText([
  { text: "Multilingual and scalable by design: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "answers in ten coastal languages, vernacular fish names, localised Problem/Answer self-explanations, ocean news translated into the reader's language (English pivot); a runtime model registry switches quality against hardware (3B laptop " + '"' + "> 72B datacenter).", options: { color: TEXT } },
], { x: M, y: 5.95, w: 12.33, h: 0.75, fontSize: 11.5, fontFace: SANS, margin: 0, valign: "top" });
s.addText("T5 asserts: class consistency, citation integrity, cache, fallback, backend naming. T6 asserts: rate limits, 401/403 role gates, security headers, body cap.", {
  x: M, y: 6.72, w: 12.33, h: 0.4, fontSize: 11, italic: true, color: MUTED, fontFace: SANS, margin: 0 });
pageNum(s, 11);
s.addNotes("The assistant layer: one self-hosted vision-language model serves summaries, grounded Q&A and image reading. The guardrails are code, not prompts: citations must resolve, the advisory class is authoritative, refusal beats invention, every answer names its backend, and a deterministic template path covers GPU-less deployments. Validation family T5 asserts each guarantee.");

/* ============ S12 — Production deployment ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 production deployment");
title(s, "Local AI on one GPU - no API bills at any traffic");
const th12 = { fill: { color: PRIMARY }, color: "FFFFFF", bold: true, fontFace: SANS, fontSize: 10.5, valign: "middle", align: "left" };
const td12 = { fontFace: SANS, fontSize: 10.5, color: TEXT, valign: "middle" };
const rows12 = [
  [{ text: "Tier", options: th12 }, { text: "Hardware", options: th12 }, { text: "Model / profile", options: th12 }, { text: "Sustains", options: th12 }],
  [{ text: "L \u00B7 laptop", options: td12 }, { text: "RTX 4050 Laptop, 6 GB", options: td12 }, { text: "Qwen2.5-VL-3B, Q4 \u00B7 6 k ctx \u00B7 1-2 concurrent", options: td12 }, { text: "Personal use, demos", options: td12 }],
  [{ text: "1 \u00B7 pilot", options: td12 }, { text: "RTX 3060/4070, 12 GB", options: td12 }, { text: "7B AWQ \u00B7 8 k ctx \u00B7 8 concurrent", options: td12 }, { text: "Thousands of requests/day", options: td12 }],
  [{ text: "2 \u00B7 recommended", options: { ...td12, bold: true, color: PRIMARY_DK, fill: { color: PRIMARY_LT } } }, { text: "RTX 4090 / NVIDIA L4, 24 GB", options: { ...td12, fill: { color: PRIMARY_LT } } }, { text: "7B AWQ \u00B7 16 k ctx \u00B7 32-64 concurrent", options: { ...td12, fill: { color: PRIMARY_LT } } }, { text: "Tens of thousands/day", options: { ...td12, fill: { color: PRIMARY_LT } } }],
  [{ text: "3 \u00B7 regional", options: td12 }, { text: "2-4\u00D7 L4/A10G + LB, or A100 40 GB", options: td12 }, { text: "7B AWQ replicas + semantic cache", options: td12 }, { text: "Millions of requests/year", options: td12 }],
];
s.addTable(rows12, { x: M, y: 1.8, w: 12.33, colW: [1.9, 3.4, 4.23, 2.8],
  border: { pt: 0.5, color: "D8E2E6" }, rowH: 0.55, margin: 0.06 });
const econ = [
  ["$0 per question", "Self-hosted inference: the marginal cost of an answer is electricity."],
  ["~$16-55k/yr avoided", "Per-token billing for 10k questions/day at commercial API rates."],
  ["~$2k once + $315/yr", "The recommended 24 GB tier: one GPU plus power, owned outright."],
];
econ.forEach((e, i) => {
  const x = M + i * 4.2;
  card(s, x, 4.85, 3.9, 1.75, PRIMARY_LT);
  s.addText([
    { text: e[0], options: { fontSize: 17, bold: true, color: PRIMARY_DK, breakLine: true, fontFace: SERIF } },
    { text: e[1], options: { fontSize: 11.5, color: TEXT } },
  ], { x: x + 0.28, y: 5.05, w: 3.35, h: 1.4, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 6 });
});
srcLine(s, "Hardened for public traffic: per-endpoint rate limits, API-key RBAC (public/officer/admin), security headers, audit log; ships as an installable PWA with an offline app shell (tailnet deployment guide). Serving: vLLM + AWQ, semaphore + summary cache.");
pageNum(s, 12);
s.addNotes("The economic argument for self-hosting: at 10,000 questions per day, commercial per-token APIs would cost 16-55k dollars a year; the recommended tier is a 2,000-dollar GPU plus electricity. Four validated hardware tiers, from a 6 GB laptop (3B model) to multi-GPU regional deployments, ship with the reference implementation.");

/* ============ S13 — Advisory engine (fig2) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "System \u00B7 advisory");
title(s, "One transparent sustainability index");
img(s, "fig2_scoring.png", AR.f2, 6.5, M, 1.85);
s.addText("S = 0.45\u00B7C + 0.25\u00B7W + 0.30\u00B7(1 \u2212 B)", {
  x: 7.4, y: 1.95, w: 5.43, h: 0.6, fontSize: 21, bold: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
const classes = [
  ["PROCEED", "S \u2265 0.75"],
  ["PROCEED WITH CAUTION", "0.60 \u2264 S < 0.75"],
  ["DELAY OR RELOCATE", "0.40 \u2264 S < 0.60"],
  ["DO NOT FISH", "S < 0.40"],
];
classes.forEach((cl, i) => {
  const y = 2.75 + i * 0.62;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.4, y, w: 3.1, h: 0.5, rectRadius: 0.1,
    fill: { color: i === 3 ? ACCENT : PRIMARY_LT }, line: { color: "FFFFFF", width: 0 } });
  s.addText(cl[0], { x: 7.4, y, w: 3.1, h: 0.5, fontSize: 11, bold: true,
    color: i === 3 ? "FFFFFF" : PRIMARY_DK, fontFace: SANS, align: "center", valign: "middle", margin: 0 });
  s.addText(cl[1], { x: 10.6, y, w: 2.2, h: 0.5, fontSize: 11.5, color: TEXT,
    fontFace: SANS, valign: "middle", margin: 0 });
});
s.addText([
  { text: "Hard rule: ", options: { bold: true, color: ACCENT } },
  { text: "inside an active MPA or seasonal closure, the advisory is DO NOT FISH \u2014 regardless of score. Weights are configuration, owned by governance, not hidden constants.", options: { color: TEXT } },
], { x: 7.4, y: 5.45, w: 5.43, h: 1.35, fontSize: 12, fontFace: SANS, margin: 0, valign: "top" });
srcLine(s, "Surface shows S over catch likelihood (C) and weather safety (W) at bycatch risk B = 0.20.");
pageNum(s, 13);
s.addNotes("Scoring is a weighted sum: catch 45%, weather safety 25%, ecological term 30%. Monotonic in every input, thresholds fixed at 0.40/0.60/0.75. Constraints run before scoring - no weight configuration can legalise an illegal trip.");

/* ============ S14 — Case study (fig4) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Case study");
title(s, "Southwest coast of India");
img(s, "fig4_calendar.png", AR.f4, 7.1, M, 1.9);
s.addText("Why this coast", { x: 8.0, y: 1.95, w: 4.83, h: 0.4, fontSize: 15, bold: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Active closure regime: June\u2013July monsoon closure, spawning protection for the oil sardine", options: { bullet: bu(), breakLine: true } },
  { text: "A network of marine protected areas enforced as hard constraints", options: { bullet: bu(), breakLine: true } },
  { text: "Sardine and mackerel fisheries dominate \u2014 and fluctuate strongly year to year", options: { bullet: bu(), breakLine: true } },
  { text: "Four coastal cities anchor the live-fetch validation tests", options: { bullet: bu() } },
], { x: 8.0, y: 2.45, w: 4.83, h: 2.6, fontSize: 12, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 9, margin: 0, valign: "top" });
s.addText([
  { text: "Registry: ", options: { bold: true, color: PRIMARY_DK } },
  { text: "Sardinella longiceps, Rastrelliger kanagurta, Thunnus tonggol, Penaeus monodon \u2014 the prawn exercises the data-poor habitat fallback.", options: { italic: true, color: TEXT } },
], { x: 8.0, y: 5.35, w: 4.83, h: 1.3, fontSize: 11.5, fontFace: SANS, margin: 0, valign: "top" });
srcLine(s, "Calendar is the schematic configured for the case study; landings context: ICAR-CMFRI.");
pageNum(s, 14);
s.addNotes("The case study concentrates every challenge: closures, protected areas, volatile small pelagics, and a data-poor high-value taxon. Cross-hatch marks the June-July spawning closure on the sardine.");

/* ============ S15 — Methodology (fig3) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Methodology");
title(s, "Phase-gate engineering, test-driven acceptance");
const h13 = img(s, "fig3_phases.png", AR.f3, 12.33, M, 1.55);
const tests = [
  ["T1", "Live fetch"], ["T2", "Rule enforcement"], ["T3", "Scoring behaviour"], ["T4", "Retrieval relevance"], ["T5", "Assistant behaviour"], ["T6", "Security behaviour"],
];
tests.forEach((t, i) => {
  const x = M + i * 2.09;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 6.15, w: 1.94, h: 0.62, rectRadius: 0.1,
    fill: { color: PRIMARY_LT }, line: { color: "FFFFFF", width: 0 } });
  s.addText([
    { text: t[0] + "  ", options: { bold: true, color: ACCENT } },
    { text: t[1], options: { color: PRIMARY_DK, bold: true } },
  ], { x, y: 6.15, w: 1.94, h: 0.62, fontSize: 9.5, fontFace: SANS, align: "center", valign: "middle", margin: 0 });
});
pageNum(s, 15);
s.addNotes("Seven phases, each closed by a gate that must pass before the next begins. Gates map one-to-one onto the five test families - every capability claim is tied to a test, including the assistant's grounding and guardrail guarantees (T5).");

/* ============ S16 — Results (fig6) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Results");
title(s, "Validated end to end");
const h14 = img(s, "fig6_monotonic.png", AR.f6, 10.6, 1.37, 1.6);
const findings = [
  ["Live fetches reliable", "Graceful degradation under outage, with explicit age flags"],
  ["Closure blocks exact", "June sardine request returns DO NOT FISH with the reason"],
  ["Scoring monotonic", "In every input; class thresholds land exactly as configured"],
  ["Retrieval relevant", "Top-k context attached to every advisory on the dashboard"],
  ["Assistant guarded", "Citations resolve; verdicts hold; template fallback exact"],
  ["Service hardened", "Rate limits 429; 401/403 role gates; headers on every response"],
];
findings.forEach((f, i) => {
  const x = M + i * 2.09;
  card(s, x, 5.55, 1.94, 1.45, PRIMARY_LT);
  s.addText([
    { text: f[0], options: { fontSize: 10.5, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: f[1], options: { fontSize: 8.5, color: TEXT } },
  ], { x: x + 0.12, y: 5.68, w: 1.7, h: 1.2, fontFace: SANS, margin: 0, valign: "top" });
});
srcLine(s, "Panels: one-at-a-time sweeps over C, W and B (markers = baseline point); illustrative of the configured function.");
pageNum(s, 16);
s.addNotes("Six findings: reliable live ingestion; exact rule enforcement; monotonic scoring; topically relevant retrieval; guarded assistant behaviour (T5); and a hardened service (T6) - rate limits, role gates, headers. Panels show the monotonicity sweeps from test family T3.");

/* ============ S17 — Closing (dark) ============ */
s = pres.addSlide();
s.background = { color: BG_DARK };
kicker(s, "Conclusion", true);
s.addText("Conservation, legality and safety are built into the objective function \u2014 ParaSail cannot recommend an illegal trip under any configuration.", {
  x: M, y: 0.95, w: 12.33, h: 1.5, fontSize: 25, bold: true, color: LIGHT, fontFace: SERIF, margin: 0 });
s.addText("Primary alignment: SDG 14 (Life Below Water)  \u00B7  supporting: SDG 2 \u00B7 8 \u00B7 9 \u00B7 13", {
  x: M, y: 2.55, w: 12.33, h: 0.4, fontSize: 12.5, color: LMUT, fontFace: SANS, margin: 0 });
s.addText("The five mandatory summit questions", { x: M, y: 3.15, w: 12.33, h: 0.4, fontSize: 14, bold: true, color: LIGHT, fontFace: SERIF, margin: 0 });
const qa = [
  ["Q1 \u00B7 Problem", "No real-time, integrated, explainable advisory system for sustainable fishing in data-poor regions."],
  ["Q2 \u00B7 Importance", "Livelihoods, food security, marine conservation and safety all meet at this one information gap."],
  ["Q3 \u00B7 Technology", "Geospatial AI (YOLOv8, ViT + LoRA, LSTM, random forest), dual-collection RAG, a self-hosted Qwen2.5-VL-7B assistant on vLLM with a runtime model registry, open live APIs, FastAPI + PostGIS + Qdrant; hardened with rate limiting and RBAC, shipped as an installable PWA."],
  ["Q4 \u00B7 Evidence", "Open environmental, biodiversity and satellite data; regulation datasets; a working system validated by five test families."],
  ["Q5 \u00B7 Contribution", "A production-grade platform issuing sustainability-scored, explainable, conversational advisories with conservation enforced as a hard constraint - on local AI, within 8-12 GB VRAM, at zero marginal cost."],
];
qa.forEach((q, i) => {
  const y = 3.65 + i * 0.58;
  s.addText([
    { text: q[0] + "   ", options: { bold: true, color: ACCENT } },
    { text: q[1], options: { color: LIGHT } },
  ], { x: M, y, w: 12.33, h: 0.52, fontSize: 11.5, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("Thank you  \u00B7  Anantha Krishnan AS  \u00B7  Naipunnya School of Management, Cherthala, India  \u00B7  26th Digital Blue Economy Summit", {
  x: M, y: 6.75, w: 12.33, h: 0.4, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
pageNum(s, 17, true);
s.addNotes("Close on the normative claim: constraints inside the objective function, trust earned through explainability and local adaptation. Then the five mandatory questions in one pass.");

pres.writeFile({ fileName: "ParaSail_Presentation_TechnicalBackup.pptx" }).then(() => console.log("WROTE ParaSail_Presentation_TechnicalBackup.pptx"));

/* ParaSail - 10-slide deck for a GENERAL AUDIENCE (pptxgenjs, 13.33x7.5in).
 * Problem -> solution -> proof -> impact, in plain language. Interactive:
 * a linked contents card grid, a "contents" home link on every slide, and
 * click-to-reveal animation on the four-signal slide (added by
 * add_interactivity.py, which also writes transitions + entrance builds).
 * (Technical version: build_deck_technical.js) */
const pptxgen = require("pptxgenjs");

const W = 13.33, H = 7.5, M = 0.5;
const BG_DARK = "0A2E3C", CARD_DK = "12455A";
const PRIMARY = "14707C", PRIMARY_DK = "0E4A54", PRIMARY_LT = "E3EFF1";
const ACCENT = "E76F51", TEXT = "16323D", MUTED = "6B8290";
const LIGHT = "F2F8F9", LMUT = "9DB8C0";
const TL = { go: "4C9A57", careful: "D9A62E", wait: "D97E35", stop: "C94F4F" };
const SERIF = "Georgia", SANS = "Segoe UI";

const CONTENTS_SLIDE = 2;          // 1-based slide number of the contents hub
const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 2, angle: 45, opacity: 0.14 });
const bu = () => ({ code: "2022", indent: 12 });
const link = (n) => ({ slide: n });   // internal slide hyperlink

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Anantha Krishnan AS";
pres.title = "ParaSail - a smart guide for safer fishing and healthier oceans";

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
function srcLine(s, t) {
  s.addText(t, { x: M, y: H - 0.44, w: 9.9, h: 0.3, fontSize: 10,
    color: MUTED, fontFace: SANS, margin: 0 });
}
/* home link - interactive navigation back to the contents hub */
function homeLink(s, dark) {
  s.addText("\u2630  CONTENTS", { x: W - 2.35, y: 0.42, w: 1.85, h: 0.32, fontSize: 10,
    color: dark ? LMUT : PRIMARY, fontFace: SANS, bold: true, align: "right",
    charSpacing: 1, margin: 0, hyperlink: link(CONTENTS_SLIDE) });
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07,
    fill: { color: fill }, line: { color: "FFFFFF", width: 0 }, shadow: shadow() });
}
function outlineCard(s, x, y, w, h, dash) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07,
    fill: { color: "FFFFFF" }, line: { color: dash ? "A9C2CB" : "D8E2E6", width: 1.25,
    dashType: dash ? "dash" : "solid" }, shadow: shadow() });
}
/* numbered circle + lead/description row (container-free grouping) */
function numRow(s, n, lead, desc, y, x, w, leadSize, descSize, color) {
  const c = color || PRIMARY;
  s.addShape(pres.shapes.OVAL, { x, y: y + 0.05, w: 0.6, h: 0.6,
    fill: { color: c }, line: { color: c, width: 0 } });
  s.addText(n, { x, y: y + 0.05, w: 0.6, h: 0.6, fontSize: 15, bold: true,
    color: "FFFFFF", fontFace: SANS, align: "center", valign: "middle", margin: 0 });
  s.addText([
    { text: lead, options: { fontSize: leadSize, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: desc, options: { fontSize: descSize, color: TEXT } },
  ], { x: x + 0.95, y, w, h: 1.2, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 4 });
}
/* small diamond marker used by the structured-explanation mockup */
function diamond(s, x, y, color) {
  s.addShape(pres.shapes.DIAMOND, { x, y, w: 0.13, h: 0.13, fill: { color }, line: { color, width: 0 } });
}

/* ============ S1 - Title (dark) ============ */
let s = pres.addSlide();
s.background = { color: BG_DARK };
s.addText("26TH DIGITAL BLUE ECONOMY SUMMIT", {
  x: 0.9, y: 1.25, w: 11.5, h: 0.34, fontSize: 12, color: LMUT, charSpacing: 3,
  fontFace: SANS, bold: true, margin: 0 });
s.addText("ParaSail", { x: 0.9, y: 1.66, w: 11.5, h: 1.5, fontSize: 76,
  color: LIGHT, fontFace: SERIF, bold: true, margin: 0 });
s.addText("A smart guide for safer fishing and healthier oceans", {
  x: 0.9, y: 3.22, w: 11.0, h: 0.5, fontSize: 20, color: LIGHT, fontFace: SANS, margin: 0 });
s.addText("Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods", {
  x: 0.9, y: 3.80, w: 11.0, h: 0.36, fontSize: 12.5, italic: true, color: LMUT,
  fontFace: SERIF, margin: 0 });
const qs = ["Is it safe to sail?", "Are the fish there?", "Is it allowed?"];
qs.forEach((q, i) => {
  const cx = 0.9 + i * 3.95;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 4.72, w: 3.7, h: 0.62,
    rectRadius: 0.31, fill: { color: CARD_DK }, line: { color: "2A5A6E", width: 1 } });
  s.addText(q, { x: cx, y: 4.72, w: 3.7, h: 0.62, fontSize: 14, color: LIGHT,
    fontFace: SANS, align: "center", valign: "middle", margin: 0 });
});
s.addText("One simple answer to all three questions - before you leave the harbour.", {
  x: 0.9, y: 5.60, w: 11.0, h: 0.4, fontSize: 14, color: LMUT, fontFace: SANS, margin: 0 });
s.addText("Anantha Krishnan AS  \u00B7  Naipunnya School of Management, Cherthala, India  \u00B7  September 2026", {
  x: 0.9, y: 6.55, w: 11.5, h: 0.35, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
s.addNotes("Open with the three questions every fisher asks before sailing. ParaSail answers all three in one place, in plain language. The deck is interactive: the next slide is a contents hub - every card jumps to its section, and the \u2630 CONTENTS link returns here from any slide.");

/* ============ S2 - Contents (interactive hub) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Contents");
title(s, "What we will cover");
const toc = [
  ["The problem", "Why fishers and the ocean both need better information", 3],
  ["The answer", "One clear answer: GO, GO CAREFULLY, WAIT OR MOVE, STOP", 4],
  ["What you see", "The answer in plain words - with its reasons listed", 5],
  ["The honest map", "Where the fish likely are - and where you must not go", 6],
  ["Ask the AI", "A local AI helper that cites its sources", 7],
  ["The evidence", "What we tested - and what it proved", 8],
  ["Who wins", "Fishers, the ocean, communities, authorities", 9],
  ["Conclusion", "One simple idea, and what comes next", 10],
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
s.addText("Tap any card to jump straight to that part of the story.", {
  x: M, y: 6.32, w: 12.33, h: 0.4, fontSize: 11.5, italic: true, color: MUTED,
  fontFace: SERIF, margin: 0 });
s.addNotes("Interactive contents: each card is a hyperlink to its slide. Use it to jump around during Q&A instead of paging through.");

/* ============ S3 - The problem ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem");
title(s, "Why fishing needs help");
homeLink(s);
const stats = [
  ["1 in 3", "fish populations are now overfished", "FAO, 2023"],
  ["3\u00D7 more", "plastic flowing into the ocean by 2040", "UNEP, 2023"],
  ["500 million", "people depend on small-scale fishing", "FAO, 2023"],
];
stats.forEach((st, i) => {
  const x = M + i * 4.2;
  s.addText(st[0], { x, y: 1.62, w: 3.9, h: 0.95, fontSize: 44, bold: true,
    color: ACCENT, fontFace: SERIF, margin: 0 });
  s.addText(st[1], { x, y: 2.62, w: 3.8, h: 0.75, fontSize: 13, bold: true,
    color: TEXT, fontFace: SANS, margin: 0 });
  s.addText(st[2], { x, y: 3.34, w: 3.8, h: 0.35, fontSize: 10.5,
    color: MUTED, fontFace: SANS, margin: 0 });
});
const harms = [
  ["Fish are moving", "Warming seas push fish to new waters, and the old seasonal calendars drift out of step."],
  ["Spawning is disturbed", "Fishing while fish breed leaves fewer fish for everyone next year."],
  ["The sea is dangerous", "District-wide forecasts say nothing about the wind and waves off your own ground."],
  ["Rules are hard to check", "Boundaries and closed seasons live in offices and on paper - not at sea."],
];
harms.forEach((hm, i) => {
  const x = M + i * 3.14;
  diamond(s, x, 3.98, i === 0 ? ACCENT : PRIMARY);
  s.addText(hm[0], { x: x + 0.28, y: 3.85, w: 2.68, h: 0.4, fontSize: 14.5, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(hm[1], { x, y: 4.32, w: 2.95, h: 1.9, fontSize: 11.5, color: TEXT,
    fontFace: SANS, margin: 0, valign: "top" });
});
srcLine(s, "Sources: FAO State of World Fisheries 2023; UNEP Turning off the Tap 2023; Cheung et al. 2010.");
pageNum(s, 3);
s.addNotes("Frame it in one slide: a third of stocks overfished, plastic tripling, half a billion livelihoods - and four daily problems: fish move, spawning is disturbed, the sea is dangerous, and the rules are hard to check at sea. Everything that follows answers these four.");

/* ============ S4 - Meet ParaSail: four signals (click to reveal) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution");
title(s, "Meet ParaSail - one clear answer");
homeLink(s);
s.addText("Like a weather app - but for fishing.", {
  x: M, y: 1.85, w: 4.7, h: 0.9, fontSize: 23, bold: true, color: PRIMARY,
  fontFace: SERIF, margin: 0 });
s.addText("You tell it where you will fish, what you are catching and when. Before you leave the harbour it gives you one simple answer - and the reasons behind it.", {
  x: M, y: 2.85, w: 4.7, h: 1.8, fontSize: 13.5, color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
s.addText("Free  \u00B7  in your language  \u00B7  installs like a phone app", {
  x: M, y: 4.75, w: 4.7, h: 0.4, fontSize: 12, bold: true, color: PRIMARY_DK,
  fontFace: SANS, margin: 0 });
s.addText("Click to reveal each signal", {
  x: 5.75, y: 1.60, w: 4.0, h: 0.28, fontSize: 10.5, italic: true, color: MUTED,
  fontFace: SANS, margin: 0 });
const signals = [
  [TL.go, "GO", "Calm seas, fish likely, zone open - safe to sail."],
  [TL.careful, "GO CAREFULLY", "Fishing is possible - but watch the changing weather."],
  [TL.wait, "WAIT OR MOVE", "Rough seas or young fish nearby - wait, or try another spot."],
  [TL.stop, "STOP", "Not safe, or not allowed. Stay ashore today."],
];
signals.forEach((sg, i) => {
  const y = 1.95 + i * 1.09;
  s.addShape(pres.shapes.OVAL, { x: 5.8, y: y + 0.06, w: 0.66, h: 0.66,
    fill: { color: sg[0] }, line: { color: "FFFFFF", width: 0 }, shadow: shadow() });
  s.addText([
    { text: sg[1], options: { fontSize: 16.5, bold: true, color: sg[0], breakLine: true } },
    { text: sg[2], options: { fontSize: 12.5, color: TEXT } },
  ], { x: 6.75, y, w: 6.05, h: 0.95, fontFace: SANS, margin: 0, valign: "top", paraSpaceAfter: 3 });
});
s.addText([
  { text: "Protected area or closed season? ", options: { bold: true, color: ACCENT } },
  { text: "The answer is always STOP - whatever the weather.", options: { color: PRIMARY_DK } },
], { x: 5.8, y: 6.35, w: 7.0, h: 0.5, fontSize: 13, fontFace: SANS, margin: 0 });
pageNum(s, 4);
s.addNotes("The four answers are a traffic light everyone already understands. Reveal them one at a time - ask the room to guess the colour for 'rough seas with young fish nearby'. The hard rule: protected areas and closed seasons are always STOP.");

/* ============ S5 - What you actually see ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution \u00B7 the answer");
title(s, "What you actually see");
homeLink(s);
outlineCard(s, M, 1.8, 6.15, 4.45);
s.addText("TOMORROW, 5 AM \u2014 OFF KOCHI", { x: 0.85, y: 2.02, w: 5.5, h: 0.35,
  fontSize: 12, bold: true, color: MUTED, charSpacing: 1, fontFace: SANS, margin: 0 });
s.addText("GO", { x: 0.85, y: 2.38, w: 5.5, h: 1.0, fontSize: 48, bold: true,
  color: TL.go, fontFace: SERIF, margin: 0 });
s.addText("PLAIN-LANGUAGE EXPLANATION", { x: 0.85, y: 3.42, w: 5.5, h: 0.3,
  fontSize: 10, bold: true, color: PRIMARY, charSpacing: 2, fontFace: SANS, margin: 0 });
const pointRows = [
  ["GO \u2014 calm seas.", 0],
  ["Sea right now: wind 12 km/h, waves 0.8 m, currents 1.2 km/h.", 1],
  ["Indian oil sardine likely in this area.", 2],
  ["Risk to young fish and habitats: low.", 3],
];
pointRows.forEach((pr) => {
  const y = 3.82 + pr[1] * 0.58;
  diamond(s, 0.88, y + 0.09, PRIMARY);
  s.addText(pr[0], { x: 1.14, y: y - 0.02, w: 5.05, h: 0.55, fontSize: 12.5,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("Every point is a separate reason you can check - not a wall of text.", {
  x: 0.85, y: 6.02, w: 5.5, h: 0.3, fontSize: 10.5, italic: true, color: MUTED,
  fontFace: SERIF, margin: 0 });
outlineCard(s, 7.05, 1.8, 5.78, 1.75);
s.addText("WHILE IT THINKS", { x: 7.35, y: 1.98, w: 5.2, h: 0.3, fontSize: 10.5,
  bold: true, color: MUTED, charSpacing: 2, fontFace: SANS, margin: 0 });
const barH = [0.26, 0.44, 0.34, 0.5];
barH.forEach((bh, i) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.4 + i * 0.17, y: 2.85 - bh, w: 0.1, h: bh,
    rectRadius: 0.02, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
});
s.addText("Reading the sea\u2026", { x: 8.35, y: 2.42, w: 4.1, h: 0.5, fontSize: 17, bold: true,
  color: PRIMARY_DK, fontFace: SERIF, margin: 0, valign: "middle" });
s.addText("A live progress cue - animated wave bars - so you always know it is working.", {
  x: 7.35, y: 2.98, w: 5.2, h: 0.5, fontSize: 11.5, color: TEXT, fontFace: SANS, margin: 0 });
s.addText([
  { text: "Nothing is invented. ", options: { bold: true, color: PRIMARY_DK } },
  { text: "If the data cannot support a claim, the system says so instead of guessing - and the full detail stays one tap away.", options: { color: TEXT } },
], { x: 7.05, y: 3.85, w: 5.78, h: 1.5, fontSize: 12.5, fontFace: SANS, margin: 0, valign: "top" });
s.addText([
  { text: "Simple on purpose. ", options: { bold: true, color: PRIMARY_DK } },
  { text: "A fishers' eye view first; the numbers live behind it for anyone who wants them.", options: { color: TEXT } },
], { x: 7.05, y: 5.35, w: 5.78, h: 1.0, fontSize: 12.5, fontFace: SANS, margin: 0, valign: "top" });
pageNum(s, 5);
s.addNotes("This is the change fishers asked for: instead of a paragraph, the explanation now arrives as separate, checkable points - verdict, conditions, fish likelihood, ecological risk. And while it works, an animated cue shows progress.");

/* ============ S6 - The honest map ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution \u00B7 the map");
title(s, "The map shows where - honestly");
homeLink(s);
const hZone = 6.55 / (16 / 10);
s.addImage({ path: "deck_figures/fig7_zones.png", x: M, y: 1.85, w: 6.55, h: hZone });
s.addText("Illustrative view of the coast, the likely-fish zone and a protected area.", {
  x: M, y: 1.88 + hZone, w: 6.55, h: 0.35, fontSize: 10.5, italic: true,
  color: MUTED, fontFace: SANS, margin: 0 });
numRow(s, "1", "Follows the real coastline",
  "The likely-fish area is drawn from actual shoreline geometry - it never spills over land or into backwaters.", 1.95, 7.4, 4.5, 15, 11.5);
numRow(s, "2", "Protected areas, for real",
  "Real marine-park boundaries. Inside one the answer is STOP - and it names the park you are in.", 3.28, 7.4, 4.5, 15, 11.5);
numRow(s, "3", "Honest when nothing fits",
  "If conditions do not suit the fish, it shows a small honest zone - or none - instead of inventing one.", 4.61, 7.4, 4.5, 15, 11.5);
s.addText("A fishing zone that covers a town, or a 'protected area' you cannot see, protects nothing. The map is built so a fisher can trust it.", {
  x: 7.4, y: 5.85, w: 5.43, h: 1.0, fontSize: 12, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, margin: 0, valign: "top" });
srcLine(s, "Zone geometry: GSHHG shoreline data (public domain) \u00B7 Park outlines: OpenStreetMap contributors (ODbL).");
pageNum(s, 6);
s.addNotes("Two honesty guarantees on one slide. The likely-fish zone is clipped to real shoreline geometry - no lakes, no land. Protected areas use real boundaries, and if you are inside one the answer is STOP with the park named.");

/* ============ S7 - Ask it anything (AI helper) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution \u00B7 the AI helper");
title(s, "Ask it anything - in your own words");
homeLink(s);
outlineCard(s, M, 1.78, 6.35, 3.42);
s.addText("ASK PARASAIL", { x: 0.85, y: 1.95, w: 5.6, h: 0.3, fontSize: 10.5,
  bold: true, color: MUTED, charSpacing: 2, fontFace: SANS, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.6, y: 2.32, w: 3.6, h: 0.62,
  rectRadius: 0.12, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
s.addText("\u201CCan I take my small boat out tomorrow?\u201D", {
  x: 2.75, y: 2.32, w: 3.3, h: 0.62, fontSize: 11.5, color: "FFFFFF",
  fontFace: SANS, valign: "middle", margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.85, y: 3.06, w: 5.2, h: 1.15,
  rectRadius: 0.12, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText([
  { text: "GO CAREFULLY - waves near 1 m in the morning, wind rising after noon. Best back before two.", options: { breakLine: true } },
  { text: "sources: marine forecast \u00B7 rulebook", options: { fontSize: 10.5, italic: true, color: MUTED } },
], { x: 1.0, y: 3.06, w: 4.9, h: 1.15, fontSize: 11.5, color: TEXT,
  fontFace: SANS, valign: "middle", paraSpaceAfter: 4, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.6, y: 4.34, w: 3.6, h: 0.6,
  rectRadius: 0.12, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
s.addText("\u201CAnd in June, for sardine?\u201D", {
  x: 2.75, y: 4.34, w: 3.3, h: 0.6, fontSize: 11.5, color: "FFFFFF",
  fontFace: SANS, valign: "middle", margin: 0 });
outlineCard(s, 6.98, 5.42, 5.85, 1.32);
s.addShape(pres.shapes.OVAL, { x: 7.28, y: 5.85, w: 0.2, h: 0.2,
  fill: { color: TL.go }, line: { color: TL.go, width: 0 } });
s.addText("AI: qwen2.5vl-3b-laptop  \u00B7  READY", {
  x: 7.6, y: 5.72, w: 4.9, h: 0.42, fontSize: 13, bold: true, color: PRIMARY_DK,
  fontFace: SANS, margin: 0, valign: "middle" });
s.addText("It checks what is actually installed on this computer and says so - and if a model is missing, it prints the exact command to get it.", {
  x: 7.28, y: 6.14, w: 5.25, h: 0.55, fontSize: 11, color: TEXT, fontFace: SANS,
  margin: 0, valign: "top" });
numRow(s, "1", "Answers in plain words",
  "Ask like you would ask a neighbour - and it replies in your own language.", 1.85, 6.98, 5.85, 14.5, 11.5);
numRow(s, "2", "Shows its sources",
  "Every answer points to the forecast, rule or local knowledge it used.", 3.02, 6.98, 5.85, 14.5, 11.5);
numRow(s, "3", "Honest about the hardware",
  "It never pretends a model is running when it is not.", 4.19, 6.98, 5.85, 14.5, 11.5);
s.addText("The AI explains the advice - it never overrules it. Closed season? Still STOP.", {
  x: M, y: 6.82, w: 6.35, h: 0.42, fontSize: 11.5, italic: true, color: ACCENT,
  fontFace: SERIF, margin: 0 });
pageNum(s, 7);
s.addNotes("The AI helper answers in the fisher's own words and language, cites sources, and is honest about what hardware it is actually running on - if the model is missing it says so and prints the install command instead of pretending. It explains the advisory; it can never override it.");

/* ============ S8 - Evidence ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The evidence");
title(s, "It worked - here is what we found");
homeLink(s);
const finds = [
  ["Live data kept flowing", "Even when the internet dropped, advice continued - clearly marked as slightly older information."],
  ["Closed seasons were always respected", "Every single test during a closure came back STOP. No exceptions, ever."],
  ["Advice changed sensibly", "When the weather turned or the fish moved, the traffic light changed exactly as it should."],
  ["Every answer explained itself", "The reasons shown next to each advice were checked - and they were the right ones."],
  ["The map stayed over water", "Likely-fish zones followed the coast and never covered land, lakes or backwaters."],
  ["The AI never overruled the verdict", "It explains, cites and defers - the decision stays with the rules, not the model."],
];
finds.forEach((f, i) => {
  const y = 1.82 + i * 0.83;
  s.addText("\u2713", { x: 0.6, y, w: 0.5, h: 0.6, fontSize: 20, bold: true,
    color: TL.go, fontFace: SANS, margin: 0, valign: "middle" });
  s.addText(f[0], { x: 1.2, y, w: 3.6, h: 0.6, fontSize: 14, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0, valign: "middle" });
  s.addText(f[1], { x: 4.95, y, w: 7.9, h: 0.6, fontSize: 12, color: TEXT,
    fontFace: SANS, margin: 0, valign: "middle" });
});
pageNum(s, 8);
s.addNotes("Six findings in plain terms: reliable data even offline, closures always respected, sensible changes with conditions, correct explanations, zones that stay at sea, and an AI that explains without overruling.");

/* ============ S9 - Impact ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The impact");
title(s, "Everyone on the coast wins");
homeLink(s);
const bens = [
  ["Fishers", "Save fuel, stay safer, and avoid fines from honest mistakes."],
  ["The ocean", "Protected zones and spawning seasons are left in peace - automatically."],
  ["Communities", "Generations of fishing knowledge kept in a lasting digital library."],
  ["Authorities", "Clear, fair decisions backed by evidence anyone can see."],
];
bens.forEach((b, i) => {
  const x = M + i * 3.14;
  diamond(s, x, 1.98, PRIMARY);
  s.addText(b[0], { x: x + 0.28, y: 1.85, w: 2.68, h: 0.42, fontSize: 16.5, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(b[1], { x, y: 2.35, w: 2.95, h: 1.75, fontSize: 12, color: TEXT,
    fontFace: SANS, margin: 0, valign: "top" });
});
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.35, w: W, h: 1.5, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText("Made for your coast", { x: 0.85, y: 4.55, w: 11.8, h: 0.4, fontSize: 15,
  bold: true, color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
s.addText("Quick to set up for a new coast  \u00B7  runs on an ordinary computer  \u00B7  installs like a phone app on the boat  \u00B7  answers in your language, local fish names included", {
  x: 0.85, y: 5.0, w: 11.8, h: 0.7, fontSize: 13, color: TEXT, fontFace: SANS, margin: 0 });
s.addText("Next: a season-long trial with fishing communities, and voice guidance for hands-free use at sea.", {
  x: M, y: 6.25, w: 12.33, h: 0.5, fontSize: 13.5, italic: true, color: ACCENT,
  fontFace: SERIF, margin: 0 });
pageNum(s, 9);
s.addNotes("Four winners - fishers, the ocean, communities, authorities - and one system. Close the loop with what is next: a season-long community trial and voice guidance.");

/* ============ S10 - Closing (dark) ============ */
s = pres.addSlide();
s.background = { color: BG_DARK };
kicker(s, "One simple idea", true);
homeLink(s, true);
s.addText("Fish smarter. Stay safe.\nKeep the ocean giving.", {
  x: M, y: 1.3, w: 12.33, h: 2.0, fontSize: 40, bold: true, color: LIGHT,
  fontFace: SERIF, margin: 0 });
s.addText("ParaSail answers three questions every fisher already asks - is it safe, are the fish there, is it allowed - and shows its reasons every single time.", {
  x: M, y: 3.45, w: 11.6, h: 0.9, fontSize: 16, color: LMUT, fontFace: SANS, margin: 0 });
s.addText("The phone app is here today - installed from the website, it works offline and speaks your language. Next: a season-long trial with fishing communities, and voice guidance.", {
  x: M, y: 4.55, w: 11.6, h: 0.75, fontSize: 14, italic: true, color: LMUT, fontFace: SERIF, margin: 0 });
s.addText("Aligned with the UN Sustainable Development Goals: 14 Life Below Water \u00B7 2 Zero Hunger \u00B7 8 Decent Work \u00B7 9 Innovation \u00B7 13 Climate Action", {
  x: M, y: 5.3, w: 12.33, h: 0.4, fontSize: 11.5, color: LMUT, fontFace: SANS, margin: 0 });
s.addText("Thank you", { x: M, y: 5.85, w: 12.33, h: 0.7, fontSize: 26, bold: true,
  color: LIGHT, fontFace: SERIF, margin: 0 });
s.addText("Anantha Krishnan AS  \u00B7  Naipunnya School of Management, Cherthala, India  \u00B7  26th Digital Blue Economy Summit", {
  x: M, y: 6.6, w: 12.33, h: 0.4, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
pageNum(s, 10, true);
s.addNotes("Close with the promise: fish smarter, stay safe, keep the ocean giving - then thank the audience and invite questions. The \u2630 CONTENTS link returns to the hub for jumping back into any section.");

pres.writeFile({ fileName: "ParaSail_Presentation (Ananthakrishnan AS).pptx" }).then(() => console.log("WROTE ParaSail_Presentation (Ananthakrishnan AS).pptx (10 slides, problem-led)"));

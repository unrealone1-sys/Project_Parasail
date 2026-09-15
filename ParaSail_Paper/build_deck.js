/* ParaSail - 15-slide deck for a GENERAL AUDIENCE (pptxgenjs, 13.33x7.5in).
 * Problem-led narrative: 6 slides on what is going wrong and what is at
 * stake, then the solution in plain terms (traffic light, what you see,
 * trust, local fit), evidence, and who benefits. No technical topics.
 * (Technical version: build_deck_technical.js) */
const pptxgen = require("pptxgenjs");

const W = 13.33, H = 7.5, M = 0.5;
const BG_DARK = "0A2E3C", CARD_DK = "12455A";
const PRIMARY = "14707C", PRIMARY_DK = "0E4A54", PRIMARY_LT = "E3EFF1";
const ACCENT = "E76F51", TEXT = "16323D", MUTED = "6B8290";
const LIGHT = "F2F8F9", LMUT = "9DB8C0";
const TL = { go: "4C9A57", careful: "D9A62E", wait: "D97E35", stop: "C94F4F" };
const SERIF = "Georgia", SANS = "Segoe UI";

const shadow = () => ({ type: "outer", color: "000000", blur: 7, offset: 2, angle: 45, opacity: 0.14 });
const bu = () => ({ code: "2022", indent: 12 });

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Anantha Krishnan AS";
pres.title = "ParaSail - a smart guide for safer fishing and healthier oceans";

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
function srcLine(s, t) {
  s.addText(t, { x: M, y: H - 0.44, w: 10.5, h: 0.3, fontSize: 10,
    color: MUTED, fontFace: SANS, margin: 0 });
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
function rows(s, items, y0, step, leadSize, descSize) {
  items.forEach((it, i) => {
    const y = y0 + i * step;
    s.addShape(pres.shapes.OVAL, { x: 0.62, y: y + 0.05, w: 0.6, h: 0.6,
      fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
    s.addText(String(i + 1), { x: 0.62, y: y + 0.05, w: 0.6, h: 0.6, fontSize: 15,
      bold: true, color: "FFFFFF", fontFace: SANS, align: "center", valign: "middle", margin: 0 });
    s.addText([
      { text: it[0], options: { fontSize: leadSize, bold: true, color: PRIMARY_DK, breakLine: true } },
      { text: it[1], options: { fontSize: descSize, color: TEXT } },
    ], { x: 1.6, y, w: 11.1, h: step - 0.1, fontFace: SANS, margin: 0, valign: "top" });
  });
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
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 4.75, w: 3.7, h: 0.62,
    rectRadius: 0.31, fill: { color: CARD_DK }, line: { color: "2A5A6E", width: 1 } });
  s.addText(q, { x: cx, y: 4.75, w: 3.7, h: 0.62, fontSize: 14, color: LIGHT,
    fontFace: SANS, align: "center", valign: "middle", margin: 0 });
});
s.addText("One simple answer to all three questions - before you leave the harbour.", {
  x: 0.9, y: 5.65, w: 11.0, h: 0.4, fontSize: 14, color: LMUT, fontFace: SANS, margin: 0 });
s.addText("Anantha Krishnan AS  \u00B7  Naipunnya School of Management, Cherthala, India  \u00B7  September 2026", {
  x: 0.9, y: 6.6, w: 11.5, h: 0.35, fontSize: 12, color: LMUT, fontFace: SANS, margin: 0 });
s.addNotes("Open with the three questions every fisher asks before sailing. ParaSail answers all three in one place, in plain language.");

/* ============ S2 - The sea is changing (stats) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The big picture");
title(s, "The sea is changing - fast");
const stats = [
  ["1 in 3", "fish populations are now overfished", "FAO, 2023"],
  ["3\u00D7 more", "plastic flowing into the ocean by 2040", "UNEP, 2023"],
  ["500 million", "people depend on small-scale fishing", "FAO, 2023"],
];
stats.forEach((st, i) => {
  const x = M + i * 4.2;
  s.addText(st[0], { x, y: 1.9, w: 3.9, h: 1.1, fontSize: 56, bold: true,
    color: ACCENT, fontFace: SERIF, margin: 0 });
  s.addText(st[1], { x, y: 3.1, w: 3.8, h: 0.85, fontSize: 15, bold: true,
    color: TEXT, fontFace: SANS, margin: 0 });
  s.addText(st[2], { x, y: 3.98, w: 3.8, h: 0.4, fontSize: 10.5,
    color: MUTED, fontFace: SANS, margin: 0 });
});
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.9, w: W, h: 1.5, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText("The ocean needs a break - and fishers need better information. ParaSail helps with both.", {
  x: 0.7, y: 4.9, w: 11.9, h: 1.5, fontSize: 17, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, valign: "middle", margin: 0 });
srcLine(s, "Sources: FAO State of World Fisheries 2023; UNEP Turning off the Tap 2023.");
pageNum(s, 2);
s.addNotes("Three numbers frame the crisis: a third of stocks overfished, plastic tripling by 2040, half a billion livelihoods. Then move to what this feels like day to day.");

/* ============ S3 - Problem 1: the fish are moving ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem \u00B7 1 of 4");
title(s, "The fish are moving away");
s.addText("The sea is warming - and fish follow the warmth to new waters.", {
  x: M, y: 1.7, w: 12.33, h: 0.6, fontSize: 19, italic: true, color: PRIMARY,
  fontFace: SERIF, margin: 0 });
rows(s, [
  ["Yesterday's spots are empty", "Fish that gathered off this coast for generations now gather somewhere else."],
  ["The old calendars no longer work", "The trusted months for each fish drift out of step with the sea."],
  ["The search costs real money", "Boats burn fuel and days hunting fish that simply are not there."],
], 2.55, 1.35, 16.5, 13.5);
srcLine(s, "Source: Cheung et al., Global Change Biology, 2010 - climate-driven shifts in catch potential.");
pageNum(s, 3);
s.addNotes("Problem one: the resource itself is moving. Warming seas shift fish to new waters, breaking the seasonal knowledge communities relied on, and every empty net is spent fuel.");

/* ============ S4 - Problem 2: the ocean needs a break ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem \u00B7 2 of 4");
title(s, "The ocean needs a break");
const ocean = [
  ["Spawning grounds get disturbed", "Fishing while fish are breeding leaves fewer fish for everyone next year."],
  ["Protected zones are fished by mistake", "At sea, boundaries are invisible. Honest mistakes still harm the ocean - and bring fines."],
  ["The sea is already strained", "Plastic, pollution and overfishing leave less room for error."],
];
ocean.forEach((o, i) => {
  const x = M + i * 4.2;
  card(s, x, 1.95, 3.9, 3.3, "FFFFFF");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.95, w: 3.9, h: 3.3, rectRadius: 0.07,
    fill: { color: "FFFFFF", transparency: 100 }, line: { color: "D8E2E6", width: 1 } });
  s.addText(o[0], { x: x + 0.3, y: 2.3, w: 3.3, h: 1.0, fontSize: 16, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(o[1], { x: x + 0.3, y: 3.35, w: 3.3, h: 1.7, fontSize: 13,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("Rules exist to protect all of this - but only if they are easy to follow.", {
  x: M, y: 5.65, w: 12.33, h: 0.5, fontSize: 15.5, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, align: "center", margin: 0 });
pageNum(s, 4);
s.addNotes("Problem two: ecological pressure. Spawning grounds and protected zones suffer - often from honest mistakes, because the rules are hard to check at sea. Protection that is hard to follow protects nothing.");

/* ============ S5 - Problem 3: danger ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem \u00B7 3 of 4");
title(s, "Going to sea is dangerous");
s.addText("\u201CA small boat, an open sea - and a weather forecast meant for everyone, and no one.\u201D", {
  x: M, y: 1.75, w: 12.33, h: 1.1, fontSize: 23, italic: true, color: PRIMARY,
  fontFace: SERIF, margin: 0 });
rows(s, [
  ["Warnings are too general", "City-wide forecasts say nothing about the wind and waves off your own fishing ground."],
  ["The sea turns fast", "Conditions can change completely between dawn and noon."],
  ["Families wait ashore", "Every trip carries a worry that better information could ease."],
], 3.15, 1.2, 16, 13.5);
pageNum(s, 5);
s.addNotes("Problem three: safety. Small vessels get forecasts meant for entire districts, not their fishing grounds. This is the harm that can never be undone - frame it with weight.");

/* ============ S6 - Problem 4: scattered information ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The problem \u00B7 4 of 4");
title(s, "Information is everywhere - and nowhere");
const scattered = [
  [0.7, 2.0, "THE WEATHER APP", "Wind and waves - but nothing about fish or rules."],
  [5.1, 2.75, "THE RULEBOOK", "Paper and offices - hard to read, harder to check at sea."],
  [9.5, 1.95, "THE ELDERS' KNOWLEDGE", "Rich and true - but living only in memory."],
];
scattered.forEach(sc => {
  const [x, y, head, body] = sc;
  outlineCard(s, x, y, 3.33, 1.95, true);
  s.addText(head, { x: x + 0.28, y: y + 0.22, w: 2.8, h: 0.4, fontSize: 12.5, bold: true,
    color: PRIMARY_DK, charSpacing: 1, fontFace: SANS, margin: 0 });
  s.addText(body, { x: x + 0.28, y: y + 0.68, w: 2.8, h: 1.15, fontSize: 12.5,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("Nothing connects them.", {
  x: M, y: 5.15, w: 12.33, h: 0.6, fontSize: 22, bold: true, italic: true,
  color: ACCENT, fontFace: SERIF, align: "center", margin: 0 });
s.addText("So the fisher must be their own weather expert, lawyer and fish scientist - before sunrise.", {
  x: M, y: 5.85, w: 12.33, h: 0.5, fontSize: 15, color: TEXT, fontFace: SANS,
  align: "center", margin: 0 });
pageNum(s, 6);
s.addNotes("Problem four is the root of the other three: the knowledge exists - weather apps, rulebooks, elders' wisdom - but nothing connects it. Pause on 'nothing connects them.' That is the gap ParaSail fills.");

/* ============ S7 - What's at stake ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "Why it matters");
title(s, "What is at stake");
const stakes = [
  ["Livelihoods", "Fishing feeds and employs half a billion people worldwide."],
  ["Food", "Small fish from small boats put dinner on millions of tables."],
  ["Culture", "Coastal communities are built around the sea and its seasons."],
  ["The ocean", "A sea under this much pressure recovers slowly - if at all."],
];
stakes.forEach((st, i) => {
  const x = M + i * 3.14;
  card(s, x, 1.95, 2.9, 2.75, PRIMARY_LT);
  s.addText(st[0], { x: x + 0.25, y: 2.25, w: 2.4, h: 0.5, fontSize: 17, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(st[1], { x: x + 0.25, y: 2.8, w: 2.4, h: 1.7, fontSize: 12.5,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.15, w: W, h: 1.25, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText("Fishers need better information - and the ocean needs fishers to have it. That is the idea behind ParaSail.", {
  x: 0.7, y: 5.15, w: 11.9, h: 1.25, fontSize: 16, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, valign: "middle", margin: 0 });
pageNum(s, 7);
s.addNotes("Before showing the solution, land the stakes: livelihoods, food, culture, the ocean itself. Then bridge: both fishers and the ocean win when information improves.");

/* ============ S8 - Meet ParaSail ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution");
title(s, "Meet ParaSail");
s.addText("Like a weather app - but for fishing.", {
  x: M, y: 2.0, w: 12.33, h: 0.9, fontSize: 34, bold: true, color: PRIMARY,
  fontFace: SERIF, margin: 0 });
s.addText("You tell it where you fish and what you catch. Before you sail, it gives you one simple answer - safe or not, fish or not, allowed or not - together with the reasons.", {
  x: M, y: 3.0, w: 11.6, h: 0.95, fontSize: 16, color: TEXT, fontFace: SANS, margin: 0 });
const feats = [
  ["Answers in plain words", "No numbers to decode - GO, WAIT or STOP."],
  ["Ask it anything", "A built-in AI helper answers your questions in your own words and language."],
  ["Free, open data", "Built on public weather and satellite information - and its own local AI, not a paid cloud service."],
];
feats.forEach((f, i) => {
  const x = M + i * 4.2;
  card(s, x, 4.35, 3.9, 1.9, PRIMARY_LT);
  s.addText(f[0], { x: x + 0.3, y: 4.62, w: 3.3, h: 0.45, fontSize: 14.5, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(f[1], { x: x + 0.3, y: 5.12, w: 3.3, h: 0.95, fontSize: 12,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
pageNum(s, 8);
s.addNotes("The one-line pitch: a weather app for fishing. Three qualities: plain-words answers, reasons always shown, built on free public data.");

/* ============ S9 - Traffic light ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution");
title(s, "The answer is a traffic light");
const lights = [
  [TL.go, "GO", "Good conditions. Safe to sail, fish are likely, everything is allowed."],
  [TL.careful, "GO CAREFULLY", "Fishing is possible - but keep an eye on the changing weather."],
  [TL.wait, "WAIT OR MOVE", "Rough seas, or young fish nearby. Better to wait or try another spot."],
  [TL.stop, "STOP", "Not safe, or not allowed. Stay ashore today."],
];
lights.forEach((l, i) => {
  const y = 1.7 + i * 1.02;
  s.addShape(pres.shapes.OVAL, { x: 0.75, y: y + 0.05, w: 0.72, h: 0.72,
    fill: { color: l[0] }, line: { color: "FFFFFF", width: 0 }, shadow: shadow() });
  s.addText(l[1], { x: 1.85, y, w: 3.1, h: 0.85, fontSize: 19, bold: true,
    color: l[0], fontFace: SERIF, valign: "middle", margin: 0 });
  s.addText(l[2], { x: 5.05, y, w: 7.6, h: 0.85, fontSize: 14.5,
    color: TEXT, fontFace: SANS, valign: "middle", margin: 0 });
});
s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.95, w: W, h: 1.0, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText([
  { text: "Protected area or closed season? ", options: { bold: true, color: ACCENT } },
  { text: "The answer is always STOP - no exceptions, whatever the weather.", options: { color: PRIMARY_DK } },
], { x: 0.7, y: 5.95, w: 11.9, h: 1.0, fontSize: 15.5, fontFace: SANS,
  valign: "middle", margin: 0 });
pageNum(s, 9);
s.addNotes("The four answers are a traffic light everyone already understands. The hard rule: protected areas and closed seasons are always STOP - conservation is built in, not optional.");

/* ============ S10 - What you actually see ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution");
title(s, "What you actually see");
card(s, M, 1.85, 5.85, 4.3, "FFFFFF");
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.85, w: 5.85, h: 4.3, rectRadius: 0.07,
  fill: { color: "FFFFFF", transparency: 100 }, line: { color: "D8E2E6", width: 1 } });
s.addText("TOMORROW, 5 AM \u2014 OFF KOCHI", { x: 0.85, y: 2.12, w: 5.2, h: 0.4,
  fontSize: 12.5, bold: true, color: MUTED, charSpacing: 1, fontFace: SANS, margin: 0 });
s.addText("GO", { x: 0.85, y: 2.55, w: 5.2, h: 1.05, fontSize: 52, bold: true,
  color: TL.go, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Waves 0.8 m \u2014 safe for small boats", options: { bullet: bu(), breakLine: true } },
  { text: "Sardines likely in this area", options: { bullet: bu(), breakLine: true } },
  { text: "Zone open \u2014 no restrictions", options: { bullet: bu() } },
], { x: 0.85, y: 3.75, w: 5.2, h: 2.2, fontSize: 14.5, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 10, margin: 0, valign: "top" });
card(s, 6.98, 1.85, 5.85, 4.3, "FFFFFF");
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.98, y: 1.85, w: 5.85, h: 4.3, rectRadius: 0.07,
  fill: { color: "FFFFFF", transparency: 100 }, line: { color: "D8E2E6", width: 1 } });
s.addText("JUNE 15 \u2014 ANYWHERE ON THE COAST", { x: 7.33, y: 2.12, w: 5.2, h: 0.4,
  fontSize: 12.5, bold: true, color: MUTED, charSpacing: 1, fontFace: SANS, margin: 0 });
s.addText("STOP", { x: 7.33, y: 2.55, w: 5.2, h: 1.05, fontSize: 52, bold: true,
  color: TL.stop, fontFace: SERIF, margin: 0 });
s.addText([
  { text: "Sardine season is closed", options: { bullet: bu(), breakLine: true } },
  { text: "So the fish can spawn and multiply", options: { bullet: bu(), breakLine: true } },
  { text: "Fishing opens again August 1", options: { bullet: bu() } },
], { x: 7.33, y: 3.75, w: 5.2, h: 2.2, fontSize: 14.5, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 10, margin: 0, valign: "top" });
s.addText("Simple on purpose - the details are one tap away for anyone who wants them.", {
  x: M, y: 6.45, w: 12.33, h: 0.45, fontSize: 14, italic: true, color: MUTED,
  fontFace: SERIF, align: "center", margin: 0 });
pageNum(s, 10);
s.addNotes("Make it concrete: a good morning off Kochi gets a green GO with three plain reasons; mid-June gets a red STOP because the sardine season is closed. That is the whole product.");

/* ============ S11 - Ask it anything (AI helper) ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution \u00B7 the AI helper");
title(s, "Ask it anything - in your own words");
// chat mockup (left)
outlineCard(s, M, 1.85, 6.35, 4.55);
s.addText("ASK PARASAIL", { x: 0.85, y: 2.08, w: 5.6, h: 0.32, fontSize: 11,
  bold: true, color: MUTED, charSpacing: 2, fontFace: SANS, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.55, y: 2.5, w: 3.65, h: 0.72,
  rectRadius: 0.12, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
s.addText("\u201CCan I take my small boat out tomorrow morning?\u201D", {
  x: 2.7, y: 2.5, w: 3.35, h: 0.72, fontSize: 12, color: "FFFFFF",
  fontFace: SANS, valign: "middle", margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.85, y: 3.42, w: 4.9, h: 1.62,
  rectRadius: 0.12, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText([
  { text: "GO CAREFULLY - waves near 1 m in the morning, wind rising after noon. Best back before two.", options: { breakLine: true } },
  { text: "sources: marine forecast \u00B7 rulebook", options: { fontSize: 10, italic: true, color: MUTED } },
], { x: 1.02, y: 3.42, w: 4.55, h: 1.62, fontSize: 12.5, color: TEXT,
  fontFace: SANS, valign: "middle", paraSpaceAfter: 6, margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 2.55, y: 5.22, w: 3.65, h: 0.72,
  rectRadius: 0.12, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
s.addText("\u201CAnd in June, for sardine?\u201D", {
  x: 2.7, y: 5.22, w: 3.35, h: 0.72, fontSize: 12, color: "FFFFFF",
  fontFace: SANS, valign: "middle", margin: 0 });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.85, y: 6.1, w: 4.9, h: 0.72,
  rectRadius: 0.12, fill: { color: PRIMARY_LT }, line: { color: PRIMARY_LT, width: 0 } });
s.addText("STOP - the sardine season is closed so the fish can spawn.", {
  x: 1.02, y: 6.1, w: 4.55, h: 0.72, fontSize: 12.5, color: TEXT,
  fontFace: SANS, valign: "middle", margin: 0 });
// explanation rows (right column, custom placement - rows() is full-width)
const helperRows = [
  ["Answers in plain words", "Ask like you would ask a neighbour - no forms, no jargon, and it answers in your language."],
  ["Shows its sources", "Every answer points to the forecast, rule or local knowledge it used - check it yourself."],
  ["Free for everyone, always", "The AI runs on our own computer, not a paid cloud service - heavy use costs nothing extra."],
];
helperRows.forEach((it, i) => {
  const y = 2.0 + i * 1.5;
  s.addShape(pres.shapes.OVAL, { x: 7.15, y: y + 0.05, w: 0.6, h: 0.6,
    fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
  s.addText(String(i + 1), { x: 7.15, y: y + 0.05, w: 0.6, h: 0.6, fontSize: 15,
    bold: true, color: "FFFFFF", fontFace: SANS, align: "center", valign: "middle", margin: 0 });
  s.addText([
    { text: it[0], options: { fontSize: 15.5, bold: true, color: PRIMARY_DK, breakLine: true } },
    { text: it[1], options: { fontSize: 12.5, color: TEXT } },
  ], { x: 8.1, y, w: 4.7, h: 1.4, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("The AI explains the advice - it never overrules it. Closed season? The answer is still STOP.", {
  x: 7.15, y: 6.35, w: 5.65, h: 0.75, fontSize: 13.5, italic: true, color: ACCENT,
  fontFace: SERIF, margin: 0, valign: "top" });
pageNum(s, 11);
s.addNotes("The AI helper: fishers ask questions in their own words and language; every answer cites its sources and runs on locally owned hardware with no per-question cloud costs. Crucially, the AI explains the advisory - it can never override it. A closed season is still STOP.");

/* ============ S12 - It shows its homework ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution \u00B7 trust");
title(s, "It shows its homework");
card(s, M, 1.9, 5.3, 3.3, "FFFFFF");
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.9, w: 5.3, h: 3.3, rectRadius: 0.07,
  fill: { color: "FFFFFF", transparency: 100 }, line: { color: "D8E2E6", width: 1 } });
s.addText("THE ADVICE", { x: 0.85, y: 2.15, w: 4.6, h: 0.35, fontSize: 11, bold: true,
  color: MUTED, charSpacing: 2, fontFace: SANS, margin: 0 });
s.addText("GO", { x: 0.85, y: 2.5, w: 4.6, h: 0.95, fontSize: 46, bold: true,
  color: TL.go, fontFace: SERIF, margin: 0 });
s.addText("Tomorrow, 5 AM, off Kochi\nSafe to sail \u00B7 sardines likely \u00B7 zone open", {
  x: 0.85, y: 3.55, w: 4.6, h: 1.4, fontSize: 14.5, color: TEXT, fontFace: SANS,
  margin: 0, valign: "top" });
s.addShape(pres.shapes.LINE, { x: 6.1, y: 3.55, w: 0.85, h: 0, line: { color: PRIMARY, width: 2.6, endArrowType: "triangle" } });
card(s, 7.2, 1.9, 5.63, 3.3, PRIMARY_LT);
s.addText("THE HOMEWORK", { x: 7.55, y: 2.15, w: 4.9, h: 0.35, fontSize: 11, bold: true,
  color: PRIMARY_DK, charSpacing: 2, fontFace: SANS, margin: 0 });
s.addText([
  { text: "Waves forecast: 0.8 m - safe for small boats", options: { bullet: bu(), breakLine: true } },
  { text: "Rulebook: this zone is open all year", options: { bullet: bu(), breakLine: true } },
  { text: "Sardines gather here in September", options: { bullet: bu() } },
], { x: 7.55, y: 2.6, w: 5.0, h: 2.4, fontSize: 14, color: TEXT, fontFace: SANS,
  paraSpaceAfter: 12, margin: 0, valign: "top" });
s.addText("Every recommendation shows the reasons behind it - the forecasts, the rules, even local fishing knowledge. You can always check for yourself.", {
  x: M, y: 5.45, w: 12.33, h: 0.8, fontSize: 15.5, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, margin: 0 });
s.addText("Built to grow: new rules, new data, even whole new coasts are added as documents - the library simply grows.", {
  x: M, y: 6.35, w: 12.33, h: 0.55, fontSize: 14.5, italic: true, color: ACCENT,
  fontFace: SERIF, margin: 0 });
pageNum(s, 12);
s.addNotes("Trust comes from transparency: the advice on the left always arrives with its homework on the right - forecasts, rules and community knowledge you can verify. Close on scalability: new sources plug in as documents, so the system grows with future data integration - no retraining needed.");

/* ============ S13 - Made for your coast ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The solution \u00B7 local");
title(s, "Your coast. Your fish. Your rules.");
s.addText("ParaSail is not a one-size-fits-all app. It is set up for each coast it serves:", {
  x: M, y: 1.85, w: 11.6, h: 0.5, fontSize: 15.5, color: TEXT, fontFace: SANS, margin: 0 });
rows(s, [
  ["Quick to set up", "A new coast, with its own fish and rules, can be ready in days - not months."],
  ["Runs on ordinary computers", "No supercomputer needed - a mid-range laptop is enough to teach it, and it switches to bigger or smaller AI models to match the machine."],
  ["Now a phone app", "Install it from the website: it opens on your phone even with weak signal, and answers in your language - fish names included."],
  ["Keeps local knowledge", "Fishing calendars and season wisdom from the community are saved in a digital library the system consults."],
], 2.45, 1.08, 15.5, 12.5);
pageNum(s, 13);
s.addNotes("Three local-adaptation points: quick setup per coast, modest hardware, and traditional fishing knowledge preserved and consulted digitally.");

/* ============ S14 - What we found ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The evidence");
title(s, "It worked - here is what we found");
const finds = [
  ["Live data kept flowing", "Even when the internet went down, the advice continued - clearly marked as slightly older information."],
  ["Closed seasons were always respected", "Every single test during a closed season came back STOP. No exceptions, ever."],
  ["Advice changed sensibly", "When the weather turned or the fish moved, the traffic light changed exactly as it should."],
  ["Every answer explained itself", "The reasons shown next to each advice were checked - and they were the right ones."],
];
finds.forEach((f, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = M + col * 6.35, y = 1.8 + row * 2.5;
  card(s, x, y, 5.98, 2.15, "FFFFFF");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.98, h: 2.15, rectRadius: 0.07,
    fill: { color: "FFFFFF", transparency: 100 }, line: { color: "D8E2E6", width: 1 } });
  s.addText("\u2713", { x: x + 0.28, y: y + 0.25, w: 0.55, h: 0.6, fontSize: 28, bold: true,
    color: TL.go, fontFace: SANS, margin: 0 });
  s.addText(f[0], { x: x + 0.95, y: y + 0.28, w: 4.8, h: 0.55, fontSize: 15.5, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(f[1], { x: x + 0.95, y: y + 0.9, w: 4.8, h: 1.15, fontSize: 12.5,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
pageNum(s, 14);
s.addNotes("Four findings in plain terms: reliable data even offline, closed seasons always respected, sensible changes with conditions, and correct explanations every time.");

/* ============ S15 - Who benefits ============ */
s = pres.addSlide();
s.background = { color: "FFFFFF" };
kicker(s, "The impact");
title(s, "Everyone on the coast");
const bens = [
  ["Fishers", "Save fuel, stay safe, and avoid fines from honest mistakes."],
  ["The ocean", "Protected zones and spawning seasons are left in peace - automatically."],
  ["Communities", "Generations of fishing knowledge are saved in a lasting digital library."],
  ["Authorities", "Clear, fair decisions backed by evidence everyone can see."],
];
bens.forEach((b, i) => {
  const x = M + i * 3.14;
  card(s, x, 1.95, 2.9, 3.6, PRIMARY_LT);
  s.addText(b[0], { x: x + 0.25, y: 2.25, w: 2.4, h: 0.55, fontSize: 17, bold: true,
    color: PRIMARY_DK, fontFace: SERIF, margin: 0 });
  s.addText(b[1], { x: x + 0.25, y: 2.9, w: 2.4, h: 2.4, fontSize: 12.5,
    color: TEXT, fontFace: SANS, margin: 0, valign: "top" });
});
s.addText("One system, four winners - that is what a sustainable blue economy looks like.", {
  x: M, y: 6.05, w: 12.33, h: 0.5, fontSize: 15.5, italic: true, color: PRIMARY_DK,
  fontFace: SERIF, align: "center", margin: 0 });
pageNum(s, 15);
s.addNotes("Four beneficiaries: fishers, the ocean, communities, authorities. Sustainability means all four win together.");

/* ============ S16 - Closing (dark) ============ */
s = pres.addSlide();
s.background = { color: BG_DARK };
kicker(s, "One simple idea", true);
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
pageNum(s, 16, true);
s.addNotes("Close with the promise: fish smarter, stay safe, keep the ocean giving. Mention the next step - a real trial and a free offline phone app - then thank the audience and invite questions.");

pres.writeFile({ fileName: "ParaSail_Presentation.pptx" }).then(() => console.log("WROTE ParaSail_Presentation.pptx (problem-led version)"));

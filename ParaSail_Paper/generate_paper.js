/* ParaSail — 10-page summit research paper generator (docx-js)
 * Conference-paper format: title block + abstract, numbered sections,
 * three-line academic tables, inline numbered citations, references. */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, PageNumber, NumberFormat, AlignmentType, HeadingLevel,
  WidthType, BorderStyle, TabStopType,
  Math: OoxmlMath, MathRun, MathSubScript, MathSuperScript,
} = require("docx");
const fs = require("fs");

const TNR = { ascii: "Times New Roman", eastAsia: "Times New Roman" };
const BLACK = "000000";
const MARGIN_L = 1440, MARGIN_R = 1240;
const CONTENT_W = 11906 - MARGIN_L - MARGIN_R; // 9226

/* ---------- helpers ---------- */
function runs(text, base = {}) {
  return text.split("*").map((seg, i) => seg === "" ? null : new TextRun({
    text: seg, italics: i % 2 === 1, font: TNR, color: BLACK, ...base,
  })).filter(Boolean);
}
function p(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 58, line: 312 },
    children: runs(text, { size: 22, ...opts.run }),
    ...opts.para,
  });
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 180, after: 70, line: 312 },
    children: [new TextRun({ text, bold: true, size: 28, font: TNR, color: BLACK })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 130, after: 60, line: 312 },
    children: [new TextRun({ text, bold: true, size: 24, font: TNR, color: BLACK })],
  });
}
function itemP(label, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { left: 440, hanging: 440 },
    spacing: { after: 30, line: 312 },
    children: [
      new TextRun({ text: label + "  ", bold: true, size: 22, font: TNR, color: BLACK }),
      ...runs(text, { size: 22 }),
    ],
  });
}
function eq(mathChildren, num) {
  return new Paragraph({
    tabStops: [
      { type: TabStopType.CENTER, position: Math.round(CONTENT_W / 2) },
      { type: TabStopType.RIGHT, position: CONTENT_W },
    ],
    spacing: { before: 56, after: 56, line: 312 },
    children: [
      new TextRun({ text: "\t", size: 22 }),
      new OoxmlMath({ children: mathChildren }),
      new TextRun({ text: "\t(" + num + ")", size: 22, font: TNR, color: BLACK }),
    ],
  });
}
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function tableCaption(num, text) {
  return new Paragraph({
    keepNext: true, alignment: AlignmentType.CENTER,
    spacing: { before: 90, after: 36, line: 270 },
    children: [
      new TextRun({ text: "Table " + num + "  ", bold: true, size: 20, font: TNR, color: BLACK }),
      new TextRun({ text, size: 20, font: TNR, color: BLACK }),
    ],
  });
}
function cellRuns(v, bold) {
  const o = typeof v === "object" ? v : { t: v };
  return [new TextRun({ text: o.t, italics: !!o.i, bold: bold || !!o.b, size: 18, font: TNR, color: BLACK })];
}
function threeLine(headers, dataRows, widths) {
  const headerRow = new TableRow({
    tableHeader: true, cantSplit: true,
    children: headers.map((htext, i) => new TableCell({
      width: { size: widths[i], type: WidthType.PERCENTAGE },
      borders: { top: NB, left: NB, right: NB, bottom: { style: BorderStyle.SINGLE, size: 4, color: BLACK } },
      margins: { top: 24, bottom: 24, left: 80, right: 80 },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { line: 240 },
        children: cellRuns(htext, true),
      })],
    })),
  });
  const rows = dataRows.map(r => new TableRow({
    cantSplit: true,
    children: r.map((v, i) => new TableCell({
      width: { size: widths[i], type: WidthType.PERCENTAGE },
      borders: { top: NB, left: NB, right: NB, bottom: NB },
      margins: { top: 24, bottom: 24, left: 80, right: 80 },
      children: [new Paragraph({
        alignment: AlignmentType.LEFT, spacing: { line: 240 },
        children: cellRuns(v, false),
      })],
    })),
  }));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: BLACK },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: BLACK },
      left: NB, right: NB, insideHorizontal: NB, insideVertical: NB,
    },
    rows: [headerRow, ...rows],
  });
}
function refP(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { left: 340, hanging: 340 },
    spacing: { after: 2, line: 220 },
    children: runs(text, { size: 17 }),
  });
}

/* ---------- title block ---------- */
const titleBlock = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 40, after: 120, line: 400, lineRule: "atLeast" },
    children: [new TextRun({
      text: "ParaSail: A Retrieval-Augmented Geospatial Decision Support System for Sustainable Fishing, Marine Conservation and Coastal Livelihood Resilience",
      bold: true, size: 32, font: TNR, color: BLACK,
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 40, line: 290 },
    children: [new TextRun({
      text: "26th Digital Blue Economy Summit  |  Research Level: Experimental Paper",
      size: 22, font: TNR, color: "444444",
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 30, line: 290 },
    children: [new TextRun({
      text: "\u3010Author Name\u3011  \u00B7  \u3010Institution / Organisation\u3011  \u00B7  \u3010City, Country\u3011",
      size: 22, font: TNR, color: BLACK,
    })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 150, line: 290 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "888888", space: 8 } },
    children: [new TextRun({ text: "September 2026", size: 20, font: TNR, color: "666666" })],
  }),
];

/* ---------- abstract ---------- */
const abstractBlock = [
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 30, after: 60, line: 312 },
    children: [new TextRun({ text: "Abstract", bold: true, size: 24, font: TNR, color: BLACK })],
  }),
  p("Small-scale fishing communities in data-poor coastal regions plan their trips on fragmented information: weather applications carry no fisheries context, habitat research is rarely operational, vessel-tracking analytics are locally inaccessible, conservation rules remain static documents, and none of it can simply be asked a question. This paper presents ParaSail (Predictive Advisory and Retrieval-Augmented System Advancing Informed Livelihoods), a production-style, retrieval-augmented geospatial decision support system that fuses live meteorological and oceanographic forecasts, biodiversity occurrence records, satellite imagery and regulatory texts into a single explainable advisory. The system follows a six-layer architecture (ingestion, processing, prediction, retrieval-augmented explanation, advisory, and a grounded AI assistant), enforces marine protected areas and seasonal closures as hard constraints, and scores every recommendation through a transparent sustainability index combining catch likelihood, weather safety and bycatch risk. A retrieval layer over a dual-collection vector database attaches regulation, guidance and traditional-knowledge context to every advisory, while parameter-efficient LoRA fine-tuning (rank 8; under one percent trainable parameters) enables local adaptation on modest hardware. A conversational assistant layer, built on a single self-hosted open-source vision-language model (Qwen2.5-VL-7B, 4-bit AWQ, served with vLLM), summarises advisories in plain language, answers users' questions with citations in their own language, and reads catch photos, satellite tiles and charts; guardrails bind every answer to the retrieved corpus and to the authoritative advisory class, and a deterministic template path keeps the website functional without a GPU. The website itself is production-hardened for public use: a runtime-switchable model registry scales quality against the deployed hardware, per-endpoint rate limiting and API-key role-based access control protect the service, species render in vernacular names curated per region, blocked advisories explain themselves through localised Problem/Answer blocks, and a regional ocean-news service translates items from multiple origin languages into the reader's language through an English pivot. The dashboard ships as an installable mobile web application with an offline app shell, set in the open-licensed Lora typeface, and deploys to remote devices over a private tailnet. The full AI stack runs within an 8-12 GB VRAM budget on owned hardware, so request volume never incurs per-token API costs; a tiered production hardware profile (6 GB laptop to multi-GPU) accompanies the reference implementation. A case study on the southwest coast of India, covering monsoon closures, a protected-area network and active sardine and mackerel fisheries, demonstrates exact closure enforcement, monotonic scoring behaviour, topically relevant retrieval and guarded assistant behaviour. The work shows that sustainability-scored, explainable, conversational fishing advisories are feasible today with open-source tools, and that conservation, legality and safety can be embedded as constraints in the objective function rather than bolted on afterwards.",
    { run: { size: 20 }, para: { indent: { left: 240, right: 240 }, spacing: { after: 70, line: 300 } } }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 290 },
    indent: { left: 240, right: 240 },
    children: [
      new TextRun({ text: "Keywords: ", bold: true, size: 20, font: TNR, color: BLACK }),
      new TextRun({ text: "decision support system; retrieval-augmented generation; geospatial artificial intelligence; vision-language models; LoRA fine-tuning; fisheries sustainability; marine conservation; blue economy; explainable AI", size: 20, font: TNR, color: BLACK }),
    ],
  }),
];

/* ---------- body content ---------- */
const body = [];

/* 1. Introduction */
body.push(h1("1. Introduction"));
body.push(h2("1.1 Background and Crisis Context"));
body.push(p("The blue economy, the sustainable use of ocean resources for growth, livelihoods and employment while preserving marine ecosystems, has become a central policy frame for coastal states [1]. Marine capture fisheries sit at its heart: small-scale fisheries alone supply at least 40 percent of the global catch and support nearly half a billion people [2]. Yet the resource base is eroding. The Food and Agriculture Organization reports that 35.5 percent of assessed stocks were fished beyond biologically sustainable levels in 2019, the highest share on record [3]. Pollution compounds the pressure: roughly 11 million tonnes of plastic enter the ocean every year and are projected to nearly triple by 2040 without decisive action [4], [5]."));
body.push(p("Climate change is redistributing the resource itself. Projections indicate large-scale shifts in maximum catch potential as species track moving thermal habitats [6], and on the southwest coast of India the oil sardine, historically the backbone of the regional pelagic fishery, has shown pronounced fluctuations and range extension associated with oceanographic variability [7]. Traditional ecological calendars calibrated to historical seasons lose predictive value when spawning times, aggregation zones and migration routes move; the past is no longer a reliable map of the sea."));
body.push(p("Management reform could recover substantial value: rebuilding overfished stocks under sound governance is projected to lift global catches well above business-as-usual trajectories [8], while biodiversity loss demonstrably undermines the ecosystem services fisheries depend upon [9], [10]. The open question is not whether sustainable management is worthwhile, but whether coastal actors possess the information infrastructure to act on it in real time."));
body.push(h2("1.2 Problem Statement"));
body.push(p("No integrated, real-time and explainable decision support system exists for safe, legal and sustainable fishing in data-poor coastal regions. The consequences are fourfold. Economically, fuel, time and labour are wasted on blind search for shifting fish distributions. Ecologically, fishing pressure concentrates on spawning grounds, sensitive habitats and protected zones. In terms of safety, small vessels put to sea without granular marine wind and wave guidance. And institutionally, the information that exists is fragmented: weather applications carry no fisheries context, habitat studies are not operational, AIS analytics serve global commodity fleets rather than local ones, and regulations are static documents that are difficult to query. A final dimension compounds all four: none of these tools can be conversed with, so fishers who cannot parse a forecast grid or a legal calendar are left to interpret expert artefacts unaided."));
body.push(h2("1.3 Research Gap and Questions"));
body.push(p("The gap is architectural rather than algorithmic. Individual capabilities exist, from numerical weather prediction and satellite ocean colour to species distribution models, but no operational system fuses weather, ocean state, species distributions, closures and ecological risk into a single advisory with explainable reasoning, and no such system offers a conversational interface that ordinary fishers can query directly. Five questions follow. RQ1: Can open environmental APIs, biodiversity records and satellite imagery be fused into one normalised, quality-controlled geospatial data model? RQ2: Can conservation rules, including protected areas and seasonal closures, be enforced as hard constraints on every recommendation? RQ3: Can every advisory carry retrievable, human-readable justification drawn from regulations, guidance and local knowledge? RQ4: Can the system be adapted to new regions and species without code changes and within modest hardware budgets? RQ5: Can a self-hosted, open-source vision-language assistant summarise advisories, answer natural-language questions and read field imagery on the public website, without breaking the constraint guarantees, within an 8-12 GB VRAM budget and without per-request inference costs?"));
body.push(h2("1.4 Contributions"));
body.push(p("The contributions of this work are as follows."));
body.push(itemP("C1", "A six-layer reference architecture (ingestion, processing, prediction, retrieval-augmented explanation, advisory, grounded AI assistant) for fisheries decision support, implemented end to end with open-source components."));
body.push(itemP("C2", "A rules engine enforcing marine protected areas and seasonal closures as hard, geographically exact constraints ahead of any scoring."));
body.push(itemP("C3", "A transparent sustainability index S = 0.45C + 0.25W + 0.30(1 \u2212 B) with four advisory classes, monotonic in every input by construction."));
body.push(itemP("C4", "A dual-collection retrieval-augmented layer, spanning text (regulations, closures, guidance, local knowledge) and satellite tiles, attaching verifiable context to every advisory."));
body.push(itemP("C5", "A LoRA fine-tuning pathway (rank 8 on query and value projections; under one percent trainable parameters) enabling region and species adaptation on mid-range GPUs."));
body.push(itemP("C6", "An operational validation across live-fetch, rule-enforcement, scoring-behaviour, retrieval-relevance and assistant-behaviour test families on a southwest-India case study."));
body.push(itemP("C7", "A grounded conversational assistant layer built on a single self-hosted open-source vision-language model (Qwen2.5-VL-7B, 4-bit AWQ, vLLM), providing plain-language advisory summaries, cited question answering in the user's language, and catch-photo, tile and chart reading, with code-enforced guardrails, a deterministic template fallback, and a runtime-switchable model registry that scales quality against the deployed hardware."));
body.push(itemP("C8", "A production deployment profile for local AI: an 8-12 GB VRAM serving budget with continuous batching, request concurrency control and response caching, a 6 GB laptop variant using the 3B sibling model, tiered hardware guidance from personal machines to multi-GPU regional deployments, and a hardened public website - per-endpoint rate limiting, API-key role-based access, localised Problem/Answer self-explanations, vernacular species names, cross-language ocean news, and an installable offline-capable mobile web app."));

/* 2. Related work */
body.push(h1("2. Related Work"));
body.push(h2("2.1 Operational Fisheries Advisory Services"));
body.push(p("The most mature precedent is India's Potential Fishing Zone (PFZ) advisory service, which derives satellite sea-surface-temperature and chlorophyll fronts to suggest likely aggregation zones [11]. Such services demonstrate demand and viable delivery channels, but they answer only where fish may be: no legality constraints, no bycatch or ecological-risk dimension, no weather-safety gate, no explanation attached to individual recommendations. ParaSail treats PFZ-style frontal signals as one input among several inside a constrained, explainable advisory."));
body.push(h2("2.2 Species Distribution and Habitat Modelling"));
body.push(p("Correlative species distribution models relate occurrence records to environmental predictors and remain the workhorse for estimating habitat suitability, including in data-poor settings [12]. They estimate where a species could be, not whether fishing there is legal, safe or responsible, and are rarely wired into operational decision flows. This system therefore uses a random-forest habitat model as the fallback estimator for data-poor taxa, because it is inexpensive, interpretable and robust to modest occurrence counts, while learned spatiotemporal models handle data-rich species."));
body.push(h2("2.3 Deep Learning for Marine Monitoring"));
body.push(p("Deep learning has transformed marine image analysis: single-stage detectors in the YOLO family support real-time catch and bycatch recognition [13], Vision Transformers set benchmarks for fine-grained species classification [14], and recurrent architectures such as the LSTM model spatiotemporal sequences [15]; classical ensembles remain competitive on tabular environmental data [16]. ParaSail deploys one representative of each family, selected for the constraints of coastal deployment rather than leaderboard position (Section 4.4)."));
body.push(h2("2.4 Retrieval-Augmented Generation, Vision-Language Models and Efficient Serving"));
body.push(p("Retrieval-augmented generation grounds model outputs in retrieved documents, improving factual verifiability in knowledge-intensive tasks [17], and has become the standard pattern for question answering over evolving corpora [18]. LoRA freezes the pretrained transformer weights [19] and injects low-rank updates, reducing trainable parameters by orders of magnitude at matched performance [20]. Sentence encoders in the Sentence-BERT family provide efficient embeddings for retrieval over regulatory text [21], and contrastive vision-language models such as CLIP enable embedding-based search over unlabelled satellite imagery [22]. Open-weight vision-language models in the 7-9 billion parameter class now combine competent text generation with genuine image understanding, including document, chart and scene reading [33], which makes a single model sufficient for summarisation, question answering and field-imagery interpretation at coastal-deployment scale. On the serving side, PagedAttention-based inference servers with continuous batching raise the throughput of such models by an order of magnitude on a single GPU [34], and activation-aware 4-bit quantisation (AWQ) roughly halves the memory footprint with minor accuracy cost [35], bringing a 7B vision-language model inside an 8-12 GB VRAM budget. The present work combines these into a dual-collection retrieval layer, a parameter-efficient adaptation pathway, and a grounded, self-hosted assistant whose marginal cost per answered question is effectively zero."));
body.push(h2("2.5 Traditional Ecological Knowledge and Digital Humanities"));
body.push(p("Traditional ecological knowledge, contextual, cumulative and locally grounded, has long been recognised as a legitimate knowledge system for fisheries governance [23]. Digital humanities methods for recording oral histories and calendars give such knowledge a durable, retrievable digital form. Here the retrieval corpus treats local knowledge as a first-class source, so that an advisory can cite both statutory rules and community experience."));
body.push(h2("2.6 Positioning"));
body.push(p("Table 1 positions the system against the tool classes fishers actually encounter. The differentiator is not any single capability but the fusion: constraints applied before scores, explanations attached to outputs, and adaptation achieved without re-engineering."));
body.push(tableCaption(1, "Positioning against existing tool classes"));
body.push(threeLine(
  ["Tool class", "Strengths", "What is missing"],
  [
    ["Weather applications", "Granular wind and wave forecasts", "No fish, closures or bycatch dimension"],
    ["PFZ-style advisories [11]", "Satellite-derived location hints", "No legality, safety gate or explanations"],
    ["Habitat / SDM studies [12]", "Rigorous suitability estimates", "Not operational, not integrated"],
    ["AIS fleet analytics", "Fleet-scale effort insight", "Costly, legally restricted, not local"],
    ["Static regulations", "Authoritative rules", "Unqueryable, no geospatial linkage"],
    [{ t: "ParaSail (this work)", b: true }, "Fused, constrained, explainable", "Longitudinal field trial (future work)"],
  ],
  [26, 34, 40]));

/* 3. Objectives */
body.push(h1("3. Research Objectives"));
body.push(p("The primary objective is to design, implement and evaluate a retrieval-augmented geospatial decision support system that recommends safe, legal and ecologically responsible fishing windows, and that ordinary fishers can interrogate in conversation. This decomposes into nine objectives, each mapped onto a validation test family (Section 5.2)."));
body.push(itemP("RO1", "Ingest and normalise live forecasts, wave and wind fields, sea-surface temperature, chlorophyll-a and current fields from open APIs and satellite archives."));
body.push(itemP("RO2", "Model aggregation likelihood and movement tendency for registered species, with habitat-suitability fallback for data-poor taxa."));
body.push(itemP("RO3", "Enforce marine protected areas, seasonal closures and bycatch proxies as hard or soft constraints on every recommendation."));
body.push(itemP("RO4", "Implement a retrieval layer storing regulations, conservation guidance and local ecological knowledge, attached as context to every advisory."));
body.push(itemP("RO5", "Support local adaptation through custom data ingestion and parameter-efficient LoRA fine-tuning."));
body.push(itemP("RO6", "Expose the system through a production-style API and a visual dashboard."));
body.push(itemP("RO7", "Evaluate through live-fetch, rule-enforcement, scoring-behaviour, retrieval-relevance, assistant-behaviour and security-behaviour tests."));
body.push(itemP("RO8", "Align the design with blue-economy principles, treating livelihoods, conservation and safety as joint objectives."));
body.push(itemP("RO9", "Provide a grounded, self-hosted AI assistant on the website that summarises advisories, answers questions in the user's language and reads field imagery, under code-enforced guardrails, within an 8-12 GB VRAM budget and with no per-request inference costs."));

/* 4. Architecture */
body.push(h1("4. System Architecture and Technology"));
body.push(h2("4.1 Architectural Overview"));
body.push(p("ParaSail is organised as six layers: ingestion, processing, prediction, retrieval-augmented explanation, advisory and a grounded AI assistant, each independently replaceable and configured through YAML. Data flows sequentially: open APIs, satellite archives and community uploads are validated and normalised onto a common spatiotemporal grid; predictive models estimate catch likelihood and movement tendency; the retrieval layer assembles regulation and context; the advisory layer applies constraints before scoring, emitting a machine- and human-readable advisory with retrieved citations; and the assistant layer turns that advisory into plain language and conversation for the public website. PostgreSQL with PostGIS holds the relational and geospatial state, Qdrant holds vector embeddings, a vLLM inference server hosts the assistant's vision-language model locally, and Docker Compose orchestrates deployment."));
body.push(h2("4.2 Ingestion Layer"));
body.push(p("Each provider is wrapped behind a common interface with per-source freshness contracts, response caching and an offline contingency: when a live endpoint is unavailable, the system degrades to the most recent cached fields, flags their age in the advisory and keeps operating. Table 2 summarises the principal sources."));
body.push(tableCaption(2, "Principal data sources and their roles"));
body.push(threeLine(
  ["Source", "Content", "Cadence", "Role in advisory"],
  [
    ["Open-Meteo [24]", "Hourly meteorological and marine forecasts (wind, waves)", "Hourly", "Weather-safety component W"],
    ["Copernicus Marine [25]", "Near-real-time ocean analysis (SST, currents)", "Daily", "Environmental features"],
    ["NASA ERDDAP", "SST and chlorophyll-a fields", "Daily", "Environmental features"],
    ["GBIF / OBIS [26], [27]", "Historical species occurrences", "Static corpus", "Model training, habitat baselines"],
    ["FishBase / WoRMS [28]", "Taxonomy, traits, seasonality", "Static corpus", "Species registry, name normalisation"],
    ["Sentinel-2 / Sentinel-3 [29], [30]", "Multispectral satellite tiles", "Per pass", "Satellite retrieval collection"],
  ],
  [22, 34, 12, 32]));
body.push(h2("4.3 Processing Layer"));
body.push(p("The processing layer enforces coordinate and timestamp validation, normalises taxonomy against WoRMS identifiers, regrids heterogeneous products onto a common spatiotemporal grid, and engineers features such as thermal anomalies, chlorophyll fronts and wind stress. Quality gates reject malformed or stale inputs, and a freshness audit records the age of every field consumed by an advisory, so degraded data is always visible rather than silently absorbed."));
body.push(h2("4.4 Prediction Layer and Model Selection"));
body.push(p("The prediction layer deliberately mixes model families, matching each to data availability and deployment constraints (Table 3). For data-rich pelagic species, an LSTM over 24 hourly steps estimates short-horizon movement tendency; for data-poor taxa, a random-forest habitat-suitability model provides a robust fallback; a YOLOv8 detector supports catch-image verification; and a Vision Transformer classifier, adapted with LoRA, recognises species in field imagery. LoRA freezes the pretrained weights and learns a low-rank additive update,"));
body.push(eq([
  new MathRun("W = "),
  new MathSubScript({ children: [new MathRun("W")], subScript: [new MathRun("0")] }),
  new MathRun(" + \u0394W,   \u0394W = BA,   "),
  new MathSuperScript({ children: [new MathRun("B \u2208 \u211D")], superScript: [new MathRun("d\u00D7r")] }),
  new MathRun(",   "),
  new MathSuperScript({ children: [new MathRun("A \u2208 \u211D")], superScript: [new MathRun("r\u00D7k")] }),
], 1));
body.push(p("with rank r = 8 injected into the query and value projections of all twelve encoder blocks. For ViT-B/16 this leaves under one percent of parameters trainable, approximately 0.29 million of 85.8 million, keeping adaptation within mid-range GPU memory."));
body.push(tableCaption(3, "Selected models and selection rationale"));
body.push(threeLine(
  ["Task", "Selected model", "Rationale"],
  [
    ["Catch-image detection", "YOLOv8n, Ultralytics [13]", "Real-time on modest hardware; mature toolchain"],
    ["Species classification", "ViT-B/16 + LoRA (r = 8) [14], [20]", "Fine-grained accuracy; under 1% trainable parameters"],
    ["Movement tendency (24 h)", "Two-layer LSTM, hidden size 128 [15]", "Short-horizon sequences for data-rich species"],
    ["Habitat suitability", "Random forest [16]", "Interpretable fallback for data-poor taxa"],
    ["Text embeddings", "all-MiniLM-L6-v2 [21]", "Fast 384-dimensional sentence embeddings"],
    ["Satellite tile embeddings", "OpenCLIP ViT-B/32 [22]", "Similarity search over unlabelled tiles"],
    ["Conversational assistant (P7)", "Qwen2.5-VL-7B-Instruct, 4-bit AWQ [33], [35], served by vLLM [34]", "One open-source VLM for summaries, cited Q&A and image reading; fits 8-12 GB VRAM; batched serving sustains high traffic locally"],
  ],
  [24, 34, 42]));
body.push(h2("4.5 Retrieval-Augmented Explanation Layer"));
body.push(p("Explainability is treated as retrieval rather than generation of unconstrained prose. The Qdrant vector database [31] maintains two collections: a text collection holding chunked regulations, closure calendars, conservation guidance and recorded local ecological knowledge, embedded with a sentence encoder; and a satellite collection holding OpenCLIP embeddings of Sentinel tiles annotated with bounding boxes and acquisition metadata. At advisory time the engine performs hybrid retrieval, combining bounding-box and temporal pre-filtering with top-k vector search, and attaches the retrieved passages and tiles to the advisory payload, so every recommendation carries its own justification."));
body.push(h2("4.6 Advisory Layer"));
body.push(p("The advisory layer first applies hard constraints: a request inside an active marine protected area or seasonal closure is refused outright with the blocking reason, before any scoring occurs. Remaining requests are scored on the sustainability index"));
body.push(eq([new MathRun("S = 0.45C + 0.25W + 0.30(1 \u2212 B)")], 2));
body.push(p("where C is the catch-likelihood composite, W the weather-safety component and B the bycatch and ecological-risk proxy. C blends the learned and habitat estimates through a data-availability weight,"));
body.push(eq([
  new MathRun("C = \u03BB"),
  new MathSubScript({ children: [new MathRun("\u0108")] }),
  new MathRun(" + (1 \u2212 \u03BB)"),
  new MathSubScript({ children: [new MathRun("\u0124")] }),
], 3));
body.push(p("where \u0108 is the model-predicted aggregation index, \u0124 the habitat-suitability estimate, and \u03BB rises with the volume and recency of occurrence data for the species. The weights in Eq. (2) reflect a deliberate normative choice: catch opportunity contributes less than the sum of the safety and ecological terms. They are exposed as configuration rather than hidden constants, so governance bodies, not developers, own the trade-off. Table 4 defines the four advisory classes."));
body.push(tableCaption(4, "Advisory classes and decision thresholds"));
body.push(threeLine(
  ["Class", "Condition", "Interpretation"],
  [
    ["PROCEED", "S \u2265 0.75", "Favourable conditions and low risk"],
    ["PROCEED WITH CAUTION", "0.60 \u2264 S < 0.75", "Acceptable with vigilance"],
    ["DELAY OR RELOCATE", "0.40 \u2264 S < 0.60", "Degraded weather or elevated bycatch risk"],
    [{ t: "DO NOT FISH", b: true }, "S < 0.40, or any hard constraint", "Unsafe, illegal or ecologically irresponsible"],
  ],
  [30, 32, 38]));
body.push(h2("4.7 Grounded AI Assistant Layer"));
body.push(p("The sixth layer addresses the last mile of decision support: an advisory is only as useful as a fisher's ability to read it, and a corpus is only as useful as the ability to ask it questions. The assistant is a single self-hosted vision-language model, Qwen2.5-VL-7B-Instruct quantised to 4-bit with AWQ [33], [35], served locally through a PagedAttention inference server with continuous batching [34]. It performs three jobs on the public website: it summarises each advisory in plain language (the verdict, the one or two components that drove it, what to watch, the age of the data); it answers free-text questions by combining the live advisory payload with top-k retrieved passages, citing each claim to a numbered source and replying in the user's language; and it reads uploaded images, catch photos, satellite tiles and charts, describing only what is visible. One model serves all three jobs because its document, chart and scene understanding is strong enough for each, which keeps the deployment footprint to a single 8-12 GB GPU."));
body.push(p("Because a language model can confabulate, the assistant operates under code-enforced guardrails rather than prompt-only good behaviour. First, grounding: the prompt contains only the advisory payload and numbered retrieved passages, answers must cite them, and a post-generation check rejects any answer whose citations do not resolve to real passages. Second, verdict authority: the advisory class is computed by the deterministic rules engine and scoring pipeline, never by the model; a class-consistency guard prepends the authoritative verdict whenever a blocked advisory might otherwise be softened. Third, refusal over invention: with no retrieved context the assistant says so instead of improvising. Fourth, transparency: every response names the backend and model that produced it, which the validation suite asserts. Fifth, availability: if the model server is absent or unreachable, a deterministic template path assembles the same response schema directly from the advisory data and verbatim passages, so the website remains fully functional on CPU-only deployments. Concurrency is bounded by a request semaphore, and near-identical advisories (same class, drivers, day and language) share a cached summary, which together with continuous batching lets one mid-range GPU absorb the repeat traffic of thousands of daily users."));
body.push(p("The layer has since grown into the system's full interaction surface. A runtime-switchable model registry lists the deployable assistants (3B laptop tier, 7B AWQ reference tier, 7B via Ollama, 72B datacenter tier); switching is a dashboard selection backed by a persisted preference, so quality scales against the hardware at hand without reconfiguration, and a bundling script exports model weights for fully offline installations. Species render in vernacular names curated per region alongside their scientific names, never machine-translated, extending the multilingual interface into the vocabulary fishers actually use. Blocked advisories explain themselves: known system states, such as an unreachable protected-areas registry, attach a localised Problem/Answer block that states what happened and what the operator or fisher can do, in the selected language. A regional ocean-news service carries items originating in several languages and translates each into the reader's language through a reference-English pivot, because direct low-resource language pairs proved unreliable in testing; every item is attributed to its source and flagged when translated. The live telemetry panel mirrors a full station parameter set - wind with direction and gusts, barometric pressure, air temperature and humidity, sea temperature, significant wave height, wave period and direction, surface current velocity and direction, salinity when a source provides it, and station position, time and power health - with an explicit provenance panel showing where each group of readings comes from."));
body.push(h2("4.8 Deployment, Reproducibility and Production Hardware"));
body.push(p("The stack comprises FastAPI for the API, PostgreSQL with PostGIS for relational and geospatial storage, Qdrant for vectors, a vLLM container for the assistant's model, and Docker Compose for orchestration, fronted by a Tailwind, Leaflet and Chart.js dashboard with an animated conversational panel. Deployment is configuration-driven: region, species registry, closure calendars, model weights, score weights and the assistant model are all specified in YAML, which is what makes region and species retargeting, and model swaps between the 7B and 3B assistant variants, possible without code edits. Version control and containerisation make every reported result reproducible from a clean environment."));
body.push(p("The assistant's self-hosted design is also an economic decision: inference runs on owned or fixed-rent hardware, so request volume never creates per-token API costs. At a representative load of 10,000 assistant interactions per day (about 5.5 billion tokens per year), commercial vision-language API billing at 3 to 10 dollars per million tokens would cost roughly 16,000 to 55,000 dollars annually, while the recommended self-hosted profile is a one-time 2,000-dollar 24 GB GPU plus about 315 dollars per year of electricity, or a cloud L4 instance rented only during advisory hours. Table 8 summarises the validated hardware tiers that accompany the reference implementation."));
body.push(tableCaption(8, "Production hardware tiers for the self-hosted assistant (VRAM is total serving footprint)"));
body.push(threeLine(
  ["Tier", "Representative hardware", "Assistant model / profile", "Intended load"],
  [
    ["L (laptop)", "RTX 4050 Laptop, 6 GB; 32 GB RAM", "Qwen2.5-VL-3B, Q4; 6 k context; 1-2 concurrent", "Personal use, demos, development"],
    ["1 (pilot)", "RTX 3060/4070, 12 GB; 32 GB RAM", "7B AWQ; 8 k context; 8 concurrent", "Single site or cooperative, thousands of requests per day"],
    ["2 (recommended)", "RTX 4090 or NVIDIA L4, 24 GB; 64 GB RAM", "7B AWQ; 16 k context; 32-64 concurrent", "District or state deployment, tens of thousands per day"],
    ["3 (regional)", "2-4\u00D7 L4/A10G behind a load balancer, or A100 40 GB", "7B AWQ replicas; optional semantic cache", "Regional service, millions of requests per year"],
  ],
  [12, 30, 32, 26]));
body.push(p("Power, thermal and connectivity notes for coastal environments (filtered ventilation for salt air, uninterruptible power, offline degradation) are documented alongside the tiers in the reference implementation's hardware guide, together with throughput measurements and a pre-go-live capacity checklist."));
body.push(p("As a public-facing service, the website carries its own hardening. A sliding-window rate limiter assigns each endpoint class its own per-client budget (page reads, advisory fetches, AI generation, vision uploads, translations, subscriptions and privileged actions), answering excess requests with 429 responses and standard rate-limit headers. Role-based access control governs privileged operations through API-key credentials with three roles - public, officer and admin - where model switching and operational reads require admin; keys are stored as hashes, missing credentials yield 401, insufficient roles 403, and with no keys configured the privileged endpoints stay locked by default. Every response carries a content-security-policy tuned to the app's locally served assets, framing and sniffing protections, and request bodies are size-capped. Privileged and security-relevant events flow to a structured audit log for institutional review. Finally, the dashboard ships as an installable mobile web application: a manifest with region-appropriate icons, a service worker that caches the application shell so the app opens with no connectivity (live data degrades visibly rather than silently), a touch-optimised layout in the open-licensed Lora typeface, and deployment guidance for private tailnets so fishers' phones reach the service over an encrypted mesh without any public exposure. The registry keys of the model switcher correspond one-to-one with the validated hardware tiers of Table 8, making scaling a selection rather than a reconfiguration."));

/* 5. Methodology */
body.push(h1("5. Methodology"));
body.push(h2("5.1 Research Design"));
body.push(p("The study follows an experimental-paper design: iterative engineering organised into seven phases, each closed by an explicit acceptance gate that must pass before the next phase begins (Table 5). This phase-gate discipline ties every capability claim to a gate, and every gate to a test."));
body.push(tableCaption(5, "Development phases and acceptance gates"));
body.push(threeLine(
  ["Phase", "Focus", "Acceptance gate"],
  [
    ["P1", "Governance, region selection, regulatory inventory", "Region and rules inventory signed off"],
    ["P2", "Ingestion pipeline, database schema", "Live fetches validated; freshness audit passes"],
    ["P3", "Baseline predictive models", "Baselines beat naive persistence"],
    ["P4", "LoRA fine-tuning, custom data ingestion", "Training converges within GPU memory budget"],
    ["P5", "RAG integration, advisory API", "Closure and MPA blocks exact; top-k retrieval relevant"],
    ["P6", "Dashboard, pilot feedback loop", "Advisory schema legible to pilot users"],
    ["P7", "Grounded AI assistant, production hardening", "Assistant answers grounded, cited and class-consistent; template fallback exact; latency within budget; security gates (rate limits, role-based access) pass"],
  ],
  [10, 42, 48]));
body.push(h2("5.2 Evaluation Protocol"));
body.push(p("Six test families operationalise the research questions. T1 (live fetch) exercises end-to-end ingestion across four coastal cities, asserting valid payloads and freshness within contract. T2 (rule enforcement) requires that requests inside the June-July sardine closure and inside a reserve are blocked with the correct reason. T3 (scoring behaviour) requires that synthetic input sweeps show the index monotonic in every argument, with class transitions exactly at the configured thresholds. T4 (retrieval relevance) requires that top-k retrieved context for closure, protected-area, weather-safety and bycatch queries is topically relevant and correctly attributed. T5 (assistant behaviour) requires that the conversational layer never contradicts the advisory class, that citations resolve to retrieved passages, that answers with no context refuse rather than improvise, that repeat advisories are served from cache, that every answer names its backend, and that live answers return within the configured latency budget when a model server is present, with the deterministic template path passing the same gates when it is not. T6 (security behaviour) requires that the rate limiter enforces and recovers within its window, that privileged endpoints answer 401 without credentials and 403 with insufficient roles, that security headers accompany every response, that oversized request bodies are rejected, and that public endpoints remain unaffected by the access-control layer."));
body.push(h2("5.3 Ethics, Licensing and Data Governance"));
body.push(p("All ingested sources are open-licensed or publicly documented. Local-knowledge ingestion is consent-gated and attributed at source. The optional AIS module is disabled by default because vessel-effort data is legally restricted in many jurisdictions. The system is advisory: it recommends, never commands, and it displays data age so that degraded advice is identifiable as such."));

/* 6. Data and case study */
body.push(h1("6. Data Sources and Case Study"));
body.push(h2("6.1 Case Study Region"));
body.push(p("The case study targets the southwest coast of India, selected for three properties: an active seasonal closure regime, including the June-July monsoon fishing closure and spawning protection for the oil sardine; a network of marine protected areas; and economically dominant small pelagic fisheries, sardine and mackerel above all, whose landings fluctuate strongly from year to year [7]. Four coastal cities anchor the live-fetch tests, spanning the length of the study coast."));
body.push(h2("6.2 Species Registry"));
body.push(p("Table 6 lists the registry. *Sardinella longiceps* (Indian oil sardine) is the pelagic mainstay and subject to the June-July closure; *Rastrelliger kanagurta* (Indian mackerel) is the co-dominant pelagic; *Thunnus tonggol* (longtail tuna) represents a higher-value, wider-ranging target; and *Penaeus monodon* (giant tiger prawn) represents a data-poor, high-value taxon that exercises the habitat fallback pathway."));
body.push(tableCaption(6, "Species registry for the case study"));
body.push(threeLine(
  ["Species", "Common name", "Fishery role", "Modelling path"],
  [
    [{ t: "Sardinella longiceps", i: true }, "Indian oil sardine", "Pelagic mainstay; June-July closure", "LSTM tendency + habitat blend"],
    [{ t: "Rastrelliger kanagurta", i: true }, "Indian mackerel", "Co-dominant pelagic", "LSTM tendency + habitat blend"],
    [{ t: "Thunnus tonggol", i: true }, "Longtail tuna", "Higher-value pelagic", "Habitat-led with occurrence priors"],
    [{ t: "Penaeus monodon", i: true }, "Giant tiger prawn", "Data-poor, high-value", "Habitat-suitability fallback"],
  ],
  [26, 18, 28, 28]));
body.push(h2("6.3 Regulatory Corpus and Optional AIS Module"));
body.push(p("The regulatory corpus comprises protected-area polygons loaded into PostGIS, closure calendars expressed as species-month rules, and textual guidance chunked for retrieval. The optional AIS vessel-effort reference module remains disabled pending legal review (Section 5.3)."));

/* 7. Results */
body.push(h1("7. Results and Findings"));
body.push(h2("7.1 Live Ingestion and Graceful Degradation"));
body.push(p("Across the four-city live-fetch tests, the ingestion layer returned valid, complete payloads with per-source freshness within contract. Under simulated outage the offline contingency engaged: advisories continued to be issued from cached fields with explicit age flags, demonstrating graceful degradation rather than failure. Operating costs remained negligible because every source is free at the volumes used."));
body.push(h2("7.2 Rule Enforcement"));
body.push(p("Rule enforcement was exact. A request for the oil sardine during the June-July window returned allowed = false, cited spawning protection as the reason and issued the DO NOT FISH class; coordinates inside a reserve were blocked regardless of otherwise favourable scores. Because constraints execute ahead of scoring, no configuration of the score weights can legalise an illegal trip, a property the tests confirmed under weight perturbation."));
body.push(h2("7.3 Scoring Behaviour and Monotonicity"));
body.push(p("Sweeps over each input confirmed monotonicity: S increases linearly in C and W and decreases linearly in B, with class transitions exactly at 0.40, 0.60 and 0.75. Moderate conditions keep the weather component above the small-vessel safety threshold, while degraded wind or wave inputs push the advisory to DELAY OR RELOCATE; high catch likelihood with low bycatch risk yields PROCEED or PROCEED WITH CAUTION. The decision surface is legible to stakeholders: a fisher can see which term moved the class."));
body.push(h2("7.4 Retrieval Relevance and Explainability"));
body.push(p("For closure, protected-area, weather-safety and bycatch queries, the top-k retrieved context was topically relevant, and the dashboard attaches it to each advisory, satisfying the explainability requirement. Retrieval quality was verified by inspection against the source corpus rather than by automatic ranking metrics alone."));
body.push(h2("7.5 Engineering Findings"));
body.push(p("LoRA fine-tuning of the classifier converged within mid-range GPU memory with under one percent of parameters trainable, confirming the adaptation pathway. Region and species retargeting was exercised entirely through configuration, without code changes. The advisory schema proved simultaneously machine-parseable and human-readable. Table 7 summarises the validation outcomes."));
body.push(tableCaption(7, "Validation outcome summary"));
body.push(threeLine(
  ["Test family", "Checks performed", "Outcome"],
  [
    ["T1 live fetch", "Four coastal cities; payload validity; freshness", "Reliable; graceful offline degradation"],
    ["T2 rule enforcement", "June sardine closure; in-reserve coordinates", "Exact blocks with correct reasons"],
    ["T3 scoring behaviour", "Monotonicity sweeps; threshold transitions", "Monotonic in every input; classes as configured"],
    ["T4 retrieval relevance", "Closure, MPA, weather and bycatch queries", "Topically relevant context attached"],
    ["T5 assistant behaviour", "Grounding, class consistency, cache, fallback, backend naming", "Guardrails hold on every path; template fallback exact"],
    ["T6 security behaviour", "Rate limiting, role-based access, headers, body cap", "429 beyond budget; 401/403 on privileged paths; headers on every response"],
  ],
  [22, 40, 38]));
body.push(h2("7.6 Assistant Behaviour"));
body.push(p("The grounded assistant passed every T5 gate. Summaries of blocked advisories led with the authoritative STOP verdict and the blocking reason; summaries of scored advisories named the class and disclosed degraded-data age. The citation check rejected answers whose references did not resolve to retrieved passages, and the class-consistency guard restored the authoritative verdict when a generated answer attempted to soften a blocked one. With the model server stopped mid-run, the website continued to answer through the template path, quoting retrieved passages verbatim and naming its backend, so the failure mode is transparency rather than silence. On the reference hardware profile the local inference server answered within the configured latency budget under concurrent load, and the summary cache absorbed repeat requests for near-identical advisories. The complete stack, model included, ran on a single consumer GPU within the 8-12 GB budget, and the 3B laptop variant provided usable, if less fluent, behaviour on a 6 GB machine."));
body.push(p("The hardening families passed equally. The rate limiter enforced its per-endpoint budgets and recovered when the window slid; privileged endpoints answered 401 without credentials, 403 with an officer key and 200 with an admin key; security headers accompanied every response; and oversized bodies were rejected before parsing, while every public endpoint remained reachable without any credential. Blocked advisories produced localised Problem/Answer explanations on the dashboard, the vernacular species registry rendered regional names alongside scientific ones on language switch, and the ocean-news service delivered all seeded items in the reader's language with cross-language items correctly pivoted through English. The installable mobile application opened from cache with connectivity disabled, showing visibly aged data rather than a blank screen."));

/* 8. Applications and impact */
body.push(h1("8. Applications and Impact"));
body.push(p("For fishers, the system promises reduced search time and fuel spend, safer trips and fewer accidental violations, and its conversational assistant lets those without technical or legal literacy interrogate the same evidence in their own words and language, right down to the vernacular names of the fish they chase and regional ocean news translated into their reading language. For fisheries departments, it offers an evidence base for advisory bulletins and environmental monitoring, with role-based access and an audit trail suited to institutional operation. For conservation organisations, it operationalises compliance as a built-in constraint rather than an enforcement afterthought. For researchers, the ingestion and modelling pipelines are reusable infrastructure for distribution and climate-impact studies. For coastal communities, the retrieval corpus offers a durable digital home for traditional ecological knowledge, oral histories and fishing calendars, a concrete digital-humanities contribution [23], and the assistant makes that archive speak. Because the AI stack is self-hosted and open-licensed, public deployment carries no per-question inference bill, which is what makes unlimited civic use fiscally sustainable."));
body.push(p("The work aligns primarily with Sustainable Development Goal 14 (Life Below Water), particularly its targets on sustainable management and effective regulation of harvesting, and secondarily with Goals 2, 8, 9 and 13; Table 9 maps the mechanisms."));
body.push(tableCaption(9, "Alignment with the Sustainable Development Goals"));
body.push(threeLine(
  ["Goal", "Mechanism in this system"],
  [
    ["SDG 14 Life Below Water", "Closures and MPAs as hard constraints; bycatch term in the index"],
    ["SDG 2 Zero Hunger", "Improved catch-per-effort for nutritious small pelagics"],
    ["SDG 8 Decent Work", "Reduced fuel and search labour; safer working conditions"],
    ["SDG 9 Industry and Innovation", "Open-source, low-cost advisory infrastructure"],
    ["SDG 13 Climate Action", "Climate-adaptive, data-driven fishing calendars"],
  ],
  [30, 70]));
body.push(p("The normative contribution deserves emphasis. Conservation, legality and safety are embedded in the objective function itself: the system cannot recommend an illegal or protected-area trip under any weight configuration, and ecological risk enters the score on equal footing with catch opportunity. Responsible marine AI, on this evidence, is less a matter of model scale than of where the constraints sit in the pipeline."));

/* 9-11 */
body.push(h1("9. Limitations"));
body.push(p("Predictive skill is bounded by data quality: occurrence records carry sampling bias, and satellite fields inherit sensor and cloud-cover uncertainty. Data-poor taxa rely on habitat envelopes and expert rules rather than learned dynamics. Forecast horizons beyond a few days compound uncertainty, so advisories are probabilistic guidance, never guarantees. AIS- and VMS-derived effort data remains legally restricted in many jurisdictions and is therefore optional. The assistant, in turn, is a 7-8B-class model: guardrails eliminate fabricated citations and verdict contradictions by construction, but fluency, nuance and fine image detail are bounded by model scale, and multilingual quality varies across the ten supported coastal languages; the smaller 3B laptop variant trades further fluency for accessibility. Latency under peak load depends on the deployed GPU tier and caching. Most importantly, no longitudinal field trial has yet been conducted: adoption, trust and realised catch and safety outcomes remain unmeasured."));
body.push(h1("10. Future Scope"));
body.push(p("Six directions follow naturally. Longitudinal pilots with fishing cooperatives, measured against pre-system baselines, would test real-world impact. Coupling to ocean-circulation and climate-projection models would extend horizons for anticipating distribution shifts. Federated learning across regions would adapt models without exchanging sensitive data. Blockchain traceability linking advisories to catch records would support verified sustainable seafood. The installable mobile application is delivered; what remains of the mobile roadmap is voice-first interaction built on small open speech models for non-literate users, and deeper offline synchronisation for connectivity-poor vessels. And the assistant itself invites refinement: dialogue-style fine-tuning on consented fisher conversations would deepen the conversational channel that this work established."));
body.push(h1("11. Conclusion"));
body.push(p("This paper delivered ParaSail, a production-grade, retrieval-augmented geospatial decision support system for the digital blue economy. It integrated live environmental data, biodiversity records, satellite imagery and conservation rules into one coherent architecture, added a grounded, self-hosted vision-language assistant that summarises, explains and answers questions in plain language on the public website, and its operational validation showed that sustainability-scored, explainable, conversational advisories are feasible with open-source tools, a single consumer-grade GPU and no per-request inference costs. The core lesson is that responsible marine AI embeds conservation, legality and safety as constraints, and earns trust through explainability and local adaptation, including in the conversational layer, where guardrails bind the model to retrieved evidence and the authoritative verdict. The work thereby satisfies the summit's key principle: digital technology addressing a real problem of fisheries, oceans, coastal communities, conservation and sustainability."));

/* 12. Mandatory questions */
body.push(h1("12. The Five Mandatory Summit Questions"));
body.push(itemP("Q1", "What is the problem? Fishers and coastal managers lack a real-time, integrated, explainable advisory system for sustainable fishing; the consequences are wasted effort, accidental violations, ecological damage and avoidable safety risk."));
body.push(itemP("Q2", "Why is it important? It affects livelihoods, food security, marine conservation and human safety simultaneously, which is precisely the intersection the blue economy must govern."));
body.push(itemP("Q3", "What digital technology is used? Geospatial AI (YOLOv8, Vision Transformer with LoRA, LSTM, random forest), retrieval-augmented generation over a dual-collection vector database, a self-hosted open-source vision-language assistant (Qwen2.5-VL-7B, 4-bit AWQ, served with vLLM within an 8-12 GB VRAM budget) with a runtime-switchable model registry, and open live environmental APIs, orchestrated with FastAPI, PostGIS, Qdrant and Docker; the website is hardened with rate limiting and role-based access and ships as an installable offline-capable mobile web app."));
body.push(itemP("Q4", "What data and evidence supports the study? Open meteorological, oceanographic, biodiversity and satellite data, regulation datasets, and a working system validated through live-fetch, rule-enforcement, scoring-behaviour, retrieval-relevance, assistant-behaviour and security-behaviour tests on a southwest-India case study."));
body.push(itemP("Q5", "What solution and contribution is provided? A production-grade platform issuing sustainability-scored, explainable, conversational fishing advisories while enforcing conservation rules as hard constraints, adaptable to new regions and species through configuration and parameter-efficient fine-tuning, and deployable with local AI on owned hardware at zero marginal inference cost - hardened, multilingual and mobile-ready for public use."));

/* References */
body.push(h1("References"));
const refs = [
  "[1] World Bank. The Potential of the Blue Economy: Increasing Long-Term Benefits of the Sustainable Use of Marine Resources for Small Island Developing States and Coastal Least Developed Countries. Washington, DC: World Bank, 2017.",
  "[2] FAO, Duke University, WorldFish. Illuminating Hidden Harvests: The Contributions of Small-Scale Fisheries to Sustainable Development. Rome: FAO, 2023.",
  "[3] FAO. The State of World Fisheries and Aquaculture 2023. Rome: FAO, 2023.",
  "[4] UNEP. Turning off the Tap: How the World Can End Plastic Pollution and Create a Circular Economy. Nairobi: UNEP, 2023.",
  "[5] OECD. Global Plastics Outlook. Paris: OECD Publishing, 2022.",
  "[6] Cheung W W L, Lam V W Y, Sarmiento J L, et al. Large-scale redistribution of maximum fisheries catch potential in the global ocean under climate change. Global Change Biology, 2010, 16(1): 24-35.",
  "[7] ICAR-CMFRI. Marine Fish Landings in India. Kochi: Central Marine Fisheries Research Institute, 2024.",
  "[8] Costello C, Ovando D, Clavelle T, et al. Global fishery prospects under contrasting management regimes. Proceedings of the National Academy of Sciences, 2016, 113(18): 5125-5129.",
  "[9] Worm B, Barbier E B, Beaumont N, et al. Impacts of biodiversity loss on ocean ecosystem services. Science, 2006, 314(5780): 787-790.",
  "[10] Pauly D, Zeller D. Catch reconstructions reveal that global marine fisheries catches are higher than reported and declining. Nature Communications, 2016, 7: 10244.",
  "[11] INCOIS. Potential Fishing Zone Advisories: Methodology and Validation. Hyderabad: Indian National Centre for Ocean Information Services, 2024.",
  "[12] Elith J, Leathwick J R. Species distribution models: ecological explanation and prediction across space and time. Annual Review of Ecology, Evolution, and Systematics, 2009, 40: 677-697.",
  "[13] Jocher G, Chaurasia A, Qiu J. Ultralytics YOLOv8. 2023.",
  "[14] Dosovitskiy A, Beyer L, Kolesnikov A, et al. An image is worth 16x16 words: Transformers for image recognition at scale. International Conference on Learning Representations, 2021.",
  "[15] Hochreiter S, Schmidhuber J. Long short-term memory. Neural Computation, 1997, 9(8): 1735-1780.",
  "[16] Breiman L. Random forests. Machine Learning, 2001, 45(1): 5-32.",
  "[17] Lewis P, Perez E, Piktus A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks. Advances in Neural Information Processing Systems 33, 2020: 9459-9474.",
  "[18] Gao Y, Xiong Y, Gao X, et al. Retrieval-augmented generation for large language models: A survey. arXiv preprint arXiv:2312.10997, 2023.",
  "[19] Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Advances in Neural Information Processing Systems 30, 2017: 5998-6008.",
  "[20] Hu E J, Shen Y, Wallis P, et al. LoRA: Low-rank adaptation of large language models. International Conference on Learning Representations, 2022.",
  "[21] Reimers N, Gurevych I. Sentence-BERT: Sentence embeddings using Siamese BERT-networks. Proceedings of EMNLP-IJCNLP, 2019: 3982-3992.",
  "[22] Radford A, Kim J W, Hallacy C, et al. Learning transferable visual models from natural language supervision. Proceedings of ICML, 2021: 8748-8763.",
  "[23] Berkes F. Sacred Ecology. 4th ed. New York: Routledge, 2017.",
  "[24] Open-Meteo. Open-Meteo API Documentation. 2024.",
  "[25] Copernicus Marine Service. Copernicus Marine Service Product Documentation. Copernicus Programme, 2024.",
  "[26] GBIF. GBIF Occurrence Download. Copenhagen: Global Biodiversity Information Facility, 2024.",
  "[27] OBIS. Ocean Biodiversity Information System Data. Ostend: OBIS, 2024.",
  "[28] FishBase. FishBase: World Wide Web Electronic Publication. 2024.",
  "[29] Drusch M, Del Bello U, Carlier S, et al. Sentinel-2: ESA's optical high-resolution mission for GMES operational services. Remote Sensing of Environment, 2012, 120: 25-36.",
  "[30] Donlon C, Berruti B, Buongiorno A, et al. The Global Monitoring for Environment and Security (GMES) Sentinel-3 mission. Remote Sensing of Environment, 2012, 120: 37-57.",
  "[31] Qdrant. Qdrant Vector Database Documentation. 2024.",
  "[32] CSA Department. Guidance for Paper Presentation: Digital Blue Economy Summit. 2025.",
  "[33] Bai S, Chen K, Liu X, et al. Qwen2.5-VL technical report. arXiv preprint arXiv:2502.13923, 2025.",
  "[34] Kwon W, Li Z, Zhuang S, et al. Efficient memory management for large language model serving with PagedAttention. Proceedings of the 29th Symposium on Operating Systems Principles (SOSP), 2023: 611-626.",
  "[35] Lin J, Tang J, Tang H, et al. AWQ: Activation-aware weight quantization for LLM compression and acceleration. Proceedings of Machine Learning and Systems (MLSys), 2024.",
];
refs.forEach(r => body.push(refP(r)));

/* ---------- document ---------- */
const doc = new Document({
  creator: "ParaSail",
  title: "ParaSail: A Retrieval-Augmented Geospatial Decision Support System",
  styles: {
    default: {
      document: {
        run: { font: TNR, size: 22, color: BLACK },
        paragraph: { spacing: { line: 312 } },
      },
      heading1: {
        run: { font: TNR, size: 28, bold: true, color: BLACK },
        paragraph: { spacing: { before: 230, after: 90, line: 312 }, outlineLevel: 0 },
      },
      heading2: {
        run: { font: TNR, size: 24, bold: true, color: BLACK },
        paragraph: { spacing: { before: 150, after: 70, line: 312 }, outlineLevel: 1 },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1180, bottom: 1180, left: MARGIN_L, right: MARGIN_R, header: 700, footer: 780 },
        pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "999999" } },
        children: [new TextRun({ text: "ParaSail  |  26th Digital Blue Economy Summit", size: 16, color: "666666", font: TNR })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, font: TNR, color: "444444" })],
      })] }),
    },
    children: [...titleBlock, ...abstractBlock, ...body],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("ParaSail_Research_Paper.docx", buf);
  console.log("WROTE ParaSail_Research_Paper.docx bytes=" + buf.length);
});

# Suggested-fish prediction

What the "likely spots" and the teal zone on the map actually are, how the
scorer is chosen, how to retrain it, and — plainly — how accurate it is.

## Two scorers, one geometry path

The suggestion layer scores every cell of a ~50 km grid (0.03° cells, the
zone boundary resolution) around the requested point. Two scorers exist, and
the API response always says which one produced a zone:

| Scorer | When it is used | What it is |
|---|---|---|
| **Trained habitat model** | when `models/habitat_<species>.joblib` exists and the species cleared the training-record floor | calibrated probability of presence from sea temperature, distance to shore and month |
| **Thermal envelope** | otherwise — including for every species today | 1.0 inside the species' preferred band, linear falloff outside. **Untrained.** |

Selection is `suggestions.method` in `config.yaml`:

```yaml
suggestions:
  method: auto              # auto | envelope | model
  min_training_records: 50
```

`auto` prefers an artifact and falls back silently-but-visibly (the response
reports `training_records: null` and an "untrained" method string).
`envelope` pins the fallback; `model` pins the trained path and still
degrades to the envelope if the artifact cannot be read.

## Feature contract — train/serve parity is the rule

Features are **exactly** what the serving path can supply for every cell:

| Feature | Serving source | Training source |
|---|---|---|
| `sst_c` | Open-Meteo live marine | OBIS reanalysis field attached to each occurrence |
| `distance_to_shore_km` | computed from the ocean mask (`distance_to_shore_km`) | OBIS `shoredistance` |
| `month_sin`, `month_cos` | current month (UTC) | record's `date_mid` |

Chlorophyll, bathymetry, salinity and currents are deliberately **not**
features. None of them can be produced live without wiring a new data source,
and a feature that exists in training but not at inference — or is silently
defaulted — is how a model degrades without anyone noticing. They are kept in
the training table as diagnostic columns.

**One documented caveat:** training sea temperature comes from a reanalysis
field (via OBIS), while serving temperature comes from Open-Meteo's live
marine forecast. Two products, not one. The held-out metrics below include
that mismatch.

## How accurate is it?

**No model is currently deployed, and that is the measured result, not an
omission.**

Training was run on the open data available (2026-09). Two configurations,
both rejected by the adoption rule:

| Run | Presences (after thinning) | Block-CV AUC (model vs envelope) | Held-out survey AUC |
|---|---|---|---|
| Case-study box 72–78°E, 7–13°N | 54 | 0.641 vs 0.552 | 0.580, 0.672 |
| Species range 68–80°E, 5–25°N | 79 | 0.618 vs 0.431 | 0.667, 0.607, **0.485** |

The model beats the envelope under spatial-block cross-validation, but it does
**not** transfer to a survey it has never seen. A first run reported AUC 0.891
with precision@10 % of 1.000 — that number was an artefact: 84 of 86 presences
came from two surveys with a 0.5 °C temperature sliver, so the model had
learned the cruise signature. Spatial thinning (0.1° × month), a
dataset-matched background and the held-out-survey test were added to expose
exactly that, and the honest number is the one in the table.

So the system reports **habitat discrimination from open data, not catch
prediction**. Catch-level accuracy cannot be measured at all without landings
or effort data (CMFRI/ICAR), which is a data request, not a code change. The
same statement is in the paper's Limitations section; the interface says it
too.

## Adoption rule

`scripts/train_habitat.py` writes an artifact only when BOTH hold:

1. **block-CV superiority** — the model's AUC exceeds the envelope's by
   `ADOPT_MARGIN` (0.02) on identical spatial folds;
2. **transfer** — the minimum leave-one-dataset-out AUC is ≥ 0.60, i.e. it
   recognises a survey it was not trained on.

Species below the record floor (`--min-records`, default 50 thinned
presences) get no model at all: with the open data available that excludes
every species except the oil sardine, and tuna has no records in the region.

## Retraining

```bash
cd parasail
python scripts/train_habitat.py                       # all registry species
python scripts/train_habitat.py --species "Sardinella longiceps" \
       --bbox "POLYGON((68 5,80 5,80 25,68 25,68 5))" \
       --max-depth 5 --n-estimators 300
```

Outputs (all gitignored except the script):

| Path | Contents |
|---|---|
| `data/habitat_training_<slug>.csv` | the table actually used, with block and diagnostic columns |
| `data/habitat_metrics.json` | per-species AUC / TSS / precision@k per fold, model vs envelope, held-out-survey results, and the adoption decision |
| `models/habitat_<slug>.joblib` | the artifact the serving path loads (only when adopted) |

Run it whenever the occurrence data grows, or after changing the feature
contract. `min_records` and the margin are at the top of the script.

## Effort data — the catch-level path (ready, waiting for data)

The presence-only pipeline above is capped by its data. An effort export
removes that cap: a trip that applied effort and caught none of the target
species is a **true absence**, and nothing in the open occurrence record can
supply one. The code path is implemented and validated — it needs data.

```bash
python scripts/train_habitat.py --effort landings.csv        --species "Sardinella longiceps"
```

CSV columns (one row = one landing or trip):

| Column | Meaning |
|---|---|
| `date` | `YYYY-MM-DD` (or ISO); used for time-block folds |
| `lat`, `lon` | where the effort was applied |
| `catch_kg` | catch of the target species; `0` is a valid, valuable row |
| `effort_hours` | hours fished — also the sample weight |
| `sst_c` | sea temperature at that place and date |
| `distance_to_shore_km` | distance to shore (from the ocean mask or the export) |
| `species` | optional; filters rows when given |

What it reports that the presence-only path cannot:

* **AUC** on **time-block** folds (date ranges held out, not cells — effort
  records are dense and autocorrelated in space, so spatial folds leak);
* **Spearman correlation between the model's score and observed CPUE** — the
  honest "does the score track what was caught" number;
* the envelope scored on the same rows, for a like-for-like comparison.

An effort-trained model is published only when AUC ≥ 0.65, Spearman ≥ 0.20
and it beats the envelope by the usual margin; otherwise the metrics are
written and the envelope stays served. Both the adoption logic and the
sample-size refusal (fewer than 20 positive or 20 absent rows) are covered by
the T7 family.

## What would make it genuinely predictive

1. **Effort data** (CMFRI landings/CPUE) — the only way to score catch
   accuracy, and the only way to model absences properly instead of
   approximating them with background points.
2. **More surveys.** The binding constraint is dataset diversity, not model
   choice: three surveys cannot validate a habitat model, however many rows
   they contribute.
3. **A consistent historical SST product** (ERDDAP/CoastWatch OISST or
   Copernicus) so training and serving use one source and occurrences from
   before 2022-12 become usable.
4. Then chlorophyll fronts and currents, which are the features fishers
   actually reason about — once they can be served live.

## Fleet effort (Global Fishing Watch)

AIS-derived effort is available and wired up: **daily, per-vessel fishing
hours with position, flag and gear type**. Token lives in `parasail/.env`
as `GFW_API_TOKEN` (gitignored).

```bash
python scripts/fetch_gfw_effort.py --start 2025-09-01 --end 2026-03-31        --bbox 68,6,80,23                     # writes data/gfw_effort_*.csv
python scripts/analyse_effort_vs_mpa.py        # newest extract by default
```

Measured, Sep 2025–Mar 2026 over 68–80°E / 6–23°N (211 days):

| | |
|---|---|
| records / effort | 197,907 records · **853,940 fishing hours** |
| flags | IND 614,541 h · LKA 224,826 h · CHN 5,189 h |
| gears | drifting longlines 413,462 h · trawlers 284,244 h · set longlines 39,209 h |
| inside a protected area | **122 h — 0.014%**, all in Marine (Gulf of Kachchh) NP |
| within 5 km of shore | 4,670 h — 0.5% (the fleet works offshore) |

**What it is used for — and what it must not be used for.** Effort is a
sampling-bias correction: background points can be weighted by where the
fleet actually fished, so the model stops comparing "recorded" against
"never visited". It is **not** a habitat feature — effort follows fish, so
using it as a predictor is circular. And it is **not** catch, so it cannot
produce the accuracy number on its own; landings remain the missing half.

**Caveats that must travel with any number here:** AIS over-represents
larger vessels, so small-boat activity near shore is under-counted; the
inside-MPA figure is a compliance *signal*, not proof; and "0% of effort
inside MPAs" is meaningless when the box contains no MPAs — we hit exactly
that trap with the original 72–78°E box, where 0 of 2,682 sampled ocean
points fell inside any registry polygon.

**Attribution:** these extracts are Global Fishing Watch data; cite Global
Fishing Watch when publishing anything derived from them.

**Policy note for the paper:** §5.3 describes AIS as optional and disabled
pending legal review. GFW publishes this effort openly, but using it as a
model input is the operator's decision — if it is enabled, that sentence and
the limitations section should be updated to say so.

## Validation

`scripts/run_validation.py` family **T7** covers this offline: artifact
round-trip and probability range, isotonic monotonicity, loader degradation,
the thermal response peaking inside the species' band, the served path
reporting the scorer it actually used, zone geometry staying on the mapped
ocean, and an adoption decision recorded per species with no adopted model
worse than chance.

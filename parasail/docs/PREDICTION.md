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

## Validation

`scripts/run_validation.py` family **T7** covers this offline: artifact
round-trip and probability range, isotonic monotonicity, loader degradation,
the thermal response peaking inside the species' band, the served path
reporting the scorer it actually used, zone geometry staying on the mapped
ocean, and an adoption decision recorded per species with no adopted model
worse than chance.

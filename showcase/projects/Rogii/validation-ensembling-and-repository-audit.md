---
type: project-doc
projects:
  - "[[Rogii]]"
domains:
  - "Machine Learning"
  - "Evaluation"
  - "Open Source"
topics:
  - "cross-validation"
  - "ensembling"
  - "tail risk"
  - "repository audit"
  - "reproducibility"
derived_from:
  - "[[solutions]]"
source_refs:
  - "source:rogii-leaderboard"
  - "source:rogii-writeup-01"
  - "source:rogii-writeup-02"
  - "source:rogii-writeup-03"
  - "source:rogii-writeup-04"
  - "source:rogii-writeup-05"
  - "source:rogii-writeup-06"
  - "source:rogii-writeup-07"
  - "source:rogii-writeup-08"
  - "source:rogii-writeup-09"
  - "source:rogii-writeup-10"
  - "source:rogii-repo-ruby"
  - "source:rogii-repo-lightsource"
  - "source:rogii-repo-james-early"
  - "source:rogii-toolkit-mycarta"
  - "source:rogii-repo-keithtyser-14th"
  - "source:rogii-top10-zenn"
  - "source:rogii-top10-michikusa"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---
# Validation, Ensembling, and Repository Audit

## Why these belong together

An ensemble is trained on validation predictions. A repository claim is validated against writeup and code. Both are evidence problems:

```text
What information was available?
Was it out of sample?
Does the artifact actually implement the claimed method?
What boundary prevents overclaiming?
```

ROGII's small number of wells, spatial structure and squared-error tail make weak evidence especially dangerous.

## 1. Split unit and leakage model

### Row split is invalid

Rows within a well share:

- typewell;
- spatial coordinates and trajectory;
- known prefix;
- latent geological surface;
- GR morphology;
- target path continuity.

A row split makes validation largely a reconstruction of the same well.

### Well-level GroupKFold is the minimum

Every well must be entirely in one fold. Third-place public indexing reports 773 wells split approximately 155/155/155/154/154.

### Geographic and typewell leakage

Spatial features can carry label information through nearby wells. The split and feature builder must ensure validation-well labels are absent from:

- neighbor surface fits;
- noise banks built from target residuals;
- typewell-derived aggregations;
- synthetic samples copied or warped from validation wells;
- candidate tuning.

The exact same fold map must be used across candidate generation, base models and stackers.

## 2. OOF-only stacking contract

For each fold:

```text
train base member on folds != k
predict fold k
store OOF predictions and diagnostics
```

After all folds:

```text
fit blender/gate/ranker only on OOF features
```

For final inference, retrain base members on all training wells and apply the fixed blender or a rigorously reconstructed full-data equivalent.

Violations include:

- fitting candidate parameters on all wells before OOF;
- using in-sample base predictions to train a gate;
- selecting band boundaries from validation labels without nesting;
- generating synthetic refiner inputs from a model that saw the same well.

## 3. RMSE tail anatomy

Pooled RMSE is:

\[
RMSE=\sqrt{\frac{\sum_w\sum_{i\in w} e_{wi}^2}{\sum_w n_w}}
\]

Long wells and catastrophic shifts dominate. Report:

- total SSE share by well;
- top 1/5/10 well contributions;
- per-well RMSE quantiles;
- max error and max-RMSE well;
- error by target-zone length;
- error by `md_since_anchor`.

A model can improve the median well but worsen pooled RMSE through one catastrophic shift.

### Influence test

For model A versus B, compute the score difference after removing each well. A stable winner should remain competitive under:

- leave-one-well-out;
- leave-largest-contribution-out;
- bootstrap by well;
- repeated geographic folds.

Rank 2 explicitly emphasizes largest-contribution robustness; Rank 8 highlights tail concentration.

## 4. Public leaderboard as weak evidence

The final leaderboard uses a much larger private portion than Public. Public has a comparatively small number of wells, so model ordering has high variance.

Examples:

- Rank 8 reports Public-strong members collapsing on Private.
- Rank 9 selected a strict-CV-favored but Public-worse blend and improved Private.
- Rank 10 moved from Public rank 21 to Private rank 10.
- Rank 10's spatial feature improved CV but worsened Public under neighbor-distance shift.

Decision rule:

```text
honest OOF + robustness + shift audit
> one Public score
```

Public can falsify obvious bugs, not certify generalization.

## 5. Ensemble design

### Measure diversity before blending

For every member pair, compute:

- row-level residual correlation;
- per-well RMSE correlation;
- catastrophic-well overlap;
- error correlation by distance band;
- candidate support overlap.

A low global correlation can hide identical tail failures.

### Fixed blend

Fit constrained linear or NNLS weights. Low capacity and robust with few wells. Use nested CV or regularization if many members.

### Banded blend

Rank 9 fits weights by `md_since_anchor`. This encodes a known reliability regime with relatively few parameters.

Recommended constraints:

- nonnegative weights;
- sum-to-one or bounded total scale;
- adjacent-band smoothness;
- minimum effective support per band;
- bootstrap stability.

### Neural gate

Rank 3 uses a SoftMax gate. Inputs should be deployment-visible reliability signals:

- candidate disagreement/spread;
- local GR match quality;
- prior uncertainty;
- distance from anchor;
- missingness;
- surface support;
- member-specific confidence.

Regularize weight variation and compare against banded NNLS.

### Candidate ranker

Ranks 6, 8 and 10 separate generation and selection. Always report:

```text
oracle candidate RMSE
learned selector RMSE
selector regret
candidate recall/support miss
```

### Prior guardrail

A physical prior can be a fallback or soft pull in low-confidence regions. Tune with tail metrics, not only mean OOF.

## 6. Uncertainty

Useful proxies include:

- entropy of an alignment map;
- variance of PF particles;
- candidate spread;
- ensemble variance;
- refiner disagreement;
- spatial prior fit residual;
- forward/backward HMM disagreement.

A proxy becomes useful only after calibration:

```text
bin by predicted uncertainty
→ measure actual absolute/squared error
→ inspect monotonicity and coverage
```

For RMSE, high-uncertainty cases may justify conservative prior pull or multi-path propagation.

## 7. Repository audit protocol

### Level 0 — name match

A repository contains “ROGII” in its name. This has almost no attribution value.

### Level 1 — competition linkage

README links the competition or author profile. Still insufficient for final-solution status.

### Level 2 — identity linkage

Official writeup links the repository, or author identity can be independently confirmed.

### Level 3 — semantic correspondence

Code contains the representation, model family, training procedure and decoder described in the final writeup.

### Level 4 — reproducibility coverage

Repository exposes:

- pinned revision;
- environment/dependencies;
- data layout;
- training and inference entry points;
- fold construction;
- configurations/checkpoints or retraining path;
- expected metrics;
- license.

### Status labels

- `Verified reproduction`
- `Verified partial`
- `Authentic but non-final`
- `Supporting baseline/toolkit`
- `Unverified`
- `Not found as of DATE`

Do not collapse these labels into “open source.”

## 8. Audited repositories

### Rank 1 Ruby

**Repository:** `IAmAValidUsername/kaggle_ROGII_1st_place_solution_Ruby`  
**Revision:** `fade6112ffebd9e27c08ac7f053e8d4c3d5c319a`  
**License:** Apache-2.0  
**Status:** Verified retraining reproduction.

Evidence from README/code tree:

- six archived source/config/log recipes;
- 15 models per recipe;
- relative `SETTINGS.json`;
- `reproduce_workflow.sh --verify`;
- geographic map regeneration;
- OOF and test outputs;
- data and recipe snapshots;
- no bundled multi-GB weights;
- final six-family ensemble notebook external on Kaggle;
- stochastic CUDA reproduction, not byte-exact guarantee.

This is the correct first repository to reproduce.

### Rank 4 Lightsource

**Repository:** `l1ghtsource/rogii-wellbore-geology-prediction`  
**Revision:** `2639ef335734df733ee897704dafd4a749acc64c`  
**License:** not detected  
**Status:** Verified partial/source-available.

It contains real code for residual canvases, U-Nets, Squeezeformer, synthetic data, OOF blends and reanchoring. It does not contain James's final vision system, Alijs's PF or the full team blend.

### Rank 4 James early repository

**Repository:** `JamesMcGuigan/kaggle-rogii-wellbore-geology-prediction`  
**Revision:** `2912efd8c66a9d46bff1bbbaaf325e4e763b725c`  
**License:** not detected  
**Status:** Authentic but non-final.

`pipeline.py` is a 5-fold LightGBM pipeline using mycarta features and anchor-relative delta prediction. It predates the final submission and does not implement the final ConvNeXt V2 topography component.

### mycarta toolkit

**Repository:** `mycarta/rogii-geosteering-toolkit`  
**License:** MIT  
**Status:** Supporting baseline/toolkit, not top-10 final.

### Keith Tyser

**Repository:** `keithtyser/rogii-wellbore-geology-solution`  
**Status:** Rank 14 training repository, not top ten.

It demonstrates why a complete-looking repository cannot be assigned to the requested rank range without leaderboard identity.

## 9. Search result for ranks 2, 3, 5–10

No verified final repository was found on 2026-09-01. Searches covered:

- exact writeup titles;
- distinctive method terms;
- team and Kaggle names;
- visible GitHub accounts;
- generic ROGII repositories followed by README/code inspection.

This negative result expires. Re-run the audit when using the package later.

## 10. Reproduction sequence

### Step 1 — Verify the Rank 1 package

```bash
git clone https://github.com/IAmAValidUsername/kaggle_ROGII_1st_place_solution_Ruby.git
cd kaggle_ROGII_1st_place_solution_Ruby
git checkout fade6112ffebd9e27c08ac7f053e8d4c3d5c319a
./reproduce_workflow.sh --verify
```

### Step 2 — Reproduce one family

Use `0801_V2` first because the archived README reports the best single-family OOF among the six recipes:

```bash
./reproduce_workflow.sh --train 0801_V2 --device cuda
```

Validate output schema, fold assignments, path support, OOF metric and tail vector before training all six.

### Step 3 — Inspect semantic correspondence

Trace:

```text
dataset/window construction
→ input channels
→ PF/geo prior
→ model
→ loss
→ OOF assembly
→ test inference
```

Do not begin by modifying architecture.

### Step 4 — Study the partial Rank 4 repository

Focus on geometric prior, residual target, synthetic corruption and reanchoring. Do not compare its own OOF directly to the full team's Private score.

### Step 5 — Build an ablation ledger

Every ported idea should record:

- source method;
- exact semantic change;
- held-constant components;
- well-level fold map;
- expected mechanism;
- primary and tail metrics;
- result and decision.

Templates are included.

## 11. Minimal validation dashboard

A practical dashboard has five views:

1. **Scorecard:** pooled and per-well metrics.
2. **Tail wells:** trajectories, GR alignment, candidate paths and SSE contribution.
3. **Distance bands:** error and member weights versus `md_since_anchor`.
4. **Candidate diagnostics:** oracle, selector regret, support miss.
5. **Shift:** neighbor distance, length, GR quality, typewell and surface priors.

The dashboard should compare OOF only unless explicitly labeled diagnostic/in-sample.

## 12. Boundary

The audit verifies public artifacts, not hidden competition code. A repository can be authentic and still omit checkpoints, proprietary preprocessing or final team integration. Reproducibility is a graded property.

## Evidence Map

- Ranking/metric: `source:rogii-leaderboard`
- Validation and ensemble evidence: `source:rogii-writeup-02`, `source:rogii-writeup-03`, `source:rogii-writeup-06`, `source:rogii-writeup-08`, `source:rogii-writeup-09`, `source:rogii-writeup-10`
- Code audit: `source:rogii-repo-ruby`, `source:rogii-repo-lightsource`, `source:rogii-repo-james-early`
- Counterexamples: `source:rogii-toolkit-mycarta`, `source:rogii-repo-keithtyser-14th`

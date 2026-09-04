---
type: project-doc
projects:
  - "[[Rogii]]"
domains:
  - "Machine Learning"
  - "Synthetic Data"
topics:
  - "synthetic data"
  - "domain randomization"
  - "failure modeling"
  - "pretraining"
derived_from:
  - "[[solutions]]"
source_refs:
  - "source:rogii-writeup-01"
  - "source:rogii-writeup-02"
  - "source:rogii-writeup-04"
  - "source:rogii-writeup-05"
  - "source:rogii-writeup-07"
  - "source:rogii-writeup-08"
  - "source:rogii-repo-lightsource"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---
# Synthetic Data and Failure Modeling

## Why synthetic data became central

ROGII has 773 training wells but an enormous combinatorial space:

```text
surface shape
× well trajectory
× typewell morphology
× GR deformation/noise/missingness
× known-prefix length
× prior error
× catastrophic layer-shift mode
```

Randomly perturbing each column independently does not create a coherent geology. Successful top solutions use synthetic data for different causal purposes.

## 1. Four synthetic-data roles

### Role A — Learn the nominal observation model

Rank 2 generates physically consistent paths and GR to train conditional transitions. Rank 5 builds a high-fidelity joint world where TVT, Z and GR share latent geology.

Goal:

\[
\text{learn } p(\text{observations}\mid \text{latent path})
\]

### Role B — Learn correction around a prior

Lightsource constructs a geometric prior from known prefix and Z, then simulates residual drift, spline bumps, slope changes and prior corruption.

Goal:

\[
\text{learn } p(t-t_0 \mid \text{observations}, t_0)
\]

### Role C — Learn an upstream model's error distribution

Rank 7 fabricates first-pass HMM-like predictions and trains a U-Net refiner to correct them.

Goal:

\[
\text{learn } p(t-\hat t_{\text{first}}\mid \hat t_{\text{first}}, x)
\]

### Role D — Maintain a regularizing alternate world

Rank 8 continuously mixes synthetic and real examples, preventing the real dataset from fully overwriting synthetic structural knowledge.

These roles are not interchangeable. A generator suitable for forward pretraining may be poor for refiner training.

## 2. Joint-world generator

A robust generator begins with latent variables rather than final features.

### Step 1 — Sample a geological surface

Let:

\[
S(MD)=S_0+\beta MD+\text{piecewise knots}+\text{smooth local bumps}
\]

Constrain slope, curvature and knot frequency using training-well statistics.

### Step 2 — Combine with the real or simulated well trajectory

Under the competition coordinate convention:

\[
TVT(MD)=S(MD)-Z(MD)
\]

Hard-set or smoothly align the known prefix.

### Step 3 — Generate a shared GR world

Start from a typewell GR sequence or a latent facies/GR field. Horizontal GR should be a transformed observation of the same geological coordinate:

\[
GR_h(MD)=g(GR_v(TVT(MD));\theta_{\text{warp}})+\epsilon(MD)
\]

where `g` may include local stretch, gain, offset, blur, clipping and coherent deformation.

### Step 4 — Add sensor and operational corruption

- missing runs and random NaNs;
- gain/offset drift;
- correlated noise, not only white noise;
- local magnitude warp;
- typewell mismatch or swap;
- trajectory measurement noise;
- known-prefix fraction variation.

### Step 5 — Produce prior/candidate errors

If downstream training uses a prior, generate realistic shift, slope and break errors. If it uses a refiner, run the first-pass model or emulate its empirical error clusters.

## 3. Honest synthetic construction

“Honest” means the generator does not use hidden labels in a way unavailable at inference, and synthetic samples derived from a real well stay inside the same fold.

Leakage risks:

1. copying a full real TVT path and splitting its transformed versions across folds;
2. building a noise bank using validation labels;
3. using validation-well surface neighbors when generating training priors;
4. selecting generator parameters against Public LB;
5. retaining well IDs, lengths or typewell fingerprints that trivially reveal targets.

A safe pipeline fits generator distributions on training-fold wells only, logs source-well provenance, and emits a `synthetic_id → source_well/fold/seed/recipe` ledger.

## 4. What the top solutions teach

### Rank 1 — joint training can beat staged pretraining

Ruby reports that a simple synthetic-pretrain → real-finetune pipeline was worse than mixing simulated and real data in the main training recipe.

Mechanism hypothesis: continued synthetic exposure preserves broad path geometry while real examples calibrate sensor/domain details.

Boundary: this comparison is specific to Rank 1's generator and model; it does not refute Rank 5.

### Rank 2 — synthetic data defines the transition task

AnchorCNN needs labeled transitions at many possible anchors. Synthetic trajectories provide dense supervision for conditional moves that real wells alone cannot cover.

### Rank 4 — synthetic-only competence before real finetune

Lightsource reports a geo-plane synthetic stack around 8.9 OOF before real finetune. This shows the generator captures some real structure, but the gap to the final blend also shows domain calibration remains necessary.

### Rank 5 — synthetic data is the main training world

Approximately 25 synthetic epochs followed by a short real phase, with best real checkpoints often near epoch 2. Synthetic-only Private around 6.342 is author-reported secondary reconstruction.

Interpretation: real data mainly corrects residual domain shift rather than teaching the entire task.

### Rank 7 — simulate the mistakes, not just the wells

The refiner's training distribution contains plausible first-pass errors. This directly targets the decision problem faced at inference.

### Rank 8 — mix throughout training

A 50/50 synthetic-real mixture and decoy offsets expose the U-Net to alternative paths while retaining real calibration.

## 5. Generator validation

A generator should not be accepted because samples “look realistic.” Validate four levels.

### Level 1 — Marginals

Compare distributions of:

- well length and known fraction;
- surface slope/curvature;
- TVT increments;
- GR mean/std/spectrum/autocorrelation;
- missing-run length;
- typewell range and geology proportions.

### Level 2 — Joint relationships

Compare:

- `TVT + Z` smoothness;
- GR match error conditional on offset;
- slope versus trajectory inclination;
- prior error versus distance from anchor;
- noise behavior by geology/typewell.

### Level 3 — Two-sample distinguishability

Train a classifier to separate real and synthetic using only deployment-visible features. High AUC identifies artifacts. Low AUC is not sufficient, because a generator can match marginals while missing target relationships.

### Level 4 — Downstream transfer

Measure:

```text
real-only
synthetic-only
pretrain→finetune
joint mixture
curriculum mixture
```

on identical folds and compute per-well/tail changes. Also test whether synthetic training improves candidate recall, not only average RMSE.

## 6. Failure-mode coverage matrix

| Failure mode | Forward world | Prior corruption | Refiner error simulation | Continuous mixture |
|---|---:|---:|---:|---:|
| repeated GR motif / wrong layer | high | medium | high | high |
| long-term slope drift | high | high | high | high |
| sudden slope break | high | high | medium | high |
| missing GR segment | high | medium | high | high |
| biased geometric prior | medium | high | high | high |
| upstream block shift | low | medium | **high** | medium |
| spatial neighbor shift | low unless explicit | medium | low | low |
| extremely long target zone | high | high | high | high |

The generator recipe should be chosen from this matrix, not copied wholesale.

## 7. Avoiding synthetic shortcuts

Common shortcuts include:

- boundary padding that identifies synthetic examples;
- unrealistic quantization or interpolation;
- fixed noise spectrum;
- impossible relationships among Z, TVT and surface;
- a small catalog of typewell templates reused too often;
- overly smooth paths with no difficult recoveries;
- generator parameters chosen from hidden leaderboard feedback.

Add tests that mask source identity, randomize serialization order, and inspect feature importances of a real-vs-synthetic discriminator.

## 8. Proposed generator card

Every recipe should record:

```yaml
recipe_id:
purpose: nominal | prior-correction | refiner-error | regularization
source_well_policy:
fold_isolation:
latent_surface_model:
trajectory_source:
typewell_source:
gr_forward_model:
noise_bank_scope:
missingness_model:
prior_corruptions:
known_fraction_distribution:
constraints:
seed:
validation_metrics:
known_gaps:
```

A template is included under `templates/synthetic-generator-card.template.md`.

## 9. Decision rules

Use synthetic data when one of these is true:

- the model's state space is sparsely covered by real wells;
- a physical forward relation can generate labels and observations jointly;
- catastrophic errors can be parameterized or sampled from OOF residuals;
- a prior/refiner requires controlled corruptions.

Do not use it merely because “top teams used synthetic data.” Stop or revise when:

- synthetic-only probes learn shortcuts;
- real-vs-synthetic AUC stays high after obvious fixes;
- gains disappear on leave-largest-well-out;
- finetuning rapidly destroys performance;
- improvements occur only on Public LB.

## 10. Transfer

For ECG digitization, document alignment, robotics tracking or simulation-to-real systems, the same distinction applies:

```text
simulate the world
vs
simulate the upstream model's failures
vs
regularize against a broader alternate world
```

These are different datasets with different labels and validation contracts.

## Evidence Map

- Joint/mixed training: `source:rogii-writeup-01`
- Conditional-transition synthesis: `source:rogii-writeup-02`
- Large-scale and residual synthesis: `source:rogii-writeup-04`, `source:rogii-repo-lightsource`
- Synthetic-centric CNN: `source:rogii-writeup-05`
- Refiner failure simulation: `source:rogii-writeup-07`
- Continuous synthetic/real mixture: `source:rogii-writeup-08`

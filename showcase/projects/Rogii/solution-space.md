---
type: project-doc
projects:
  - "[[Rogii]]"
domains:
  - "Machine Learning"
  - "Geosteering"
  - "Probabilistic Inference"
topics:
  - "solution space"
  - "mechanisms"
  - "design decisions"
  - "negative evidence"
derived_from:
  - "[[solutions]]"
source_refs:
  - "source:rogii-competition"
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
  - "source:rogii-top10-zenn"
  - "source:rogii-top10-michikusa"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---
# Rogii — Solution Space

## Purpose

This document is the **Mechanism / Decision / Principle canonical source**. It does not repeat all ten solutions. It asks what design choices are available, what evidence makes each choice plausible, where it fails, and how to build the next experiment without confusing leaderboard association with mechanism.

## 1. Formal problem decomposition

Let `m` denote MD position and `t(m)` the unknown TVT. Available information consists of:

- known prefix `t(m)` before Prediction Start;
- horizontal measurements `x_h(m) = {GR, X, Y, Z, ...}`;
- typewell sequence `x_v(t) = {GR, Geology}`;
- training wells with complete `t(m)`.

A useful decomposition is:

```text
Observation likelihood:
    p(horizontal_GR(m) | typewell_GR(t), local deformation, noise)

Transition / geometry:
    p(t_m | t_{m-1}, Z_m, surface slope, geological continuity)

Prior:
    p(t | known prefix, spatial neighbors, predicted surfaces)

Posterior:
    p(t_1:T | observations, trajectory, prior)

Decision:
    predict E[t_1:T | evidence] or another RMSE-optimal path estimate
```

Every top solution implements parts of this posterior, but with different storage formats and approximations.

## 2. Representation choices

### Route A — Dense alignment field

Construct a canvas with MD on one axis and candidate TVT/residual on the other. Each pixel represents compatibility between a horizontal position and a typewell depth.

**Use when**

- local matching needs neighborhood context;
- GPU memory allows a 2D field;
- a strong image encoder-decoder is available;
- the desired output is a probability ribbon rather than a single row.

**Strength**

Convolution naturally detects diagonal, curved and broken alignment patterns. Additional evidence such as PF heatmaps, surface priors, known masks and coordinate derivatives becomes extra channels.

**Boundary**

The discretization window can exclude the truth; downsampling can erase sharp transitions; a visually smooth probability map is not automatically physically valid. Full-resolution scaling did not reliably improve Rank 1.

### Route B — Conditional transition distribution

Predict `p(ΔTVT | anchor TVT, local evidence)` and combine transitions with DP.

**Use when**

- local dynamics are easier to learn than absolute paths;
- exact or approximate global decoding is feasible;
- path uncertainty should remain explicit.

**Strength**

The model exposes the state transition structure and can delay hard commitment until later evidence. It is compact relative to a full 2D canvas.

**Boundary**

Teacher forcing creates train/inference mismatch. Discrete transitions impose a support limit. Exact DP is only exact for the model actually specified; model misspecification remains.

### Route C — Candidate bank + learned selection

Generate trajectories using PF, HMM, beam search, geometric projection or multiple neural models; then rank or blend candidates.

**Use when**

- classical dynamics can generate valid paths cheaply;
- posterior modes are easy to enumerate but hard to score;
- interpretability and modular ablation matter.

**Strength**

Candidate recall and candidate scoring are separately measurable. A wrong selector can be diagnosed independently from a missing candidate.

**Boundary**

A selector cannot choose a trajectory absent from the bank. More candidates may only add correlated noise. Candidate generation must be OOF for stacking.

### Route D — Geometric prior + residual correction

Build a physically/geometrically plausible prior `t0(m)` and predict `r(m)=t(m)-t0(m)`.

**Use when**

- a prefix-anchored surface extrapolation is informative;
- absolute depth range is large but residual range is bounded;
- long sequences can be decoded in chunks.

**Strength**

Reduces the learning target, makes prior error explicit, and supports reanchoring.

**Boundary**

A biased prior can narrow the canvas around the wrong layer. The model must be trained against corrupted priors, slope breaks and other realistic prior failures.

## 3. Candidate-generation mechanisms

### Particle Filter

PF approximates a multi-modal sequential posterior with particles. In ROGII it combines transition noise, GR likelihood and geometry/surface constraints.

What the top solutions add is not simply “use PF”:

- Rank 1 converts PF output into a neural evidence channel.
- Rank 3 retains PF as one independent expert.
- Rank 6 deliberately builds 91 diverse PF configurations and learns row/candidate fusion.
- Rank 8 ranks about 20 PF trajectories.
- Rank 10 uses 16-seed PF in a staged candidate system.

The transferable lesson is to separate:

```text
particle dynamics
observation likelihood
resampling/smoothing
candidate diversity
candidate scoring
```

A single PF score does not reveal which part failed.

### HMM and level-slope trackers

HMMs provide explicit state transitions and forward/backward or Viterbi-style inference. They are strong near a trusted prefix anchor and when the dynamics are approximately stationary.

Their common failure is accumulated layer shift. Ranks 3, 7, 9 and 10 therefore pair HMMs with neural candidates, correction networks or distance-aware blending.

### Beam search

Beam search keeps a finite set of high-scoring path prefixes. It can represent sharper alternatives than a particle cloud, but pruning can permanently remove the correct branch.

Use it when the transition space is discrete enough to enumerate and when a scoring function has meaningful prefix discrimination.

## 4. Global decoding and drift control

### Why local argmax is structurally weak

Repeated GR patterns create several local peaks. Row-wise argmax can jump between peaks. Greedy autoregression can lock into a wrong peak. A path decoder should aggregate evidence across future positions and enforce continuity.

### Exact DP expectation

Rank 2 combines transition distributions with DP and reports better results than greedy rollout or Viterbi-only decoding. For RMSE, posterior expectation is the natural point estimate when the posterior is calibrated; the most probable path is not necessarily the minimum expected squared-error path.

### Reanchoring

Rank 4 Lightsource decodes a limited MD chunk, appends the trusted part of the prediction to the prefix, rebuilds the geometric prior and repeats.

Mechanism:

```text
long-horizon absolute extrapolation
→ bounded-horizon residual prediction
→ update anchor
→ rebuild local coordinate frame
→ repeat
```

This reduces numerical and representational drift, but can also convert an early wrong chunk into a false hard constraint. Reanchor length and confidence policy must be validated.

### Whole-well context

Ranks 1, 5 and 9 use wide/full canvases or whole-well models to give the decoder future context. This can reduce drift without hard reanchoring, at the cost of memory and potential train/test length mismatch.

## 5. Synthetic data design space

### Synthetic as forward world simulation

Generate latent geological surfaces, derive TVT from the well trajectory, sample typewell/horizontal GR from shared geology, then add realistic noise and missingness.

This is the strongest form because labels and observations share a cause.

### Synthetic as prior-corruption training

Start from real trajectory/typewell structure, create a geometric prior, corrupt its shift/slope/breaks, and train residual correction. Lightsource's honest/geo-plane recipes follow this family.

### Synthetic as failure-model training

Run or imitate a first-pass method, fabricate its characteristic errors, and train a refiner. Rank 7 uses this approach. The target distribution is not “all valid wells”; it is “errors produced by this upstream system.”

### Synthetic as continuous mixture

Rank 8 keeps synthetic examples in the training mixture rather than treating them only as initialization. This can prevent rapid forgetting during real finetuning.

### Required calibration tests

A generator should be evaluated on:

- marginal distributions of length, slope, curvature, GR spectrum, missingness;
- joint relationships among `TVT`, `Z`, surface and GR;
- prior-error distributions;
- candidate failure modes and layer shifts;
- model performance on synthetic-only, real-only and mixed validation;
- nearest-neighbor similarity to prevent copying real labels.

The generator is a model and needs its own validation card.

## 6. Fusion choices

### Fixed global blend

Simple and low variance. Appropriate when members have stable relative reliability across the well and OOF sample size is limited.

### Row-wise SoftMax gate

High flexibility. Appropriate when per-position features identify which expert is reliable. Risk: overfits OOF noise and can create fast weight oscillations.

### Candidate ranker / selector

Outputs scores over discrete curves. Easy to assess candidate oracle versus learned selector:

```text
candidate recall / oracle RMSE
→ selector regret
→ final path RMSE
```

This decomposition is especially valuable for Ranks 6, 8 and 10.

### Banded NNLS

Rank 9 uses seven `md_since_anchor` bands. It is less flexible than a neural gate but directly represents the known reliability shift from heel to toe and has fewer degrees of freedom.

### Prior pull and guardrail

Rank 10 tempers selector weights and pulls predictions toward a physical prior. This trades some local fit for catastrophic-error control.

## 7. Validation is part of the hypothesis

### Minimum split contract

- Group by well; never split rows from one well across train and validation.
- Spatial or typewell-related features must be constructed fold-safely.
- Stacking features and candidate predictions must be OOF.
- Synthetic samples derived from a real well must remain on that well's training side.

### Minimum metric vector

Do not report only pooled RMSE. Report:

```text
pooled RMSE
per-well median / p75 / p90 / p95 / max
top-k SSE contribution
RMSE by md_since_anchor band
RMSE by well length and GR quality
candidate oracle RMSE
selector regret
seed/repeat dispersion
```

### Robust selection

Use leave-largest-contribution-out or influence analysis. A model whose superiority disappears after one well is removed is not a stable winner.

### Shift audits

Compare train/validation/test-proxy distributions for:

- nearest-neighbor XY distance;
- typewell identity/frequency;
- target-zone length;
- GR missingness and spectral statistics;
- prior slope and curvature;
- distance from Prediction Start.

Rank 10's spatial-feature reversal shows why this check is not optional.

## 8. Negative evidence ledger

### Do not infer “bigger is better”

Rank 1 found that transformers and model/resolution scaling did not consistently improve the final system. The representation and evidence channels mattered more.

### Do not infer “synthetic pretrain always helps”

Rank 1 preferred joint real/sim training; Rank 5 relied heavily on pretraining; Rank 8 maintained a continuous mixture; Rank 7 generated upstream error states. “Use synthetic data” is too coarse to be a principle.

### Do not use local oracle as learnability proof

Rank 10 reported a strong local GR oracle but a weak learned selector. The target signal available to a human oracle may not be recoverable from deployment features.

### Do not treat Public LB as validation

Ranks 8, 9 and 10 document Public/Private reversals or feature shift. Public evidence is useful only after a defensible OOF protocol exists.

### Do not equate repository presence with final-solution availability

Rank 4 has a genuine author repository that is non-final, a genuine partial component repository, and no complete team repository. Provenance must be explicit.

## 9. Decision guide for a new ROGII system

### Stage 0 — Establish an honest baseline

Build well-grouped geographic CV, a simple surface prior, a GR likelihood, and one PF/HMM tracker. Produce OOF trajectories and tail diagnostics.

**Exit criterion:** deterministic replay, no row leakage, stable per-well metrics, and candidate oracle measured.

### Stage 1 — Choose uncertainty representation

Choose one primary route:

- dense alignment field if GPU/image modeling is strongest;
- transition distribution if exact path decoding is central;
- candidate bank if physical trackers are mature;
- residual prior if geometric extrapolation is strong.

**Exit criterion:** representation contains the true path within its support on nearly all OOF wells.

### Stage 2 — Build a calibrated synthetic generator

Model joint geology/trajectory/GR, not independent noise. Include prior corruption and long-tail path modes.

**Exit criterion:** a classifier cannot trivially separate real and synthetic from deployment-visible features, and synthetic-only probes learn useful path structure without label copying.

### Stage 3 — Add global decoding or reanchoring

Measure long-distance drift by `md_since_anchor`. Compare posterior expectation, DP, whole-well decoding and chunk reanchoring.

**Exit criterion:** improvement persists across length bands and largest-contribution leave-outs.

### Stage 4 — Add diversity only with measurable complementarity

Generate candidates with orthogonal state models or representations. Measure error correlation and candidate oracle before training a selector.

**Exit criterion:** candidate recall improves, not just candidate count.

### Stage 5 — Fit the lowest-capacity adequate gate

Start with banded NNLS or constrained blend; move to neural gate only when OOF data supports it.

**Exit criterion:** selector regret decreases without tail or seed instability.

### Stage 6 — Reproduce before extending

Use Rank 1's repository to reproduce one family and verify metric semantics. Use Lightsource's repository to study residual canvas and reanchoring. Only then port ideas into a new codebase.

## 10. Top principles

### Principle 1 — Preserve multimodal hypotheses until global evidence can resolve them

**Use when:** observations have repeated patterns or ambiguous local matches.

**Mechanism:** delay point collapse; aggregate over sequence context, transitions and geometry.

**Boundary:** multimodality is useful only if the decoder and validation can score modes correctly.

### Principle 2 — Model the failure distribution, not only the nominal data distribution

**Use when:** errors are dominated by rare shifts, drift, missingness or upstream model mistakes.

**Mechanism:** synthetic examples target causal relationships and catastrophic regimes.

**Boundary:** uncalibrated synthetic diversity can train artifacts and worsen real adaptation.

### Principle 3 — Treat validation design as an executable part of the model

**Use when:** groups, space, long horizons and squared-error tails matter.

**Mechanism:** fold-safe features and OOF stacking determine what information the model is actually allowed to learn.

**Boundary:** even strict CV is a model of deployment; maintain explicit shift checks and uncertainty.

## 11. Open questions

1. Can an end-to-end differentiable PF/DP system match dense U-Net accuracy while retaining calibrated posterior modes?
2. What is the best way to calibrate path uncertainty under pooled RMSE and rare catastrophic wells?
3. Should reanchoring use a hard predicted prefix, a distribution over anchors, or confidence-weighted pseudo-observations?
4. Can synthetic generators be validated with likelihood-free two-sample tests tied to downstream path errors?
5. What candidate-diversity metric predicts ensemble value better than raw prediction correlation?
6. How should spatial priors adapt when test neighbor density is unknown?
7. Can a selector be trained with structured regret rather than row-wise loss?
8. How much of Rank 1's ensemble gain survives a fully reproduced, environment-controlled ablation?

## Evidence Map

- Concrete solutions: [[solutions]]
- Representation and decoding: [[representation-and-global-decoding]]
- Synthetic data: [[synthetic-data-and-failure-modeling]]
- Physics and tracking: [[physics-priors-and-probabilistic-tracking]]
- Validation, fusion and code: [[validation-ensembling-and-repository-audit]]
- Primary source identities: `source:rogii-writeup-01` … `source:rogii-writeup-10`

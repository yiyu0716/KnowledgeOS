---
type: project-doc
projects:
  - "[[Rogii]]"
domains:
  - "Machine Learning"
  - "Probabilistic Inference"
topics:
  - "alignment"
  - "path decoding"
  - "U-Net"
  - "dynamic programming"
  - "candidate paths"
derived_from:
  - "[[solutions]]"
source_refs:
  - "source:rogii-writeup-01"
  - "source:rogii-writeup-02"
  - "source:rogii-writeup-03"
  - "source:rogii-writeup-06"
  - "source:rogii-writeup-08"
  - "source:rogii-writeup-09"
  - "source:rogii-writeup-10"
  - "source:rogii-repo-ruby"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---
# Representation and Global Decoding

## Central question

ROGII 的关键不是选 ConvNeXt、EfficientNet、GRU 还是 LightGBM，而是回答：

> 当一段 horizontal GR 与 typewell GR 在多个深度都相似时，系统如何表示“这些位置都可能”，并等待整条轨迹的证据来消歧？

逐行点回归把 posterior 提前压成一个数值。上位方案则采用四种主要 uncertainty container：

```text
dense probability field
conditional transition table
explicit candidate paths
heterogeneous model predictions
```

它们都在做 delayed commitment。

## 1. Dense MD × TVT alignment field

### Construction

For horizontal position `m_i` and candidate typewell depth `t_j`, build evidence such as:

\[
D_{ij}=|GR_h(m_i)-GR_v(t_j)|
\]

A real model adds local GR windows, normalized correlation, geometric offsets, masks, PF heatmaps and spatial priors. The target path becomes a curve through this image.

Rank 1 uses approximately:

```text
width: 345 MD positions
height: 400 TVT candidates
candidate range: ±100 ft at 0.5 ft spacing
```

The horizontal axis compresses a long prefix/target sequence by 32×. This is a design tradeoff: wide context versus local resolution.

### Why U-Net fits

Encoder layers aggregate broad context to distinguish repeated GR motifs. Skip connections retain precise candidate-row detail. The decoder emits a probability ribbon rather than an absolute scalar.

A good target is not necessarily a one-pixel hard line. Cumulative masks, signed-distance fields or smoothed row distributions provide gradients around the truth and can encode uncertainty.

### Additional channels

A reusable channel taxonomy is:

1. **Observation:** horizontal/typewell GR mismatch, NCC, local statistics.
2. **Coordinates:** MD, residual TVT axis, absolute/relative Z.
3. **Dynamics:** dZ, d²Z, local inclination, prior slope.
4. **Known state:** prefix mask, known TVT trace, prediction-start distance.
5. **Prior:** geometric path, spatial surface estimate.
6. **Candidate evidence:** PF/HMM occupancy or heatmap.
7. **Quality:** missingness, local GR variance, prior uncertainty.

Channels should be fold-safe and deployment-visible.

## 2. Conditional transition distributions

Rank 2's AnchorCNN represents:

\[
p(\Delta t_i \mid t_{i-1}=a,\; x_{1:T})
\]

for multiple possible anchors `a`. The network does not emit one next value; it emits a distribution over 21 movement classes.

### Teacher forcing

During training, query the transition table at the ground-truth anchor. This gives clean supervision but differs from inference, where the anchor distribution is uncertain.

Mitigations include:

- scheduled sampling;
- train-time anchor perturbation;
- marginalizing over a neighborhood of anchors;
- differentiable forward recursion;
- synthetic trajectories containing recovery after wrong anchors.

### Exact DP

Suppose `α_i(t)` is the probability mass at TVT state `t` after processing position `i`. A forward recursion is:

\[
\alpha_i(t)=\sum_{t'}\alpha_{i-1}(t')\,p_i(t-t' \mid t')
\]

The posterior mean

\[
\hat t_i=\sum_t t\,\alpha_i(t)
\]

minimizes expected squared error if the posterior is calibrated. This explains why posterior expectation can outperform only selecting the most probable Viterbi path.

### Boundary

State discretization, transition clipping and likelihood calibration determine whether DP is useful. Exact inference over the wrong transition model is still wrong.

## 3. Explicit candidate paths

### PF

A particle filter represents the posterior by weighted paths/states:

\[
\{t_i^{(k)}, w_i^{(k)}\}_{k=1}^K
\]

At each step:

1. propagate with transition/geometry noise;
2. score GR likelihood and prior consistency;
3. normalize;
4. resample if effective sample size is low;
5. optionally smooth backward or with fixed lag.

One run may collapse to one mode. Rank 6 therefore varies the observation representation, transition noise and priors across 91 PF configurations.

### HMM

HMM uses a discrete state grid with transition and emission matrices. Forward-backward retains state marginals; Viterbi returns a single maximum-probability path. Level-slope state augmentation can represent local geological trend but increases state size.

### Beam search

Beam search retains `B` high-scoring path prefixes. It is effective when transition candidates are sparse and prefix scores are informative. It is vulnerable to pruning the correct mode before later observations disambiguate it.

### Candidate recall versus selector regret

Evaluate candidate systems in two stages:

```text
oracle candidate RMSE
= choose the best candidate using truth

selector regret
= learned selected RMSE - oracle RMSE
```

If oracle is poor, improve generation. If oracle is strong but selector is poor, improve features/objective. Mixing these errors hides the bottleneck.

## 4. Heterogeneous prediction sets

Rank 3 gates five families; Rank 9 blends eight whole-well/tracker models; Rank 10 stages physics and learned candidates.

This representation is coarser than a dense posterior. Each model output is one hypothesis. Its advantage is diversity in inductive bias:

- tracker: local state continuity;
- image model: broad correspondence context;
- residual model: stable geometric coordinate;
- sequence model: long-range correction;
- spatial model: neighboring-well surface.

The key is not model count but **failure-mode coverage**.

## 5. Decoding choices

### Row argmax

Fast but unstable. It may switch between nearby modes.

### Soft expectation

Smooth and RMSE-aligned, but averages separated modes into an implausible middle layer.

### Viterbi / shortest path

Returns a valid high-probability path, but optimizes mode rather than squared-error expectation.

### Dynamic programming expectation

Retains multiple paths and returns state expectations. Strong when transitions are calibrated and state support covers truth.

### Constrained path optimization

Minimize:

\[
\sum_i C_i(t_i)
+\lambda_1 |t_i-t_{i-1}|
+\lambda_2 |(t_i-t_{i-1})-(t_{i-1}-t_{i-2})|
\]

This can decode any probability/cost field. The penalties must not erase true slope breaks.

### Reanchored decoding

Predict a chunk, accept a trusted subsegment, rebuild local prior, continue. It bounds coordinate drift but introduces pseudo-label feedback.

## 6. Proposed ablation matrix

Hold data, folds, synthetic generator and backbone budget fixed. Compare:

| Axis | Variants |
|---|---|
| State container | scalar regression / dense field / transition table / PF bank |
| Decoder | argmax / expectation / Viterbi / DP / constrained spline |
| Context | local 256 ft / 1,024 ft / full well |
| Prior | none / geometric / PF heatmap / XY surface |
| Drift control | none / whole-well / reanchor 250/500/1,000 ft |
| Uncertainty | entropy / spread / ensemble variance / calibrated residual quantile |

Required outputs include pooled RMSE, per-well tail, distance bands, support miss rate and oracle/selector decomposition.

## 7. Transfer

This pattern applies to sequence alignment, tracking, OCR line tracing, ECG digitization, map matching and any task where local observations repeat. The transferable principle is not “use U-Net”; it is:

> Store ambiguity in a structure that the eventual global decoder can still use.

## Evidence Map

- Rank 1 dense field: `source:rogii-writeup-01`, `source:rogii-repo-ruby`
- Rank 2 transitions/DP: `source:rogii-writeup-02`
- Candidate banks/gates: `source:rogii-writeup-03`, `source:rogii-writeup-06`, `source:rogii-writeup-08`
- Heterogeneous/banded/staged decoding: `source:rogii-writeup-09`, `source:rogii-writeup-10`

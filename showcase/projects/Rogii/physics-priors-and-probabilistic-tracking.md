---
type: project-doc
projects:
  - "[[Rogii]]"
domains:
  - "Geosteering"
  - "Probabilistic Inference"
  - "Machine Learning"
topics:
  - "physics prior"
  - "particle filter"
  - "HMM"
  - "surface coordinate"
  - "reanchoring"
derived_from:
  - "[[solutions]]"
source_refs:
  - "source:rogii-competition"
  - "source:rogii-writeup-01"
  - "source:rogii-writeup-02"
  - "source:rogii-writeup-03"
  - "source:rogii-writeup-04"
  - "source:rogii-writeup-06"
  - "source:rogii-writeup-07"
  - "source:rogii-writeup-08"
  - "source:rogii-writeup-09"
  - "source:rogii-writeup-10"
  - "source:rogii-repo-lightsource"
  - "source:rogii-toolkit-mycarta"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---
# Physics Priors and Probabilistic Tracking

## Scope

Physics does not directly reveal the correct TVT. It supplies invariants, feasible transitions and priors that reduce the posterior search space. ROGII's strongest systems combine those constraints with learned observation models and error correction.

## 1. Coordinate identity

Under the competition's sign convention, define a surface-like geological coordinate:

\[
A(MD)=TVT(MD)+Z(MD)
\]

Some implementations center it by a per-well baseline:

\[
\tilde A(MD)=TVT(MD)+Z(MD)-b_{\text{well}}
\]

If the well follows a locally smooth geological surface, `A(MD)` changes more simply than raw TVT. Then:

\[
\Delta TVT = \Delta A - \Delta Z
\]

Rank 2 uses this relation to generate physically consistent transition labels; Rank 10 reports the identity is numerically satisfied to within small rounding tolerance in the data.

### What this gives

- a lower-complexity prior coordinate;
- explicit relationship between trajectory change and TVT change;
- a way to generate synthetic paths;
- constraints on transition increments.

### What it does not give

- the unknown surface `A(MD)`;
- the correct GR alignment;
- protection from spatial distribution shift;
- a calibrated posterior.

Physics narrows the question from “any TVT” to “TVT consistent with a plausible surface.”

## 2. Observation likelihood from GR

A basic likelihood is:

\[
\ell(t;m) \propto \exp\left(
-\frac{\rho(GR_h(m)-GR_v(t))}{\tau}
\right)
\]

where `ρ` may be squared error, Huber, normalized correlation distance or a learned score. Robust versions compare windows and include multiple scales.

### Required nuisance modeling

Horizontal and typewell GR may differ through:

- additive offset and multiplicative gain;
- local stretch/compression in geological depth;
- missing values and clipping;
- correlated noise;
- different tool response;
- repeated lithology motifs;
- typewell mismatch.

A pointwise Gaussian likelihood is therefore a baseline, not a truth model.

### Multi-representation likelihood

Rank 6's 91 PFs vary GR representations. A systematic bank could include:

```text
raw GR difference
z-normalized local windows
NCC at several window sizes
gradient / edge similarity
band-pass or spectral features
self-GR heel matching
neighbor/typewell alternatives
learned contrastive similarity
```

Diversity should be measured by candidate coverage and OOF error correlation.

## 3. Transition model

A transition can be written:

\[
t_i = t_{i-1} + (\Delta A_i - \Delta Z_i) + \epsilon_i
\]

where `ΔA_i` is a latent surface slope and `ε_i` absorbs modeling error.

### State choices

1. **TVT only:** simple, but slope changes become high process noise.
2. **TVT + slope:** smoother and predictive, larger state space.
3. **TVT + surface coordinate:** separates well geometry from geology.
4. **TVT + regime:** allows piecewise dynamics or geology-conditioned transitions.

HMM level-slope and PF implementations approximate these choices.

### Transition constraints

Constraints should come from train-fold data:

- plausible first derivative;
- plausible slope-change frequency;
- curvature bounds;
- known-prefix continuity;
- typewell range;
- surface depth bounds.

Hard constraints reduce catastrophic paths but risk excluding rare truth. Prefer soft penalties unless the invariant is exact.

## 4. Particle filtering

### Core loop

For particles `k=1…K`:

\[
t_i^{(k)} \sim p(t_i \mid t_{i-1}^{(k)}, Z_i, \theta^{(k)})
\]

\[
\tilde w_i^{(k)}=w_{i-1}^{(k)}
p(GR_i \mid t_i^{(k)})
p(t_i^{(k)} \mid \text{surface prior})
\]

Normalize and resample based on effective sample size:

\[
ESS=\frac{1}{\sum_k (w_i^{(k)})^2}
\]

### Failure modes

- **particle impoverishment:** resampling repeatedly clones an early wrong mode;
- **likelihood overconfidence:** one local GR match collapses the posterior;
- **under-dispersed dynamics:** correct slope changes lie outside support;
- **over-dispersed dynamics:** particles waste mass and produce noisy candidates;
- **path ancestry loss:** filtering state marginals do not preserve good full paths;
- **long-horizon drift:** small slope bias accumulates.

### Remedies seen in top solutions

- bins or aggregated states for efficient updates;
- multiple PF configurations rather than one over-tuned filter;
- fixed-lag smoothing;
- neighbor/self-GR likelihoods;
- neural fusion of candidate curves;
- use PF as a heatmap channel rather than final answer;
- combine with HMM/U-Net/selector.

## 5. HMM and forward-backward inference

Let `s_i` be discrete TVT or level-slope state. Then:

\[
p(s_{1:T},x_{1:T})
=p(s_1)\prod_i p(x_i\mid s_i)\prod_{i>1}p(s_i\mid s_{i-1})
\]

Forward-backward yields marginals; Viterbi yields a mode path. A forward/backward pair can expose disagreements and provide uncertainty features.

HMM works well when:

- transition grid covers true movement;
- emissions are reasonably calibrated;
- known prefix anchors initial state;
- state dimension stays manageable.

It struggles with nonstationary deformation, unmodeled GR shifts and long-range surface changes.

## 6. Spatial priors

Nearby wells can estimate a geological surface at the target well's XY location. Rank 1 uses fold-safe XY information; Rank 10 demonstrates a dangerous reversal when neighbor distance differs between CV and leaderboard.

### Fold-safe construction

For validation well `w`:

1. remove all rows and derived summaries of `w`;
2. fit neighbor/surface model only on training-fold wells;
3. generate prior and uncertainty at `w`;
4. store nearest-neighbor distance and support count;
5. repeat for every fold.

### Required uncertainty

A spatial prior should expose:

- nearest-neighbor distance;
- local density;
- extrapolation flag;
- surface fit residual;
- slope uncertainty;
- typewell compatibility.

A single prior value hides whether it is interpolation or extrapolation.

### Shift guard

If test-proxy nearest-neighbor distance exceeds the OOF distribution, reduce prior weight or widen the residual canvas. Rank 10's reported 470 vs 683 distance shift illustrates this need.

## 7. Geometric prior and residual canvas

A simple prior can extrapolate the visible surface:

\[
A_0(m)=A_{\text{PS}}+\hat \beta (m-m_{\text{PS}})
\]
\[
t_0(m)=A_0(m)-Z(m)
\]

The learned target is:

\[
r(m)=t(m)-t_0(m)
\]

Inputs should include prior uncertainty and corruption features. Training should sample:

- constant shift;
- slope bias;
- piecewise slope breaks;
- low-frequency drift;
- local bumps;
- prefix anchor errors.

Without corruption, the model may assume the prior is always nearly correct.

## 8. Reanchoring as state estimation

Lightsource's chunk loop can be interpreted as approximate Bayesian filtering with a learned observation/update model:

```text
prior from current anchor
→ predict residual distribution for next chunk
→ choose trusted prefix of chunk
→ update anchor / prior
→ repeat
```

### Design variables

- chunk length;
- overlap and blending;
- how much of prediction becomes known;
- confidence threshold;
- whether to propagate a mean, mode or distribution;
- fallback when confidence is low.

### Safer variants

1. **Soft reanchor:** pass distribution/variance, not hard path.
2. **Multi-hypothesis reanchor:** carry K anchors.
3. **Delayed commitment:** only anchor after future overlap confirms.
4. **Bidirectional reconciliation:** decode from multiple anchor points and blend.
5. **Prior reset:** if evidence/prior disagreement exceeds a threshold, widen search.

## 9. Physics loss versus physics input

There are three places to use constraints:

### Input prior

Provide geometry/PF/XY evidence to the model. Flexible but model may ignore it.

### Loss penalty

Penalize GR mismatch, surface roughness or impossible slope. Direct but weight-sensitive.

### Decoder constraint

Restrict transitions or optimize a structured path. Strongest guarantee but risks excluding truth.

A robust system can use all three with different strength:

```text
soft prior channel
+ weak auxiliary consistency loss
+ hard only for exact support/range constraints
```

## 10. Evaluation protocol for physics components

A physics component should be judged by:

- candidate support coverage: fraction of true rows inside the PF/canvas band;
- oracle path RMSE;
- calibration of particle/spatial uncertainty;
- error by neighbor distance;
- error by distance from anchor;
- sensitivity to likelihood temperature and process noise;
- recovery after simulated wrong-layer initialization;
- runtime and deterministic replay.

Do not report only the final blended score; it hides whether physics improved recall, selection or tail risk.

## 11. Transfer

The general pattern applies to map matching, robotics localization, signal alignment and medical trace recovery:

```text
exact invariant
→ probabilistic state dynamics
→ noisy observation likelihood
→ learned correction
→ uncertainty-aware global decoder
```

Classical estimators and neural models are complements when each owns a distinct part of the factorization.

## Evidence Map

- Surface/geometry and dense prior: `source:rogii-writeup-01`, `source:rogii-writeup-02`, `source:rogii-writeup-10`
- PF/HMM candidate systems: `source:rogii-writeup-03`, `source:rogii-writeup-06`, `source:rogii-writeup-07`, `source:rogii-writeup-08`, `source:rogii-writeup-09`
- Geometric residual and reanchoring: `source:rogii-writeup-04`, `source:rogii-repo-lightsource`
- Supporting toolkit: `source:rogii-toolkit-mycarta`

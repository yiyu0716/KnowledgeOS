---
type: project
parents:
  - "[[KnowledgeOS]]"
domains:
  - "Machine Learning"
  - "Geosteering"
  - "Sequence Modeling"
  - "Kaggle"
topics:
  - "ROGII"
  - "TVT prediction"
  - "trajectory inference"
  - "synthetic data"
  - "particle filter"
  - "U-Net"
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
  - "source:rogii-top10-zenn"
  - "source:rogii-top10-michikusa"
  - "source:rogii-repo-ruby"
  - "source:rogii-repo-lightsource"
  - "source:rogii-repo-james-early"
  - "source:rogii-toolkit-mycarta"
  - "source:rogii-repo-keithtyser-14th"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---
# Rogii

> ROGII – Wellbore Geology Prediction 前十方案与真实代码的 KnowledgeOS 0.2.1 项目知识包。

## 30-second orientation

ROGII 表面上是逐行预测 `TVT` 的回归任务，实质上是一个 **partially observed, physically constrained, multimodal trajectory reconstruction** 问题：

```text
known TVT prefix + horizontal GR + well trajectory + typewell GR
                              ↓
                ambiguous local correspondences
                              ↓
     candidate paths / alignment probability / physical prior
                              ↓
          global decoding + correction + regime-aware fusion
                              ↓
                         future TVT path
```

上位方案没有共享一个唯一 architecture，却几乎都在做三件事：

1. 把局部 GR 模糊匹配提升为 **path-level representation**；
2. 用 physics/HMM/PF/synthetic data 保留或制造合理候选；
3. 用 global decoder、reanchoring、gate、ranker 或 banded ensemble 控制长程漂移与 catastrophic wells。

## Problem model

每口 horizontal well 在 Prediction Start 前给出 `TVT_input`，之后隐藏。`MD/X/Y/Z/GR` 与 typewell 的 `TVT/GR/Geology` 提供观测。核心近似是：

```text
surface coordinate A(MD) ≈ TVT(MD) + Z(MD)
horizontal_GR(MD) ≈ typewell_GR(TVT(MD)) + noise
```

困难不在于求一个局部最优匹配，而在于：

- GR 重复、噪声、缺失和域差使 posterior 多峰；
- 一次错层可能让后续数千英尺整体偏移；
- RMSE 让少量 catastrophic wells 主导总分；
- 773 口训练井与较小 Public 子集不足以让普通 random split 或榜单试探可靠；
- spatial neighbor 特征既强，又可能因测试近邻密度变化而产生 shift。

## Top-10 landscape

| Rank | Team | Core representation | Candidate / decoder | Private | Verified final code |
|---:|---|---|---|---:|---|
| 1 | Ruby | 345×400 MD×TVT alignment grid | U-Net probability map + PF/XY priors | 5.639 | **Yes: retraining reproduction** |
| 2 | Bilzard | conditional transition grid | AnchorCNN + exact DP expectation | 5.802 | Not found |
| 3 | tereka & Takoi | five independent candidate families | HMM/PF/NN/SDF + SoftMax Gate | 5.836 | Not found |
| 4 | L & J & A & A | topography image + residual canvas + PF | OOF ridge; chunk reanchoring | 5.870 | **Partial only** |
| 5 | daimaru | 14-channel 2D canvas | SDF + row-classification ensemble | ≈5.94 | Not found |
| 6 | k256.dev | 91 PF trajectories | learned row/candidate fusion | 5.984 | Not found |
| 7 | roglike | HMM path + error-conditioned canvas | U-Net refiner + confidence gate | 6.057 | Not found |
| 8 | Mount Fuji | PF candidate windows + 2D residual canvas | PF ranker + ResNet34 U-Net | ≈6.18 | Not found |
| 9 | tremors | eight whole-well/tracker representations | seven-band NNLS | 6.251 | Not found |
| 10 | Can | physics candidate bank + 2D ranking | LGBM selector + TCN/U-Net correction | 6.269 | Not found |

`≈` 表示本轮未从官方榜单直接读取精确小数；不应用于细粒度比较。

## Repository truth

### Verified retraining reproduction

`IAmAValidUsername/kaggle_ROGII_1st_place_solution_Ruby`

- 官方第一名 writeup 对应仓库；
- 六个历史 source/config/log recipe；
- 每个 recipe 为 3 geographic repeats × 5 folds；
- Apache-2.0；
- 不含 `models.pkl` 权重，最终六族 ensemble notebook 在 Kaggle。

### Verified partial

`l1ghtsource/rogii-wellbore-geology-prediction`

- README 明确标注 “lightsource's part”；
- 公开 2D U-Net、1D Squeezeformer、synthetic training、OOF blend、reanchoring；
- 不是第四名团队全部代码；
- 审计时未检测到明确 license。

### Authentic but non-final

`JamesMcGuigan/kaggle-rogii-wellbore-geology-prediction`

- 是真实第四名成员的参赛仓库；
- 公开的是 2026-07-04 的 LightGBM/domain-feature pipeline；
- 与最终 topography → 2D rendering → ConvNeXt V2 Large 分支不一致。

因此，**仓库名匹配比赛名不等于获奖方案身份成立**。完整审计见 [[projects/Rogii/validation-ensembling-and-repository-audit|Validation, Ensembling and Repository Audit]] 与根目录 `REPOSITORIES.md`。

## Three compressed conclusions

### 1. Preserve ambiguity until path-level evidence can resolve it

把每行立即压成一个 TVT 数值会丢失后验的多峰结构。Alignment grid、AnchorCNN、PF、HMM、beam search 都是在延迟承诺；真正的决策发生在 DP、sequence model、ranker 或 gate。

### 2. Synthetic data must model a joint world or a real failure process

成功的 synthetic data 不是独立给 GR、TVT、Z 加噪声。它要么由共享 latent geology 联合生成观测与轨迹，要么显式复制 first-pass 的错层、漂移和 prior error。目标是覆盖真实长尾，而非增加行数。

### 3. Validation is part of the model

Well-group split、geographic leakage control、OOF-only stacking、largest-contribution stability、distance-to-anchor bands、per-well tail metrics 和 neighbor-density shift 检查共同决定哪个方案值得提交。Public LB 只能是弱证据。

## Navigation

- [[projects/Rogii/solutions|Solutions]] — 前十方案的 Concrete Method Reconstruction。
- [[projects/Rogii/solution-space|Solution Space]] — 跨方案的收敛路线、替代路线、负证据、决策指南。
- [[projects/Rogii/representation-and-global-decoding|Representation and Global Decoding]] — alignment grid、conditional transitions、PF/HMM/beam 与 global decoder。
- [[projects/Rogii/synthetic-data-and-failure-modeling|Synthetic Data and Failure Modeling]] — synthetic world、domain randomization、refiner error simulation。
- [[projects/Rogii/physics-priors-and-probabilistic-tracking|Physics Priors and Probabilistic Tracking]] — surface identity、GR likelihood、PF/HMM、reanchoring。
- [[projects/Rogii/validation-ensembling-and-repository-audit|Validation, Ensembling and Repository Audit]] — OOF、tail risk、gating、banded blend、真实代码审计。

Project Learning:

- [[learning/Rogii Learning|Rogii Learning]] — ambiguity、physics prior、synthetic failure modeling、reanchoring、regime-aware ensemble 与 tail-aware validation 的单一项目入口。

## Recommended study order

```text
Competition model
→ Rank 1 representation and reproduction package
→ Rank 2 conditional path distribution
→ Rank 3/6/8 candidate diversity
→ Rank 4/5/7 synthetic-data roles
→ Rank 9/10 regime-aware fusion and validation
→ solution-space decision guide
```

For code, first run Rank 1 `--verify`, reproduce one family, then inspect Lightsource's residual/reanchoring code. Do not begin with a generic same-name repository.

## Evidence Map

- Competition and metric: `source:rogii-competition`, `source:rogii-leaderboard`
- Rank-specific reality: `source:rogii-writeup-01` … `source:rogii-writeup-10`
- Verified code: `source:rogii-repo-ruby`, `source:rogii-repo-lightsource`, `source:rogii-repo-james-early`
- Counterexamples/tooling: `source:rogii-toolkit-mycarta`, `source:rogii-repo-keithtyser-14th`
- Secondary access recovery: `source:rogii-top10-zenn`, `source:rogii-top10-michikusa`

---
type: project-doc
projects:
  - "[[Rogii]]"
domains:
  - "Machine Learning"
  - "Geosteering"
topics:
  - "top solutions"
  - "method reconstruction"
  - "repository audit"
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
  - "source:rogii-repo-james-early"
  - "source:rogii-top10-zenn"
  - "source:rogii-top10-michikusa"
origin: mixed
status: studied
created: 2026-09-01
updated: 2026-09-01
---

# Rogii — Solutions

## Scope and reading contract

This document is the **Reality canonical source** for the ten highest-ranked public writeups. Each section reconstructs the actual system along the same axes:

```text
Problem interpretation
→ representation
→ candidate generation
→ model
→ training data / objective
→ inference / decoding
→ validation
→ negative evidence
→ code status
```

Reported leaderboard and OOF numbers describe the authors' systems. They do not turn rank differences into causal ablations. Where a primary Kaggle page body was not directly exposed, the exact detail is marked as reconstructed from two secondary summaries that link back to the official writeup.

## Normalized comparison

| Rank | Dominant state representation | Main source of multimodality | Global consistency mechanism | Synthetic role | Fusion |
|---:|---|---|---|---|---|
| 1 | dense MD×TVT probability grid | 400 candidate TVT rows | U-Net context + expected path | joint real/sim augmentation | six-family weighted ensemble |
| 2 | anchor-conditioned transition distribution | 21 moves per anchor | exact dynamic programming | physically consistent full trajectories | implicit in path distribution |
| 3 | five candidate trajectories/families | HMM, PF, NN49, NN31, SDF | SoftMax sequence gate | member-specific | row-wise learned gate |
| 4 | topography image, residual canvas and 1D residual | three independent pipelines | chunk reanchor + ridge | 500k/geo-plane recipes | OOF ridge |
| 5 | 14-channel 2D canvas | SDF + row logits, multi-backbone | 2D path decoding | primary representation learning | heterogeneous CNN blend |
| 6 | bank of 91 PF curves | PF parameter/GR diversity | smoother + sequence fusion | limited / not central | GBM + TCN + curve attention |
| 7 | HMM path plus error-conditioned canvas | fabricated first-pass errors | U-Net correction + confidence gate | refiner failure modeling | gated hedge |
| 8 | 20 PF curves and residual-spatial image | PF bank plus independent U-Net | window ranker + CNN path | continuous 50/50 mixture | near-equal two-leg blend |
| 9 | eight tracker/whole-well outputs | heterogeneous model families | seven distance bands | member-specific | banded NNLS |
| 10 | staged physics and learned candidate bank | PF/HMM/2D candidates | selector + TCN/U-Net correction | limited / phase-specific | tempered selection + prior pull |

## Shared task model

The unknown object is a continuous latent path `TVT(MD)`. Local observation likelihood comes from GR-to-typewell alignment; dynamics and geometry constrain how the path can move. A robust system therefore needs all of the following, even when they are implemented inside one network:

```text
observation model
+ transition / smoothness prior
+ multimodal hypothesis representation
+ path decoder
+ drift control
+ uncertainty / candidate reliability
+ grouped validation
```


## 1. Ruby — 2D alignment grid + ConvNeXt U-Net + PF/XY priors

**Reported result:** Private `5.639`; Public `5.980`; CV/OOF `4.627（加权 ensemble）`.

### Problem interpretation

不要逐行直接回归 TVT；把 horizontal-well MD 与候选 typewell TVT 的对应关系展开成二维概率场，再从概率场中恢复一条连续轨迹。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

alignment grid 约为 345 个 MD 位置 × 400 个 TVT 候选。MD 轴由 1,024 ft 可见前缀与约 10,000 ft 目标区按 32 倍下采样组成；TVT 轴围绕最后可见 TVT 的 ±100 ft、0.5 ft 间隔展开。

### Model and evidence channels

ConvNeXt-Small encoder 的 Sequence U-Net；将 LayerNorm 替换为 BatchNorm，并使用 BF16、average pooling 与 interpolation。输入不只是 GR mismatch，还含 horizontal GR 统计与交互、z/dz 几何信息、PF heatmap、fold-safe XY 邻井先验。

### Training and objective

核心损失组合是 per-cell cross entropy、从概率场解码的期望路径 Huber loss、以及 GR 一致性惩罚。最终使用 3 次 geographic repeat × 5 folds，并对六个历史 recipe 做模型族融合；作者报告联合混合 real/simulated data 比先 synthetic pretrain 再 real finetune 更好。

### Inference and decoding

模型产生整张 path probability map，再以期望位置/连续路径方式解码；PF 与空间先验作为输入证据，而不是在网络之外简单替代神经模型。

### Why it can work

二维化把局部 GR 的多解性保留为一条带状概率结构，卷积模型可以同时观察邻近 MD、候选 TVT 与几何连续性；PF 和 XY 先验缩小搜索空间但不会强迫唯一答案。

### Negative evidence and boundary

Transformer backbone、单纯扩大模型/分辨率、复杂 loss reweight、删除所谓坏标签，以及 synthetic→real 的简单两阶段训练并未稳定胜出。排名差异不能证明其中任何组件单独具有因果增益。

### Repository audit

**Class:** Verified reproduction

Verified reproduction：完整公开六个历史 source/config/log recipe 与重训入口，Apache-2.0；不含多 GB models.pkl，最终六族 saved-model ensemble 仍通过 Kaggle notebook。

**Source identity:** `source:rogii-writeup-01`, `source:rogii-repo-ruby`.

## 2. Bilzard — AnchorCNN conditional transition distribution + exact DP

**Reported result:** Private `5.802`; Public `6.146`; CV/OOF `5.140（公开整理）`.

### Problem interpretation

预测条件移动分布 P(ΔTVT | 当前 anchor TVT)，而不是把整条未来路径压成一次点估计；最终用 dynamic programming 求全局期望路径。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

以 anchor-grid 组织输入，模型在每个 anchor 上输出 21 个离散移动类别（0 与 ±2…±20 ft）。公开整理给出的训练 tensor 形态为约 (B, 21, 128, 336)。

### Model and evidence channels

EfficientNet-B0 + FPN 风格 CNN，在候选 anchor 周围读取 horizontal/typewell GR 的匹配证据和几何条件。

### Training and objective

使用 teacher forcing：训练时在真实轨迹 anchor 上读取条件转移。合成数据从 typewell 归并出的 54 条 master 序列生成，并显式遵守 ΔTVT = Δsurface − ΔZ 一类物理关系。

### Inference and decoding

把局部条件分布沿 MD 组合为 path distribution，再用 exact DP 计算期望路径。作者报告这一解码优于 greedy rollout 或只取 Viterbi 路径。

### Why it can work

局部观测可能支持多条轨迹；条件分布保留分支，DP 则在整段序列上聚合未来证据，避免早期一次错误锁死后续。

### Negative evidence and boundary

teacher forcing 与推理时自回归条件存在 exposure gap；离散 transition 范围会限制跳变。作者采用 leave-largest-contribution-out 等稳健性检查，但公开代码尚未找到，实施细节只能以 writeup 为界。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。精确方案名、作者名和 GitHub 关键词搜索均未返回可归属的最终代码。

**Source identity:** `source:rogii-writeup-02`.

## 3. tereka & Takoi — HMM/PF + three neural candidates + row-wise SoftMax Gate

**Reported result:** Private `5.836`; Public `6.043`; CV/OOF `5.2884`.

### Problem interpretation

先保持多个相互独立的物理与神经候选，再让 gate 按井段动态决定每个候选的权重。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

候选集合包含 HMM、Particle Filter、NN49（absolute offset + uncertainty）、NN31（delta prediction）与 Adaptive 1D SDF；这些分支在 gate 之前独立生成。

### Model and evidence channels

物理分支显式追踪轨迹；神经分支从不同目标空间学习。最终使用 CNN/BiLSTM SoftMax Gate 对五类候选做位置相关融合。

### Training and objective

每个 split 训练 NN49、NN31 等成员；公开 writeup 使用 5-fold × 5 split/seed 的多模型组织，并用 well-level OOF 训练融合器。

### Inference and decoding

每个 MD 位置产生五类候选及其辅助不确定度/特征，SoftMax Gate 输出归一化权重并构成最终 TVT。

### Why it can work

HMM/PF 与神经模型的失败模式不同；晚融合让系统在 heel、mid、toe 或不同 GR 质量区域切换可靠专家，而非强迫单一模型兼顾所有 regime。

### Negative evidence and boundary

gate 只能利用 OOF 中出现过的错误模式；候选若高度相关或在某一 regime 同时失效，动态融合也无法创造正确路径。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。Takoi 的公开 GitHub 账户中检索到其他 Kaggle 仓库，但未见 ROGII 最终代码。

**Source identity:** `source:rogii-writeup-03`.

## 4. L & J & A & A — Three independent pipelines blended from OOF

**Reported result:** Private `5.870`; Public `5.452`; CV/OOF `4.998`.

### Problem interpretation

把 topography vision、geometric-prior residual learning 与 Particle Filter 视为三套独立世界模型，再以 OOF ridge 组合。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

James 分支先预测地形并渲染成 2D，再由 ConvNeXt V2 Large + feature pyramid 预测 control-point offsets；Lightsource 分支围绕 geometric prior 建 residual-TVT × MD canvas，同时另建 1D residual sequence；Alijs 分支为 PF。

### Model and evidence channels

James：ConvNeXt V2 Large vision pipeline；Lightsource：ResNet34/ConvNeXt-Tiny/Swin-Tiny U-Net 与 1D Squeezeformer；Alijs：Particle Filter。

### Training and objective

James 使用约 500k synthetic wells，并追加约 37k 筛选样本；Lightsource 采用 honest synthetic pretrain → geo-plane post-pretrain → real-well finetune，synthetic-only OOF 约 8.9；最终成员通过 OOF ridge 融合。

### Inference and decoding

公开整理的 ridge 权重约为 James 0.644、Lightsource 0.327、Alijs 0.029。Lightsource 对长后缀使用 500–950 ft chunk reanchoring，不断把预测前段加入已知前缀并重建 prior。

### Why it can work

三条路线分别擅长空间表面、局部 GR 对齐和概率追踪；残差表示与 reanchoring 把长期绝对深度预测拆成可校正的短程问题。

### Negative evidence and boundary

这是团队级 ensemble，不能用任一成员仓库替代完整提交。ridge 权重只反映该 OOF 分布下的互补性，不证明 PF 在一般情况下仅值 2.9%。

### Repository audit

**Class:** Verified partial / authentic non-final

Verified partial only：Lightsource 公开其 2D/1D 分支但未检测到明确许可证；James 的公开仓库是 2026-07-04 的 LightGBM/domain-feature 早期管线，不是最终 ConvNeXt topography 分支；未找到完整团队仓库。

**Source identity:** `source:rogii-writeup-04`, `source:rogii-repo-lightsource`.

## 5. daimaru — Synthetic-Data-Centric 2D CNN

**Reported result:** Private `约 5.94（精确小数未在本轮直接核验）`; Public `未单独核验`; CV/OOF `未单独核验`.

### Problem interpretation

先构造足够逼真的联合地质世界，让网络主要从 synthetic data 学会对齐，再用很短的 real finetune 做域适配。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

主 canvas 约 256 × 768，并带 256 × 48 side canvas；14 个输入通道同时编码 GR correspondence、几何和已知/未知区域。

### Model and evidence channels

MaxViT-Tiny、EfficientNetV2-RW-S、HRNet-W18 等 U-Net 型成员，使用 SDF 与 row-classification 双 head；最终通过异构 backbone ensemble。

### Training and objective

高保真 generator 让 TVT、Z、GR 共享 latent geology，而不是独立随机扰动。先 synthetic 约 25 epochs，再 real 约 8 epochs；作者报告最佳 real checkpoint 通常在 epoch 2 左右。

### Inference and decoding

多个 2D 成员输出轨迹距离场/行分类，再解码并融合；辅助 trajectory drawing loss 用于让输出形成连续可读路径。

### Why it can work

真实井数量有限，而对齐失败常由罕见地层形态、噪声和 prior 偏移触发。联合生成这些关系可以覆盖真实数据中稀疏的长尾组合。

### Negative evidence and boundary

作者报告 synthetic-only 已可达到约 6.342 Private，real finetune 的增益相对有限；这支持 synthetic world 的重要性，但不能说明任意合成数据都有效。过度真实数据 finetune 可能快速覆盖 synthetic 学到的结构。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。方法细节主要来自官方 writeup 的链接与两份二次交叉整理。

**Source identity:** `source:rogii-writeup-05`.

## 6. k256.dev — 91 Particle Filters + learned row/candidate fusion

**Reported result:** Private `5.984`; Public `5.626`; CV/OOF `5.4577`.

### Problem interpretation

决定上限的不是单个 PF 参数，而是能否生成覆盖不同错误模式的候选集合，并学习何时相信哪条候选。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

构造 91 套 PF trajectory，变化 GR 表示、likelihood、过程噪声、邻井/自相关证据、物理 prior 与 smoothing 参数；候选曲线本身成为后续模型输入。

### Model and evidence channels

GPU 加速 PF（作者报告相对 CPU 约 200×）、fixed-lag smoother，以及 candidate-curve attention、GBM、TCN 等 row-level/sequence fusion 分支。

### Training and objective

PF 参数与候选配置经 Optuna/OOF 选择；融合模型只使用 OOF 候选，避免把同井拟合输出作为无偏训练目标。

### Inference and decoding

91 条 PF 先并行产生，再由 neural/GBM/TCN 成员做 row-level bagging；最终三类融合腿组合成轨迹。

### Why it can work

GR 波形有重复结构，后验天然多峰。大候选池覆盖 mode，学习器则根据候选间相对位置、物理一致性和局部证据进行选择。

### Negative evidence and boundary

逐行独立的 tabular selector 会产生 block shift 和不连续路径；候选数量不是越多越好，高相关候选只增加成本而不增加 posterior coverage。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。精确标题、91 PF、row-level bagging 等 GitHub 关键词搜索无可验证结果。

**Source identity:** `source:rogii-writeup-06`.

## 7. roglike — HMM first pass + U-Net refiner + uncertainty gate

**Reported result:** Private `6.057`; Public `未单独核验`; CV/OOF `5.2025（pooled OOF）`.

### Problem interpretation

不是要求第一阶段直接完美，而是显式模拟 first-pass 会如何犯错，再训练 refiner 修复错误并用不确定度决定修多少。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

HMM 产生初始轨迹；初始轨迹被编码为 refiner 的 conditioning channel，与 GR/typewell/geometry canvas 一起输入 U-Net。

### Model and evidence channels

HMM + U-Net correction/refiner，多 refiner 或 hedge 输出的 spread/std 被用作 confidence proxy 和 gating 信号。

### Training and objective

生成约 6,000 条 synthetic wells，并人为制造 first-pass error channel；公开整理给出约 60 epochs synthetic pretrain + 8 epochs real adaptation。

### Inference and decoding

先 HMM，再 U-Net 预测 correction；gate 在低置信度区域保留更保守的 HMM/hedge，在高置信度区域采用 refiner。

### Why it can work

修错任务的输入分布与从零预测不同。让 synthetic data 复制 first-pass 的偏移、漂移与错层，可把模型容量集中于可诊断的残差结构。

### Negative evidence and boundary

作者报告 refiner 在 held-in 与 held-out 的差距很大（公开整理约 3.20 vs 9.34），说明泄漏和 domain gap 风险极高；confidence 只能作为经验代理，不是校准后的概率保证。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。精确方案标题和 HMM+UNet 关键词检索未找到可归属的最终仓库。

**Source identity:** `source:rogii-writeup-07`.

## 8. Mount Fuji — PF ranker + synthetic-pretrained ResNet34 U-Net

**Reported result:** Private `约 6.18（精确小数未在本轮直接核验）`; Public `未单独核验`; CV/OOF `PF selector ensemble 约 5.7087`.

### Problem interpretation

并行维护一条可解释的 PF selection 路线和一条端到端 2D U-Net 路线，利用完全不同的错误结构做接近等权融合。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

约 20 条 PF trajectories 配合位置、地质和匹配特征；selector 以约 256 MD 的 window 判断候选。另一支使用 residual-spatial canvas。

### Model and evidence channels

五个 CPU selector/ranker 的 PF ensemble，加上 9-channel ResNet34 U-Net。

### Training and objective

U-Net 训练中持续混合约 50% synthetic / 50% real，并注入 ±15 ft decoy（约 p=0.25）；不是只在开头 pretrain。PF ranker 使用 OOF 候选和 window-level supervision。

### Inference and decoding

PF ranker 路线与 U-Net 路线近似等权融合；一条路线输出候选选择，另一条输出连续概率场/残差路径。

### Why it can work

PF 提供显式多峰与可解释候选，U-Net 可利用二维上下文进行模式补全。两者的相关性较低时，简单融合也可能有效。

### Negative evidence and boundary

作者观察到 Public 约 5.5 的部分模型在 Private 上掉到约 6.7–7.0；尾部 20% 井贡献了大量 SSE。Public 选择和平均分不足以识别 catastrophic wells。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。`sggpls` 等公开账户检索未发现该最终方案仓库。

**Source identity:** `source:rogii-writeup-08`.

## 9. tremors — Eight heterogeneous models + seven-band NNLS

**Reported result:** Private `6.251`; Public `5.435`; CV/OOF `5.28（strict）`.

### Problem interpretation

模型可靠性随距 anchor 的位置变化；因此按 heel→toe 的误差 regime 学习分带权重，而不是全井一个固定 ensemble。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

成员覆盖 autoregressive Dilated Conv2D+BiGRU、whole-well U-Net、relief U-Net、level-slope HMM、segmented beam interpreter、HMM×beam、HMM×U-Net 与 CNN baseline。

### Model and evidence channels

八类异构 tracker/vision/sequence 模型，外加以 md_since_anchor 七个分位带为条件的 non-negative least squares；另用约 80 个 spread bins 做校准。

### Training and objective

每个成员先产生 strict OOF；再按 MD 距离带拟合 NNLS，保证融合器只看到 held-out predictions。

### Inference and decoding

在 heel、mid、toe 不同带应用不同非负权重，并根据成员 spread 做后处理/校准。

### Why it can work

局部 tracker 近 anchor 强，但误差会累积；whole-well 模型远端更稳定但近端未必最佳。分带融合直接编码这一可靠性迁移。

### Negative evidence and boundary

团队选择了 Public 略差但 strict CV 更好的组合，Private 从约 6.503 改善到 6.251。该现象支持 CV 选择策略，但一次 leaderboard 结果不能证明策略普遍因果有效。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。`Banded NNLS`、团队名和方案标题搜索未返回可验证最终代码。

**Source identity:** `source:rogii-writeup-09`.

## 10. Can — Physics candidates → 2D ranker → LightGBM selector → TCN corrections

**Reported result:** Private `6.269`; Public `5.620`; CV/OOF `5.7189`.

### Problem interpretation

物理模型给方向而非完整地图：先产生多条可信候选，再逐阶段排名、拉回 prior、做 sequence correction。

This interpretation matters because an apparently small local offset can represent a different geological layer. A method that minimizes row-wise error without a path state can alternate between locally plausible matches and create a globally impossible trajectory.

### Representation

Phase A 以 surface coordinate、KD-tree/local plane/IDW、16-seed PF 和 forward/backward HMM 生成候选；Phase B 用 2D ranking U-Net；Phase C 对每条 curve 构造 49 个特征。

### Model and evidence channels

physics candidate bank + 2D U-Net + per-well LightGBM selector（tempered softmax 与 prior pull）+ dilated TCN + 第二 U-Net/gate。

### Training and objective

所有 selector/corrector 使用 OOF 候选；作者按阶段记录 CV 增益，并对 neighbor distance、anchor distance 与 worst wells 做诊断。

### Inference and decoding

候选生成后先排名/混合，再由 TCN 做 row correction；最终对 heel 附近使用约 1.024 的 gain calibration 并保留 prior guardrail。

### Why it can work

候选生成与候选选择是不同问题：物理模型保证可行域，learned selector 识别当前井的证据，sequence correction 修复局部系统偏差。

### Negative evidence and boundary

空间邻井特征把 CV 从约 5.7544 改善到 5.5762，却让 Public 从约 5.648 恶化到 5.977，作者归因于近邻距离分布约 470 vs 683 的 shift；local GR selector 也出现 oracle 很强而可学目标很差的失败。

### Repository audit

**Class:** No verified final repository found

No verified final repository found as of 2026-09-01。精确标题与 49-feature selector/TCN 关键词搜索无可归属结果。

**Source identity:** `source:rogii-writeup-10`.

## Cross-solution reconstruction

### Convergence

All ten systems accept, explicitly or implicitly, that GR alignment is ambiguous and the prediction is a trajectory. The strongest convergence is not “everyone used U-Net”; it is:

```text
preserve several plausible states
→ inject physical/geometry evidence
→ aggregate evidence over a path
→ control drift
→ weight experts by regime
```

The concrete implementations differ. Rank 1 stores ambiguity in a dense image; Rank 2 stores it in conditional transitions; Ranks 3/6/8 store it in candidate banks; Rank 9 stores it in heterogeneous model outputs; Rank 10 stores it across pipeline stages.

### Alternative routes

There are at least four valid design routes:

1. **Dense alignment field:** direct 2D representation, strong convolutional context, expensive canvas.
2. **Probabilistic transition model:** compact dynamics and exact decoding, exposed to transition discretization and teacher-forcing gap.
3. **Candidate bank + selector:** interpretable and modular, limited by candidate recall.
4. **Geometric prior + residual correction:** reduces target range and supports reanchoring, sensitive to prior construction.

A new system should choose a route based on which uncertainty it can represent and validate, not on leaderboard fashion.

### Negative evidence

- Bigger backbone or resolution was not consistently better.
- A synthetic pretrain stage is not automatically better than joint training.
- Row-independent selectors can produce block shifts even with strong local scores.
- Spatial neighbor features can improve CV yet fail under neighbor-density shift.
- A Public-favored model can collapse on Private when a few long-tail wells differ.
- A repository with the competition name can be an early experiment, a baseline, a lower-rank solution, or a post-competition reconstruction.

## Evidence Map

Primary writeups: `source:rogii-writeup-01` through `source:rogii-writeup-10`.

Repository evidence: `source:rogii-repo-ruby`, `source:rogii-repo-lightsource`, `source:rogii-repo-james-early`.

Secondary access recovery: `source:rogii-top10-zenn`, `source:rogii-top10-michikusa`.

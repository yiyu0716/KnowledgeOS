---
type: project-doc
projects:
  - "[[OrbitWars]]"
domains:
  - reinforcement-learning
  - multi-agent-systems
  - game-ai
  - kaggle
topics:
  - representation
  - future-state
  - action-representation
  - geometry
  - relation
origin: codex
source_refs:
  - "source:orbitwars-isaiah-writeup"
  - "source:orbitwars-simjeg-writeup"
  - "source:orbitwars-felix-writeup"
  - "source:orbitwars-jake-writeup"
  - "source:orbitwars-tonyk-writeup"
  - "source:orbitwars-flg-writeup"
  - "source:orbitwars-audun-writeup"
  - "source:orbitwars-ender-writeup"
  - "source:orbitwars-isaiah-repo"
  - "source:orbitwars-simjeg-repo"
  - "source:orbitwars-tonyk-repo"
  - "source:orbitwars-flg-repo"
  - "source:orbitwars-ender-repo"
updated: 2026-08-29
---
# Orbit Wars — Representation Design

## Scope

本文只研究 Orbit Wars 强方案如何表达 state、future consequence、geometry、relation 和 action candidate。训练分布、stability 控制与 submission engineering 只有在直接影响表示取舍时才提及（训练专题见 [[ppo-training]]，全项目综合见 [[solution-space]]）。

## Core Problem

raw observation 同时包含 planet、fleet、comet、owner、production、garrison、velocity、incoming fleet、目标移动和遮挡关系。policy 如果必须从这些底层实体重新推导 ETA、可达性、战斗结果和资源代价，就要在连续几何与 delayed consequence 上承担过大的 inference burden——而它的参数预算从 2.5M 到 200M 不等，这个负担并不总是付得起。

## Representation Landscape

八个方案的真实表示配置（具体训练配置见 [[solutions]] 各节）：

| Solution | 基础状态 | 未来状态接口 | 关系表达 | 几何解析 | 动作接口 |
|---|---|---|---|---|---|
| Isaiah | entity token（planet/fleet/comet）+ 17 辅助 token（player/global/plan/value/scratch） | **无显式**——靠 200M 容量自学 | 目标选择用 QK 相似度 | Rust 侧解角度 | target factorization + 8 分量连续 mixture（fleet size ∈ [3, garrison]） |
| Hober | 每 body 10 特征（production、radial/angular 坐标、四方舰数、capture cost） | **T=19 无动作假设下的 body 时间序列**（含即将发生的占领/战斗） | 无显式 pairwise；几何隐含在时间序列与坐标特征中 | 无 planner——短 ETA mask 约束 | no-op / all-in，ETA<20 目标 mask |
| Felix | 48 token（4 player + 44 planet），garrison 用 embedding（≤384 精确、sqrt 桶到 768） | **到达日历**（2P 24 步 / 4P 16 步，每格 embedded 加权求和） | **graphormer 式 attention bias**：reachability 派生的 pairwise 特征加进 attention logits | **reachability tensor** (B,P,P,S,3)：每对 (source,target)×动作存舰数/角度/ETA | 每 planet 177 维 categorical（1 no-op + 44 目标 × 4 semantic intent），intent 舰数由 tensor 解析 |
| Jake | 45 token（40 planet + 4 comet + CLS），self-state + top-K fleet 摘要 | **combat preview**（不发射会怎样：未来 owner/舰数/翻转裕度）+ **resolved launch-size 表**（每 intent 每目标的真实代价） | pairwise 几何（距离、太阳遮挡、到达步、轨道相位）直接进目标头 | C++ 引擎解析 intent 精确舰数 | 44 目标 × 3 intent（100% / Capture-Defend / Maintain-ownership）+ no-op；特征旋转不变 |
| TonyK | planet / edge / arrival 三类输入分块编码融合；连续量归一化 + 离散量 embedding | 到达时间轴投影（temporal horizon） | **显式 directed edge block**（距离、战术裕度） | C++ 环境与观测路径 | 每 planet 独立 destination × send-amount bucket，masked 合法性 |
| flg | 纯相对输入：无绝对坐标、无绝对玩家 id（玩家按起始位置相对命名） | **23 个到达桶**（多少舰队、何时到、谁赢、ownership 是否保持）；fleet 完全不是输入实体 | **custom edge attention**：A→B 关系（100% 发射 7 步占领、50% 发射 11 步失败）进注意力 | 前向预测在 C++ 扩展内完成 | NxN MLP 头（concat[src,target,edge]）× 4 档 fleet share + no-op |
| Audun | planet token + pairwise 特征进 attention bias；fleet 折叠进目标 planet；按座位旋转视角 | 24 桶 incoming + **辅助预测头**（2/8/32/64 步后的 ownership/garrison/产量，推理时丢弃） | pairwise bias（~60 特征 / 138 通道，多数与 timing 相关） | **analytic planner**（Newton lead pursuit + 最近点碰撞检查，recall 93–95%）+ top-4 自选目标 + 4 随机 | 两段式：目标 × 6 发射桶（20/40/60/80/100% 或恰好占领） |
| Ender | entity + CLS，2D RoPE 位置，p0 视角归一 | **24 桶未来 ownership/garrison 投影**（ceasefire 假设）+ incoming net 桶（fleet 间战斗先解析） | target MLP 吃候选特定特征（hidden、fleet size、ETA、是否大于 garrison、发射后双方投影） | 训练时 256 方向并行模拟；提交时切线窗 + sextic roots 解析 | micro-step：halt/launch → origin×比例（5 档）→ 43 可达目标（含 abort），≤16 次/回合 |

共同的表示底座：**没有人用原始像素或棋盘网格**——全部是 planet/comet 级 token 化结构输入；也没有人让 fleet 作为自由实体同时出现在所有方案里（Isaiah 是唯一保留完整 fleet token 的）。

## Key Design Axes

1. **Entity vs relation**：独立 entity token（Isaiah、Ender）vs 显式 pairwise/edge（Felix、Jake、TonyK、flg、Audun）vs 隐含在时间序列（Hober）。
2. **当前 vs 未来**：无显式 future interface（Isaiah）vs 直接输入型 future features（Hober/Felix/Jake/TonyK/flg/Ender，窗口按方案而异）vs auxiliary future prediction（Audun：2/8/32/64 steps）。
3. **Learned vs analytic geometry**：模型自学（Isaiah 部分、Hober）vs 解析系统（Felix tensor、Jake 引擎、Audun planner、Ender 候选计算）。
4. **Raw vs semantic action**：连续 mixture（Isaiah）→ 比例桶（TonyK、Audun、Ender）→ semantic intent（Felix、Jake）→ 二值极简（Hober）。
5. **Full vs pruned candidates**：全枚举（Felix 177 维）vs mask（Hober、Jake）vs 自剪枝 top-k + random（Audun）vs 因式分解条件化（Ender）。
6. **绝对 vs 相对**：旋转不变（Jake）、座位相对命名（flg）、按座位旋转（Audun）、p0 归一（Ender、Felix）vs 原始绝对量（Isaiah entity 特征中的位置）。

## Cross-solution Convergence

- **未来后果被显式结构化**：Hober/Felix/Jake/TonyK/flg/Ender 将 future/arrival/consequence 信息直接输入 policy；Audun 通过 2/8/32/64-step auxiliary targets 强制 trunk 学 future state。它们共享“不要让 raw state 独自承担 delayed consequence”的机制，但 horizon 与接口形式并不统一。
- **fleet 实体的"折叠"**：Hober（时间序列）、flg（到达桶）、Audun（折叠进目标 planet）、Ender（incoming net 桶，fleet 间战斗先按规则解析）四家独立选择不让 policy 直接面对自由 fleet 实体；TonyK 用到达时间轴投影同属此列。反面：Isaiah 保留完整 fleet token 且成功——但有 200M 容量兜底。
- **关系作为一等公民**：Felix、Jake、TonyK、flg、Audun、Ender 六个方案以 attention bias、pairwise geometry、edge block/attention 或 candidate-conditioned features 显式表达 source-target 关系，使 ETA、可达性、角度或候选后果进入决策路径。
- **视角归一化消除座位偏差**：五家独立实现（见 Axis 6），flg 明确报告"不再有按起始位置的胜率差异，训练非常平滑"。

## Alternative Routes

- **低层 entity + capacity**（Isaiah）：明确减少显式 future/pairwise engineering，用 200M/15B steps 让模型自己学习更多 dynamics。它证明显式 future interface 不是必要条件；低预算下能否复制这条路线没有受控证据，不能仅由 Ender 的小模型结果反推。
- **时间序列即未来**（Hober）：不构造 pairwise 关系，把每个 body 的未来演化整体作为时序输入，用 1D-CNN 编码。比 pairwise 路线便宜得多，代价是 T=20 之外不可见（作者自己也列在"想改进"清单首位）。
- **预测头 vs 输入特征**（Audun）：同样一份未来信息，其余六家作为输入，Audun 额外让网络自己预测未来（辅助损失）。Audun 的解释是"强制 trunk 建立内部世界模型"——与其他六家机制互补而非互斥。

## Negative Evidence

- **flg：4 档 fleet share 完全无收益**——agent 最终只用 100%。表示层给了自由度但策略不需要；配套的 edge 前向预测工程也随之贬值。
- **Audun 的候选剪枝压力测试**：从 top-16+8 random 一路压到 4+4，性能始终在噪声内；完全去掉随机目标也只输到 45.7%（勉强平手）。作者的解读：训练早期 logits 是噪声，top-k 等价随机；logits 锐化后它恰好擅长这个任务。这同时是对"剪枝必然伤探索"直觉的否决。
- **Isaiah：action mask（遮蔽明显愚蠢的发射）让训练后的模型更差**。作者推测是被迫自学更多物理带来的副作用——这是解释，不是已证明的因果。
- **SimJeg（IL 阶段）放弃的表示**：第三档发射比例头、T>20 的更长 horizon、目标 mask 作为 attention bias（收敛更快但结果相同）、更大/更小的 CNN 与 transformer——被 IL 实验直接筛掉的表示选项。
- **Ender：更大模型学得更慢且无收益**（在其 $170 预算下）——表示工程收益与模型规模之间存在替代关系。

## Open Questions

1. semantic action 的收益来自更好的 inductive bias 还是更低的 action entropy？公开材料无法分离。
2. learned world model 能否替代 hand-written forward simulator？本专题全部未来接口都依赖解析/模拟事实源。
3. 一回合多次发射的表达力价值边界：Ender 实际用到且有效，flg/SimJeg 的比例档却无人使用——两份证据方向相反。
4. 直接输入型 future interface 是否需要超过约 20–24 步仍是开放问题：Hober 把更长 horizon 列为改进方向；Audun 的 32/64-step 信息来自 auxiliary prediction target，不能直接当作输入 horizon 的对照。

## Mechanism Synthesis

**1. 信息接口（把未来变成可比较的输入）**
```text
delayed consequence 下的判断难以从 raw state 学习
→ future-state / reachability tensor / combat preview / 到达桶
→ 未来结果从"学习目标"变成"输入特征"
→ 学习负担转移到战略选择
```
证据：七家收敛 + Isaiah 容量替代。边界：horizon 不足（Hober T=20）时模型对更远 fleet 系统性失明；forecast 依赖 simulator parity。

**2. 关系接口（让 attention 看见边）**
```text
标准 attention 只见 token embedding，不见 token 间的关系
→ graphormer bias / edge attention / edge block / 候选条件化特征
→ ETA、可达性、角度进入注意力或决策路径
→ 目标选择在真实几何约束下进行
```
证据：六个方案采用显式 source-target 关系（Felix、Jake、TonyK、flg、Audun、Ender）。边界：pairwise 数量 P² 增长，需要 gather/scatter 稀疏化、候选剪枝或关系折叠控制成本。

**3. 可行性接口（解析先行）**
```text
角度、ETA、可达性、精确占领成本是可解析的物理量
→ planner / reachability tensor / 引擎解析
→ policy 只在可执行候选中选择
→ 探索不再被无效动作稀释
```
证据：五家收敛（Felix、Jake、Audun、Isaiah 角度、Ender 候选）。边界：Isaiah 的 mask 负结果提示——把过多合法性判断移出模型可能剥夺其学习物理的机会；recall 93–95%（Audun planner）意味着 5–7% 的真实可行 shot 被永久排除。

**4. 视角归一化（消除座位这一虚假自由度）**
```text
绝对坐标/绝对玩家 id 引入与策略无关的输入方差
→ 旋转不变 / 相对命名 / p0 归一
→ 同一策略在不同座位产生一致输入
→ 样本效率提高、按座位过拟合消失
```
证据：五家收敛 + flg 的平滑训练报告。边界：需要全域旋转对称或可枚举的座位变换；4P 的对手置换需要额外处理（Hober 用增广、flg 用相对命名解决）。

## Trade-offs

- entity 保留表达力，要求 policy 自学 future dynamics（Isaiah 的 200M）vs 折叠降低负担，要求 forecast 准确且 horizon 足够（六家）。
- 显式 pairwise 关系信息完整，成本 P² 增长 vs 折叠/时间序列便宜但丢失来源信息（fleet 从哪来在 Hober/flg 的表示中不可见）。
- analytic planner 精确且快（Audun 最近点检查使 140 步飞行与 5 步同价），但 recall 有硬上限 vs 学习式可行性无上限但需数据。
- semantic intent 把舰数决策绑定进意图（省一个维度）vs 比例桶保留显式资源控制（TonyK、Ender）——Felix 的 late switch（固定比例→semantic）学习速度大增是前者最强的单点证据。
- 候选剪枝控制几何成本，Audun 的压力测试显示剪枝上限远比直觉高，但完全去掉随机候选已现边缘退化（45.7%）。

## Decision Guide

面向下一次表示设计；最后一列只列公开证据支持的廉价检验。

| 观察到的表示问题 | 候选干预 | 机制 | 边界/风险 | 最便宜的诊断/证伪 |
|---|---|---|---|---|
| policy 学不会判断延迟后果 | future ownership/garrison 投影、到达桶、combat preview | 未来结果从学习目标变成可比较的输入 | horizon 之外系统性失明；预测误差累积 | 固定预算下接口有/无成对 ablation |
| attention 忽视 source-target 关系 | graphormer bias / edge attention / 候选条件化特征 | ETA、可达性、角度进入决策路径 | pairwise 成本 P² 增长，需稀疏化或折叠 | 先测关系特征对目标选择质量的边际贡献 |
| 几何解算拖慢训练 | analytic planner + top-k 自剪枝 + 随机候选兜底 | policy 只在可执行候选中选择 | recall 上限即策略上限 | 对暴力 oracle 测 recall（Audun：93–95%） |
| 按座位/起始位置出现胜率差异 | 旋转不变特征 / 相对命名 / p0 归一 | 同一策略在不同座位产生一致输入 | 4P 对手置换需额外处理 | 分座位/分起始位胜率统计（flg 的原始观察方式） |
| 不确定动作自由度是否多余 | 先做高价值行为覆盖审计再定接口宽度 | 搜索难度重新分配 | 漏掉高价值行为即 ceiling；多余自由度有工程成本 | 对强 replay 测候选覆盖（flg fraction 档无收益是反面教材） |

## Top Principles

由四个机制候选排序（信息接口证据最宽，关系接口与可行性/动作接口次之，视角归一化证据宽度相同但 impact 更局部）；项目级 canonical 原则见 [[solution-space]]，本节是表示专题版本：

### 1. Expose delayed consequences when they are cheap and reliable

- **Problem Signature**：动作价值要经过 ETA、战斗或 ownership 变化才显现，且这些未来量可可靠计算。
- **Principle**：当 future-state / preview 可以廉价且可靠地计算时，优先显式暴露给 policy；如果 compute/data/capacity 足够，模型自行学习是有证据支持的替代路线。
- **Mechanism**：未来结果从需要网络自行外推的隐变量，变成直接输入或辅助监督，学习负担转移到战略比较。证据：六个直接输入型 future interface + Audun 的 multi-horizon auxiliary target；Isaiah 200M/15B 的 low-level route 是最强 scaling counterexample。
- **Use When**：long-horizon control、调度、多智能体规划中未来结果可可靠计算。
- **Boundary**：horizon 之外的后果系统性不可见；forecast 误差累积会误导而非帮助；需要 parity。

### 2. Make source–target relations first-class inputs

- **Problem Signature**：几何与资源约束密集，而标准 token attention 只见两个 token 的 embedding，看不见它们之间的 ETA/可达性/角度。
- **Principle**：把 source-target 关系显式表达（graphormer bias、edge attention、edge block、pairwise 特征、候选条件化特征），让目标选择在真实几何约束下进行。
- **Mechanism**（信息路由）：关系量进入 attention logits 或决策路径，目标选择不再依赖网络从 embedding 自行归纳几何。证据：六个方案的不同实现（Felix、Jake、TonyK、flg、Audun、Ender）。
- **Use When**：任务核心是实体对之间的选择，且关系量可计算。
- **Boundary**：pairwise 成本 P² 增长，需 gather/scatter 稀疏化（Felix）或折叠（其余）；关系表达不自动包含可行性，可行性解析见原则 3。

### 3. Choose action abstraction by coverage, not convenience

- **Problem Signature**：raw action 高维组合、回报延迟稀疏，接口宽度与候选生成方式的选择缺少客观依据。
- **Principle**：动作分解（semantic、factorized、bucket、micro-step、no-op/all-in）与可执行候选解析（planner / tensor / mask）的选择依据都是高价值行为覆盖，不是接口优雅。
- **Mechanism**：动作分解与可行性解析都在重新分配搜索难度；覆盖决定探索是否集中在高价值行为附近。证据：Felix semantic switch 提速、Hober 极简进 top 5、flg fraction 档无收益、Ender 保留多发射且用到；五家可行性解析（Felix tensor、Jake intent 解算、Audun planner、Isaiah Rust 侧解角、Ender 候选计算）。
- **Use When**：raw action 高维组合、回报延迟稀疏、或一回合含多次相关动作。
- **Boundary**：coverage 论证（recall、held-out、随机候选兜底）必须先行；可行性层 recall 上限即策略上限（Audun planner 93–95%）；合法性判断全部移出模型可能剥夺有用学习信号（Isaiah mask 负结果）；多给的自由度也有成本（flg 的工程投入打水漂）。

## Transfer

这些表示机制可迁移到 robotics、resource allocation、scheduling、program synthesis 和 long-horizon control。迁移决策顺序：先判断未来结果能否可靠计算（决定 future-state 接口是否存在），再判断关系是否稀疏可枚举（决定 pairwise 还是折叠），再判断候选生成器能否测 recall（决定解析层边界），最后才选择 planner、learned model 或 hybrid。视角归一化适用于任何存在等价变换群（座位、朝向、排列）的输入空间。

## Evidence Map

- E1 — Isaiah Pressman solution — official writeup + public repository
- E2 — SimJeg / Hober Malloc solution — official writeup + public repository
- E3 — Felix Neumann solution — official writeup
- E4 — Jake Will solution — official writeup
- E5 — TonyK solution — official writeup + public repository
- E6 — flg solution — official writeup + public repository
- E7 — Audun Ljone Henriksen solution — official writeup
- E8 — Ender / Billy Bradley solution — official writeup + public repository

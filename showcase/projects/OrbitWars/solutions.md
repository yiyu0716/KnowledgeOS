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
  - self-play
  - behavior-cloning
  - action-representation
  - game-simulation
  - evaluation
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
# Orbit Wars：前八名方案重建

本文按 `Thesis → What → Why → Mechanism` 忠实重建八份公开方案：`Thesis` 用一句话概括该方案区别于相邻路线的设计押注；`What` 是 Concrete Method Reconstruction——这个方案实际上怎么运行，包括真实配置与规模；`Why` 区分作者陈述与推断；`Mechanism` 只做单方案内部解释，不做跨方案综合（综合见 [[solution-space]]）。证据强度通过自然措辞保持区分，详细 anchors 由 frontmatter 与结构化 provenance 负责。`Evidence Map` 统一放在文末。


## 问题模型

Orbit Wars 是 2P/4P 的同步行动、连续空间、长时序策略模拟。每回合 agent 返回 `[from_planet_id, angle, num_ships]`；planet 生产舰船，部分 planet 运动，fleet 速度依赖规模，太阳/其他 planet 可能阻挡路径，comet 会生成并离场。核心 bottleneck 是延迟后果下的组合决策：发射时机、来源、目标、角度、舰队规模和多回合资源分配相互耦合。训练需要高吞吐且与官方 engine parity 的 simulator；提交受 CPU 延迟、文件大小和 overage 限制。

这些瓶颈决定了下方矩阵的列：表示与未来接口决定 policy 的 inference burden，动作接口决定探索难度，训练路线与对手分布决定学习信号质量，推理方式决定提交可行性。

## 导航矩阵

这张矩阵是快速定位用的坐标图（具体配置见各节正文与 [[ppo-training]]、[[representation-design]]）；它只恢复事实，不做因果结论。

| Solution | Representation core | Future-state interface | Action interface | Training route | Opponent distribution | Inference |
|---|---|---|---|---|---|---|
| Isaiah (R1) | entity tokens（planet/fleet/comet）+ 17 辅助 token | 无显式预测，靠 200M 容量 | target factorization + 连续 fleet size | PPO from scratch，15B steps | pure self-play（4P 赛后明确认为应加入 past-checkpoint league） | int8/NF4 量化 + 5M fallback |
| Hober/SimJeg (R2) | 每 body 10 特征 × T=19 时间序列 | 无动作假设下的 body 未来序列 | no-op / all-in，短 ETA 目标 | IL→RL→最终 from scratch，10B steps | pure self-play | Rust 桥 + TTA + 发射阈值 |
| Felix (R3) | 48 token + graphormer edge bias | reachability tensor（全量源目标-动作） | 4 个 semantic intent，每 planet 177 维 | PPO from scratch + PFSP，8.4B/2.7B steps | PFSP 按难度采样 | JAX planner 解析动作 |
| Jake (R4) | 45 token + combat preview | "不发射会怎样"预演 + intent 代价表 | 3 种 launch intent + no-op | PPO from scratch，~4B/~2B steps | 2P 最新冻结 / 4P PFSP | C++ 引擎解析角度 |
| TonyK (R5) | planet/edge/arrival 分块特征 | 到达时间轴投影 | 每 planet 目标 × 发射量桶，masked | BC → IMPALA/V-trace | live + 冻结池 + 专用强 checkpoint | AOTInductor CPU 提交 |
| flg (R6) | 相对输入 + A-to-B edge attention | 23 个到达桶 + 前向预测 | 4 档 fleet share（实际只用 100%） | 小模型 dense → teacher KL 迁移 → async PPO | 2P self-play / 4P 手工 league | 2P 贪心 2 步搜索 |
| Audun (R7) | planet token + pairwise bias，fleet 折叠 | 24 桶 incoming + 辅助未来预测头 | 两段式：目标 × 6 发射桶 | PPO from scratch，2.2B/1.6B steps | 冻结自身（2P）/ 全历史池（4P） | planner + 自剪枝候选 |
| Ender (R8) | entity + 2D RoPE + 24 桶预测 | incoming net + 未来 ownership/garrison | micro-step（≤16 次/回合，5 档比例） | PPO from scratch，3.1B/1.5B samples | 胜率优先历史 league | 采样动作搜索 |

## 1. Isaiah Pressman（R1）


**Thesis**：押注 Bitter Lesson——用 200M 参数与 15B 步训练，让模型从低层 entity 与连续动作自学动力学和策略，以规模替代领域工程。

**What — Concrete Method**

- **模型**：200M 参数 Transformer，38 层 × d768 × 16 头，MLP 隐层 1536。输入为 planet/comet/fleet entity token（位置、速度、编码后舰数等各自经 MLP 投影）加 17 个辅助 token（4 player summary、1 global、4 plan、4 value、4 scratch）。所有玩家的动作在**单次前向**中算出，节省 2–4× 计算。
- **动作**：每个来源 planet 先出 Bernoulli 发射 logit；发射后用 QK 相似度选目标；舰队规模用 8 分量 discretized logistic mixture 在 `[3, num_ships]` 上连续选择。
- **训练**：PPO from scratch 纯 self-play，15B steps，2P/4P 各半（后半程误判改为 90% 2P）。±1 终局 reward，rollout 64，gamma=1.0（4P value head 的定义要求），GAE-λ + clipped PG + advantage 归一化 + 熵项，另加对 previous-best checkpoint 的 policy KL 与 value cross-entropy。评估对 previous-best 胜率 >70% 才替换 checkpoint。
- **规模**：8×B200 + 2048 envs，末期 4 节点 8192 envs，~6.3M steps/GPU-h，总计 ~2400 B200-hours。
- **提交**：int8 线性层 + NF4 4-bit 量化（group 128）压进 100MiB；约 8% 的 4P 慢 CPU 局在剩 1 秒 overage 时切换到 5M fallback 模型。
- **环境**：Rust 重写，replay parity 测试，角度由 Rust 侧计算。

**Why**：作者明确陈述——检验 Bitter Lesson：足够大的模型 + 足够多的训练能否替代领域工程设计。观测与动作故意保持低层。

**Mechanism**：用容量和 15B 步训练让模型自己学会动力学，domain engineering 全部让位于 scaling。target factorization 是唯一保留的接口简化（从 raw angle 改为选目标）。量化与 fallback 解决的是提交约束而非策略机制。

## 2. Hober Malloc / SimJeg（R2）


**Thesis**：把动作空间压缩到极致（每 body 仅 no-op/all-in 射向短距目标）并把短期未来直接放进输入，让 4.3M 参数在 10B 步内足以覆盖策略空间。

**What — Concrete Method**

- **模型**：4.3M 参数三段式——1D-CNN 编码器（290K，4 个 Conv1D 残差块）编码每个 body 的 10 特征 × T=19 时间序列；ModernBERT XXS（3.9M，7 层 d256 4 头，无 token embedding、无位置编码，全局注意力）；每 body 两个动作头（发射 + 注意力式目标选择）加全局 value 头（130K）。
- **未来接口**：时间序列是"假设此后不再发射"下模拟 T=19 步的 body 状态演化——显式包含即将发生的占领、生产与战斗结果。
- **动作**：每个 body 只有 no-op 或 all-in（全部舰船）射向 ETA<20 的短距目标；两个 mask（发射合法性 + 可达性）。
- **训练路线**：heuristic → IL（5M 样本，来自 189K 官方 episode 中按分数 >1500 过滤的 20K 局，launch BCE 权重 5.0 + target CE，进入 top 10）→ IL+RL（top 5）→ **最终 from scratch RL 反超一切 IL 初始化**。
- **最终训练**：PPO（PufferLib，Rust→C 特征 + Torch→CUDA 模型），10B steps 分三阶段（3B/3.5B/3.5B，LR 1e-3→3e-4→1e-4 cosine 衰减）；1024 agents，8×H100，~40K steps/s；horizon 128，gamma 0.995，λ 0.97，minibatch 4096，clip 0.2；发射头熵系数 0.01（目标头 0.002，5×）；40% 局为 4P；±1 reward 但 500 步限时获胜降为 +0.5；40 步无动作截断 rollout；旋转 + 对手置换增广。

**Why**：作者明确陈述——raw action space 太难；观察 top player replay 发现 no-op 和 all-in 占绝大多数，短距离发射为主。最终从 IL 转向 from scratch 是因为后者"快速超过了 IL 初始化的模型"。

**Mechanism**：把探索问题压缩到极致（每 body 二选一 + 短距目标），把短期未来直接放进输入，让 4.3M 模型在 10B 步内足以覆盖策略空间。作者自述多个 stabilization trick"很可能没用"（未认真 ablation）——诚实标注了哪些是必要机制、哪些是噪声。

## 3. Felix Neumann（R3）


**Thesis**：把全部几何事实集中进一份全量 reachability tensor，让特征、动作头与 mask 共享同一事实源；policy 只在 semantic intent 之间选择。

**What — Concrete Method**

- **模型**：6.2M 参数 pre-norm Transformer，dim 192，expansion 4。trunk 8 层；critic 2 层 + MLP 只处理 4 个 player token（单次前向给出每玩家 value baseline）；actor 2 层只处理 planet token。48 token = 4 player + 44 planet（含 comet 槽位）。
- **Reachability tensor**：形状 (B, P, P, S, 3)——每对 (source, target) × 每个动作存三个数（舰数、发射角、ETA），几乎一切下游（特征、动作头、semantic 舰数、mask）都读它。JAX 实现，编译时间是最痛的工程约束。
- **动作**：每 source planet 一个 177 维 categorical（1 no-op + 44 目标 × 4 semantic intent：send-all / sortie / hold / kill-at-arrival）。intent 的实际舰数由 reachability tensor 按意图解析，而非固定比例（最后一周从固定 0.25/0.5/0.75/1.0 换过来，学习速度大幅提升）。发射头 = 可分解 bilinear + 仅在可达边上 gather/scatter 的 full-rank edge MLP + intent bias。
- **表示**：garrison 用 embedding（≤384 精确，sqrt 分桶到 768）；incoming fleet 用到达日历（2P 24 步 / 4P 16 步），每格 embedded 加权求和；graphormer 式 attention bias 注入 reachability 边信息；全局标量经 FiLM 调制每个 block。
- **训练**：PPO from scratch + PFSP（按胜率难度采样历史 checkpoint；对手固定 2 次更新共 512 步以从 rollout 免费获得胜率估计）。2P/4P 分模型，分别 8.4B / 2.7B steps；1024 envs，2 GPU，~19K/15K SPS。winner-take-all ±1（4P 败者 -1/3）。rollout 256，**1 个 PPO epoch**，minibatch 8192，λ 0.95，gamma 0.993/0.99，KL-targeted 自适应 LR，clip 0.2。熵退火是作者口中"最重要的单一旋钮"。
- **评估**：训练中对历史 checkpoint 跑 1024 局并行评估；2P 胜率近单调上升，4P 用 1v3-对抗自身克隆的设置（作者承认缺陷）。

**Why**：作者明确陈述——reachability tensor 是核心 idea，"计算它几乎和模型本身一样费工"；semantic action 来自观察 Jake 的对局后的一次 late switch。

**Mechanism**：把连续几何（角度、ETA、可达性、精确舰数）整体移入 feasibility 接口，policy 只在有语义的 intent 之间选择。新颖处在于该接口是全量张量而非按需 planner，因此特征、动作头与 mask 共享同一事实源。

## 4. Jake Will（R4）


**Thesis**：把"不行动会怎样"（combat preview）与"每个 intent 的真实代价"（resolved cost）变成可直接比较的输入，并用三个正则化项分别管理探索、节奏与 4P 归因。

**What — Concrete Method**

- **模型**：7.5M 参数 Transformer，45 token（40 planet + 4 comet + 1 CLS），8 层 trunk；单次前向输出所有动作，无自回归结构。
- **特征**：每 token 含 self-state（owner/舰数/产量/轨道态）；**combat preview**——"如果不再发射，每个 planet 会变成谁、多少舰、翻转裕度"；top-K incoming/outgoing fleet 摘要；每对 (source, target) 的几何特征（距离、太阳遮挡、预计到达、轨道相位）直接进目标头；**resolved launch-size 表**——每个 intent 对每个目标实际会发射多少舰；CLS 聚合全局（玩家总量、攻击矩阵、游戏阶段）。全部特征旋转不变。
- **动作**：每 owned planet 三个头——44 路 target categorical、3 种 fleet intent（100% / Capture-Defend / Maintain-ownership，后两者由 C++ 引擎解析出精确舰数）、no-op 头。
- **训练**：PPO from scratch，2P/4P 分模型（~4B / ~2B steps，作者注明数字因多次平台期而虚高）。2P ±1；4P +1/0/-0.5/-1（区分非第一名以稳定泛化）。rollout 64，minibatch 4096，batch ~400K，2 epochs，LR 1e-4 起多次下调，gamma 0.995，λ 0.90，熵 0.002 起下调。附加损失：launch-success BCE（系数 0.2，作者有小规模 A/B 证明加速早期训练）、no-op KL 锚（平均 10% 发射率，系数 0.5→0.1）、4P 每玩家 value head。
- **Opponent pool**：2P 主要打最新冻结 checkpoint（末期扩到最近 3 个），胜率近单调提升、未见循环；4P 末期 PFSP——随机选 ~200 个 3-checkpoint 组合各打 ~50 局，取胜率 <25% 的组合按二次加权（12.5% 胜率权重 4×）专攻，每 ~30M steps 一轮。仅 ~300M steps 就带来 4P 大幅提升（作者："extremely effective"，后悔没早做）。
- **Surrender（仅 2P）**：双方 value 预测越过阈值即结束；5% holdout 全程局校准阈值（目标 99% 正确率），砍掉 60–70% 回合。
- **规模**：8×5090 + 384 核，CPU 瓶颈，15–20K SPS。

**Why**：作者明确陈述——policy 应直接看到"不行动会怎样"和"每个 intent 的真实代价"，而不是从 raw fleet 自己推导；no-op 锚防止"spray and pray"。

**Mechanism**：把 delayed consequence 变成可比较的输入（preview + resolved cost），把资源/防守约束解析进 intent 定义，用三个正则化项（BCE/KL 锚/多 value 头）分别处理探索、节奏与 4P 归因。各组件对最终强度的独立贡献未被逐项 ablation。

## 5. TonyK（R5）


**Thesis**：把"会玩"（BC 廉价提供）与"变强"（RL off-policy 优化）分离，用 delayed moving teacher 与 V-trace 压住异步训练的漂移。

**What — Concrete Method**

- **两阶段 pipeline**：先对 top player 的 Kaggle replay 做 masked behavior cloning（重建每步 observation，把原动作转成与 RL 相同的 per-planet action class，masked CE 只让合法动作参与损失）；再进入 IMPALA 式异步 actor-learner——CPU actor 批量推理、写共享 buffer，GPU learner 更新，V-trace 校正 actor/learner 的 policy lag。
- **对手课程**：live policy + 全程冻结 checkpoint + 2P/4P 专用强 checkpoint 的混合池（作者称之为简单 league）。
- **稳定化**：delayed moving teacher——teacher 是延迟数十万 env steps 加载的历史 checkpoint，用 KL 把当前 policy 锚在其附近；teacher 随训练缓慢进步而非永久冻结。
- **Reward**：刻意全部禁用中间 shaping，只用终局胜负。
- **模型**：planet/edge/arrival 三类输入分块编码融合；16 个 cross-attention block，hidden 128，4 头；policy head 每 source planet 独立预测 destination × send-amount bucket，非法动作 mask；value head 池化全局。
- **规模**：单张 RTX 5090 训练约一周；BF16 前向、`torch.compile`、C++ 环境与观测路径。
- **提交**：AOTInductor 导出 CPU 推理，2P/4P 独立 artifact，C++ runner。

**Why**：作者明确陈述——random self-play 在大 action space 上浪费大量 compute 重新发现基本行为；BC 立即提供这些基础，RL 负责长期胜负与变强。稀疏 reward 的理由是避免优化手工代理目标。

**Mechanism**：把"会玩"（BC 廉价提供）与"变强"（RL off-policy 优化）分离；V-trace + delayed teacher 共同处理异步带来的 policy lag 与漂移。单一组件的独立贡献未做受控分离。

## 6. flg（R6）


**Thesis**：把表示问题做"薄"——纯相对输入加 fleet 折叠进前向预测，让 2.5M 模型在低吞吐下也可训。

**What — Concrete Method**

- **模型**：2.5M 参数 Transformer（4 层 d256 8 头，ff expansion 2，GELU/LayerNorm），自定义 edge attention。输入只用相对量：无绝对坐标、无绝对玩家 id（玩家按起始位置相对命名），避免按座位区分行为。
- **未来接口**：fleet 不作为输入实体——前向预测折叠为每 planet 23 个到达桶（多少舰队、何时到、谁赢、ownership 是否保持）；edge 特征描述 A→B（100% 发射 7 步到达并占领、50% 发射 11 步到达但失败等）。
- **动作**：NxN MLP 头（concat[src, target, edge]）预测 4 档 fleet share logits（25/50/75/100%）+ no-op（NxN+1），每个来源单动作选择。
- **Value**：CLS token + Gaussian histogram loss（51 bins），比此前 MSE 稳定得多；bins 与 sigma_ratio 选择是关键。
- **训练路线**：先训一个 2 层 d128 小模型，双模式、dense capture reward（占领/失守时的产量差）；一周后用 teacher KL 把知识迁移到大模型（"big speedup"）。之后 async PPO + GAE：gamma 2P 0.999 / 4P 1.0，λ 0.9–0.98，bs 1024，lr 1e-6..3e-5，clip 0.2（对联合动作空间整体裁剪），EMA advantage 归一化，value coef 0.1–0.3，熵 2e-3，单遍 PPO。
- **对手**：2P self-play；4P 打手工维护的固定 league。
- **规模**：2 个 rollout actor × 24–48 async envs × 32 steps，单机 + 租用 1×A100，SPS 800–2000（CPU-bound）。SWA 5 个 checkpoint 参加大规模 all-against-all tournament 选模型。
- **提前终止**：一方拥有 95% 舰船和全部 planet 即结束（给全额未来 reward），每局省 ~30 回合。
- **推理**：4P argmax；2P 贪心 2 步 rollout 搜索（自己采样 5 个动作 vs 对手 argmax，再 argmax 推一步），+30–40 分。

**Why**：作者明确陈述——相对输入消除按座位的行为差异（训练非常平滑）；fold fleet 进前向预测让模型完全不必处理 fleet 实体。

**Mechanism**：用相对化 + 前向预测把表示问题做"薄"，让 2.5M 模型在低 SPS 下也可训。league 稳定 4P 但池太窄（遇弱反而差，作者自述）。负证据：<100% 发射档位投入大量工程但完全无收益——最终 agent 只用 100%。

## 7. Audun Ljone Henriksen（R7）


**Thesis**：用 analytic planner + top-k 自剪枝把几何成本压到可训，并用逐改动的受控实验流程产出因果级证据。

**What — Concrete Method**

- **模型**：~9M 参数 Transformer（含推理时丢弃的辅助头），planet token + pairwise 特征进 attention bias；fleet 折叠进目标 planet 特征；观测按座位旋转到统一视角。
- **动作**：每 planet 两段式——先选目标（或 no-op），再从 6 个发射桶（20/40/60/80/100% 或"恰好占领"）中选择。
- **Planner 与自剪枝**：解析 planner（Newton 式 lead pursuit + 最近点碰撞检查）为每个 (source, target, size) 解算角度/ETA 并 mask 不可达项；原始 48×48×6 = 13,824 次解算太慢，改为只允许模型自身 logits 的 top-4 目标 + 4 个随机目标（从 48 压到 8）。逐步收紧（16+8 → 8+8 → 4+4）性能始终不掉；完全去掉随机目标也只 45.7%（勉强平手）。planner 对 3,600 角暴力 oracle 的 recall 为 93–95%、命中率 99%。
- **辅助未来损失**：小头预测 2/8/32/64 步后的 ownership、garrison、产量（目标免费来自 rollout），强制 trunk 建立内部世界模型。
- **Early reset**：一方失去最后一颗 planet 即结束（不等最后一艘 doomed fleet 飞完），显著提升。
- **训练**：PPO from scratch，2P 2.2B / 4P 1.6B steps，2 GPU。2P 对手是 ≤1M steps 旧的冻结自身副本；4P 崩溃后改为从全历史采样的 opponent pool（"single change"扭转）。reward +1 胜 / -1/3 负。
- **实验流程**：~200 个实验，每个 100M steps + ~512 局 round-robin 对基线判定；独立 git worktree 隔离每个改动。
- **4P 起源**：长时间直接用 2P 模型"骗着玩"——观测中把三个对手折叠成一个虚拟敌人。

**Why**：作者明确陈述——上一届 Lux 的混乱流程教训：一次混 5 个改动、中途弃 run、改代码失控；这次每改动独立训练独立判定。planner + top-k 是为了把几何成本压到可训。

**Mechanism**：受控实验流程本身是方法的一部分——它产出了整个比赛中最系统的 negative evidence 表（见 [[solution-space]]）。2P 过拟合事故（只打旧自身副本 + 末期低熵低 LR 微调 + 只对自己模型评估 → 对 top 10 几乎全败）是"评估回路定义过拟合可见性"的最尖锐案例。

## 8. Ender / Billy Bradley（R8）


**Thesis**：保留最大动作表达力（micro-step 多次发射）并用 KL-to-prior 重新定义默认行为，以最小预算（$170）证明规模不是必要条件。

**What — Concrete Method**

- **模型**：4 层 d192 Transformer encoder，CLS + planet token，位置用 2D RoPE；观测归一到 p0 视角。实验过更大模型，"学得更慢且无收益"。
- **特征**：实体类型/owner/产量/garrison/速度/半径/回合数；incoming fleet 按 24 桶编码净效果（fleet 间战斗先按规则解析）；4P 另加 24 桶幸存 owner one-hot；被 abort 屏蔽的比例档；**24 步未来 ownership/garrison 投影**（ceasefire 假设）。target MLP 额外吃 fleet size、ETA、"是否大于目标 garrison"布尔、发射后的双方未来投影。
- **Micro-step 动作空间**：每回合最多 16 次发射，每次为一个 micro-step——先全局 halt/launch，再从联合分布采样 origin + 发射比例（0.2/0.4/0.6/0.8/1.0），对选定 origin-fraction 计算 43 个可达目标采样（含 abort）；新 fleet 立即加入观测；RL 完全在 micro-step 粒度上进行。因式分解把 44×43×5=9,460 个候选压到每步 43 个。
- **训练**：PPO + GAE（JAX 环境，不追踪 fleet 位置——只维护每 planet 的 incoming 桶每回合左移）。gamma 0.998，λ 0.95，clip 0.2，2 epochs，minibatch 2048，grad norm 0.5。reward 0/1/2（负/平/胜）——刻意不用负值：gamma<1 时负 reward 会鼓励"拖延失败"。2P 2048 envs / 4P 384 envs，rollout 256/512 micro-steps。
- **稳定化**：halt/fraction 头用对初始 prior 的 KL（halt_init_prob=0.9，fraction 比例 1:1:1:1:10）替代标准熵奖励——直接解决小舰队 spam，"立即大幅改善"；后期降低系数（甚至 0）继续获益。
- **Earlygame envs**：4P 一半 envs 在 50 步处带 value bootstrap 截断，保证早期数据供给。
- **League**：部分 envs 打历史 checkpoint + 强旧实验模型，按近期胜率优先采样难对手；每 checkpoint 的 ELO 可从对局估计。
- **规模**：$170 总预算（自有 3080 + 11 天租用 4090），最终 2P run 3.4 天；2P 3.1B samples / 1.5B 4P。
- **推理**：4P 采样动作搜索（整回合采样 10 次，用蒸馏小模型模拟对手，选均值 value 最高）；2P 提交其一为 launch/halt 深搜索。

**Why**：作者明确陈述——不是专家，不敢断言部分发射/同源多次发射无价值，所以把动作空间设计得"表达力最大"；gamma=1 的实验（领先/落后双方都躺平浪费吞吐）驱动了 reward 设计。

**Mechanism**：micro-step 把每回合的组合爆炸转成序列决策，candidate 条件化让后续决策基于已选 origin/fraction；KL-to-prior 重新定义了"默认行为"这个隐含假设。$170 预算进入前 8 是"规模是充分条件而非必要条件"的直接反例。


## Evidence Map

- E1 — Isaiah Pressman solution — official writeup + public repository
- E2 — SimJeg / Hober Malloc solution — official writeup + public repository
- E3 — Felix Neumann solution — official writeup
- E4 — Jake Will solution — official writeup
- E5 — TonyK solution — official writeup + public repository
- E6 — flg solution — official writeup + public repository
- E7 — Audun Ljone Henriksen solution — official writeup
- E8 — Ender / Billy Bradley solution — official writeup + public repository

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
  - ppo
  - self-play
  - opponent-distribution
  - training
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
# Orbit Wars — PPO Training

## Scope

本文只研究 Orbit Wars 前 8 名方案的 training system：训练路线、规模与吞吐、opponent distribution、reward、PPO/actor-learner 更新、stability 控制与 checkpoint evaluation。Representation 与 submission engineering 只有在直接影响训练行为时才提及。

## Core Problem

训练难点不是选择某个 optimizer，而是让 policy 在 delayed consequence、长时序 credit assignment 和 non-stationary opponent distribution 下持续获得有效信号。2P 接近零和，4P 存在联盟、循环和 stalling，使"只击败当前对手"不等于学到可泛化策略；同时大量 rollout 时间消耗在早已决定胜负的局面上，进一步稀释了有效信号。

## Training Landscape

八个方案的真实训练配置如下（均为 writeup 记录的事实；Isaiah / SimJeg / TonyK / flg / Ender 另有 code 佐证）：

| Solution | 训练路线 | 规模与吞吐 | Opponent distribution | Reward | 更新核心 | Stability 控制 |
|---|---|---|---|---|---|---|
| Isaiah (R1) | PPO from scratch，pure self-play，明确拒绝 IL | 200M 参数，15B steps；8×B200 + 2048 envs，末期 4 节点 8192 envs；~6.3M steps/GPU-h，共 ~2400 B200-hours | pure self-play，无 league（作者赛后明确表示若重做会给 4P 加 past-checkpoint league） | ±1 终局 | rollout 64；gamma=1.0；对 previous-best checkpoint 加 policy KL + value cross-entropy | 周期性对 previous-best 评估，胜率 >70% 才替换 checkpoint |
| SimJeg (R2) | heuristic → IL (top 10) → IL+RL (top 5) → **RL from scratch**（最终） | 4.3M 参数，10B steps；1024 agents，8×H100，~40K steps/s；40% 局为 4P | pure self-play（曾用 frozen checkpoint 占 2/4 席位，最终放弃） | ±1；500 步限时获胜降为 +0.5 | horizon 128，gamma 0.995，λ 0.97，minibatch 4096，clip 0.2，3 阶段 LR 1e-3→3e-4→1e-4 | launch 头熵系数 5× 于 target 头；40 步无动作即截断 rollout；旋转/对手置换增广 |
| Felix (R3) | PPO from scratch + PFSP，无 IL；2P/4P 分模型 | 6.2M 参数，2P 8.4B / 4P 2.7B steps；1024 envs，2 GPU，~19K/15K SPS | PFSP：按胜率难度采样历史 checkpoint | winner-take-all ±1，4P 败者 -1/3 | rollout 256，**1 个 PPO epoch**，minibatch 8192，λ 0.95，KL-targeted 自适应 LR | 熵退火是"最重要的单一旋钮"；对手固定 2 次更新（512 步）以从 rollout 免费获得胜率估计 |
| Jake (R4) | PPO from scratch；2P/4P 分模型 | 7.5M 参数，2P ~4B / 4P ~2B steps（含多次平台期重调）；8×5090，15–20K SPS，CPU 瓶颈 | 2P：主要打 latest frozen checkpoint；4P：末期 PFSP，专打胜率 <25% 的 checkpoint 组合，二次加权 | 2P ±1；4P +1/0/-0.5/-1 | rollout 64，batch ~400K，2 epochs，λ 0.90，gamma 0.995，LR/熵多次下调 | no-op KL 锚定 10% 发射率；launch-success BCE 辅助损失；4P 每玩家 value head；value 预测触发的 surrender（砍掉 60–70% 回合） |
| TonyK (R5) | **BC warm start** → IMPALA actor-learner + V-trace | 单张 RTX 5090 训练约一周；hidden 128 × 16 blocks | live policy + frozen 历史 checkpoint + 2P/4P 专用强 checkpoint（league 式混合） | 稀疏终局（刻意禁用所有中间 shaping） | 异步 actor-learner，V-trace 校正 policy lag；BF16 前向 | delayed moving teacher KL（延迟约数十万 env steps 的移动教师） |
| flg (R6) | 小模型 dense-reward 起步 → teacher KL 迁移到大模型 → async PPO；2P/4P 分模型 | 2.5M 参数；SPS 800–2000（CPU-bound）；本地 3090 + 租用 1×A100 | 2P self-play；4P 打手工维护的固定 league | 仅终局 | bs 1024，single PPO pass，joint-action-space clipping，EMA advantage 归一化，gamma 2P 0.999 / 4P 1.0 | Gaussian histogram value loss（51 bins）；熵系数 2e-3；已胜局面提前终止（省 ~30 回合） |
| Audun (R7) | PPO from scratch；2P/4P 分模型 | ~9M 参数，2P 2.2B / 4P 1.6B steps，2 GPU；~200 个 100M-step 实验各经 ~512 局 round-robin 判定 | 2P：≤1M steps 旧的 frozen 自身副本；4P：全历史 opponent pool（崩溃后加入） | +1 胜 / -1/3 负 | planner 掩码的离散动作空间 | 辅助 future 损失（预测 2/8/32/64 步后状态）；失去最后一颗星球即 early reset |
| Ender (R8) | PPO from scratch（micro-step 轨迹）；2P/4P 分模型 | 4 层 d192；2P 2048 envs / 4P 384 envs，rollout 256/512 micro-steps；总花费 ~$170（3080 + 11 天 4090）；2P 3.1B samples | self-play + 按近期胜率优先采样的历史 checkpoint league | 0/1/2（负/平/胜），刻意不用负 reward | gamma 0.998，λ 0.95，clip 0.2，2 epochs，minibatch 2048 | halt/fraction 头对初始 prior 的 KL（halt 0.9、fraction 1:1:1:1:10）替代熵奖励；4P 一半 envs 在 50 步处带 value bootstrap 截断 |

共同的工程底座：多个前列方案明确依赖 Rust / JAX / C++ 等重实现或加速路径来获得 RL 所需吞吐，并通过 replay/parity 检查降低 silent mismatch 风险。公开材料呈现出很强的工程收敛，但这里不把它提升成“没有重写就不可能进行大规模训练”的反事实定律。

## Key Design Axes

1. **Initialization**：from-scratch self-play（Isaiah、SimJeg、Felix、Jake、Audun、Ender）vs BC warm start（TonyK）vs 小模型 dense-reward 迁移（flg）。
2. **Opponent distribution**：pure self-play（Isaiah、SimJeg）vs frozen/latest checkpoint（Jake 2P、Audun 2P）vs PFSP（Felix、Jake 4P）vs 手工 league（flg 4P、TonyK）vs 胜率优先 league（Ender）。
3. **Objective / shaping**：最终 strategic objective 高度收敛于 terminal outcome；Audun 的部分 shaping 被受控实验否决，而 flg 的 dense capture reward 作为 temporary scaffold + teacher transfer 获得正向经验。
4. **更新量 vs 数据新鲜度**：Felix 明确 1 epoch（更多 epoch "买到的是不稳定"）；Jake、Ender 用 2 epochs；其余接近单遍。对应 rollout 长度从 64 到 512 micro-steps 不等。
5. **Stability / exploration**：reference-policy KL 控制 update drift；behavior-prior/no-op KL 重塑 exploration semantics；teacher KL 可用于 competence transfer；entropy schedule 控制随机探索压力——这些实现名相似但 changed variable 不同。
6. **已定局面的处理**：value-based surrender（Jake）、early reset（Audun）、提前终止（flg）、no-op 截断（SimJeg）、earlygame 专用 envs（Ender）。
7. **模型组织**：单模型双模式（Isaiah、SimJeg、TonyK）vs 2P/4P 分模型（Felix、Jake、flg、Audun、Ender）。

## Cross-solution Convergence

- **历史对手进入训练分布**：Felix（PFSP）、Jake（4P PFSP）、TonyK（checkpoint pool）、flg（league）、Audun（全历史 pool）、Ender（胜率优先 league）六个主要系统独立采用。Isaiah 赛后明确认为 4P 应加入 league；SimJeg 曾实验 frozen checkpoint pool，但 final run 移除，因此不能写成“两个未采用者都后悔”。
- **最终 objective 收敛于 terminal outcome，但 shaping 不是一律无效**：TonyK 刻意禁用中间 shaping；Audun 的 dominance shaping 在固定预算实验中只有 34.6%；与此同时 flg 用 dense capture reward 训练便宜的小模型，再通过 teacher KL 迁移到最终模型，并报告明显加速。更准确的结论是：shaping 更适合作为临时 scaffold / auxiliary signal，而不是长期替代真实胜负目标。
- **稳定性机制家族——对参考策略或行为先验的 KL 约束**：以两种形式出现，且改变的机制变量不同（实现相似≠机制相同）：**漂移锚**——Isaiah（对 previous-best）、TonyK（delayed moving teacher），把更新约束在已知可玩策略附近；**默认行为锚**——Ender（对初始 prior）、Jake（no-op 锚），重新定义默认行为与探索语义，替代裸熵（仅两家采用，证据宽度窄于漂移锚）。注意 flg 的 teacher KL 属能力迁移（冷启动），不是行为先验锚。
- **提高有效状态密度**：Jake（surrender 砍 60–70% 回合）、Audun（early reset "significant boost"）、flg（省 ~30 回合）、SimJeg（no-op 截断）、Ender（earlygame envs 直击分布）——五种实现、同一机制：不把 rollout 预算花在已决定的局面上。
- **吞吐决定可实施的训练/实验规模**：多个强方案通过 simulator 重实现、并行 env 和更高效 rollout 把十亿级 self-play、league、tournament 或 search 变得可行；这是强工程收敛，而不是“所有方案都必须重写环境”的普遍定律。

## Alternative Routes

- **BC warm start**（TonyK，R5）：当 random exploration 冷启动成本极高且存在高质量 replay 时，先解决 basic competence 再交给 RL。这是条件路线而非共识——SimJeg 的 IL 初始化模型最终被 from-scratch 训练反超。
- **IMPALA/V-trace 异步 actor-learner**（TonyK）：其余七家都是同步 PPO；TonyK 用 V-trace 换来单卡上的异步吞吐。
- **小模型 dense reward → teacher KL 迁移**（flg）：独有路线，用便宜模型先学会"赢是什么"，再迁移到大模型。
- **micro-step 轨迹**（Ender）：把一回合拆成最多 16 个 micro-step 参与 PPO，其余方案一回合一个决策点。
- **Bitter-lesson 规模化**（Isaiah）：唯一把资源押在模型规模（200M）而非 domain engineering 上的方案，且成功了；但 Ender 的反例（4 层 d192 + $170 训练进前 8）说明规模是充分条件之一而非必要条件。

## Negative Evidence

- **Audun 的受控否决表**（每个改动 100M steps + ~512 局 round-robin）：dominance reward shaping 34.6%、对 live copy 训练 20.7%、8-model league（每 GPU 一模型）17.6%、double batch size 41.4%、更短 rollout 33.4%、连续 fraction head 50.2%。这排除了"shaping 应该有帮助""league 一定更好""batch 越大越稳"等直觉心智模型。
- **Isaiah：action mask 使模型变差**。作者推测被迫自己建模更多物理反而有益；这是解释而非已证明原因。同一方案中 gamma=1.0 导致"领先然后 stalling"，浪费已定局面的 rollout。
- **Ender：gamma=1.0 的两种恶果**——领先方躺平、落后方也躺平，双方都在浪费吞吐；负 reward + gamma<1 会鼓励"拖延失败"。这解释了为何多家选择特定 reward 缩放（0/1/2、-1/3、+0.5 限时胜）。
- **flg：<100% 发射比例完全无收益**，尽管投入大量 feature 与 forward-prediction 工程量；4P league 池太窄，遇到弱 agent 反而表现差。
- **SimJeg 的诚实声明**：多个 stabilization trick "很可能没用"（没有认真 ablation）；fraction bucket 在 IL 实验中已被放弃；frozen checkpoint 池在最终 run 中被去掉。
- **Audun 2P 过拟合事故**（最尖锐的反面案例）：只打 ≤1M steps 旧的自身副本 + 末期低熵低 LR 微调 + 全部评估只对自己模型，三者叠加导致 2P 对 top 10 几乎全败——训练与评估回路中没有任何信号能告诉你已过拟合自己的 playstyle。修复方式是给 2P 也加上全历史 opponent pool（未及实施）。
- **Felix**：至少三倍于展示数量的 run 平台化或崩溃归零；4P 一个 bug 在截止前 36 小时才被发现，严重削弱 4P 表现。

## Open Questions

1. 相同 compute 预算下，from-scratch 与 BC/IL warm start 的净收益差是多少？SimJeg 的反超发生在 10B 步规模，低吞吐条件下未验证。
2. 4P 最佳 opponent curriculum（historical pool / PFSP / league / exploiter）无横向比较；各家都有效但无法排序。
3. 1 个 PPO epoch（Felix）vs 2 epochs（Jake、Ender）没有同环境统一 ablation 裁决。
4. replay 数量、质量与 playstyle diversity 如何量化影响 BC → RL，公开证据无法回答。

## Mechanism Synthesis

这些方案真正改变的训练系统变量：

**1. 训练分布（谁在对面）**
```text
对手分布过窄（只打当前/近期自身）
→ 历史 checkpoint pool / PFSP / league
→ policy 的训练分布覆盖更宽的策略空间
→ 降低 playstyle overfit 与 strategic cycling
```
证据：Jake（4P PFSP "extremely effective"，仅 ~300M steps 就大幅提升）；Audun（4P 崩溃后加入全历史 pool，"single change"扭转）；Isaiah 在赛后明确写道若重做会为 4P 加入 past-checkpoint league；SimJeg 曾让 frozen checkpoints 占 4P 的两个席位，但在 final run 中移除；flg 的 league 稳定了 4P。边界：池仍可能过窄（flg 4P 遇弱则败）；每模型预算不足时 league 动力学本身会失败（Audun 8-model league 17.6%）。

**2. 有效状态密度（每样本的信息量）**
```text
已定局面消耗大量 rollout 预算
→ surrender / early reset / 提前终止 / earlygame 专用 envs
→ 同样样本量中"局面尚未决定"的状态占比上升
→ sample efficiency 提高
```
证据：Jake 砍掉 60–70% 回合；Audun early reset 显著提升；flg 每局省 ~30 回合；Ender 用截断直接修正 4P 早期数据不足。边界：截断依赖 value/胜负判定的准确性；Ender 的 gamma=1 躺平现象说明若不处理，浪费会自动出现。

**3. 稳定化家族（锚的两种机制变量）**
```text
非平稳 self-play 中 policy 漂移过快，或探索被退化行为（spam / spray-and-pray）占据
→ 对参考策略 / 初始行为先验的 KL 约束，替代裸熵
→ 两类锚改变的是不同系统变量：
   a) 漂移锚（Isaiah previous-best、TonyK delayed teacher）→ policy-update drift：更新被限制在已知可玩策略附近，训练稳定；
   b) 默认行为锚（Ender 初始 prior、Jake no-op 锚）→ exploration semantics：默认行为被重新定义，探索集中在有意义的动作附近（Ender："立即大幅改善"小舰队 spam）
```
实现相似（都是 KL 项）但机制变量不同，不能合并计数为同一收敛。边界：默认行为锚仅两家采用（Ender、Jake），证据宽度有限；漂移锚过强限制进步空间（TonyK 的 teacher 必须随训练缓慢移动）；默认行为锚太强锁死退化默认——Ender 后期主动降低系数（甚至 0）反而更好；Audun 末期熵退火过狠是 2P 过拟合的成因之一（裸熵路线的反面案例）。

**4. 冷启动（competence vs 长期目标）**
```text
大动作空间中 random exploration 难以产生合法且有意义的行为
→ BC 初始化（TonyK）或小模型 dense reward 迁移（flg）
→ 基础能力由监督信号廉价提供
→ RL 只负责长期胜负优化
```
证据：TonyK（BC 提供"怎么玩"，RL 负责变强）；flg（"big speedup"）。边界（条件路线）：SimJeg 的 from-scratch 最终反超 IL 初始化——当吞吐足够时冷启动优势会被摊薄；replay 覆盖决定 BC 上限。

**5. 评估即训练信号的一部分**
```text
"谁在进步"由评估协议定义
→ 只对自己模型评估时，过拟合不可见（Audun 2P）
→ 固定 opponent set + round-robin tournament（Jake、Felix、Audun、SimJeg）
→ 才能区分真实提升与循环/过拟合
```
边界：本地 tournament 仍可能与线上 matchmaking 分布不一致（Isaiah 90% 2P 的误判、赛后 4P 占比反转）。

## Trade-offs

- from-scratch 避免专家分布偏差，代价是冷启动慢（TonyK 估计 random self-play 要花大量 compute 重新发现基本行为）。
- opponent pool / PFSP / league 增加 robustness，代价是 rollout 与评估成本上升，且池质量本身成为新超参数。
- KL 锚提高稳定性或重塑默认行为，代价是可能压制新策略出现（Ender 后期降系数获益；TonyK 的 teacher 需缓慢移动）。
- 提前终止提高 sample efficiency，代价是依赖判定器的准确性（Jake 为此保留 5% holdout 全程局校准 surrender 阈值）。
- 1 epoch 保新鲜度（Felix），2 epochs 换样本效率（Jake、Ender）——没有统一 ablation 裁决，属于可辩护的局部选择。

## Decision Guide

面向下一次训练系统设计；最后一列只列公开证据支持的廉价检验。

| 观察到的训练问题 | 候选干预 | 机制 | 边界/风险 | 最便宜的诊断/证伪 |
|---|---|---|---|---|
| self-play 循环、停滞或只赢自己的风格 | 历史 checkpoint pool / PFSP / league | 训练分布覆盖更宽策略空间 | 池过窄；rollout 与评估成本上升 | 单变量替换对手分布的固定预算对照 + round-robin（Audun 流程） |
| 非平稳训练中 policy 漂移失控 | 对 previous-best / delayed teacher / 初始 prior 的 KL 锚 | 更新被约束在已知可玩策略附近 | 锚过强压制探索，后期需放松 | 锚系数退火对照（Ender 后期降至 0 仍获益） |
| rollout 大量消耗在已定局面 | surrender / early reset / 提前终止 / earlygame envs | 有效状态密度上升 | 判定不准引入偏差 | 保留小比例全程局校准阈值（Jake 5% holdout） |
| 冷启动无法产生合法、有意义的行为 | BC warm start 或小模型 dense-reward 迁移 | 基础能力由监督信号廉价提供 | 专家分布偏窄；吞吐足够时优势被摊薄 | 短预算 from-scratch 对照（SimJeg） |
| 本地胜率上升但外部/线上表现差 | 独立对手 tournament + replay inspection | 让过拟合对评估回路可见 | 本地分布仍可能脱离线上 | held-out 外部对手评估（Audun 2P 事故的暴露方式） |
| reward shaping 的直觉诱惑 | 先做固定预算受控 ablation 再决定 | shaped reward 可能被证伪而非证实 | 单次实验噪声 | Audun 式 100M steps + ~512 局 round-robin |

## Top Principles

以下原则由上述矩阵与机制分析归纳（候选机制：opponent distribution、漂移锚、默认行为锚、状态密度、冷启动、评估协议、simulator 吞吐、单/双模型 → 合并等价项；注意 KL 锚家族经机制分离后拆为漂移锚与默认行为锚两个候选 → 按影响、证据宽度、机制清晰度、可迁移性、独立性排序）；项目级 canonical 原则见 [[solution-space]]，本节是训练专题版本：

### 1. Opponent distribution is part of the training algorithm

- **Problem Signature**：self-play/对抗训练中，对手分布随训练移动，局部胜率与真实强度脱节。
- **Principle**："对手从哪来"和 loss 一样是算法的一部分；显式设计历史池、PFSP 或 league。
- **Mechanism**：训练分布覆盖更宽的策略空间，降低 playstyle overfit 与 strategic cycling。证据：六个主要系统独立采用；Audun 对 live copy 的受控对照只有 20.7%，Jake 与 Audun 都报告历史对手机制扭转 4P 训练；Isaiah 的 postmortem 明确支持 4P league。
- **Use When**：环境非平稳、self-play 循环明显、或本地胜率与线上表现不一致。
- **Boundary**：池可能过窄且增加 rollout/评估成本；每模型预算不足时 league 动力学会失败。

### 2. Define the default behavior explicitly instead of relying on raw entropy

- **Problem Signature**：探索被退化重复行为占据（小舰队 spam、spray-and-pray），而熵奖励无法区分"有用的探索"与"噪声"。
- **Principle**：用一个显式的行为先验（初始 prior、固定发射率基线）上的 KL 替代或补充裸熵，重新定义"默认行为"。
- **Mechanism**：改变的是 exploration semantics 而非 update drift：探索围绕有意义的默认动作展开，退化行为被先验直接压制。证据：Ender（halt 0.9 / fraction 1:1:1:1:10 prior，"立即大幅改善"小舰队 spam，后期可降系数甚至 0）、Jake（no-op 锚定 10% 发射率防 spray-and-pray）——仅两家采用，迁移时按机制而非采用数评估。
- **Use When**：训练早期被高频退化行为占据，或熵系数调不出"探索但不 spam"的平衡。
- **Boundary**：先验太强会锁死退化的默认行为本身；后期通常需要衰减（Ender）或退火（Felix 把熵调度称为最重要旋钮——裸熵路线在另一条件下仍成立）。注意与漂移锚（previous-best / delayed teacher KL）区分：后者控制 policy-update drift，是不同机制，见 Secondary Findings。

### 3. Raise the density of informative states, don't just collect more

- **Problem Signature**：episode 远长于胜负实际决定点，或关键阶段在数据分布中欠采样。
- **Principle**：先提高每份样本中"局面未定"状态的密度，再考虑增加样本总量。
- **Mechanism**：surrender、early reset、提前终止、专用 earlygame envs 把 rollout 预算从已定局面转移到未定局面。证据：五个方案，Jake 有量化收益（60–70% 回合）。
- **Use When**：episode 长度与决定点明显不匹配，且存在可靠（或可校准）的胜负判定器。
- **Boundary**：依赖判定准确性，需要校准 holdout（Jake）或保守触发条件。

### Secondary Findings（未进 Top 3 但值得保留）

- **漂移锚（reference-policy KL）**：Isaiah（previous-best KL + value CE）、TonyK（delayed moving teacher）把更新约束在已知可玩策略附近；证据宽度窄于 Top 3 但机制清晰。与默认行为锚（Top #2）实现相似、机制不同，不可合并计数。
- **评估协议定义"进步"**：只对自己模型评估时过拟合不可见（Audun 2P 事故）；本地 tournament 也可能脱离线上分布（Isaiah 的 2P/4P 误判）。
- **冷启动可以与长期优化分离**（条件路线）：见 Alternative Routes 的 BC 与小模型迁移。
- **simulator 吞吐是重要 enabling infrastructure**：多个前列方案通过 Rust / JAX / C++ 等路径把大规模 rollout、league、tournament 和 search 变得可实施；它强烈影响实验预算，但不写成“所有方案必须重写环境”的 universal claim。

## Transfer

这套训练系统经验可迁移到 adversarial training、RLHF/RLVR 后训练、offline-to-online RL、多智能体控制与任何"对手/任务分布随训练移动"的系统。迁移时按序检查：训练分布是否过窄（要不要历史对手池）、稳定化需要哪种锚（漂移控制用 previous-best / delayed teacher，默认行为重塑用行为先验——两者机制不同，选错会失效）、有效样本密度如何（哪里在浪费 rollout）、评估回路能否暴露过拟合。不要直接复制 PPO 超参数——上表显示各家在 gamma（0.993–1.0）、epochs（1–2）、rollout（64–512）上分歧极大且都成功了；真正收敛的是机制，不是超参数。

## Evidence Map

- E1 — Isaiah Pressman solution — official writeup + public repository
- E2 — SimJeg / Hober Malloc solution — official writeup + public repository
- E3 — Felix Neumann solution — official writeup
- E4 — Jake Will solution — official writeup
- E5 — TonyK solution — writeup + public repository
- E6 — flg solution — official writeup + public repository
- E7 — Audun Ljone Henriksen solution — official writeup
- E8 — Ender / Billy Bradley solution — official writeup + public repository

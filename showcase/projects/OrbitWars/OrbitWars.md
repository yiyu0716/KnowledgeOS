---
type: project
project_id: orbit-wars
parents:
  - "[[KnowledgeOS]]"
domains:
  - reinforcement-learning
  - multi-agent-systems
  - game-ai
  - kaggle
status: studied
created: 2026-08-25
updated: 2026-08-28
origin: codex
source_refs:
  - "source:orbitwars-isaiah-repo"
  - "source:orbitwars-simjeg-repo"
  - "source:orbitwars-tonyk-repo"
  - "source:orbitwars-flg-repo"
  - "source:orbitwars-ender-repo"
---

# Orbit Wars

## Project Overview

Orbit Wars 是一个 2-player / 4-player 的实时策略模拟比赛。玩家从初始星球发射舰队，争夺会生产舰船的 planet 和临时 comet；研究价值在于它把几何可行性、延迟后果、组合动作和多智能体训练压缩到一个可复现实验场中。

## Task

每回合 agent 需要决定从哪个 planet 发射、朝哪个方向、发送多少舰船，以及是否连续发射多个舰队。planet 会生产舰船，目标会移动，路线可能被太阳或其他 planet 阻挡；行动结果经过 ETA 才兑现。

## Evaluation

胜负取决于终局舰船总量或提前消灭 opponents。可靠评估不能只看单一 self-play reward，还要覆盖 2P/4P、多 seed、不同 opponent styles、历史 checkpoint，以及独立 round-robin tournament。提交阶段还受 CPU 延迟、文件大小、overage 和 simulator parity 约束。

## Core Challenges

1. **Delayed consequence**：发射成本立即发生，ownership、garrison、incoming fleet 和 production 的影响延迟出现。
2. **Geometric feasibility**：角度、移动目标、遮挡、fleet speed 和 ETA 相互耦合。
3. **Combinatorial action**：来源、目标、角度、舰队规模和多次发射形成巨大组合空间。
4. **Non-stationary opponents**：2P 与 4P 的价值结构不同，纯近期 self-play 容易循环、停滞或过拟合。
5. **System constraints**：训练需要高吞吐，提交需要低延迟且与官方 engine 保持 parity。

## Solution Landscape

高排名方案大致分成几条路线：

- 用 JAX、Rust 或 C++ 重写 simulator，把吞吐和规则一致性作为算法基础。
- 用 future ownership、garrison、arrival timeline、capture cost、reachability 或 edge features 提供未来接口。
- 用 semantic intent、target factorization、bucket、no-op/all-in 或 micro-step 控制 action exploration。
- 用 PPO/self-play、BC → RL、IMPALA/V-trace、PFSP、历史 checkpoint pool 和 league 处理 opponent distribution。
- 用 planner、candidate pruning、search、quantization、cache 和 fallback 适配推理约束。

## Top 3 Principles

以下仅保留一句话压缩与最强边界；完整的问题签名、机制、证据与推导见 [[solution-space]]（项目级 canonical），训练与表示专题的版本分别见 [[ppo-training]]、[[representation-design]]。

### 1. Expose useful delayed structure when it is cheap and reliable

当未来状态、到达信息与战斗预演可以廉价且可靠地计算时，优先显式暴露给 policy；足够大的 capacity/data 也可能成为替代路线（详见 [[solution-space]]）。

### 2. Action representation controls exploration

动作分解（semantic intent、bucket、micro-step、no-op/all-in）与可行性解析（planner / tensor / mask）都在重新分配搜索难度，选择标准是高价值行为覆盖而非接口优雅。最强反例：flg 的 4 档发射比例投入大量工程后完全无收益；可行性层 recall 是策略上限（Audun planner 93–95%）。

### 3. Opponent distribution is part of the training algorithm

历史池、PFSP、league 改变的是 training distribution 本身，与 loss 同级。最强边界：池过窄或低预算下 league 动力学会失败（Audun 8-model league 17.6%）；必须与独立 tournament 配合。

## Knowledge Map

- Solutions → [[solutions]]
- Solution Space → [[solution-space]]
- Related Learning → [[learning/OrbitWars Learning|OrbitWars Learning]]
### Focused Deep Dives

- [[ppo-training|PPO Training]]
- [[representation-design|Representation Design]]

## Evidence Map

- E1 — Isaiah Pressman — public repository and official writeup
- E2 — SimJeg / Hober Malloc — public repository and official writeup
- E3 — Felix Neumann — official writeup
- E4 — Jake Will — official writeup
- E5 — TonyK — public repository and writeup
- E6 — flg — public repository and writeup
- E7 — Audun Ljone Henriksen — official writeup
- E8 — Ender / Billy Bradley — public repository and writeup

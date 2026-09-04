---
type: project-doc
projects:
  - "[[Agent]]"
domains:
  - artificial-intelligence
  - software-engineering
  - developer-tools
topics:
  - agent-harness
  - coding-agent
  - agent-runtime
  - persistent-agent
  - multi-agent
  - agent-security
source_refs:
  - "source:agent-opencode-official"
  - "source:agent-codex-official"
  - "source:agent-grok-build-official"
  - "source:agent-pi-official"
  - "source:agent-openclaw-official"
  - "source:agent-hermes-official"
  - "source:agent-deepseek-harness-official"
origin: mixed
status: studied
created: 2026-08-31
updated: 2026-08-31
---

# Solution Space

## First-principles Problem Model

选型的第一问题不是“哪个 Agent feature 最多”，而是：**哪一层应该拥有决策、状态和风险？**

```text
Model Layer      → reasoning / coding / tool-use capability
Harness Layer    → context, tools, loop, session, policy, observability
Product Layer    → UX, workflows, clients, collaboration, defaults
Control Plane    → identity, routing, nodes, secrets, persistent automation
Knowledge Layer  → evidence, verified mechanisms, transfer
```

OpenCode、Codex 与 Grok Build 把 Product Layer 做得更完整；Pi 与 DeepSeek Harness 让 Harness Layer 更可改；OpenClaw 把 Control Plane 变成主产品；Hermes 把 Memory / Skill Promotion 变成主状态。类别不是互斥标签，但揭示了它们首先优化的变量。

## Normalized Comparison

| Axis | OpenCode | Codex | Grok Build | Pi | OpenClaw | Hermes | DeepSeek Harness |
|---|---|---|---|---|---|---|---|
| Primary job | 多模型编码工作台 | 受控工程执行 | 长程并行终端操作 | 自定义 Harness | 长期 Gateway | 学习型长期 Agent | Runtime 研究与组合 |
| Main state | Session / project config | Thread / history / events | Session / task / worktree | Session tree | Gateway / workspace / memory | Profile / memory / skills / SQLite | Typed event log |
| Parallelism | child sessions | subagent threads | subagent + native worktree + task pane | 由 extension/tmux 组合 | multi-agent routing / nodes | Profiles/Bots/worktrees | plugin scheduler / subagents |
| Safety center | tool permission | OS sandbox + approval | permission + optional sandbox | external isolation | identity/policy + optional sandbox | defense-in-depth + approvals | explicit policy seams + enforcement facts |
| Extensibility | Tools/MCP/Skills/SDK/Plugins | Skills/Plugins/MCP/Hooks/SDK | Skills/Plugins/Hooks/MCP | Extensions/Packages/SDK/RPC | Plugin SDK / runtime registry | Skills/Plugins/Gateway | Cordis plugins/profiles/bundles |
| Stability boundary | fast product evolution | surface-dependent open-source boundary | sandbox default and platform gaps | user-owned composition | high-privilege control plane | durable-state drift | Developer Preview APIs |

## Cross-solution Convergence

### Agent = Model + Harness + Environment

七个方案虽然定位不同，但共同证明一个实用事实：模型只负责部分能力。Context assembly、tool schema、session state、environment access、retry/verification 与 UI/control plane 会改变最终行为。因此跨 Agent benchmark 必须固定这些变量，不能把产品得分直接归因于 Harness 或模型单项。

### Skills 成为 procedure reuse layer

OpenCode、Codex、Grok Build、Pi、OpenClaw 与 Hermes 都提供 Skills 或相近的按需能力包；DeepSeek Harness 把 Skills 作为可替换 plugin capability。共同方向是用 progressive / on-demand disclosure 代替不断扩大的 System Prompt。

收敛只说明 `Skill` 是合理封装，不证明任何 Skill 正确。Skill 需要 version、source、test、permission scope 与 rollback；由 Agent 自动更新时，还需要 Promotion Gate。

### Context decomposition 正在取代单一长对话

OpenCode、Codex、Grok Build 与 DeepSeek Harness 提供 subagent / child session；OpenClaw 与 Hermes 通过 multi-agent、Profile、Bot 或 delegation 拆分状态；Pi 把这项能力留给 extension 和外部进程。机制目标是把探索日志、测试输出和专门任务从主决策 Context 中移开。

但 Context isolation 不等于 State isolation。多个 Agent 同时写同一 checkout、使用同一数据库或占用同一端口，仍会冲突。Grok Build 与 Hermes 的 Worktree 路线说明，parallel write 还需要 workspace/branch isolation。

### Permission 与 Sandbox 趋向分离

Codex、Grok Build、OpenClaw 与 DeepSeek Harness 的官方材料明确区分“是否允许运行”和“获准后能影响什么”。OpenCode提供细粒度 permission mapping；Pi 则明确不在核心替用户规定 permission popup 和 sandbox workflow。

这形成四层模型：

```text
Identity / Authorization → 谁能请求
Permission / Approval    → 这次是否运行
Sandbox / Capability     → 最坏能影响什么
Audit / Replay           → 之后能否重建与问责
```

任意一层都不能自动替代另一层。

### Durable state 成为产品差异的核心

Pi 的 Session Tree 优化 branch 与回看；Grok Build 的 Session + Task + Worktree 优化并行操作；DeepSeek Harness 的 Event Log 优化重放与研究；OpenClaw 的 Gateway + Workspace Memory 优化跨渠道连续性；Hermes 的 Memory + Skills + Profile 优化经验积累。主状态决定系统最容易延续什么，也决定最容易污染什么。

## Alternative Routes

### Route A — Opinionated Coding Product

`OpenCode / Codex / Grok Build`

- OpenCode 优先解决 Provider、Agent role 与客户端统一；
- Codex 优先解决高质量执行、sandbox/approval 与产品嵌入；
- Grok Build 优先解决长期任务、后台进程与 Worktree 并行。

它们适合直接完成软件工程任务，但默认 policy、模型耦合和产品节奏由项目方更多决定。

### Route B — Composable Harness

`Pi / DeepSeek Harness`

- Pi 用 small core + arbitrary extension 获得快速改造能力；
- DeepSeek Harness 用 plugin tree + typed event sourcing 获得形式化组合与 replay。

Pi 更适合快速把个人 workflow 做出来；DeepSeek Harness 更适合控制变量、观察轨迹和替换 runtime mechanism。后者的复杂度与版本风险更高。

### Route C — Persistent Agent System

`OpenClaw / Hermes Agent`

- OpenClaw 从 control plane 出发，解决 Gateway、channel、node、routing、identity 和 automation；
- Hermes 从 learning loop 出发，解决 bounded memory、procedure skill、profile 与 self-improvement review。

两条路线可以组合，但一旦同时启用跨渠道、高权限工具和自动长期写入，security / provenance / rollback 必须升级为主设计，而不是附加设置。

## Negative Evidence

### Multi-agent 不自动带来净收益

每个 subagent 会增加模型调用、tool execution、等待、重复探索与协调。Codex 官方明确提示 token 增长和 parallel write 风险；只有任务可分解、结果可合并、状态被隔离且验证预算可控时，多 Agent 才更可能优于单 Agent。

### Permission 不等于 isolation

Ask popup 可以阻止一次操作，却不能限制用户误批后的影响；Sandbox 可以限制影响，却不会阻止边界内的错误删除、资源浪费或错误提交。Pi 的 explicit omission、Grok/OpenClaw 的 sandbox-off default 和 DeepSeek 的 file-only sandbox vocabulary 都说明必须读取真实默认值。

### Worktree 只隔离 repository files

独立 checkout 不能自动隔离端口、service、cloud account、database schema、cache、secret 与外部 queue。需要为每个并行 worker 定义资源命名、credential scope 和 teardown contract。

### Event Log 不等于 semantic correctness

DeepSeek Harness 可以记录模型看到什么和工具发生什么，但 trace 不证明实现满足真实意图，也不证明测试覆盖业务语义。Traceability 是调查基础；Correctness 仍依赖 specification、evidence、test 与 evaluation。

### Memory 不等于 verified knowledge

OpenClaw Memory 与 Hermes Memory/Skills 服务未来行为和连续性；它们可以包含偏好、决定、观察和 procedure。KnowledgeOS 的职责是绑定来源、区分 Fact/Claim/Mechanism、保留反例与迁移边界。一次成功操作不足以把经验升级为长期真理。

### Open-source Harness 不等于 open full stack

Codex 的官方 Open Source 表明确区分开源 CLI/SDK/App Server 与非开源 IDE/cloud；其他项目也可能依赖闭源模型、托管认证、官方服务或同步式开发流程。选型应分别审查 source availability、model portability、protocol stability、self-hostability 与 governance。

## Open Questions

1. 如何在固定模型、Prompt、Context、Tools、Permissions、Retries 和验证预算后，公平测量 Harness 增益？
2. subagent 的收益如何扣除 token、latency、merge conflict 与重复验证成本？
3. 不同 OS/backend 报告的 Sandbox Profile 是否具有可比较的真实 enforcement？
4. Agent 自动产生的 Memory / Skill 需要怎样的来源、单元测试、回归与过期策略？
5. Event-sourced trace 如何绑定可重放环境、外部服务版本与用户真实意图？
6. Persistent Gateway 如何在单用户便利性与多租户最小权限之间演进？

## Mechanism Synthesis

| Intervention | Changed Variable | Expected Effect | Boundary |
|---|---|---|---|
| Provider abstraction | 更换模型时需重建的 workflow state | 降低模型切换与横向验证成本 | Tool calling quality 与 model behavior 仍不等价 |
| Plan/Build 或 read/write role split | 主 Context 中的执行权限与噪声 | 先收敛意图，再允许修改 | 角色配置错误会产生虚假安全感 |
| Approval + Sandbox separation | autonomy 与 blast radius 解耦 | 减少逐命令人工控制，同时限制最坏影响 | 必须核对 default、backend 与 escape path |
| Subagent + Worktree | context 与 checkout 同时隔离 | 提高可并行任务吞吐，减少文件覆盖 | 外部资源仍需独立命名和权限 |
| Append-only Event Log | 运行事实源从可变 transcript 变为 event stream | 提高 replay、fork、audit 与实验可重复性 | 外部环境和语义 specification 仍需绑定 |
| Gateway control plane | channel、identity、routing、node state 集中 | 支持跨设备和长期在线 Agent | Gateway 成为高价值信任与攻击面 |
| Memory / Skill split | facts 与 procedures 分开持久化 | 降低常驻 Context，积累可复用行为 | 自动 Promotion 会固化错误，需审批和回归 |
| Minimal core + extensions | opinionated policy 移出 core | 快速定制、容易做机制实验 | 组合安全与兼容性责任转移给用户 |

## Decision Guide

| Primary Need | First Candidate | Why | Before Adoption |
|---|---|---|---|
| OpenAI 模型主力编码与受控执行 | Codex | local sandbox、approval、App Server、SDK 与成熟工程面 | 限制验证循环和 subagent 预算；核对 open/closed surface |
| 多 Provider / 本地模型统一工作台 | OpenCode | Provider、client、Agent role 与 permission 统一 | 把 Build 默认权限改成项目需要的最小集合 |
| 多个长期任务原生并行 | Grok Build | Worktree、background task、monitor、queue | 开启合适 sandbox；隔离端口、凭据和外部服务 |
| 自己设计轻量 Harness | Pi | small core、Extension、RPC/SDK、session tree | 先设计 container / permission / secret boundary |
| 跨渠道、设备和节点的长期入口 | OpenClaw | Gateway、routing、nodes、runtime registry | 按高权限 control plane 部署；不要照搬 single-operator default 到多租户 |
| 跨会话个性化与 procedure learning | Hermes | bounded memory、Skills、Profile、self-improvement review | 打开 write approval / version / test；为 Agent 分 Profile |
| Harness 机制研究、trace 与 replay | DeepSeek Harness | plugin composition、event sourcing、runtime modes | 锁定版本；验证 sandbox enforcement 与 API churn |

### Current Toolchain Fit

```text
KnowledgeOS  → verified long-term knowledge and promotion gate
Codex        → primary controlled implementation and validation
Pi           → custom harness / remote / context experiments
OpenCode     → multi-model comparison and fallback workbench
```

在此基础上：需要原生 Worktree / background orchestration 时加入 Grok Build；需要手机、聊天渠道和多节点统一入口时引入 OpenClaw；需要研究 Memory/Skill self-improvement 时吸收 Hermes 的 Promotion 机制；需要做同模型不同 Harness 的因果实验时使用 DeepSeek Harness。

## Top Principles

### 1. Select by System Layer and State Ownership

**Use When:** 同时比较 coding agent、harness 与 persistent assistant，feature list 越看越相似时。

**Principle:** 先问谁拥有 Session、Workspace、Memory、Policy 与 Routing，再比较 UI 或插件数量。

**Boundary:** 项目可能跨层；分类用于识别 primary optimization，不是永久标签。

### 2. Separate Authorization, Permission, Isolation and Audit

**Use When:** Agent 能运行命令、并行修改或跨设备执行时。

**Principle:** identity、per-call approval、sandbox/capability、workspace isolation 与 event audit 分别建模并测试。

**Boundary:** 即使每层存在，配置错误、backend gap 与 external service 仍可能突破预期风险模型。

### 3. Promote Experience, Do Not Auto-declare Knowledge

**Use When:** Agent 会写 Memory、Skill、AGENTS.md、Plugin 或长期配置时。

**Principle:** 把自动写入视为 Candidate Learning；经过 source binding、counterexample、scope、test、approval 与 rollback 后再进入长期事实或 procedure。

**Boundary:** 低风险个人偏好可以使用更轻流程；影响代码、凭据、安全或跨项目决策的知识需要严格 Gate。

## Transfer

这套模型可迁移到任何 Agent 设计：先定义主状态与信任边界，再选择工具和模型。对自研长期 Agent，合理分层是：OpenClaw 式 control plane 处理设备/渠道，Pi 或自定义 runtime 处理可编程 loop，Codex 类 executor 处理高质量代码任务，KnowledgeOS 处理可验证长期知识；Hermes 式 learning loop 只能向 KnowledgeOS 提交候选项，不能绕过 Verification。

## Evidence Map

- `source:agent-opencode-official` — Workbench、Agents、Provider 与 permission evidence。
- `source:agent-codex-official` — execution boundary、App Server、subagent 与 open-source boundary。
- `source:agent-grok-build-official` — parallel operation、worktree、task、permission 与 sandbox defaults。
- `source:agent-pi-official` — minimal core、extension-first strategy、session tree 与 omitted defaults。
- `source:agent-openclaw-official` — Gateway control plane、runtime selection、memory 与 trust model。
- `source:agent-hermes-official` — durable learning state、profiles、security 与 rollback controls。
- `source:agent-deepseek-harness-official` — plugin/runtime composition、event sourcing 与 enforcement semantics。

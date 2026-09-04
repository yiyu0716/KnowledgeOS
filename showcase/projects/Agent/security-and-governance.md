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

# Security and Governance

## Scope

本 Focused Doc 比较七个 Agent 的 Identity、Permission、Sandbox、Workspace Isolation、Secrets、Persistent State、Rollback 与 Audit。目标不是宣布某项目“安全”，而是恢复它们控制什么、默认是否开启、仍有哪些逃逸面，并给出可迁移的部署基线。

## Core Problem

Agent 能力越强，风险越不像普通 Chat UI：

```text
Untrusted input
→ model decision
→ tool authorization
→ process / filesystem / network effect
→ persistent memory, task, plugin, or node consequence
```

安全不能只检查一次 Bash 命令。攻击或错误可能来自 project file prompt injection、MCP/plugin supply chain、shared checkout、credential inheritance、persistent cron、memory poisoning、remote node、sandbox backend gap 或 operator fatigue。

## Concrete Security Landscape

| Solution | Identity / Authorization | Permission | Isolation | Persistent / Audit | Important Default or Gap |
|---|---|---|---|---|---|
| OpenCode | 本地用户与 Provider credentials；Agent role 可配置 | ask / allow / deny，支持 tool pattern 与 external directory | 当前 Evidence Set 只确认 permission surface | parent/child sessions、summary/compaction | Build 默认 full tools；Plan 的 edit/bash 默认 ask |
| Codex | local/cloud account 与 client protocol | Approval Policy | local OS-enforced sandbox；network 默认 off；cloud container | thread/history、streamed events、subagent threads | open-source component 不覆盖 IDE/cloud；remote WS experimental |
| Grok Build | local config / enterprise policy | Ask 默认；Auto / Always-approve；deny wins | Landlock/Seatbelt profiles，默认 off；Worktree 隔离 checkout | disk session、file snapshots、tasks、hooks | `~/.ssh` 等需 custom deny；部分 macOS child network no-op |
| Pi | 启动用户、Provider auth、project trust | 核心无 permission popups；可扩展 | 默认继承进程权限；container/microVM/OpenShell 由用户组合 | session tree、JSON/event output、extensions | project trust 不是 command sandbox；安全责任显著外置 |
| OpenClaw | channel pairing、Gateway auth、owner role、node identity | tool policy、owner-only control tools、exec approvals | sandbox 默认 off；Docker/Podman/SSH/OpenShell；Gateway 留在 host | Gateway sessions、cron、nodes、memory、logs | trusted single-operator host exec 是设计默认，不适用于敌对多租户 |
| Hermes | platform allowlist / pairing、Profile identity | dangerous-command approval、optional write approval | file safety、container isolation、worktree；Profile 不隔离 filesystem | SQLite sessions、Memory/Skills、checkpoint/rollback、audit command | Skill write approval 默认 false；checkpoint 默认 off |
| DeepSeek Harness | profile/application/client layer | approval policy、pre-execute hooks、permission presets | read-only/workspace-write/danger-full-access；full/partial enforcement | append-only events、approval decisions、policy switches、replay | sandbox mode 聚焦 file effects；Developer Preview；minimal example 可为 full access |

## Key Design Axes

### Identity and Request Authority

Persistent Agent 必须先回答“谁能发起动作”。OpenClaw 把 channel pairing、Gateway owner 与 node identity 放在 control plane；Hermes 提供 platform authorization 和独立 Profile。Local coding Agent 常继承 OS 用户身份，因此任何打开的 repository、credential helper 和 shell environment 都可能成为隐式权限。

Identity 只证明请求来自某个主体，不证明该主体理解模型将执行的具体命令。高风险 remote node 或 persistent job 仍需要 action policy 与 audit。

### Permission and Approval

Permission 决定这次 tool call 是否可运行。OpenCode 使用 ask/allow/deny；Codex 使用 Approval Policy；Grok Build 默认 Ask 并允许 deny override；DeepSeek Harness 把 Approval 作为独立 seam；Hermes 对危险命令进行人工确认。

Approval 的失败模式是 fatigue：大量低价值 Prompt 会让用户机械批准。正确策略不是把每条命令都标成危险，而是用 narrow allowlist、typed operation、read-only Agent、policy hook 和 sandbox 减少需要人工判断的表面积。

### Sandbox and Capability Boundary

Sandbox 限制获准动作的最大影响。Codex 本地默认有 OS sandbox；Grok Build 和 OpenClaw 支持 Sandbox 但默认关闭；DeepSeek Harness 明确报告 file-effect mode 与 enforcement completeness；Pi 建议从进程外部构造隔离。

必须验证四件事：默认是否启用、保护哪些资源、哪个进程位于边界外、backend 在当前 OS 是否完整。仅看到 `sandbox: true` 或 profile 名称不足以建立威胁模型。

### Parallel Workspace Isolation

subagent 的 Context 独立不会阻止文件覆盖。Grok Build Worktree 与 Hermes Worktree 提供 branch/directory isolation；Codex 官方建议谨慎进行 parallel write。即使 Worktree 成立，数据库、端口、cache、cloud resource 和 shared secret 仍需 per-worker namespace。

### Secrets and Plugin Supply Chain

Agent 通常继承 Provider key、Git credential、SSH config、MCP environment 与 cloud CLI login。Grok Build 文档明确要求额外 deny 保护凭据路径；Pi 默认继承启动进程权限；OpenClaw Gateway/plugin 和 Hermes Profile/Gateway 可能长期持有 secrets。

Plugin、Extension、Skill 与 MCP 不是同一风险：Markdown Skill 可能诱导危险调用，native plugin/extension 可以直接执行 host code，MCP server 可能拥有独立凭据和网络。安装来源、版本锁定、环境变量过滤与最小 capability 必须分别处理。

### Persistent State and Memory Poisoning

OpenClaw Memory、Hermes Memory/Skills、AGENTS.md、Cron、Hooks 与 Agent config 会跨 Session 改变未来行为。一次 prompt injection 若能写入这些位置，就会从 transient input 变为 persistent policy change。

Hermes `write_approval`、Profile isolation、Skill curator、checkpoint；OpenClaw owner-only control tool、sandbox policy、Memory file visibility；KnowledgeOS Evidence Gate 可以分别降低写入风险。关键原则是把“Agent 建议写入”与“durable state 生效”拆成两个动作。

### Audit, Replay and Rollback

DeepSeek Harness 的 append-only typed event log 最直接服务 replay；Codex App Server 与 Grok Session 保存 tool/event history；Pi Session Tree 便于 branch；Hermes 有 Session search 和可选 checkpoint；OpenClaw 维护 Gateway session、logs 与 Memory 文件。

Audit 回答“发生了什么”，Rollback 回答“如何恢复”，Verification 回答“结果是否正确”。三者不能合并：完整日志不能恢复被删除的外部数据库，Git checkpoint 也不能证明业务语义正确。

## Convergence, Alternatives and Negative Evidence

### Convergence

- Permission 与 Isolation 被越来越多项目拆成独立层；
- read-only / plan / explore Agent 用于在执行前缩小意图；
- Session、Hook 与 Event 提供运行可见性；
- Worktree 或 Profile 用于隔离某一类状态；
- Skill、Plugin 与 Memory 需要成为显式治理对象。

### Alternative Routes

- **Built-in OS boundary:** Codex 把 local sandbox 设为核心默认；
- **Optional product sandbox:** Grok Build、OpenClaw 提供多个 profile/backend，由部署者开启；
- **External composition:** Pi 保持核心最小，让 container/extension 决定边界；
- **Capability-seam model:** DeepSeek Harness 把 file sandbox、approval、enforcement fact 与 tool pipeline 插件化；
- **Defense-in-depth application:** Hermes 组合 user authorization、command approval、file policy、container、context scan 与 rollback。

### Negative Evidence

1. Permission popup 不能限制误批后的 blast radius。
2. Sandbox 不能证明边界内操作符合用户意图。
3. Worktree 不隔离外部 service 和 credentials。
4. Profile / Agent ID 不自动等于 process isolation。
5. Event log 不自动提供 environment replay 或 semantic verification。
6. 自动 Memory / Skill 写入可能形成持久 prompt injection。
7. 开源代码不代表默认模型、托管服务和整个 client surface 开放。

## Mechanism Synthesis

```text
Least privilege identity
→ narrow tool permission
→ sandboxed capability
→ isolated workspace/resources
→ append-only audit
→ reversible checkpoint
→ semantic verification
```

这条链的 changed variable 依次是 requester scope、allowed action set、effect radius、parallel interference、observability、recoverability 与 correctness confidence。越靠前越偏预防，越靠后越偏检测和恢复；不能只部署其中一段却声称获得完整安全。

## Recommended Baselines

### Local Trusted Repository

- 先用 read-only/plan/explore 收敛任务；
- 对 edit/test 使用 workspace-write，network 按任务临时开放；
- command allowlist 覆盖稳定 build/test，危险操作保持 ask；
- secrets 不放在 repository tree；
- Git checkpoint + targeted test + diff review 后再提交。

### Untrusted Repository or Dependency

- 在 disposable clone、container 或 microVM 中运行；
- 禁止 project-local plugin/extension 自动加载，先审查 AGENTS/Skills/Hooks；
- network 默认关闭，credential mount 为空；
- 使用 read-only 或 strict profile 做第一次分析；
- 不把分析 Session 的自动 Memory/Skill 写入长期状态。

### Persistent Gateway / Remote Nodes

- Gateway 与 channel identity 使用强认证并限制 owner；
- control-plane tool、cron、session spawning 与 node execution 默认 deny 给 untrusted sender；
- Gateway host 与 tool sandbox 分离，Node 采用自己的 exec approval；
- 每个 Agent/Profile 分离 credentials、workspace 和 session scope；
- persistent automation 有 owner、expiry、logs 与 emergency disable。

### Self-improving Memory / Skills

- Facts 与 procedures 分开；
- 高影响写入启用 approval；
- 每条 Skill 记录 source、scope、test 与 last verified version；
- Memory entry 有 expiry / contradiction path；
- promotion 前从 Agent trace 提取候选，再由 KnowledgeOS 验证，不直接写成全局知识。

## Focused Top Principles

### 1. Default Is Part of the Security Contract

**Use When:** 文档写着“支持 sandbox/approval”，但不清楚安装后真实行为。

**Boundary:** 默认值仍可能被 enterprise policy 或 project config 覆盖，必须检查 effective configuration。

### 2. Persistent State Is a Privileged Write Surface

**Use When:** Agent 能写 Memory、Skill、Hook、Cron、Plugin、AGENTS.md 或 Gateway config。

**Boundary:** 低风险临时 Session note 可更宽松；会影响后续代码执行或跨用户行为的状态需要强审批。

### 3. Audit Is Necessary but Not Sufficient

**Use When:** 系统拥有完整 session/event log，容易把 replayability 当 correctness。

**Boundary:** 对纯信息检索，trace 可能已足够；对代码、外部系统和安全决策，还需要环境快照、测试与语义验收。

## Transfer

为自研 Agent 设计 contract 时，至少把以下对象独立配置并记录：`requester identity`、`tool permission`、`sandbox backend/mode`、`workspace/resource namespace`、`credential scope`、`persistent state writes`、`audit events`、`rollback point`、`semantic acceptance test`。这样更换模型或 Harness 时，安全与验证语义不会一起丢失。

## Evidence Map

- `source:agent-opencode-official` — tool permission、Agent roles 与 default Build/Plan behavior。
- `source:agent-codex-official` — OS sandbox、approval、network default、App Server 与 subagent caution。
- `source:agent-grok-build-official` — permission precedence、sandbox defaults/platform limits、worktrees 与 hooks。
- `source:agent-pi-official` — core omissions、process permission inheritance 与 external isolation patterns。
- `source:agent-openclaw-official` — Gateway trust model、owner tools、nodes、sandbox scope/backend 与 host boundary。
- `source:agent-hermes-official` — defense-in-depth、write approval、Profiles、worktrees 与 checkpoints。
- `source:agent-deepseek-harness-official` — approval/sandbox seams、file-effect modes、enforcement facts 与 event audit。

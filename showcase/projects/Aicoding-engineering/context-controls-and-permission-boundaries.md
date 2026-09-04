---
type: project-doc
projects:
  - "[[Aicoding-engineering]]"
domains:
  - ai-engineering
  - security-engineering
topics:
  - context-engineering
  - skills
  - hooks
  - permissions
  - sandbox
  - agent-identity
derived_from:
  - "[[solutions]]"
  - "[[solution-space]]"
source_refs:
  - source:ai-native-sdlc-playbook
  - source:anthropic-secure-ai-sdlc
origin: codex
status: studied
created: 2026-08-30
updated: 2026-08-30
---

# Context, Controls, and Permission Boundaries

## Scope

本篇区分六种经常被混在一起的工程对象：

```text
Persistent Context
Conditional Skills
Deterministic Hooks
Tool Permissions
Runtime Sandbox
Agent Identity
```

它们都能影响 Agent 行为，但作用变量不同。

## Core Problem

一份不断增长的 `AGENTS.md` / `CLAUDE.md` 往往被迫同时承担：

- 仓库介绍；
- coding conventions；
- 某类任务的完整流程；
- 高风险命令禁令；
- 所有验证要求；
- 审批规则；
- 历史事故；
- 领域知识；
- 输出格式。

这会形成两个相反问题：

1. **规则太多**：所有任务都读取和执行不相关内容，token、时间与重复验证上升。
2. **边界太软**：即使写了“绝不修改某目录”，它仍只是自然语言建议，不能保证动作不可达。

解决办法不是单纯精简文本，而是把每类规则迁移到能直接控制其目标变量的层。

## Control Stack

| Layer | 解决的问题 | 何时加载/执行 | 能否硬性阻止动作 | 典型内容 |
|---|---|---|---|---|
| Persistent Context | 每次任务都需要知道什么 | session start | 否 | commands、architecture、常见错误 |
| Conditional Skill | 某类任务需要什么流程/政策 | task trigger | 否 | security review、experiment audit |
| Deterministic Hook | 哪些可形式化 invariant 必须成立 | matching action/event | 是，若不可绕过 | protected paths、lint、secret check |
| Tool Permission | Agent 可以调用哪些 capability | tool dispatch | 是 | read/write/shell/network/deploy |
| Runtime Sandbox | 调用后能影响哪些资源 | process/runtime | 是 | filesystem、network、credentials |
| Agent Identity | 动作以谁的授权和审计主体发生 | every external action | 是 | service account、repo role、environment role |
| Approval Gate | 谁能允许高风险状态转移 | stage boundary | 是 | merge、release、exception |

## Persistent Context

### What belongs

- build/test/lint commands；
- 不读代码很难立即知道的 architecture boundary；
- 跨大多数任务都成立的 conventions；
- 高概率重复、且已有两次以上证据的错误；
- Skill、script、runbook 的路由入口；
- source-of-truth 和安全总原则。

### What does not belong

- 只用于某一种任务的 50 步检查表；
- 可由脚本直接验证的细节；
- 完整历史事故叙事；
- 临时 experiment plan；
- 某个具体 bug 的调试日志；
- 低频 API 文档全文；
- 每次都要求重跑的重型评估；
- 能由权限系统表达的动作禁令。

### Quality rule

Persistent context 的目标是提高 **initialization quality per token**，不是最大化覆盖。

一个实用维护规则：

```text
Add:
  repeated high-cost mistake
  + broadly applicable
  + cannot be cheaply discovered

Remove or route elsewhere:
  stale
  low-frequency
  task-specific
  deterministic
  duplicated
```

## Conditional Skills

Skill 适合 institutional knowledge：

- 安全 API review；
- 数据库 migration；
- research comparison；
- benchmark release；
- incident response；
- accessibility check；
- experiment preregistration。

Skill 的触发条件必须清楚，输出和停止条件必须可检查。它最大的价值是 **selective activation**：只有相关任务支付上下文和执行成本。

但 Skill 仍是 advisory control。常见失败包括：

- 没触发；
- 触发但被忽略；
- 与 official policy 漂移；
- 互相冲突；
- 内容过长，重新制造全局 context bloat。

因此至少需要：

- policy owner；
- source of truth；
- trigger eval；
- version control；
- policy change → Skill change 的 latency metric；
- 对强规则配置对应 Hook/reviewer。

## Deterministic Hooks

Hooks 适合可明确写成 predicate 的规则：

```text
before(action):
    if violates_invariant(action):
        BLOCK
    elif requires_named_approval(action):
        ASK
    else:
        ALLOW
```

### Good hook candidates

- 修改 frozen/generated path；
- secret pattern 进入 diff；
- formatter/lint 对 changed file 失败；
- 生产部署缺少 ticket/approval；
- fix task 修改 test oracle；
- dependency version 被非 owner 修改；
- artifact revision stale；
- shell command 命中 destructive pattern；
- network destination 不在 allowlist。

### Bad hook candidates

- “确认架构优雅”；
- “判断实验是否有科研价值”；
- “检查所有潜在 bug”；
- 每次 edit 都运行完整 integration suite；
- 需要十分钟且经常误报的扫描。

Hooks 应快、scope 小、可解释。重检查放在 task/commit/PR gate。

### Governance

Non-negotiable hook 不能只存在于个人可修改配置；应由 managed settings、CI 或平台层持有。Hook 也要有 unit test、negative test、bypass audit 和版本 owner。

## Tool Permissions

Tool schema 决定 Agent 理论上可以请求什么。不要给所有 Agent 一个“万能 shell + 全网 + prod credential”组合。

按角色拆分：

| Agent | Read | Write | Shell | Network | Merge | Deploy |
|---|---:|---:|---:|---:|---:|---:|
| Planner | ✓ | artifact only | limited | docs only | ✗ | ✗ |
| Coder | ✓ | worktree | build/test | allowlisted | ✗ | ✗ |
| Verifier | ✓ | report only | run/read | usually none | ✗ | ✗ |
| Reviewer | ✓ | findings only | analysis tools | allowlisted | ✗ | ✗ |
| Release Agent | release artifact | pipeline state | runbook only | target APIs | gated | gated |
| Monitor Agent | logs/metrics | docs/ticket | diagnosis only | monitored | ✗ | ✗ |

“Verifier 不允许修复”不是洁癖，而是保持 verdict 与 intervention 分离。如果 verifier 自动改完再说通过，原始失败可能被隐藏。

## Runtime Sandbox

Permission 是逻辑层；sandbox 是执行层。即使工具说只允许读某目录，实际 process 若能访问主机 credential 或任意网络，边界仍不可信。

Sandbox 重点限制：

- filesystem mount；
- process capabilities；
- environment secrets；
- network egress；
- package installation；
- persistent state；
- production endpoints；
- inter-process communication；
- clipboard/host integration。

Anthropic 的 remote VM + egress allowlist 案例表明，面对 prompt injection，更重要的是限制外泄路径，而不是只要求模型识别所有恶意文本。

## Agent Identity

所有外部动作需要 attribution：

```text
actor_identity
triggering_human
session/run
tool/action
target
decision
result
timestamp
```

Agent 不应借用触发者的全部身份。独立 identity 能使：

- permission 最小化；
- logs 区分 Agent 与人；
- revoke 更清晰；
- rate/risk policy 可按 Agent 配置；
- separation of duties 可执行。

### Composite authority

权限审计不能只看单个节点，必须看 reachable graph：

```text
Agent A → Slack → Agent B → Git → CI → Deploy API
```

A 没有 deploy 权限，不代表 A 无法影响 deploy。需要分析：

- 可联系对象；
- 委托是否会被另一 Agent 当成授权；
- 跨 channel 消息是否可伪造；
- tool output 是否携带 provenance；
- downstream Agent 是否验证 requester identity 和 intent artifact；
- 最终 gate 是否绑定 named approver。

## Mapping a Bloated AGENTS File

迁移表：

| 当前内容 | 目标位置 |
|---|---|
| 项目目标与不可变语义 contract | `AGENTS.md` |
| 常用 build/test commands | `AGENTS.md` |
| “做 research comparison 时如何工作” | compare Skill |
| “发布 benchmark 前执行哪些步骤” | release Skill |
| shape、schema、format、secret 检查 | scripts + Hooks |
| 全量 integration/semantic audit | explicit CI/gate，不是每次 edit |
| 禁止写 source repo | filesystem/tool permission |
| 禁止 deploy | identity + deploy permission |
| 生产 exception | named human gate |
| 过去出现过的真实 failure | eval case；必要时在 context 留一行路由 |
| 一次任务的具体范围和验证 | `plan.md` |
| 工具输出和结果 | evidence record |

## Failure Modes

### Prompt-as-firewall

把“绝不执行 X”写得非常醒目，但 Agent 仍具有执行 X 的工具和 credential。修复：移除 capability 或加 managed gate。

### Context accumulation

每次事故都追加一段规则，从不删除。修复：事故先变成 eval/hook/skill；只有高频初始化知识留在 persistent context。

### Silent Skill failure

团队以为 policy 已自动应用，但 Skill 没触发。修复：trigger eval + PR finding metric。

### Hook explosion

每个动作运行大量检查，导致 Agent 更慢、重复输出和 token 消耗。修复：per-edit 只做 fast local invariant；重检查移到阶段 gate。

### Shared super-identity

多个 Agent 使用同一高权限 token，无法区分行为或实施 separation。修复：role-specific identity、scoped tokens、short lifetime。

### Permission edge not modeled

单个 Agent 看似安全，但可通过其他 Agent、chat 或 CI 间接扩大权限。修复：graph-level threat model。

## Focused Principles

### Put each rule where it can control the right variable

知识规则影响选择概率；Hook 影响 action legality；sandbox 影响 blast radius；identity 影响 authority；test 影响 evidence；gate 影响 transition。错层实现会产生“看起来有规则、实际上没控制”的假安全。

### Minimize always-on context, not institutional knowledge

目标不是删除知识，而是把知识从全局注入改为按需可发现、可触发、可验证。

### Least privilege is insufficient without least delegation

限制直接权限之外，还要限制 Agent 能向谁委托、委托携带什么授权、下游怎样验证来源。

## Transfer Checklist

对每条现有 Agent 规则标记：

```text
K = knowledge
P = conditional procedure
I = deterministic invariant
C = capability boundary
A = approval decision
E = evaluation/regression
```

然后迁移到对应层。若一条规则同时属于多个类别，拆为多个实现，而不是保留一段包罗万象的 prose。

## Evidence Map

- `source:ai-native-sdlc-playbook` — short `CLAUDE.md`、Skills、advisory vs deterministic Hooks、managed settings、sandbox 与 approval gates。
- `source:anthropic-secure-ai-sdlc` — remote VM、egress allowlist、single-purpose identity、cross-Agent communication 与 loop security。

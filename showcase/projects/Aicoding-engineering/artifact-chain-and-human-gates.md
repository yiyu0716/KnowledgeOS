---
type: project-doc
projects:
  - "[[Aicoding-engineering]]"
domains:
  - software-engineering
  - ai-engineering
topics:
  - artifacts
  - workflow-state
  - human-gates
  - auditability
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

# Artifact Chain and Human Gates

## Scope

本篇只回答一个问题：

> 在长程、多 Agent、跨角色的软件交付中，怎样让状态持续存在，同时让责任集中在少数明确的判断点？

## Core Problem

聊天记录不适合作为唯一状态载体。它通常包含：

- 未采纳的探索；
- 过期假设；
- 大量工具输出；
- 隐式决策；
- 无法快速定位的批准；
- 模型更换后难以继承的上下文。

如果后续 Agent 只能读取完整轨迹，它必须重新判断哪些内容仍有效；若只依赖摘要，又可能丢失关键约束。Artifact chain 的作用是把已确认的状态从轨迹中提炼出来。

## Concrete Artifact Chain

| Artifact | 必须回答 | 主要作者 | 主要批准者 | 下游读取者 |
|---|---|---|---|---|
| `intent.md` | 为什么做、为谁做、什么结果算成功、什么不做 | Product owner + Agent | Problem owner | Design Agent |
| `spec.md` | 系统应如何满足 intent、约束和 policy | Design Agent | Tech lead / policy owner | Planning Agent |
| `plan.md` | 修改什么、顺序、风险、验证方式、回滚 | Coding Agent | Engineer / architect | Execution Agent |
| diff + tests | 实际做了什么、行为怎样改变 | Coding Agent | Review pipeline | Test/Review Agent |
| evidence record | 跑了什么、看到了什么、是否符合 plan | Generator + verifier | Code owner | Reviewers |
| PR + findings | 哪些风险已检查、如何修复、谁批准 | Review agents + human | Code owner | Release pipeline |
| release record | 哪个版本进入哪个环境、授权与回滚状态 | Release pipeline | Named release owner | Operations |
| incident record | 发生了什么、影响、根因、修复和学习 | Monitor/response Agent + owner | Incident owner | New Plan cycle |
| new `intent.md` / eval | 未来必须改变什么 | Agent + owning team | Product/security owner | Full loop |

Artifact 深度应按 risk 调整。一个小型局部修复可以把 intent/spec/plan 合并成单一 change record；高风险 migration 则需要分别审查。

## Artifact Quality Contract

每个 artifact 至少需要：

```text
Identity
Owner
Status
Inputs
Decision
Evidence
Open questions
Downstream trigger
Freshness / revision
```

### Identity

必须能稳定引用。文件名、ticket ID、commit SHA 或 PR number 都可以，关键是下游不依赖模糊的“上次那个方案”。

### Owner

Agent 可以生成 artifact，但必须有负责其语义正确性的角色。Owner 不是每行作者，而是当内容错误时负责纠正的人或团队。

### Status

至少区分：

```text
draft
reviewed
approved
superseded
blocked
```

未经批准的 draft 不应悄悄成为执行输入。

### Inputs

记录使用了哪些上游 artifact 和版本。否则 intent 更新后，旧 plan 仍可能继续执行。

### Decision

Artifact 不应只是信息堆积。必须明确当前决定、非目标和被拒绝的 alternative。

### Evidence

所有“已完成”“已通过”“无风险”都应绑定具体工具输出、测试结果或 reviewer finding，而不是自述。

### Downstream trigger

明确什么条件允许进入下一阶段，失败时回到哪里：

```text
approved spec
→ planning

failed verification
→ implementation

unresolved high-risk finding
→ human escalation

production incident
→ new intent + regression eval
```

### Freshness

下游开始前验证上游 artifact 是否仍是 active revision。否则 Agent 可能正确执行一个已被替换的计划。

## Gates as State-transition Control

Gate 不是一个模糊的“需要 review”，而是：

```text
Given:
  current state
  proposed next state
  evidence
  risk tier
  actor identity

Return:
  ALLOW
  BLOCK
  ESCALATE
```

### Deterministic gate

适合可机械判断的规则：

- protected path 被修改；
- tests 未通过；
- secret 出现在 diff；
- migration 没有关联 ticket；
- required artifact 缺失；
- artifact hash 已 stale；
- production credential 不应出现在当前 environment。

其优点是稳定、快速、可批量执行；缺点是只能表达已形式化的 invariant。

### Agentic gate

适合需要语义判断的任务：

- spec 是否真正满足 intent；
- finding 是否有可复现 proof；
- change 是否偏离 plan；
- incident diagnosis 是否解释 observed evidence；
- risk description 是否遗漏重要攻击路径。

Agentic gate 必须有明确 scope、输入和输出 schema，并接受 eval。

### Human gate

保留给：

- ambiguous intent；
- architecture trade-off；
- risk acceptance；
- regulated decision；
- irreversible action；
- production release；
- exception approval；
- model/reviewer governance。

Human gate 的价值是责任与判断，不是重做所有机械检查。因此进入 human gate 前应附足够 evidence。

## Human Attention Budget

人类 attention 是有限资源。可以用下式理解 gate 成本：

```text
Expected human load
= change volume
× escalation rate
× average review effort
```

AI 提高 change volume 后，若 escalation rate 和 review effort 不变，人类仍会成为瓶颈。优化方向包括：

- 让 deterministic checks 在进入人类队列前消除机械失败；
- 让 Agent finding 携带 proof；
- 用 risk tier 降低低风险 change 的 escalation rate；
- 让 artifact 只呈现 active decision，而不是完整轨迹；
- 将 exception 送给正确 owner，而不是泛化审批委员会。

## Source-of-truth Patterns

### Pattern A — Git is authoritative

每个 artifact 直接提交到 repo。优点是统一 versioning、review 与 timestamps；缺点是非工程角色的 workflow 可能不自然。

### Pattern B — Existing system is authoritative

Jira、ServiceNow、requirements system 等保存正式记录，Markdown 是 Agent working copy。Agent 必须在同一会话内读写回 authoritative system。

### Pattern C — Linked records

Git artifact 保存 legacy record ID，legacy system 保存 commit SHA。适合迁移期，但冲突和 stale copy 必须有裁决规则。

最低要求：

```text
One owner of truth per artifact type
or
explicit bidirectional linkage + conflict rule
```

## Failure Modes

### Artifact theater

文件存在，但内容只是模板填充，不能改变下游行为。修复方式是把 gate condition 和 downstream trigger 与内容绑定。

### Approval laundering

人点击批准，但没有看到 risk/evidence，或默认所有请求都通过。需要记录批准依据、异常率和 post-approval incident。

### Stale-plan execution

Agent 在 intent/spec 已改变后继续执行旧 plan。需要 input revision/hash check。

### Hidden side channel

正式 artifact 说“不部署”，Agent 却通过 chat、另一个 Agent 或外部 tool 形成非正式部署路径。需要把跨 Agent communication 纳入权限图和 telemetry。

### Over-artifactization

低风险任务也强制产生多份长文档，导致工程师绕过流程。需要 risk-scaled artifact depth。

### Gate on every action

人类 approval prompt 出现在每次 edit/command，使并行 Agent 全部停在 critical path。应把机械规则交给 deterministic hook，把人类判断集中到阶段性 gate。

## Focused Principles

### Artifact depth follows uncertainty and irreversibility

不按任务名称决定文档量，而按：

```text
uncertainty
× coordination breadth
× blast radius
× irreversibility
```

### A gate without evidence is ceremony

Gate 输入必须包含满足该阶段目标的 proof；否则批准只是把未知风险转移给审批人。

### An artifact without a downstream consumer is likely waste

每个字段都应对应下游 decision、check 或 audit need。没人读取、不会改变行为的字段应删减。

## Transfer Checklist

引入一个新 artifact 前，回答：

1. 它替代了哪段隐式会话状态？
2. 谁拥有它？
3. 哪个系统是 source of truth？
4. 哪个下一阶段会读取它？
5. 什么状态允许继续？
6. 什么证据支持继续？
7. 它过期时怎样被发现？
8. 低风险任务能否使用简化版本？
9. 谁能批准 exception？
10. 这次失败会怎样改变未来 artifact 或 eval？

## Evidence Map

- `source:ai-native-sdlc-playbook` — committed artifact chain、source-of-truth patterns、Plan/Design/Build/Test/Deploy/Maintain gates。
- `source:anthropic-secure-ai-sdlc` — identity、separation、monitoring agent 与跨 Agent communication 所揭示的 gate 边界。

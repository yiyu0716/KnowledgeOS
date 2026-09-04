---
type: project
parents:
  - "[[KnowledgeOS]]"
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

# Agent

> 截至 2026-08-31，用统一问题模型比较 OpenCode、Codex、Grok Build、Pi、OpenClaw、Hermes Agent 与 DeepSeek Harness。这里比较的是 Agent 系统设计和适用层级，不把不同模型、预算与任务下的公开成绩混成一个“总榜”。

## Overview

这七个项目覆盖三种相互重叠、但主目标不同的系统层级：

```text
Coding Product       → OpenCode / Codex / Grok Build
Composable Harness   → Pi / DeepSeek Harness
Persistent Agent     → OpenClaw / Hermes Agent
```

它们的关键差异并不只是“能否调用 Bash”，而是由谁拥有 Provider、Context、Tool Policy、Sandbox、Session、Memory、Parallel Workspace 与 Audit Trail。选择错误的层级，往往比少一个功能更昂贵。

## Task

本项目回答四个问题：

1. 每个 Agent 的真实 Thesis、What、Why、Mechanism 与 Boundary 是什么；
2. 哪些设计已经收敛，哪些只是不同路线；
3. 如何在编码执行、Harness 研究、长期 Gateway 与自学习之间选型；
4. 如何让 Agent Memory / Skill 与 KnowledgeOS 的 verified knowledge 协作，而不是相互污染。

## Evaluation

没有采用单一 leaderboard 排名。当前 Evidence Set 不包含同模型、同任务、同上下文、同工具权限、同测试时计算预算的七方受控实验，因此只按下列工程轴比较：

- task fit 与主系统层级；
- model / provider portability；
- context 与 subagent decomposition；
- tool semantics、permission 与 sandbox；
- session、memory、replay 与 rollback；
- parallel workspace isolation；
- extension surface 与 plugin trust boundary；
- maturity、default behavior 与明确限制。

## Challenges

第一，产品边界不同。Codex 与 OpenCode 主要承担软件工程执行，OpenClaw 与 Hermes 主要解决长期存在和跨渠道状态，DeepSeek Harness 更强调 Runtime 组合与轨迹研究。

第二，名字相同不代表机制相同。`Skills` 可能是按需说明文档，也可能由 Agent 自动改写；`Sandbox` 可能限制 filesystem，也可能同时限制 child network；`Session` 可能是对话文件、树状历史、SQLite 记录或 typed event log。

第三，默认值决定真实风险。permission prompt、OS sandbox、container、worktree 与 Gateway identity 是不同边界；“支持”某能力不代表它默认开启。

## Solution Landscape

| Solution | 主抽象 | 最强辨识度 | 主要边界 |
|---|---|---|---|
| OpenCode | 多模型 Coding Workbench | Provider、客户端、primary/subagent 与权限统一 | Build 默认 full-tool access；当前证据不把 permission 等同 OS sandbox |
| Codex | 受控 Coding Executor + App Server | OS sandbox、approval、SDK/App Server 与高完成度执行 | 不是全栈开源；subagent 增加 token 与协调成本 |
| Grok Build | 长程 Terminal Operator | Worktree、background task、monitor 与并行操作 | Sandbox 默认关闭；凭据与跨平台网络限制需额外治理 |
| Pi | Minimal Extensible Harness | 小内核、Extensions、RPC/SDK 与 session tree | 核心不替使用者提供完整 permission / isolation policy |
| OpenClaw | Self-hosted Gateway / Agent Control Plane | 多渠道、节点、routing、runtime registry 与长期状态 | Gateway 仍在 host；trusted-operator default 不等于多租户隔离 |
| Hermes Agent | Learning-oriented Persistent Agent | bounded memory、Skills、自改进 review 与 Profiles | 自动写入需要审批与回滚；Profile 不是 sandbox |
| DeepSeek Harness | Plugin-composed Event-sourced Runtime | Everything-as-plugin、typed event log 与 replay | Developer Preview；sandbox vocabulary 主要覆盖 file effects |

## Compressed Conclusions

1. **先按系统层级和主状态选型。** 需要 Coding Product、Composable Harness 还是 Persistent Agent，应在比较 feature checklist 之前确定。
2. **把 Permission、Sandbox、Workspace Isolation、Audit 分开。** 它们分别解决是否执行、影响范围、并行冲突和事后重建，不能互相替代。
3. **Memory / Skill 是候选经验，不是自动成立的知识。** 长期写入应经过来源绑定、边界检查、回归与可回滚 Promotion。

对当前工具链，最稳健的主干是：`Codex` 负责受控执行，`Pi` 负责 Harness 实验，`OpenCode` 负责多模型横向验证，`KnowledgeOS` 负责长期可信知识。Grok Build、OpenClaw、Hermes 与 DeepSeek Harness 分别在原生并行、控制平面、学习闭环和 Runtime 研究成为核心问题时引入。

## Knowledge Map

- [[projects/Agent/solutions|Solutions]] — 七个方案的具体 Reality：Thesis、What、Why、Mechanism、Boundary。
- [[projects/Agent/solution-space|Solution Space]] — Convergence、Alternative Routes、Negative Evidence、Open Questions、Decision Guide 与 Transfer。
- [[projects/Agent/security-and-governance|Security and Governance]] — Permission、Sandbox、Identity、Secrets、Workspace、Memory、Rollback 与 Audit 的专门比较。
- [[learning/Agent Learning|Agent Learning]] — 系统层级、控制语义与长期状态的单一项目 Learning。

## Evidence Map

- `source:agent-opencode-official` — OpenCode repository、Intro、Agents、Permissions、Providers。
- `source:agent-codex-official` — Codex repository、Open Source、Security、App Server、Subagents、Configuration。
- `source:agent-grok-build-official` — Grok Build repository、Permissions、Sandbox、Worktrees、Tasks、Sessions。
- `source:agent-pi-official` — Pi repository、project site、documentation、providers、security boundary。
- `source:agent-openclaw-official` — OpenClaw repository、Gateway、runtime、memory、security、sandboxing。
- `source:agent-hermes-official` — Hermes repository、memory、skills、profiles、security、checkpoints。
- `source:agent-deepseek-harness-official` — DeepSeek Harness repository、architecture、sessions、sandbox、permission pipeline。

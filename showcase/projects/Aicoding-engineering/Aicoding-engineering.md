---
type: project
parents:
  - "[[KnowledgeOS]]"
domains:
  - software-engineering
  - ai-engineering
  - security-engineering
topics:
  - ai-native-sdlc
  - agentic-coding
  - software-governance
  - verification
  - agent-security
source_refs:
  - source:ai-native-sdlc-playbook
  - source:anthropic-secure-ai-sdlc
  - source:datawhale-ai-native-sdlc-cn
origin: codex
status: active
created: 2026-08-30
updated: 2026-08-30
---

# Aicoding-engineering

## Overview

AI coding engineering 研究的是：当 Agent 已能快速生成大量代码后，怎样把需求、设计、实现、验证、审批、部署与线上反馈重构为一条可版本化、可验证、可审计的交付循环。

它不是“选择更强模型”或“写更长 Prompt”的同义词。核心对象是整个 socio-technical loop：

```text
Intent
→ Specification
→ Plan
→ Execution
→ Evidence
→ Review
→ Approval
→ Deployment
→ Monitoring
→ New Intent
```

## Task

构造一个工程系统，使 Agent 能够提高实现吞吐，同时满足四个条件：

1. **任务状态不只存在于会话里**：关键决策由持久 artifact 保存。
2. **不可接受动作不能只靠自觉避免**：强规则进入 deterministic controls。
3. **“完成”必须有可复现证据**：测试、构建、运行结果和 independent verification 可追溯。
4. **责任边界没有因自动化消失**：高风险状态转移仍有明确的人类 owner、身份和审批记录。

## Evaluation

不能只看 generated lines 或完成任务数。至少同时观察：

| 层面 | 核心问题 | 代表指标 |
|---|---|---|
| Flow | Build 加速后，端到端 lead time 是否真的下降？ | intent-to-production time、gate wait time、review time |
| Correctness | Agent 输出是否在进入人工审查前已有可靠证据？ | first-pass CI、task eval pass rate、rework rate |
| Safety | 不可接受动作是否被系统边界阻止？ | blocked actions、escaped violations、credential exposure |
| Governance | 谁要求、生成、审查和批准是否可追溯？ | identity attribution、approval coverage、audit completeness |
| Learning | 事故和重复错误是否改变未来行为？ | repeat-error rate、incident-to-eval latency、regression recurrence |
| Economics | 验证和审查成本是否随风险合理分配？ | inference cost per merged change、reviewer cost by risk tier |

## Challenges

### Bottleneck migration

Agent 把 Build 压缩后，需求澄清、review、security、release 与 exception handling 会成为新的 critical path。继续优化代码生成可能只会扩大队列。

### Non-deterministic execution

Agent 会受 context、model、tool result、retrieval 和环境状态影响。相同任务不保证产生相同轨迹，因此配置本身也需要 eval。

### Composite authority

单个 Agent 权限很小，不代表系统整体安全。Agent 可能通过工具、CI、其他 Agent 或人类 channel 组合出更大的实际权限。

### Verification-induced drag

验证太弱会放大风险；验证无差别过重则会吞掉 AI 带来的吞吐收益。需要按 risk、blast radius 与 reversibility 配置验证预算。

## Solution Landscape

- [[projects/Aicoding-engineering/solutions|Solutions]]：重建 Anthropic Playbook、安全实践与中文解读各自解决的问题和具体方法。
- [[projects/Aicoding-engineering/solution-space|Solution Space]]：综合它们共同指向的控制架构、替代路线、边界与决策方法。
- [[projects/Aicoding-engineering/artifact-chain-and-human-gates|Artifact Chain and Human Gates]]：解释 artifact 如何承载状态，gate 如何承载责任。
- [[projects/Aicoding-engineering/context-controls-and-permission-boundaries|Context Controls and Permission Boundaries]]：区分 persistent context、Skills、Hooks、permissions、sandbox、identity。
- [[projects/Aicoding-engineering/verification-review-and-evals|Verification, Review and Evals]]：设计 feedback loop、fresh verifier、multi-agent review 与 Agent Evals。
- [[projects/Aicoding-engineering/adoption-roadmap-and-metrics|Adoption Roadmap and Metrics]]：从当前人工流程逐步迁移到 AI-native loop。
- `templates/`：可直接复制的 intent、spec、plan、review、risk tier、eval 与 incident 模板。

## Top 3 Project Principles

### 1. Artifacts carry state; gates carry accountability

会话可以结束，Agent 可以替换，但 `intent/spec/plan/diff/review/incident` 必须持续承载状态。人和确定性系统只在明确 gate 上批准或阻断下一次状态转移。

**Use When**：任务跨多个阶段、多个 Agent 或多个工作日。  
**Boundary**：artifact 若没有唯一 source of truth、owner 和 freshness 规则，只会制造另一层文档漂移。

### 2. Advisory context shapes behavior; deterministic controls bound behavior

`AGENTS.md`、`CLAUDE.md` 和 Skills 负责提供知识；Hooks、permissions、sandbox、identity 和 branch protection 负责限制动作。两者不可互相替代。

**Use When**：一部分规则是“最好遵守”，另一部分规则是“一旦违反就不可接受”。  
**Boundary**：deterministic control 也需要版本管理、测试和绕过路径审计，否则只是表面边界。

### 3. Verify the loop, not only the final diff

除了测试代码，还要验证 Agent 配置、reviewer、工具调用、权限路径、跨 Agent 委托和事故反馈。最终正确 diff 不能证明产生它的 loop 是可靠的。

**Use When**：模型、Prompt、Skill、Hook 或工具链持续演化。  
**Boundary**：eval 只覆盖它包含的任务；高 pass rate 不代表未建模风险不存在。

## Knowledge Map

```text
[[projects/Aicoding-engineering/solutions|Solutions]]
   ↓ concrete reality
[[projects/Aicoding-engineering/solution-space|Solution Space]]
   ├── [[projects/Aicoding-engineering/artifact-chain-and-human-gates|Artifact Chain and Human Gates]]
   ├── [[projects/Aicoding-engineering/context-controls-and-permission-boundaries|Context Controls and Permission Boundaries]]
   ├── [[projects/Aicoding-engineering/verification-review-and-evals|Verification, Review and Evals]]
   └── [[projects/Aicoding-engineering/adoption-roadmap-and-metrics|Adoption Roadmap and Metrics]]
          ↓ transfer
[[learning/Aicoding-engineering Learning|Aicoding-engineering Learning]]
```

## Evidence Map

- `source:ai-native-sdlc-playbook` — 生命周期流程、artifact chain、context/control、verification、deployment 与 maintenance loop。
- `source:anthropic-secure-ai-sdlc` — Anthropic 内部吞吐背景、安全架构、remote containment、review、identity、monitoring 与 governance。
- `source:datawhale-ai-native-sdlc-cn` — 中文综合叙事及其传播压缩；不作为独立机制验证。

# KnowledgeOS

> **KnowledgeOS turns real projects into reusable knowledge: from evidence, to mechanisms, to principles, to better decisions on the next problem.**
>
> **KnowledgeOS 将真实项目转化为可复用知识：从证据出发，理解机制，提炼原则，再把过去的经验用于下一个问题。**

KnowledgeOS is a lightweight, evidence-grounded, Markdown-first personal knowledge system assisted by AI agents. It is designed for learning from real code, papers, competitions, and experiments, not merely collecting summaries.

KnowledgeOS 是一个轻量、以证据为基础、以 Markdown 为核心、由 AI Agent 协助维护的个人长期知识系统。它关注的不是保存更多摘要，而是从真实代码、论文、比赛和实验中提炼可复用的解决问题能力。

## Why / 为什么

Ordinary note systems often stop at:

```text
Source -> Summary -> Notes
```

KnowledgeOS continues the chain:

```text
Evidence -> Solution -> Mechanism -> Synthesis -> Learning -> Transfer -> New Project
```

普通笔记库通常停留在“资料 → 摘要 → 笔记”。KnowledgeOS 继续追问：这个方案解决了什么问题？为什么这样设计？背后的机制是什么？什么条件下可以迁移？

The goal is a compounding problem-solving memory: each new project can strengthen, qualify, or challenge existing Learning instead of creating an isolated summary.

目标是形成不断增强的问题解决记忆：新项目可以补强、修正或反驳已有 Learning，而不是为每个项目创建一套孤立笔记。

## Knowledge Model / 知识模型

```text
Evidence
   ↓
Project
   ↓
Solution
   ↓
Synthesis
   ↓
Learning
```

- **Evidence** — repositories, commits, papers, writeups, experiments, and benchmarks.
- **Project** — what the task is, why it is difficult, and how it is evaluated.
- **Solution** — how one real approach addresses the problem.
- **Synthesis** — what multiple approaches reveal about the solution space.
- **Learning** — a reusable mechanism with a problem signature, use conditions, and boundaries.

- **Evidence**：仓库、commit、论文、writeup、实验和 benchmark。
- **Project**：任务是什么、难在哪里、如何评估。
- **Solution**：一个真实方案具体如何解决问题。
- **Synthesis**：多个方案放在一起后，solution space 呈现什么规律。
- **Learning**：带有问题签名、适用条件和边界的可复用机制。

## Two Views, One Knowledge Base / 两种视图，一套知识库

The **Project Map** is a minimal navigation view. It shows only `type: project` pages and their `parents` hierarchy.

**Project Map** 是极简项目导航图，只显示 `type: project` 页面以及由 `parents` 表达的项目层级。

The **Knowledge Graph** retains the complete internal graph: Projects, Solutions, Synthesis, Learning, Evidence references, `projects`, `derived_from`, `source_refs`, `wikilinks`, and `parents`.

**Knowledge Graph** 保留完整内部关系，用于查询、推理、Learning promotion、trace 和维护。两种视图来自同一套 Markdown，不是两套数据库。

## Human-first, Evidence-grounded / 人类优先，证据支撑

Human-facing Markdown prioritizes `What`, `Why`, `Mechanism`, principles, and transfer. A concise Evidence Map helps orientation.

面向人的 Markdown 优先解释 `What`、`Why`、`Mechanism`、核心原则和迁移条件，并在文末提供简洁的 Evidence Map。

Detailed repository, commit, path, symbol, line, confidence, and verification state live in structured provenance and derived indexes. When verification is needed, an Agent can trace the claim back to its source.

详细 repository、commit、path、symbol、line、confidence 和 verification state 由结构化 provenance 与派生索引负责。需要核验时，Agent 可以沿 provenance 追溯到底层 Evidence。

## Workflow / 工作流程

### One solution / 单个方案

```text
Evidence
→ What
→ Why
→ Mechanism
→ Candidate Principles
→ Top 3 Project Principles
→ Transfer
→ Learning Promotion
```

### Multiple solutions / 多个方案

```text
Solutions
→ Normalized Comparison
→ Difference
→ Mechanisms
→ Solution Space
→ Top 3 Project Principles
→ Transfer
→ Learning Promotion
```

Project Top 3 Principles summarize what matters most for that project. They do not automatically create three global Learning notes. Existing Learning is updated when a mechanism recurs; a new Learning requires real evidence, clear boundaries, and cross-project value.

Project Top 3 代表该项目最值得记住的三条原则，但不会强制创建三篇全局 Learning。机制重复出现时更新已有 Learning；只有具备真实证据、明确边界和跨项目价值时才创建新的 Learning。

## Four Agent Workflows / 四个 Agent 工作流

- `search` — retrieve prior Learning and related evidence / 找回已有 Learning 与相关证据。
- `summarize` — reconstruct one real Solution / 重建一个真实方案。
- `compare` — compare multiple Solutions and synthesize the solution space / 比较多个方案并综合 solution space。
- `maintain` — audit links, provenance, source drift, and promotion debt / 检查关系、provenance、source drift 和 promotion debt。

The workflows are reasoning protocols, not separate data models. Deterministic operations are delegated to local tools.

这些工作流是 reasoning protocol，不是四套数据模型。Graph、BM25、provenance、lint 和 source drift 等确定性工作由本地工具完成。

## Architecture / 架构

```text
                 Agent Skills
        search / summarize / compare / maintain
                           ↓
              Human Knowledge Layer
       Markdown + Properties + Wikilinks + Learning
                           ↓
             Deterministic Projections
        BM25 / Graph / Project Map / Provenance / Lint
                           ↓
                    Evidence Layer
       Git repositories / Papers / Writeups / Experiments
```

The repository is intentionally dependency-light. Markdown is the durable, human-auditable artifact; generated JSON indexes under `.knowledgeos/` are rebuildable projections.

本项目保持依赖简单。Markdown 是持久且可人工审计的事实表达；`.knowledgeos/` 下的 JSON 只是可重建的派生投影。

## Usage / 使用

```bash
python3 tools/knowledgeos.py search "your concept"
python3 tools/knowledgeos.py graph
python3 tools/knowledgeos.py projects
python3 tools/knowledgeos.py trace "Learning name"
python3 tools/knowledgeos.py lint
python3 tools/knowledgeos.py maintain
python3 tools/knowledgeos.py rebuild
```

Configure Human-facing generation in `knowledge-config.yaml`:

```yaml
output_style: zh_en_terms
```

Supported styles are `english` and `zh_en_terms`. The setting changes presentation only, never knowledge semantics, graph relations, or provenance.

## Design Principles / 设计原则

```text
Simple by default.
Evidence-grounded.
Human-readable.
Many-to-many.
Traceable.
Rebuildable.
Composable.
```

简单优先、真实证据、多对多关系、正文为人服务、证据随时可追溯、索引全部可重建、功能保持可组合。

## Public Repository Boundary / 公开仓库边界

This repository contains the reusable KnowledgeOS design, deterministic tooling, schemas, Skills, and tests. Personal vault notes, raw source collections, cloned repositories, derived indexes, and credentials are intentionally excluded from the public repository.

本仓库只公开可复用的 KnowledgeOS 设计、确定性工具、schema、Skills 和测试。个人 vault 笔记、原始资料、克隆仓库、派生索引和凭证会被明确排除。

## License

No license has been selected yet.

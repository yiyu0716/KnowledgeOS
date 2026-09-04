---
type: project-doc
projects:
  - "[[Aicoding-engineering]]"
domains:
  - software-engineering
  - ai-engineering
topics:
  - verification
  - code-review
  - agent-evals
  - continuous-integration
  - observability
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

# Verification, Review, and Agent Evals

## Scope

本篇构造从“Agent 认为做完了”到“组织有足够证据允许状态转移”的完整验证体系。

## Core Problem

AI coding 中至少有五种不同正确性：

```text
Execution correctness
  命令是否真正运行、退出码是否成功

Behavioral correctness
  改动是否产生预期行为

Regression correctness
  邻近功能和旧行为是否保持

Intent correctness
  实现是否真正解决 intent/spec

Process correctness
  Agent 是否在正确权限、配置和审查路径中完成
```

单一测试套件通常只覆盖其中一部分。尤其是“测试通过”可能仍然发生在错误目标、被修改的 test oracle、过宽权限或未经批准的路径上。

## Verification Layers

| Layer | 执行时机 | 主要对象 | 失败后谁修复 | 主要证据 |
|---|---|---|---|---|
| Fast deterministic checks | edit/action 后 | syntax、format、protected path、secret | Generator | exit code、changed-file report |
| Task feedback loop | 实现过程中反复 | unit/integration/runtime behavior | Generator | test/build/run output |
| Completion evidence | Generator 准备报告完成时 | plan checklist、actual diff、commands | Generator | evidence record |
| Fresh-context verifier | 完成声明前 | changed flow、neighbor flows、plan alignment | 原 Generator 或人 | independent verdict |
| PR review | merge 前 | logic、security、policy、architecture | Generator/owner | finding + proof + resolution |
| Agent eval suite | config/model/harness 变化时 | Agent 在真实任务上的整体表现 | Platform owner | pass/fail、score、trajectory |
| Release gate | production transition 前 | risk acceptance、rollback、authorization | Named owner | approval record |
| Runtime monitoring | 上线后 | real behavior、security、SLO | Response system | alert、incident、postmortem |
| Incident regression | 修复后长期保留 | 重复失败模式 | Config/code owner | permanent eval/test |

## 1. Fast Deterministic Checks

目标是把反馈延迟压到最小，使 Agent 在仍理解当前 edit 时修复。

适合：

- formatter；
- type check on changed module；
- linter；
- schema validation；
- protected-path rule；
- secret scanning；
- generated-file integrity；
- simple invariant；
- file-size or dependency policy。

要求：

- 通常在秒级；
- 只检查 changed scope；
- 输出可解析；
- 失败说明原因和修复路径；
- 不调用高成本模型；
- 不要求人类介入。

不适合把 full benchmark、全仓库 integration suite 或数十分钟 security scan 放在每次 edit 后。

## 2. Task Feedback Loop

生成 Agent 应有一条最短路径观察实际结果。形式取决于任务：

| Task | Feedback |
|---|---|
| backend logic | unit + integration test |
| API change | contract test + request/response |
| UI | run app + screenshot diff + interaction |
| data pipeline | fixture + schema + statistical invariant |
| RL/training | smoke run + replay/shape/NaN checks |
| infra | plan/dry-run + policy check |
| migration | reversible test environment + data invariant |
| bug fix | failing regression test first |

Feedback loop 是生成过程的一部分，Agent 可以根据结果修改代码。它不是独立审查。

### Proof-carrying completion

任务完成报告至少应包含：

```text
Plan revision:
Changed files/components:
Commands executed:
Exit codes:
Tests passed/failed/skipped:
Observed behavior:
Neighbor flows checked:
Known gaps:
Evidence locations:
```

自然语言“全部通过”不能替代工具结果。

## 3. Fresh-context Verifier

Verifier 应在 Generator 认为完成后启动，并尽量满足：

- 新 context；
- 只读代码；
- 可运行 tests/app；
- 不修改实现；
- 读取 active intent/spec/plan；
- 检查 changed behavior 和最近邻行为；
- 报告 evidence，而非给空泛分数。

### Why read-only

若 verifier 发现失败后直接修改，最终“通过”可能掩盖：

- Generator 原本没完成；
- 哪个假设导致失败；
- 修复是否引入新偏差；
- verifier 是否越过 separation of duties。

更清晰的循环是：

```text
Verifier FAIL
→ evidence returned
→ Generator fixes
→ new verifier run
```

### What fresh context does and does not do

它降低的是 **trajectory-correlated error**。它不能解决：

- shared wrong spec；
- shared model blind spot；
- missing test oracle；
- malicious code hidden from both；
- environment mismatch；
- unverifiable product judgment。

因此 verifier 是一层，不是 ground truth。

## 4. PR Review Architecture

### Reviewer decomposition

避免 mega-agent，把 review 拆为互相独立的 narrow roles：

- intent/spec alignment；
- logic and edge cases；
- security/data flow；
- authorization and permissions；
- migration/rollback；
- test quality；
- performance/cost；
- historical incident patterns。

每个 reviewer 只输出：

```text
finding_id
scope
severity
claim
proof
reproduction
affected artifact
recommended next action
confidence
```

### Proof requirement

没有 proof 的 finding 只能作为 hypothesis，不能自动 block 高成本流程。Proof 可以是：

- concrete execution trace；
- data/control flow；
- failing test；
- reachable permission path；
- policy citation；
- minimal reproduction；
- invariant violation。

### Aggregation

Aggregator 不应简单多数投票。它需要：

- 去重同源 finding；
- 标记 reviewer disagreement；
- 按 severity 和 confidence routing；
- 检查是否有 required risk class 未覆盖；
- 保留原始 proof；
- 将 uncertain/high-impact finding 升级给人。

### Human review

人类重点检查：

- intent 是否正确；
- architecture trade-off；
- reviewer conflict；
- high-severity proof；
- residual risk；
- exception；
- irreversible release。

Human review 质量不能只用“耗时变短”评价，还要结合 escaped defect 和 change failure rate。

## 5. Continuous Agent Evals

代码测试回答“这个实现是否工作”；Agent Eval 回答“当前 Agent configuration 能否稳定完成代表性任务”。

### Eval unit

每个 eval 至少包含：

```text
Task prompt / intent
Repository or fixture state
Allowed tools and permissions
Expected artifact/behavior
Deterministic checks
Semantic rubric
Forbidden actions
Budget
Termination condition
```

### Dataset construction

优先来源：

1. 最近真实任务；
2. 生产 incident；
3. 重复 review finding；
4. 曾经失败的 model/config change；
5. 权限与 prompt injection red-team；
6. 高价值边界任务；
7. 容易被“做少一点”规避的任务。

Playbook 建议从 20–50 个真实任务开始。这个数字是起始规模，不是覆盖充分性的证明。

### Trigger policy

Eval 应在以下变化后运行：

- model；
- system prompt；
- `AGENTS.md` / `CLAUDE.md`；
- Skill；
- Hook；
- tool schema；
- permissions；
- sandbox image；
- reviewer prompt；
- retrieval/index；
- orchestration loop。

高成本 suite 可以分层：

```text
PR smoke evals
nightly representative suite
weekly adversarial suite
release-blocking critical suite
incident-triggered focused suite
```

### Metrics

不要只看 overall pass rate。至少分解：

- task success；
- first-pass success；
- policy compliance；
- forbidden-action rate；
- verification honesty；
- tool efficiency；
- token/time/cost；
- retry count；
- human escalation；
- severity-weighted failures；
- stability across repeated runs；
- regression by task family。

### Anti-gaming

常见 eval gaming：

- 通过少做任务避免错误；
- 修改测试或 fixture；
- 把失败标成 skipped；
- 输出符合格式但行为错误；
- 依赖偶然缓存或外部状态；
- 过度调用昂贵工具直到碰巧成功；
- 在 benchmark task 上特化。

需要检查 completeness、forbidden edits、budget 和 behavior oracle。

## 6. Risk-tiered Verification Budget

建议采用四级参考：

| Tier | Example | Required checks | Human gate |
|---|---|---|---|
| R0 — trivial/reversible | docs、local refactor | fast checks + task feedback | optional sample |
| R1 — bounded product change |普通 feature/bug fix | feedback + verifier + PR reviewers | code owner |
| R2 — sensitive/high blast radius | auth、payments、data migration、infra | full suite + security reviewers + staging + rollback | named lead/security |
| R3 — regulated/irreversible/prod critical | production access、compliance decision | adversarial eval + separation + explicit evidence package | designated accountable owner |

Risk classifier 不能只看 changed lines。还要看 data class、permission, user impact、reversibility、novelty、incident history 和 environment。

## 7. Loop Observability

最终 diff 无法解释所有问题。Telemetry 应覆盖：

- session/run identity；
- triggering human；
- model/config revision；
- loaded context/Skills；
- tool calls；
- permission decisions；
- Hook allow/block/ask；
- network destinations；
- Agent-to-Agent messages；
- artifacts read/written；
- verifier/reviewer findings；
- approvals；
- deployment/rollback；
- cost and latency。

### Observability boundaries

日志本身可能包含 code、PII、secrets 或 prompt-injected data。需要：

- redaction；
- access control；
- retention；
- region/compliance policy；
- integrity protection；
- correlation IDs；
- immutable audit for critical events。

## 8. Incident-to-Eval Loop

一个 incident 只有在改变未来行为时才成为 organizational learning。

```text
Incident
→ observed evidence
→ causal/conditional mechanism
→ correction target
   ├── code
   ├── test
   ├── Skill/context
   ├── Hook/permission
   ├── reviewer
   └── runbook
→ permanent regression
→ owner and retirement rule
```

不要把所有 incident 都追加到 `AGENTS.md`。先判断失败发生在哪一层：

- 缺知识 → context/Skill；
- 规则可形式化 → Hook/test；
- 权限过宽 → permission/sandbox；
- reviewer 漏检 → reviewer eval；
- approval 错误 → gate policy；
- 真实分布未知 → monitoring/eval data。

## Negative Evidence / Trade-offs

- 更多 tests 不等于更接近 intent；错误 oracle 会稳定验证错误目标。
- Reviewer comment 数量增加不等于 precision/recall 提高。
- Eval suite 会随模型进步失去区分度，需要持续更新。
- 低失败率可能来自任务变简单、Agent 少做或 escalation 增加。
- 全量 telemetry 提高可解释性，也提高隐私、成本和攻击面。
- Risk tier 错误会把高风险 change 错路由到轻验证。
- Human gate 若成为 rubber stamp，形式存在但控制失效。

## Focused Principles

### Evidence must be attached before judgment

人类 gate 的输入应是已经结构化的 evidence package，而不是让审批人重新探索代码和运行环境。

### Independence is a design variable

通过不同 context、tool permissions、identity、oracle 与 model family，降低 reviewer 与 generator 的相关错误；独立性不是“开第二个聊天窗口”这么简单。

### Every production failure should choose a correction layer

同一 incident 不应该默认同时增加 Prompt、测试、Hook 和审批。先定位 failure mechanism，再把修正放到最能控制该变量的一层。

## Evidence Map

- `source:ai-native-sdlc-playbook` — task feedback、fresh verifier、literal evidence、continuous evals、review records 与 incident regression。
- `source:anthropic-secure-ai-sdlc` — narrow reviewers、finding proof、agentic + deterministic review、risk samples、DAST、loop observability。

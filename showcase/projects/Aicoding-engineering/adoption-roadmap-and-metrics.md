---
type: project-doc
projects:
  - "[[Aicoding-engineering]]"
domains:
  - software-engineering
  - ai-engineering
  - security-engineering
topics:
  - adoption
  - operating-model
  - metrics
  - maturity-model
  - implementation-roadmap
derived_from:
  - "[[solutions]]"
  - "[[solution-space]]"
source_refs:
  - source:ai-native-sdlc-playbook
  - source:anthropic-secure-ai-sdlc
origin: codex
status: active
created: 2026-08-30
updated: 2026-08-30
---

# Adoption Roadmap and Metrics

## Scope

本篇给出一个 vendor-neutral reference design：怎样从“个人使用 coding Agent”逐步迁移到可控的 AI-native engineering loop。

它不是 Anthropic 官方 rollout plan，也不是对任何组织的已验证方案。实际实施必须根据代码风险、团队规模、合规要求和现有工具调整。

## Starting Principle

不要一开始复制完整六阶段体系。优先修复当前最大的系统瓶颈，同时先建立测量基线。

```text
Observe current flow
→ find dominant bottleneck/risk
→ introduce one control loop
→ measure
→ expand only after evidence
```

## Maturity Model

| Level | Operating model | Main risk |
|---|---|---|
| L0 — Ad hoc assistant | 人给 Prompt，Agent 写代码，人手工检查 | 结果依赖个人习惯，无可复现流程 |
| L1 — Repository-guided | 有短 `AGENTS.md` / `CLAUDE.md`、标准命令 | 指导仍是 soft，验证和权限不一致 |
| L2 — Evidence-producing | Agent 必须运行 checks 并附完成证据 | 生成与验证可能共享盲区 |
| L3 — Gated delivery | plan、fresh verifier、PR reviewers、human merge gate | review capacity 和配置漂移 |
| L4 — Risk-tiered autonomy | Skills/Hooks/sandbox/identity、按风险自动路由 | classifier 和组合权限错误 |
| L5 — Closed-loop operations | monitor → intent/eval → controlled fix/release | 长循环、跨 Agent 与生产风险 |

Level 不是成熟度荣誉，而是权限和责任范围。若 L3 的 evidence、gate 或 rollback 不可靠，不应追求 L5 autonomy。

## Phase 0 — Baseline and Source of Truth

### Goal

先知道当前端到端流程在哪里等待、哪里失败，以及每类 artifact 的权威位置。

### Deliverables

- 当前 workflow map；
- artifact/source-of-truth inventory；
- risk taxonomy；
- 最近 20–50 个真实任务样本；
- 最近 incident/review finding 列表；
- lead time、review time、rework、failure baseline；
- Agent 能访问的 tool/credential/communication graph。

### Decisions

- Git、ticket system、design tool 各自谁是 authoritative；
- 哪些 action 必须保留 human approval；
- 哪些目录、数据、环境属于 protected；
- 哪些指标可以可靠收集。

### Exit Gate

能够回答：

```text
当前最慢的阶段是什么？
当前最危险的可达动作是什么？
当前最常见的重复失败是什么？
当前谁能批准 merge/release？
当前失败怎样被记录？
```

## Phase 1 — Minimal Artifacts and Persistent Context

### Goal

减少任务定义漂移和重复仓库探索，但不增加大规模流程负担。

### Implement

- 一页以内的 `AGENTS.md` / `CLAUDE.md`；
- 统一 build/test/lint commands；
- 小型 `intent.md` / change record；
- 高风险任务要求 `plan.md`；
- 明确 non-goals、success criteria 和 evidence；
- 每类 artifact 指定 source of truth；
- 把 task-specific 大流程移出 always-on context。

### Leading metrics

- Agent 重复犯已记录错误的频率；
- 首次找到正确 build/test command 的成功率；
- intent 进入 Build 后的重大修改次数；
- plan 与实际 changed scope 的偏离率；
- persistent context 字符/token 量及 stale rule 数。

### Lagging metrics

- rework cycles；
- task lead time；
- new contributor/Agent 首次成功 PR 时间；
- 因需求理解错误造成的 rollback/abandon。

### Exit Gate

至少一类任务中，artifact 能被不同 Agent/session 正确接续，且 context 没有继续无界增长。

## Phase 2 — Deterministic Feedback and Evidence

### Goal

让大部分机械错误在进入人工 review 前被发现。

### Implement

- formatter/lint/schema/secret/protected-path checks；
- 一条可重复的 task feedback command；
- bug fix 要求 regression test；
- 完成报告附 literal output、exit code 和 skipped checks；
- verifier role 定义为 read/run/report；
- CI 保护 test oracle 和关键 fixtures。

### Leading metrics

- first-pass local check success；
- Agent 自我修复次数；
- 无证据完成声明比例；
- skipped/timeout checks；
- per-task check latency。

### Lagging metrics

- first-pass CI success；
- 人工 review 中机械问题占比；
- escaped regression；
- 返工耗时；
- cost per verified change。

### Exit Gate

人工 review 不再主要发现 formatter、明显 test failure、protected path 或缺失运行证据。

## Phase 3 — Independent Review and Agent Evals

### Goal

把生成轨迹与最终判断分离，并把 Agent configuration 当作可回归的软件。

### Implement

- fresh-context verifier；
- narrow PR reviewers；
-统一 finding + proof schema；
- 20–50 个真实 task evals；
- model/context/Skill/Hook change 触发 eval；
- incident → permanent eval；
- reviewer disagreement 和 false-positive sampling；
- branch protection 保留 human merge gate。

### Leading metrics

- verifier finding rate；
- finding proof reproduction rate；
- eval pass by task family；
- config change regression rate；
- time to first review；
- reviewer disagreement；
- automated finding resolution rate。

### Lagging metrics

- pre-merge catch / production escape ratio；
- change failure rate；
- review time；
- repeat incident rate；
- human review minutes per risk tier。

### Exit Gate

Agent/harness 变化不会未经代表性 eval 直接进入主流程；reviewer 质量有抽样证据，而非只看输出数量。

## Phase 4 — Hard Boundaries and Risk Routing

### Goal

限制 compromised、confused 或 prompt-injected Agent 的 blast radius，并按风险分配验证预算。

### Implement

- role-specific tool permissions；
- remote/container sandbox；
- network egress allowlist；
- short-lived scoped credentials；
- single-purpose Agent identities；
- managed non-negotiable Hooks；
- risk tiers；
- environment permission tiers；
- Agent-to-Agent communication logging；
- composite authority threat model；
- shadow mode、red-team、sample audit。

### Leading metrics

- blocked/asked/allowed actions by rule；
- approval wait time；
- egress attempts；
- permission denials；
- risk routing distribution；
- automated approval sample error；
- un-attributed Agent action count；
- cross-Agent delegation count。

### Lagging metrics

- escaped gate violation；
- credential/security incident；
- permission-related near miss；
- high-risk change failure；
- time to revoke compromised identity；
- blast radius of simulated attack。

### Exit Gate

每个高权限动作都有独立 identity、可追溯 artifact、明确 gate 和测试过的 denial/rollback 路径。

## Phase 5 — Controlled CI/CD and Closed-loop Maintain

### Goal

让 Agent 在无人持续盯守时处理诊断和低风险流程，同时不获得无条件生产权限。

### Implement

- non-interactive Agent job in sandbox；
- deploy/status/rollback 暴露为 scoped interfaces；
- no standing production credentials；
- staging autonomy；
- production named authorization；
- tested rollback；
- deterministic control bands；
- Monitor Agent 的 restricted identity；
- alert → diagnosis/postmortem/PR；
- incident → intent + eval + owning team；
- full loop telemetry and SIEM routing。

### Leading metrics

- pipeline failure 自动诊断比例；
- alert-to-diagnosis；
- diagnosis-to-intent/PR；
- rollback rehearsal success；
- control-band escalations；
- autonomous run abort/escalation rate。

### Lagging metrics

- DORA deployment frequency、lead time、change failure rate、recovery time；
- repeat incident；
- unauthorized production action；
- time from incident to permanent regression；
- closed-loop fix acceptance rate。

### Exit Gate

系统能在低风险路径中闭环，同时任何高风险或不确定状态都会停在可解释 gate，而不是通过隐藏 side channel 继续。

## Risk-tier Reference

```yaml
R0:
  impact: local/reversible
  required:
    - fast_checks
    - task_feedback
  approval: none_or_sample

R1:
  impact: bounded_product_change
  required:
    - fast_checks
    - task_feedback
    - fresh_verifier
    - standard_review
  approval: code_owner

R2:
  impact: sensitive_or_large_blast_radius
  required:
    - full_tests
    - security_review
    - staging
    - rollback_evidence
    - audit_log
  approval: named_technical_or_security_owner

R3:
  impact: regulated_irreversible_or_production_critical
  required:
    - independent_reviews
    - adversarial_eval
    - separation_of_duties
    - explicit_risk_acceptance
    - rehearsed_rollback
  approval: designated_accountable_owner
```

## Metric System

### Do not optimize a single throughput metric

AI coding 可使 generated changes 增多，同时造成 review queue、rollback 和 hidden risk 上升。指标必须成对观察：

| Speed metric | Guardrail metric |
|---|---|
| changes per engineer | rework rate |
| deployment frequency | change failure rate |
| autonomous task completion | forbidden-action rate |
| time to first review | escaped defect severity |
| eval pass rate | task completeness / escalation rate |
| automated approval rate | sampled wrong-approval rate |
| context shrinkage | repeated mistake rate |
| lower verification cost | production escape rate |

### Leading vs lagging

**Leading** 指系统控制是否正常工作：

- Skill trigger；
- Hook block；
- evidence attached；
- verifier coverage；
- eval regression；
- identity attribution；
- gate wait。

**Lagging** 指真实结果：

- incidents；
- change failure；
- recovery；
- repeat bugs；
- escaped vulnerabilities；
- end-to-end lead time。

只看 leading 会优化流程外观；只看 lagging 反馈太慢。

### Measurement definitions

每个指标需要：

```text
Name
Decision it informs
Numerator / denominator
Population
Risk segmentation
Source system
Owner
Update cadence
Target or control band
Known bias
Retirement condition
```

例如“first-pass CI success”必须定义 retry 是否算失败、哪些 PR 排除、Agent-written 如何识别。

## Recommended First Experiments

### Experiment A — Split a bloated AGENTS file

**Hypothesis**：把 task-specific validation 移入 Skills/CI，可降低 token 与 wall time，同时不增加关键失败。

**Compare**：

- current monolithic instructions；
- minimal persistent context + triggered Skill + deterministic check。

**Metrics**：

- input tokens；
- tool calls；
- duplicate validations；
- task success；
- escaped invariant；
- human correction time。

### Experiment B — Fresh verifier

**Hypothesis**：read-only fresh verifier 能发现生成会话未发现的 plan mismatch，且成本低于人工全量复查。

**Metrics**：

- unique valid findings；
- false positive；
- reproduction rate；
- added latency/cost；
- post-review escape。

### Experiment C — Risk-routed validation

**Hypothesis**：R0/R1 减少重型检查、R2/R3 保持完整 gate，可降低平均成本而不提高 severity-weighted escape。

**Metrics**：

- cost/time by tier；
- rerouted/misclassified tasks；
- escaped failures；
- human load；
- rollback rate。

### Experiment D — Incident-to-eval

**Hypothesis**：把 incident 编码为 permanent eval，比只在 `AGENTS.md` 追加提醒更能防止 model/config regression。

**Metrics**：

- regression reproduction；
- config change blocked；
- repeat failure；
- context size；
- incident-to-eval latency。

## Stop Conditions

出现以下情况时，不应继续增加 autonomy：

- evidence 不能复现；
- verifier/reviewer 未校准；
- production action 无独立 identity；
- rollback 未演练；
- high-risk artifact 没有 owner；
- source-of-truth 冲突；
- logs 无法关联 Agent、tool 与 approver；
- risk classifier 未经过样本审计；
- Agent 能通过其他 Agent 绕过 gate；
- config/model 变化没有回归 suite。

## Decision Ownership

| Asset | Recommended owner |
|---|---|
| Project context | code owners |
| Institutional Skill | policy owner |
| Hook / permission | platform/security owner |
| Eval task family | owning engineering team |
| Eval infrastructure | AI/platform team |
| Risk taxonomy | engineering + security + compliance |
| Reviewer | domain owner + platform |
| Production gate | named accountable release owner |
| Incident regression | incident-owning team |
| Telemetry/SIEM | security/platform |

## Evidence Map

- `source:ai-native-sdlc-playbook` — stage-wise adoption、leading/lagging indicators、eval triggers、approval gates、CI/CD 与 maintenance loop。
- `source:anthropic-secure-ai-sdlc` — risk tiering、shadow/red-team/sampling、identity/egress、review scaling、DAST 与 monitoring controls。

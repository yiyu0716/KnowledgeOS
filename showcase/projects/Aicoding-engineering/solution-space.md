---
type: project-doc
projects:
  - "[[Aicoding-engineering]]"
domains:
  - software-engineering
  - ai-engineering
  - security-engineering
topics:
  - solution-space
  - control-architecture
  - agent-governance
  - engineering-transfer
derived_from:
  - "[[solutions]]"
source_refs:
  - source:ai-native-sdlc-playbook
  - source:anthropic-secure-ai-sdlc
  - source:datawhale-ai-native-sdlc-cn
origin: codex
status: studied
created: 2026-08-30
updated: 2026-08-30
---

# Solution Space — AI Coding Engineering

## First-principles Problem Model

### The system, not the model, ships software

最终交付结果可抽象为：

```text
Outcome
= f(
    Intent,
    Context,
    Model,
    Tools,
    Permissions,
    Environment,
    Verification,
    Review,
    Approval,
    Operations
  )
```

模型能力只是其中一个变量。即使 code generation accuracy 提高，错误的 intent、过期的 context、过宽的 permission、无法运行的 tests、拥堵的 review queue 或缺失的 release gate 都可以决定最终结果。

因此 AI coding engineering 的基本单位不是单次 Prompt，而是一个受控状态机：

```text
State_t
+ Agent action
+ Deterministic constraints
+ Evidence
+ Gate decision
→ State_t+1
```

### Why the bottleneck moves

若一个传统任务中：

- Plan/Design：3 天
- Build：10 天
- Test/Review：4 天
- Deploy：2 天

即使 Agent 把 Build 从 10 天压缩到 1 天，端到端周期仍是 10 天。继续把 Build 从 1 天压缩到 2 小时，收益已经很小。真正的优化对象转为：

- 是否能更快形成可批准的 intent/spec；
- 是否能在 Agent 输出进入人工队列前生成机械证据；
- 是否能按风险分配 review；
- 是否能让 release gate 明确而不散落；
- 是否能把 incident 迅速转成可执行的修正。

### Why the control model must change

传统流程常把“操作人可信”作为隐含前提。Agent 系统则存在：

- non-deterministic decision；
- untrusted retrieved content；
- tool-mediated actions；
- long autonomous runs；
- multiple interacting agents；
- rapidly changing model/configuration；
- high output volume。

于是安全不能只问“这个 diff 有没有漏洞”，还要问：

```text
谁产生了它？
读取了什么？
调用了什么？
本来允许做什么？
是否通过另一个 Agent 组合出更大权限？
用什么证据宣称完成？
谁批准它进入下一状态？
```

## Normalized Comparison

| Design question | Playbook 给出的答案 | Security article 给出的答案 | 综合含义 |
|---|---|---|---|
| 状态怎样跨阶段持续？ | committed artifact chain | logs、review records、postmortem | Durable artifacts 是 human/agent 共同状态层 |
| 组织知识放哪里？ | short `CLAUDE.md` + conditional Skills | secure guidance + organizational context | 常驻知识与条件知识必须分层 |
| 强规则怎样执行？ | Hooks、managed settings、sandbox | VM、egress、identity、least privilege | Prompt 不构成硬边界 |
| 怎样证明完成？ | feedback loop、fresh verifier、literal evidence | proof-carrying review、deterministic tools | 自我验证与独立验证都需要 |
| 怎样扩展 review？ | layered agentic review、human gates | narrow agents、risk tiering、sampling | 审查按风险和独立性组合 |
| 谁承担责任？ | humans judge intent/risk/approval | humans own critical approval | 自动化移动责任点，不取消责任 |
| 怎样形成长期学习？ | incident → new intent/eval | bug class → guidance；loop monitoring | 失败必须改变 future executable behavior |
| 安全边界覆盖什么？ | action hooks、permissions、branch/release gate | identity、resources、communication、composite authority | 必须审计完整 reachable action graph |

## Cross-source Convergence

### 1. Artifact replaces implicit handoff

两篇官方文章都把可审计 artifact 视为核心。它们可以是 Markdown、code/test、PR finding、release record 或 incident record，形式不同，但共同要求：

- 可由人和 Agent 读取；
- 有 owner；
- 有版本；
- 能关联上下游；
- 能说明当前状态；
- 能成为下一阶段的输入。

这比让所有 Agent共享无限聊天历史更可靠，因为 artifact 是策展后的任务状态，而不是完整轨迹的无差别累积。

### 2. Human judgment moves to state transitions

人不再观察 Agent 的每个 token 或每次 file edit。人类注意力移动到：

- intent 是否正确；
- spec/plan 是否可接受；
- 高风险 finding 是否真实；
- 是否允许 merge/release；
- 不确定 incident 是否升级；
- 哪个 residual risk 被接受。

这是一种 **judgment relocation**，不是 human removal。

### 3. Soft guidance and hard constraints must coexist

系统至少需要四种不同对象：

```text
Knowledge:    What the agent should know
Policy:       What should normally be done
Constraint:   What actions are possible
Evidence:     What actually happened and whether it worked
```

将四者都塞入一份 `AGENTS.md` 会产生三个问题：

1. 每个任务都支付全部 context 成本；
2. 必须规则仍只是一段 advisory prose；
3. 验证流程容易被当作永久指令，每个小改动都重复运行重型 audit。

正确方向是把知识、条件流程、动作边界和验证脚本分别放在最合适的执行层。

### 4. Review must become evidence-oriented

当 diff 体积增长时，纯人工逐行读取不能线性扩展。Agentic review 的价值不只是“多一个模型意见”，而是让进入人工 gate 前已经有：

- tests/build output；
- finding proof；
- spec/plan alignment；
- deterministic scan；
- risk classification；
- independent reviewer verdict。

人类因此能审查 intent、risk 与 exceptions，而不是重新执行所有机械工作。

### 5. The loop itself becomes a maintained product

Model、Prompt、Skill、Hook、tool、permission 和 reviewer 都会变化。任何一项改变都可能使原有行为退化。因此 Agent harness 需要：

- version control；
- eval suite；
- shadow deployment；
- red-team；
- telemetry；
- incident regression；
- rollback。

Agent configuration 不再是项目外的“设置”，而是需要发布管理的软件组件。

## Alternative Routes

这些来源并未要求所有组织采用唯一实现。主要 alternative routes 如下。

### Source of truth

**Repo-authoritative**

- intent/spec/plan 直接以 Git artifact 为权威；
- 审计链统一；
- 适合工程主导、Git 普及的团队。

**Legacy-authoritative**

- Jira、ServiceNow、requirements tool 等仍是权威；
- Agent 读取记录并把结果写回；
- 适合已有监管认可流程的组织。

**Linked dual representation**

- 两侧保存 record ID 与 commit SHA；
- 迁移成本低；
- 但必须承担同步和 freshness 风险。

选择标准不是“Markdown 是否先进”，而是谁拥有合法审计权、更新权和冲突裁决权。

### Review topology

**Sequential reviewers**

逻辑 → 安全 → 合规依次运行。易解释，但延迟累加。

**Parallel narrow reviewers**

多个 reviewer 同时检查不同 risk class。速度快，但需要统一 finding schema、去重和冲突处理。

**Risk-routed reviewers**

先 deterministic classifier / policy 判断 risk tier，再选择 reviewer 组合。经济性更好，但 classifier 误判会导致覆盖缺口。

### Verification cadence

**Per-edit checks**

formatter、lint、protected-path check。反馈快，必须轻量。

**Per-task feedback**

unit/integration test、run app、screenshot diff。用于生成 Agent 自我修复。

**Fresh final verification**

任务结束时独立 context 检查邻近行为和 plan alignment。

**CI eval suite**

Agent 配置或模型变化时，运行真实任务集。

**Scheduled/incident-driven scan**

面对成本较高或不需要每次运行的 security/eval。

没有一种 cadence 能替代其他层次；它们针对不同失败时机和成本。

### Deployment autonomy

从低到高可以是：

```text
Agent proposes only
→ Agent opens PR
→ Agent fixes review findings
→ Agent deploys to test/staging
→ Agent requests production approval
→ Agent executes authorized production release
```

升级条件应由 risk、reversibility、observability、rollback maturity 和 historical eval evidence 决定，而不是模型版本名称。

## Negative Evidence and Boundaries

### Throughput numbers do not establish end-to-end causality

Anthropic 的 8× 是代码交付量背景，不证明业务价值、质量或 lead time 同比提高。相反，Playbook 的存在说明外围流程可能尚未同步提速。

### Self-reported internal numbers have limited transfer confidence

约 80% merged code、16%→54% substantive comments、历史 incidents 约三分之一可被发现，说明 Anthropic 的内部 scale 与方向，但公开文章没有提供足够信息复现完整测量。它们适合作为 case evidence，不适合作为组织 adoption 的目标值。

### Fresh context is not independent ground truth

若生成者和 verifier 使用同一模型、同一错误文档或同一测试盲区，二者仍可能一致犯错。Fresh context 只减少轨迹相关性，不能替代 external oracle、deterministic invariant 或 human domain judgment。

### Multiple agents can add correlated complexity

更多 reviewer 可能提高 coverage，也会增加：

- inference cost；
- conflicting findings；
- orchestration failure；
- shared model blind spots；
- prompt injection surface；
- identity/permission edges。

应根据 marginal risk reduction 而非 reviewer 数量评价。

### Artifactization can become bureaucracy

若每个小任务都强制生成冗长 intent/spec/plan，artifact 会退化成模板填充。Artifact depth 应与 uncertainty、coordination cost、blast radius 和 reversibility 成比例。

### Hard controls are not permanently hard

Hook 可能被关闭，sandbox 可能配置错误，allowlist 可能过宽，CI credential 可能泄漏，另一个 Agent 可能拥有补足权限。边界本身需要测试、managed ownership 与 graph-level audit。

### Secondary synthesis cannot increase evidence breadth

中文文章提高可读性，但其事实大多来自两篇官方文章。它能帮助发现传播误差，不能把一项官方自述变成多源验证。

## Open Questions

1. **Artifact granularity**：什么规模的任务需要完整 intent/spec/plan，什么任务只需单一 change record？
2. **Context freshness**：怎样自动识别 `AGENTS.md` / `CLAUDE.md` 中已过期或低价值规则，而不因频繁重写造成漂移？
3. **Eval representativeness**：20–50 个历史任务能覆盖多少未来工作分布？怎样维护 hard cases 而不只保留容易通过的回归题？
4. **Reviewer calibration**：怎样测量 reviewer false positive、false negative 和 proof quality，而不是只统计评论数量？
5. **Composite permission analysis**：怎样自动发现 Agent、tool、CI、human channel 之间可组合出的高权限路径？
6. **Economic frontier**：在不同 risk tier 下，多少验证、review 与 sampling 才是最优投入？
7. **Long-loop recovery**：Agent 中断、环境变化或 artifact stale 时，怎样恢复而不重放全部上下文？
8. **Organizational ownership**：谁拥有 Skill、Hook、eval、risk policy 和 incident regression 的更新权？
9. **Model transition safety**：新模型能力增强时，既有 Prompt/permission 假设是否会反而失效？
10. **Cross-vendor portability**：如何把机制表示成 vendor-neutral contracts，而不是绑定具体文件名或产品功能？

## Mechanism Synthesis

| Intervention | Changed variable | Expected effect | Main failure mode |
|---|---|---|---|
| `intent.md` | problem ambiguity、state persistence | 减少后期方向修正 | 形式化了错误意图 |
| `spec.md` + policy context | design-policy alignment | 在写代码前发现冲突 | policy stale 或未触发 |
| pre-execution `plan.md` | change visibility、blast-radius awareness | 让人先审方案而非事后审大 diff | 实现偏离但 plan 未更新 |
| short persistent context | session initialization quality | 降低重复探索与常见错误 | 文件膨胀、过期、全局激活 |
| conditional Skills | policy availability at point of action | 一致应用组织知识 | trigger 失败；仍是 advisory |
| Hooks | reachable action set | 阻止明确违规动作 | 绕过、配置漂移、检查过重 |
| sandbox + scoped identity | blast radius | 降低 compromised Agent 的影响 | 跨系统组合权限 |
| continuous feedback | error detection latency | Agent 在人工前自我修复 | tests 不代表真实目标 |
| fresh verifier | error correlation | 发现生成轨迹中的假设盲区 | shared model/source blind spot |
| narrow reviewers | risk-class coverage | 扩大审查吞吐与专业性 | 冲突、成本、共同盲区 |
| risk tiering | verification budget allocation | 把人和算力用于高风险变更 | 低估风险导致漏检 |
| branch/release gate | authority over irreversible transition | 保留明确责任 | rubber-stamp 或审批拥堵 |
| incident → eval/intent | executable memory | 降低重复失败 | 只记录表象，不编码机制 |
| loop telemetry | attribution and diagnosability | 支持审计、调优和异常发现 | 日志不完整或敏感信息泄漏 |

## Decision Guide

### 当问题是需求反复变化

先引入最小 `intent.md`，要求 problem、outcome、constraints、non-goals 和 unresolved questions。不要先增加更多 coding rules。

### 当 Agent 每次都重新探索仓库

建立一页以内的 persistent context，只保存 commands、architecture、immutable constraints 与重复错误。低频流程移到 conditional Skills。

### 当 `AGENTS.md` 太长、验证重复

按执行层拆分：

```text
Always-on project facts     → AGENTS.md / CLAUDE.md
Task-triggered procedure    → Skill
Fast deterministic invariant→ Hook / script
Heavy validation            → explicit task gate / CI
High-risk transition        → human approval
Historical regression       → eval suite
```

这样可以避免“所有任务都激活所有规则”，同时让真正不可违反的规则不再依赖 Prompt。

### 当 Agent 口头声称“已完成”

要求 literal evidence：命令、退出码、测试数量、关键运行观察或 screenshot diff。最终使用 read/run-only verifier，不允许 verifier 顺手修改失败。

### 当 PR review 成为瓶颈

先分析风险类别和重复机械检查，再引入 narrow reviewers。人类保留 intent、architecture、regulated risk 与 release decision。不要以评论数量替代 finding accuracy。

### 当需要更长 autonomous run

先建立：

- versioned plan；
- fast feedback；
- protected paths；
- sandbox；
- scoped credentials；
- independent verifier；
- checkpoint/recovery artifact；
- explicit escalation condition。

Autonomy 是控制成熟度的结果，不是一个单独开关。

### 当准备让 Agent 触碰生产

至少满足：

- independent identity；
- no standing production credential；
- environment-tiered permissions；
- branch protection；
- named release authorization；
- tested rollback；
- full action/tool/communication logs；
- failure escalation；
- shadow evidence。

否则保持 propose-only 或 staging-only。

## Top 3 Principles

### Principle 1 — Artifacts carry state; gates carry accountability

**Problem Signature**

任务跨越多个角色、Agent、工具或时间段；会话历史太长或不可审计；不同阶段对“当前目标”理解不一致。

**Mechanism**

将 intent、design、execution plan、evidence、review 和 incident 从隐式上下文提升为 versioned artifacts。每个 gate 只判断清晰的状态转移，且保留批准主体和依据。

**Use When**

- 长程 coding task；
- 多 Agent 协作；
- 高合规或高审计要求；
- 需求/实现/验证易发生漂移。

**Boundary**

- artifact 必须有 canonical owner 和 source of truth；
- 小变更不需要复制完整企业流程；
- artifact 不能替代 sandbox、permission 或 runtime evidence。

### Principle 2 — Advisory context shapes behavior; deterministic controls bound behavior

**Problem Signature**

团队把所有规则写进一份 Prompt/AGENTS 文件；上下文越来越长；危险行为仍然只能依赖 Agent“记得不要做”。

**Mechanism**

根据约束性质选择执行层：

- knowledge → persistent context；
- conditional workflow → Skill；
- invariant → Hook/test；
- capability boundary → permission/sandbox/identity；
- irreversible action → approval gate。

**Use When**

既要降低 token/执行开销，又要保证关键规则真正可执行。

**Boundary**

- deterministic layer 也可能配置错误；
- 一些语义判断无法完全 deterministic，需要 reviewer/human；
- 拆分后必须保留可发现性，避免 Agent 不知道哪个 Skill 或 gate 存在。

### Principle 3 — Verify the agent loop, not only the final diff

**Problem Signature**

代码测试通过但过程不可解释；模型/Prompt 更新后行为悄然变化；Agent 可通过工具或其他 Agent 走出预期路径。

**Mechanism**

把 Agent config、tool calls、identity、permission edges、review behavior 与 incident regression 一起纳入 eval、telemetry、shadow、red-team 和 sampling。

**Use When**

- 模型或 harness 经常升级；
- 自动审查/批准比例增加；
- 运行时间和 Agent 数量增长；
- 涉及外部系统、敏感数据或生产环境。

**Boundary**

- 观测不等于预防；
- eval 只能覆盖已表达的风险；
- 日志本身需要隐私、访问和 retention policy。

## Transfer

### 对个人 Codex / coding-agent 项目

最小可行结构不是一份超长 `AGENTS.md`，而是：

```text
AGENTS.md
  └── permanent project contract and routing

skills/
  └── task-specific research, implementation, audit procedures

scripts/checks/
  └── deterministic fast checks

evals/
  └── representative historical tasks and regressions

artifacts/<task>/
  └── intent, plan, evidence, decision log

permissions/
  └── protected paths, network and command boundaries
```

### 对科研与强化学习项目

- intent 明确 experiment question 和 frozen variables；
- plan 明确唯一变量、seed、checkpoint、metrics 与 abort condition；
- deterministic checks 验证 shape、resume、replay、semantics；
- independent verifier 检查结果是否真的回答预注册问题；
- incident/evaluation failure 进入 regression test；
- 人类 gate 决定是否把结果解释为因果证据、是否冻结 checkpoint。

### 对 KnowledgeOS 自身

KnowledgeOS 与 AI-native SDLC 共享同一结构性思想：

```text
Evidence / Intent
→ explicit coverage contract
→ verified intermediate artifacts
→ write gate
→ human-readable durable output
→ maintenance loop
```

KnowledgeOS 的 Research Gate 是“artifact carries state, gate carries accountability”在知识生成领域的一个具体实现。

## Evidence Map

- `source:ai-native-sdlc-playbook` — lifecycle reference architecture、artifact chain、source of truth、context/control、verification、review、deployment、maintenance。
- `source:anthropic-secure-ai-sdlc` — Anthropic internal scale、security containment、review layers、identity、Agent communication 与 loop governance。
- `source:datawhale-ai-native-sdlc-cn` — secondary communication layer、中文压缩与事实范围扩大风险。

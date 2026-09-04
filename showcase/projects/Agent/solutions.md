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

# Solutions

## Problem Model

一个 Agent 的真实能力不是模型分数的同义词。更有用的工程模型是：

```text
Useful Agent Behavior
≈ Model Capability
× Context Construction
× Tool Semantics
× State Continuity
× Execution Boundary
× Verification Discipline
```

任一项接近零，系统都会失效：模型很强但工具语义错误，会执行错事；工具很多但状态不可恢复，会在长任务中失控；权限提示很多但没有 sandbox，仍无法限制最坏影响；trace 完整但缺少语义评测，只能复盘错误，不能证明正确。

本项目只将官方仓库与官方文档中明确陈述的内容当作 Solution Reality。`Why` 与跨方案 `Mechanism` 中出现的综合判断会显式标为本项目推论，不把排名、共同出现或产品宣传提升为因果证据。

## Concrete Comparison Matrix

| Solution | 主要入口 | Model / Provider | Agent decomposition | Durable state | Extension plane | Permission / Isolation |
|---|---|---|---|---|---|---|
| OpenCode | Terminal、Desktop、IDE | 多 Provider 配置 | Build / Plan + General / Explore / Scout | parent/child sessions、自动 compaction | Tools、LSP、MCP、Skills、ACP、SDK、Server、Plugins | ask / allow / deny；Build 默认 full tools |
| Codex | CLI、App、IDE、Cloud、SDK/App Server | OpenAI 路线为主，配置层可定义 Provider | 默认支持 parallel subagents | threads/history、App Server streamed events | AGENTS.md、Skills、Plugins、MCP、Hooks、Rules、SDK | local OS sandbox + approval；network 默认关闭 |
| Grok Build | TUI、Headless、ACP | Grok 为主，可配置 agent/model surface | subagents、fork、worktree sessions | disk sessions、tasks、file snapshots | Skills、Plugins、Hooks、MCP、AGENTS.md | Ask 默认；sandbox 独立且默认关闭 |
| Pi | TUI、Print/JSON、RPC、SDK | 多 Provider、custom models/providers | 核心不内置 subagents / plan | 单文件 session tree、branches、compaction | Extensions、Skills、Prompts、Themes、Packages | 核心不内置 permission popups；外部 container/sandbox |
| OpenClaw | Gateway、Channels、Web UI、CLI、Nodes | 多 Provider + runtime selection | multi-agent routing、plugin harnesses | Gateway state、sessions、workspace Markdown memory | Plugin SDK、resources、channels、tools、memory backends | trusted-operator policy；sandbox 默认关闭且 Gateway 在 host |
| Hermes Agent | CLI、Desktop、Gateway、Channels | 多 Provider / compatible endpoints | Profiles、Bots、delegation、worktrees | SQLite sessions、bounded memory、Skills、profile state | Skills、plugins、MCP、gateway integrations | defense-in-depth；write approval / checkpoints 可配置 |
| DeepSeek Harness | Web、Headless、SDK、ACP | model adapter plugin | Standard / Code / Minimal / Creator + subagents | append-only typed event log | Cordis plugins、profiles、bundles、patches | sandbox and approval knobs；file enforcement full/partial |

## OpenCode

### Thesis

OpenCode 将“多模型编码工作台”作为主要产品抽象。它不是只提供一个 terminal loop，而是把 Provider、primary agent、subagent、tool permission、project instructions 与多种客户端放入同一个运行体系，使用户在更换模型或界面时保留相似的工作方式。

### What — Concrete Method

官方文档将 OpenCode描述为 open-source AI coding agent，并提供 Terminal、Desktop 与 IDE 三类入口。Provider 层允许通过 API key 选择不同 LLM；项目执行 `/init` 后会分析仓库并生成 `AGENTS.md`，把结构和约定带入后续 Session。

Agent 层分为 primary agents 与 subagents。内置 primary agents 是 `Build` 和 `Plan`：Build 是默认开发 Agent，拥有完整工具；Plan 面向分析与规划，文件编辑和 Bash 默认设为 `ask`。内置 subagents 包括 `General`、`Explore` 与 `Scout`：General 处理复杂研究和多步任务，Explore 是快速只读代码探索，Scout 用于外部文档与依赖源码研究。subagent 创建 child session，用户可以在 parent / child 之间导航。隐藏 Agent 还负责 compaction、title 与 summary。

Permission 使用 `ask / allow / deny`，可以按 read、edit、bash、task、external directory、web、LSP、skill 以及 MCP/custom tool name pattern 细化。产品还暴露 LSP、MCP、Skills、ACP、custom tools、Server、SDK 与 Plugins 等扩展面。

### Why

官方材料强调让不同 Provider 和专门 Agent 共用一套工作台。本项目推论是：它主要降低的是**模型与客户端切换成本**，并通过 Plan/Build 分工和只读探索 Agent 减少不必要修改；它并不试图让每个模型的工具能力天然等价。

### Mechanism

```text
Provider abstraction
+ Agent role configuration
+ Tool permission mapping
+ Shared client/session surface
→ lower switching and workflow reconstruction cost
```

### Negative Evidence / Boundary

Build 默认 full-tool access，因此安装后的默认开发体验不是最小权限模式。Permission 能决定工具是否执行，但当前 Evidence Set 没有把 OpenCode 证明为具有 Codex 同等语义的 OS-enforced local sandbox。横向模型比较也必须固定 prompt、tool schema、context、approval 与 retry budget，否则“同一个 OpenCode”仍不是受控实验。

## Codex

### Thesis

Codex 的主轴是把高完成度的软件工程执行放进明确的 local/cloud execution boundary，并提供 App Server 与 SDK，让同一 Agent 能力被 CLI、IDE、桌面客户端和自动化系统复用。

### What — Concrete Method

官方 Open Source 页面明确列出 Codex CLI、SDK、App Server、Skills 与 Plugins 等开源组件，同时把 IDE extension 与 Codex cloud 标记为非开源。CLI 能读取、编辑并运行代码；配置层管理 model/provider、approval、sandbox 与 MCP 等选项。

本地安全由两个独立层组成：Sandbox Mode 限制命令在技术上能触及的文件与网络；Approval Policy 决定何时必须停下请求用户允许。官方文档说明 local agent 默认关闭 network，并使用 OS-enforced sandbox，通常把写入限制在当前 workspace。Cloud 任务位于隔离环境，但属于另一部署面。

App Server 为 rich client 提供 authentication、conversation history、approvals 与 streamed agent events，并使用 JSON-RPC 风格协议。它还提供 remote TUI 连接，但 WebSocket transport 当前标为 experimental，非本地暴露时需要认证和 TLS/安全转发。

当前 Codex release 默认启用 subagent workflow。主线程可以把探索、测试、triage 等独立任务委托给专门线程，再收集摘要。官方同时说明，每个 subagent 都会独立进行模型与工具工作，因此会增加 token；并行 write-heavy task 还可能产生冲突与协调成本。

### Why

Codex 把“是否允许运行”与“运行后能影响什么”分开，使自治程度可以提高，而最坏影响范围仍由 sandbox 约束。App Server 则把 Agent Runtime 与具体 UI 解耦，便于桌面端、IDE、远程 TUI 或自定义产品共享历史、审批和事件流。

### Mechanism

```text
Approval → authorize an operation
Sandbox  → bound the operation's effect
App Server → expose the same stateful agent protocol to clients
Subagents → move bounded noisy work out of the main context
```

### Negative Evidence / Boundary

“Codex 开源”不能概括整个产品栈：模型权重、IDE extension 与 Codex cloud 并未因此开放。subagent 适合 read-heavy 并行，但不会自动解决共享目录的 write conflict。高 reasoning、长 context、反复 validation 与多 subagent 叠加时，成本和延迟可能成为主要约束；本 Evidence Set 没有跨 Harness 的受控成本曲线。

## Grok Build

### Thesis

Grok Build 把终端中的长程软件工程操作作为主要产品形态：Session 不只产生一次 Patch，还能分叉、进入独立 Worktree、运行后台命令、监控事件并处理排队 Prompt。

### What — Concrete Method

Grok Build 提供全屏 TUI、Headless/Scripting 与 ACP 入口。项目可用 `AGENTS.md` 常驻编码约定，Skills 保存复用指令、脚本和资源，Plugins、Hooks 与 MCP 扩展工具和 lifecycle behavior。Hook 可以在工具执行前阻断危险命令、记录调用，或在编辑后运行 formatter。

Permission Mode 包括默认 `Ask`、可选 `Auto` 与 `Always-approve`。allow/deny rule 可按 Bash、Edit、Read、MCPTool、WebFetch、WebSearch 等过滤，deny 优先。Sandbox 是另一控制层，使用 Linux Landlock 或 macOS Seatbelt 等机制限制 filesystem 与部分 child network；它默认关闭，并提供 workspace、read-only、strict 等 profile。

subagent 在独立 child session 中工作。Worktree session 使用独立 Git checkout，使并行 Agent 不直接覆盖同一工作目录；subagent 也可以请求 Worktree isolation。Background Tasks 能运行 command、subagent 与 monitor，`/loop` 可周期触发 Prompt，queue 保存运行中收到的新指令。Session 会把 conversation、tool call 与 file snapshot 保存到磁盘，并可跨 TUI、headless 和 ACP 使用。

### Why

本项目推论是：Grok Build 将**并行上下文**与**并行文件系统状态**同时提升为产品能力。单纯多开 Agent 只隔离思考过程，Worktree 才进一步隔离写入对象；Background Task 与 Monitor 则让长进程不必阻塞主对话。

### Mechanism

```text
Independent child context
+ Git worktree checkout
+ Background process registry
+ Persistent session/task view
→ parallel long-running operation with lower overwrite risk
```

### Negative Evidence / Boundary

Sandbox 默认关闭。官方文档还指出，built-in profile 不会永久保护 `~/.ssh` 等凭据路径，需要自定义 deny；macOS 上部分 child-network restriction 不生效，模型 API 与 in-process web tool 也不受 child-network setting 约束。Worktree 降低文件覆盖，却不隔离共享外部资源，例如端口、数据库、云账号和外部 queue。

## Pi

### Thesis

Pi 选择 minimal harness：核心保持小而稳定，把 workflow、UI、permission、subagent、memory 与 remote integration 交给可安装或自行编写的扩展。它优化的不是默认 feature count，而是可改造性。

### What — Concrete Method

Pi 默认向模型提供 `read`、`write`、`edit` 与 `bash` 四个主要工具。运行方式包括 Interactive TUI、Print/JSON、stdin/stdout RPC 与 SDK。Provider 层支持多家订阅或 API-key 模型，并允许通过配置或 Extension 添加 custom model/provider。

Customization 由 TypeScript Extensions、Skills、Prompt Templates、Themes 与 Pi Packages 构成。Extension 可以注册 tools、commands、events、keyboard shortcuts 和 TUI；也可以注入 dynamic context、过滤 message history、实现 RAG、memory、permission gate、SSH execution 或 sandbox adapter。`AGENTS.md`、`SYSTEM.md`、Skills 与自定义 compaction 共同形成 context-engineering surface。

Session 是树结构：用户可以跳转到历史点形成 branch，分支保存在同一文件中；长 Context 可自动 compaction，完整历史仍保留。项目官方明确选择不在核心内置 MCP、subagents、permission popups、plan mode、built-in todos 与 background bash，而是建议用 CLI/README、Extension、Package、container 或 tmux 组合。

### Why

Pi 认为 opinionated feature 不应锁死 Harness。小核心让用户可以替换 context assembly、tool behavior、UI 和 integration，而不必 fork 大量内部代码。本项目推论是：它特别适合研究“一个机制变化是否真的改善 Agent”，因为不必同时接受整套产品假设。

### Mechanism

```text
Small runtime primitives
+ open extension lifecycle
+ inspectable session tree
+ provider-neutral model adapter
→ low-friction harness experimentation
```

### Negative Evidence / Boundary

Pi 的灵活性以责任转移为代价。官方仓库明确说明它不内置限制 filesystem、process、network 或 credentials 的完整 permission system，默认继承启动用户和进程权限。Project trust 只决定是否加载项目资源，不能替代 command sandbox。运行不可信代码时，应在 container、microVM、OpenShell 或经过审计的 Extension boundary 中启动，而不是把 prompt 当安全控制。

## OpenClaw

### Thesis

OpenClaw 的主抽象是 self-hosted Gateway：把多个消息渠道、Agent Runtime、Tools、Sessions、Memory、Control UI 与移动/远程 Node 连接为长期在线的控制平面。

### What — Concrete Method

一个 Gateway process 可以同时服务多个 channel plugin、WebChat、CLI、Control UI 与 mobile nodes。官方文档把 Gateway 描述为 sessions、routing 与 channel connections 的 single source of truth。multi-agent routing 可以按 Agent、Workspace 或 sender 分离 Session；paired node 可以提供 camera、screen、voice 与 `system.run` 等能力。

OpenClaw 当前拥有 built-in agent runtime：agent core 负责 loop、message、compaction、prompt、skills 与 session contract；harness registry 可以选择 built-in runtime 或 plugin-registered harness，例如 Codex。Plugin SDK 允许扩展 channels、tools、resources、memory backend 与 runtime behavior。

默认 Memory 通过 Agent Workspace 中的 Markdown 文件保存。`USER.md`、`MEMORY.md`、dated notes 与可选 `DREAMS.md` 分别承担偏好、长期事实、近期观察与 review；官方强调没有被写入磁盘的内容不会形成隐藏长期状态。其他 memory plugin 可以提供 vector recall 或知识编译层。

安全模型以 trusted operator 为起点。Gateway/config 与 persistent cron 等 control-plane tool 受到 owner restriction；处理 untrusted content 的 Agent 应 deny gateway、cron、session spawning/sending 等能力。Tool Sandbox 支持 Docker、Podman、SSH 与 OpenShell backend，但默认关闭；启用后 tool execution 进入 sandbox，Gateway 本身仍在 host。

### Why

当用户希望从手机、聊天平台和多台机器持续访问 Agent 时，Terminal Session 已不足以承担 identity、routing、channel auth、node pairing 与长期 automation。Gateway 把这些状态集中，Execution Node 与 Sandbox 则把实际动作分发到不同位置。

### Mechanism

```text
Authenticated channels / clients
→ Gateway routing and policy
→ selected agent runtime
→ host, node, or sandbox tool execution
→ persistent session and memory state
```

### Negative Evidence / Boundary

OpenClaw 的默认 trusted-operator host execution 不是 hostile multi-tenant boundary。Sandbox 开启后 Gateway 和部分 host-side capability 仍位于高权限控制平面；paired node 的身份批准也不等于每条命令审批。Plugin、Skill、Cron 与 Memory backend 能跨 Session 产生持续影响，必须按代码依赖和长期状态变更审计。

## Hermes Agent

### Thesis

Hermes 把 Experience → Memory / Skill 的学习闭环放在系统中心：不仅保存历史，还尝试把用户修正、环境事实和可复用流程提炼为未来 Session 会读取的状态。

### What — Concrete Method

Hermes 提供 CLI、Desktop 与 multi-platform Gateway。Session 自动保存，可在 SQLite state 中进行 metadata 与 full-text search。Profile 是独立 Hermes Home，每个 Profile 拥有 config、API keys、SOUL、Memory、Sessions、Skills、Cron 与 Gateway state；官方同时强调 Profile 不是 filesystem sandbox。

Memory 被限制为两份较小的常驻文件：`MEMORY.md` 约 2,200 chars，保存环境、约定和经验；`USER.md` 约 1,375 chars，保存用户偏好与交流期待。它们在 Session 开始时作为 frozen snapshot 注入。Skills 是按需加载的程序性知识，遵循 progressive disclosure，Agent 可以创建、修改或删除。

后台 self-improvement review 可能在 Turn 结束后保存 Memory 或更新 Skill。`write_approval` 可以把这些写入先 staging，再由用户批准；官方当前文档显示 Skill 自动写入默认允许。安全体系包括用户授权、危险命令审批、文件写入保护、container isolation、MCP credential filtering、context-file injection scanning、cross-session isolation 与 input sanitization。Checkpoint / rollback 可以在 destructive operation 前保留快照，但当前为 opt-in、默认关闭；Worktree 可给 Agent 独立 branch 与 directory。

### Why

Hermes 将“事实”和“流程”分开：少量事实进入常驻 Memory，复杂操作进入按需 Skill，以避免把全部历史持续塞入 System Prompt。本项目推论是：这种拆分使 Agent 能形成稳定行为，但也把学习质量问题转化为 durable-state governance 问题。

### Mechanism

```text
Interaction trace
→ detect durable fact or reusable procedure
→ write Memory or Skill
→ future session snapshot / on-demand load
→ changed future behavior
```

### Negative Evidence / Boundary

自改进写入可能固化错误结论、过拟合偏好或让 Skill 漂移，因此 write approval、Profile isolation、Skill curation、versioning、test 与 rollback 是学习闭环的必要组成。两个 Agent 不应共享同一 Profile/Home 自动写 Memory。官方材料描述的是 durable context 与 procedure 更新，本项目不把它表述为 online weight training。

## DeepSeek Harness

### Thesis

DeepSeek Harness 将 Agent Runtime 本身作为可组合研究对象：model adapter、tool registry、session log、sandbox、storage、loop、scheduler 与 UI 由 Cordis plugin 贡献，并以 typed event log 记录运行。

### What — Concrete Method

Cordis plugin 向 shared context 注册 services、typed events 与 reversible effects；官方架构强调没有需要 patch 的 privileged core。Profile 是按顺序组合的 plugin tree，Bundle 和 patch file 定义可替换配置。开发者可以在不改 Harness source 的情况下替换 Agent capability。

Session 是 append-only typed `SessionEvent` log。LLM message history 从日志派生，而不是另存一份可变 transcript；prompt、reasoning、tool call/result、subagent scheduling 与 context injection 被记录，resume、fork、search、replay 使用同一 event stream。Runtime 包括 Standard、Code、Minimal 与 Creator：Standard 是完整 Coding Agent；Code Mode 让模型生成 TypeScript 组合多轮 tool call；Minimal 只保留 persistent shell 与 editor；Creator 面向 runtime inspection 和 preset authoring。

Tool pipeline 把 pre-execute policy/hook、monotonic guard、execute、post-execute、result observation 分层。Sandbox 与 Approval 是独立 knob；Permission Preset 把它们打包成用户可选组合。SandboxMode 包括 read-only、workspace-write 与 danger-full-access，但该 vocabulary 只约束 file effects，network 与 process visibility 属于其他 capability seam。Runner 会报告 enforcement 是 full 还是 partial。

### Why

事件溯源避免“模型看到的消息”和“系统实际发生的事件”分裂，插件化则允许研究者替换单个 mechanism 而不重写整个应用。本项目推论是：它最适合构造同模型、不同 Harness 的因果对照，以及检查 tool policy、context injection 与 replay semantics。

### Mechanism

```text
Plugin-composed capabilities
+ append-only canonical event stream
+ derived model surface
+ replayable policy and tool outcomes
→ inspectable and reconfigurable agent experiments
```

### Negative Evidence / Boundary

项目处于 Developer Preview，API 与 core plugin 仍可能变化。Event Log 提高可调查性，不证明 Agent 意图、代码语义或因果解释正确。Sandbox 的 `read-only` / `workspace-write` 主要描述 file effects；Windows ACL 与旧 Landlock 可能是 partial enforcement。官方 Python minimal example 使用 danger-full-access，因此不能把“Minimal”误读为“默认安全”。

## Evidence Map

- `source:agent-opencode-official` — OpenCode product surfaces、Agent roles、permissions 与 Provider abstraction。
- `source:agent-codex-official` — Codex open-source boundary、sandbox/approval、App Server 与 subagents。
- `source:agent-grok-build-official` — Grok Build sessions、permissions、sandbox、worktrees 与 background execution。
- `source:agent-pi-official` — Pi minimal core、extension model、session tree 与 explicit omissions。
- `source:agent-openclaw-official` — OpenClaw Gateway、runtime registry、memory 与 host/sandbox boundary。
- `source:agent-hermes-official` — Hermes learning loop、bounded memory、Skills、Profiles 与 security controls。
- `source:agent-deepseek-harness-official` — DeepSeek Harness Cordis architecture、event sourcing、runtime modes 与 policy seams。

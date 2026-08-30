# KnowledgeOS Policy

## Source of Truth

1. Primary evidence: `sources/repos/`, `sources/papers/`, captured writeups, experiments, and other source material.
2. Durable knowledge: `vault/` Markdown and Properties.
3. Registry: `registry/` source identity and ingestion metadata only.

Generated indexes, Research Runs, graph data, caches, and lint reports are rebuildable projections.

## Safety

- Repositories under `sources/repos/` are read-only by default for learning and ingestion.
- Before durable code knowledge, record remote, branch, HEAD, and working-tree state.
- Never store secrets, credentials, API keys, or tokens in KnowledgeOS.
- Preserve human-owned notes. `origin: human` and missing origin are human-owned.
- Do not modify `.obsidian/` or `.base` files unless explicitly requested.
- Do not use ranking differences as causal evidence.
- Keep unknowns unknown and label inference.

## Output Language

Human-facing generation reads `knowledge-config.yaml`. With `output_style: zh_en_terms`, normal prose is Chinese while established technical terms, model/algorithm names, code identifiers, schema keys, and canonical IDs remain English. Explicit per-request language instructions override the workspace preference.

## Human / Machine Boundary

Human-facing Markdown is optimized for understanding: concrete `What`, `Why`, `Mechanism`, comparison, principles, transfer, and a concise `Evidence Map` at the end. Human `source_refs` contain only stable `source:<id>` identities.

Detailed repository, commit, path, symbol, line, confidence, excerpt hashes, Fact IDs, Claim IDs, and verification state remain authoritative in Research Runs, registry, and derived provenance indexes. Hiding machine detail must never reduce verification strength.

`Paths may be hidden; facts may not.`

## Knowledge Quality Objective

KnowledgeOS does **not** optimize for the shortest verified document. It optimizes:

```text
maximize useful verified knowledge
subject to correctness and provenance constraints
```

A formal research document passes only when it achieves all three:

```text
Precision  — what is written is supported and calibrated.
Coverage   — important supported knowledge is not omitted to avoid verification work.
Synthesis  — facts are converted into mechanisms, decisions, and bounded transfer.
```

`Precision without Coverage` is verification-induced under-documentation. `Coverage without Precision` is untrusted note dumping. `Precision + Coverage without Synthesis` is an archive, not a knowledge system.

## Write Boundary

Exploration, inspection, explanation, comparison, and search are read-only. Write to `vault/` only when explicitly asked to save, ingest, summarize into KnowledgeOS, create/update project knowledge or Learning, or synchronize knowledge.

Formal generated research Markdown may be written only through `research finalize` after the Research Gate passes. Search must never write knowledge automatically.

## Three Loops

### Read Loop

```text
Question → BM25 + Vector + RRF → relevant notes → graph/context links → task
```

Retrieval should prefer reusable Learning when relevant, but must preserve relevance across Learning, focused docs, Project docs, and Project Home. Related notes are context, not automatic rank overrides.

### Research Loop

```text
Evidence
→ Coverage Plan
→ Dense Fact Extraction
→ Coverage Gate
→ Evidence Verification
→ Frozen Facts
→ Claims / Mechanisms
→ WRITE_ALLOWED
→ Full Human Draft
→ Completeness Gate
→ Finalize
```

The Research Gate protects both correctness **and** knowledge recall. A model may not obtain a cleaner PASS merely by writing less.

### Maintenance Loop

```text
Knowledge used
→ new evidence / contradiction / confirmation
→ impacted knowledge
→ targeted patch proposal
→ verification
→ finalize
```

Small updates should use targeted maintenance rather than re-running an entire research project. Before applying a generated patch, compare the target note's current hash with the hash read at patch planning time; stale writes must be rejected and regenerated.

## Four Skills

- `search`: retrieve prior knowledge read-only; prefer relevant reusable Learning without hard ordering.
- `summarize`: reconstruct one real Solution concretely and preserve the supported details needed to recover its mental model.
- `compare`: reconstruct multiple Solutions, prove adequate evidence coverage, then synthesize Convergence / Alternatives / Negative Evidence / Open Questions / mechanisms / decisions.
- `maintain`: report links, provenance, staleness, canonical ownership, currentness, and under-documentation before any update.

## Research Coverage Contract

Every formal complex Research Run has `coverage-plan.json` before Facts are frozen.

The plan declares:

- the expected entities/solutions;
- important evidence axes that must be represented when supported;
- a minimum Fact coverage floor;
- the Human output contract (required knowledge roles/sections and expected entity labels);
- an optional suspiciously-thin warning threshold.

The plan is not a word-count target. It is a **knowledge coverage contract**. Missing an expected entity or required axis is `KNOWLEDGE_COVERAGE_FAIL` and blocks Fact freeze.

Examples of high-value axes for a multi-solution engineering/RL project include `thesis`, `representation`, `model`, `action`, `training`, `opponent/data distribution`, `inference/system`, `why`, `mechanism`, and `negative/boundary`. The actual plan must be generated from the task and Evidence; do not force irrelevant axes.

## Verification Budget

Verification should be strict where errors change understanding, but it must not make every descriptive detail equally expensive.

High-risk/Core facts require explicit semantic verification against bound Evidence, especially:

- numbers and concrete configurations;
- author-stated motivations;
- experimental results / ablations / negative evidence;
- facts supporting cross-solution Claims or Top Principles;
- counterexamples and causal wording.

Supporting descriptive facts may be grouped into coherent evidence-backed Fact statements instead of atomizing every sentence. The goal is dense verified reconstruction, not maximum Fact count.

## Summary Quality Protocol

All important Project, Solution, and focused summaries follow:

```text
Evidence
→ Dense Concrete Method Reconstruction
→ Normalized Comparison
→ Convergence / Alternative Routes / Negative Evidence / Open Questions
→ Mechanism Synthesis
→ Candidate Principles
→ Top Principles
→ Decision / Transfer
```

Rules:

1. **No premature synthesis.** Evidence cannot jump directly to principles.
2. **Concrete reality is first-class.** `solutions.md` retains useful implementation/configuration details even when they do not support a cross-solution Claim.
3. **Compare on facts first.** A Concrete Solution Matrix restores real configurations and differences before evaluative prose.
4. **Do not optimize by omission.** If Evidence supports important facts needed to understand an expected Solution or axis, omitting them to reduce verification work is a quality failure.
5. **Classify findings.** Convergence, Alternative Routes, Negative Evidence, and Open Questions must remain distinguishable.
6. **Mechanism similarity is not name similarity.** Similar terms such as KL, teacher, pool, or entropy remain separate when they change different variables.
7. **Top Principles come only after synthesis.** Rank by Impact, Evidence Breadth, Mechanistic Clarity, Transferability, and Distinctness. Each Principle includes `Use When` and `Boundary`; strongest counterexamples must change wording, strength, or boundary.
8. **Acceptance = Reality + Mechanism + Transfer.** A safe but skeletal summary fails just as a detailed but unsupported summary fails.
9. **Learning Promotion and machine maintenance never appear in Human-facing prose.** They run after the document is complete.

## Human Completeness Contracts

Canonical documents have different responsibilities:

- `Project Home`: 30–60 second orientation; Overview, Task, Evaluation, Challenges, Solution Landscape, compressed principles, Knowledge Map, Evidence Map.
- `solutions.md`: Reality canonical source. Reconstruct every expected Solution with a Thesis and enough concrete method detail to understand how it runs.
- `solution-space.md`: Project-wide synthesis canonical source. Preserve Convergence, Alternatives, Negative Evidence, Open Questions, Mechanism Synthesis, Decision Guide, Top Principles, and Transfer when supported.
- Focused Project Docs: high-density treatment of one direction with Scope, Concrete Landscape/Matrix, key axes, mechanisms, trade-offs, focused principles, and Transfer.
- `Learning`: cross-project reusable mechanism; not a copy of Project prose.

The exact headings may vary, but the knowledge roles may not silently disappear. A generated draft missing required roles/entities is `DOCUMENT_COMPLETENESS_FAIL`. Extremely short output relative to its declared task receives `SUSPICIOUSLY_THIN_OUTPUT` even if all written sentences are verified.

## Claim Lifecycle

Durable high-value Claims may carry:

```text
current | superseded | contested
```

`current` is the default actionable conclusion; `superseded` remains searchable as history but should not be presented as the current recommendation; `contested` requires its conflict/boundary to travel with the Claim. Newer modification time alone never establishes currentness.

`claims.yaml` is an optional generated projection, not a second hand-maintained source of truth. Only the latest active, verified canonical `solution-space` run may refresh it. Its freshness is determined by run identity and durable-Claim hashes, never by an `updated` date. If a newer canonical run supersedes the run that generated the ledger, report `CLAIM_LEDGER_STALE`; if ledger content diverges from the verified durable Claims, report `CLAIM_LEDGER_DRIFT`. If the latest canonical run contains no durable Claims, no stale prior ledger may remain.

## Multi-Solution Evidence Axes

Track separately:

- implementation confidence: source code > tests/configuration > writeup;
- motivation confidence: explicit author rationale > documented context > inference;
- effectiveness confidence: controlled comparison > same-pipeline evaluation > repeated/independent evidence > leaderboard correlation;
- transfer confidence: repeated mechanism across projects/tasks > controlled mechanism evidence > strong inference.

Multiple Solutions sharing a component establish a recurring pattern worth testing, not causal effectiveness.

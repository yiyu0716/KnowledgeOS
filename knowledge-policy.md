# KnowledgeOS Policy

## Source of Truth

1. Primary evidence: `sources/repos/`, `sources/papers/`, and captured source material.
2. Durable knowledge: `vault/` Markdown and Properties.
3. Registry: `registry/` source identity and ingestion metadata only.

Generated indexes, graph data, caches, and lint reports are projections.

## Safety

- Repositories under `sources/repos/` are read-only by default for learning and ingestion.
- Before durable code knowledge, record remote, branch, HEAD, and working-tree state.
- Never store secrets, credentials, API keys, or tokens in KnowledgeOS.
- Preserve human-owned notes. `origin: human` and missing origin are human-owned.
- Do not modify `.obsidian/` or `.base` files unless explicitly requested.
- Do not use ranking differences as causal evidence.
- Keep unknowns unknown and label inference.

## Output Language

Human-facing generation reads the workspace preference from `knowledge-config.yaml`:

```yaml
output_style: zh_en_terms
```

Supported styles:

- `english`: all normal prose and headings are English.
- `zh_en_terms`: normal prose is Chinese; established technical terms, algorithm/model names, code identifiers, schema keys, canonical IDs, and provenance references remain English.

A user's explicit per-request language instruction overrides the workspace preference for that response. Language changes presentation only; it must not change facts, evidence status, Graph relations, or provenance.


Human-facing Markdown is optimized for understanding: What, Why, Mechanism, principles, transfer, and a concise Evidence Map at the end. Detailed repository, commit, path, symbol, line, confidence, and verification metadata remain authoritative in structured provenance and derived indexes. Hiding detail from the reading layer must never reduce provenance verification.


Exploration, inspection, explanation, and discussion are read-only. Write to `vault/` only when explicitly asked to save, record, ingest, summarize into KnowledgeOS, create/update project knowledge or learning, or synchronize knowledge.

## Four Skills

- `search`: retrieve prior Learning first, then Projects/Solutions/Evidence.
- `summarize`: reconstruct one real Solution and test Learning promotion.
- `compare`: reconstruct multiple Solutions and synthesize the solution space.
- `maintain`: audit links, provenance, duplicates, staleness, and promotion debt; report first.

## Research Passes

Complex multi-solution work uses Evidence, Synthesis, and Red-team passes. Evidence is collected before solution-space claims are drafted; red-team checks causal inflation, missing counterexamples, source gaps, and What/Why confusion.

## Multi-Solution Evidence Axes

Track separately:

- implementation confidence: source code > tests/configuration > writeup;
- motivation confidence: explicit author rationale > documented context > inference;
- effectiveness confidence: controlled comparison > same-pipeline evaluation > repeated/independent evidence > leaderboard correlation;
- transfer confidence: repeated mechanism across projects/tasks > controlled mechanism evidence > strong inference.

Multiple solutions sharing a component establish a recurring pattern worth testing, not causal effectiveness.

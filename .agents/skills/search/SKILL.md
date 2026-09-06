---
name: search
description: Retrieve prior KnowledgeOS experience read-only using lexical + semantic retrieval, then add only useful relation/provenance context without changing knowledge.
---

# Search

Search answers: **“What have I learned before that is relevant now?”** It is read-only.

## Retrieval

Use the current deterministic search pipeline (BM25 and, when enabled, Vector + RRF). Preserve relevance across Learning, focused docs, Project docs, and Project Home; Learning is a soft preference, not a hard ordering rule.

After primary retrieval, use existing `projects`, `derived_from`, Wikilinks, and provenance to add a small amount of 1-hop context when it materially helps interpretation. Do not flood the answer with graph neighbors.

Prefer current durable conclusions when claim lifecycle metadata is available. `superseded` knowledge remains useful for historical questions; `contested` knowledge must carry its conflict/boundary.

## Response behavior

- For experience/transfer questions, surface the most relevant Learning and the Project/focused evidence that makes it concrete.
- For project-specific factual questions, focused Project docs may outrank Learning.
- If multiple near-duplicate notes express the same mechanism, prefer the canonical owner and mention related notes rather than returning redundant copies.
- Trace to raw Evidence only when the user needs verification or implementation detail.

Search never auto-writes or auto-maintains the Vault. If the current task produces new evidence that could update knowledge, report it as a maintenance candidate; do not modify knowledge unless explicitly asked.

## Parallel units and exact retrieval

Respect both `learning_kind: project` and `learning_kind: mechanism`; do not
prefer a mechanism card when the question needs the complete project unit. Return
the matched section, conditions and evidence pointer. Do not treat `projects` or
`derived_from` as proof of reuse. Declared application records are not controlled
validation. Never write back from search without explicit user authorization.

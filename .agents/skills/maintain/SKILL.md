---
name: maintain
description: Run a report-first KnowledgeOS audit for integrity, provenance, source drift, claim lifecycle, retrieval state, canonical ownership, duplication, and under-documentation.
---

# Maintain

## Core rule

**Report first.** Do not silently modify notes, registry, sources, indexes, claims, or Obsidian files.

## Deterministic pass

Run:

```bash
python3 tools/knowledgeos.py lint
python3 tools/knowledgeos.py maintain
```

Review Research Gate issues such as `FINALIZATION_HASH_DRIFT`, `COVERAGE_PLAN_STALE`, `FACT_MATRIX_STALE`, `CLAIM_MATRIX_STALE`, `MECHANISM_MAP_STALE`, and `CLAIM_SUPPORT_DRIFT`. Never rewrite machine state merely to clear a report; create a new verified run when required.

## Human / Machine boundary

Warn when Human prose exposes registry paths, commits, repo paths, line anchors, Fact/Claim IDs, or verification bookkeeping. `Evidence Map` should be last and human-readable. Stable `source:<id>` belongs in frontmatter; exact anchors belong in machine provenance.

## Canonical ownership

```text
solutions.md      = per-solution Reality
solution-space.md = project-wide Mechanism / Principle
focused docs      = focus-specific Reality + Mechanism
Project Home      = orientation + compressed navigation
Learning          = cross-project reusable Principle
```

Flag long semantic duplication, but do not use deduplication as a reason to strip the canonical owner. Evidence Maps and short navigation summaries are not knowledge duplication.

## Coverage / completeness integrity

Report under-documentation as seriously as unsupported claims:

- expected Solutions missing from `solutions.md`;
- a canonical owner much thinner than its declared task;
- focused docs reduced to summary cards with no concrete landscape/matrix or mechanism synthesis;
- a Project Home containing substantially more topic detail than the focused/canonical owner;
- important Evidence axes present in the Research coverage plan but absent from the finalized Human document;
- `SUSPICIOUSLY_THIN_OUTPUT` from a formal run.

Do not enforce a universal word-count target. Character thresholds are only smoke alarms.

## Semantic integrity

Review:

- fact attribution and conflicting configurations;
- writeup-only facts promoted to code-verified;
- unsupported universal claims;
- strongest counterexamples;
- contradictions caused by over-compression;
- Mechanism separation (`historical pool`, `reference-policy KL`, `behavior prior`, `teacher transfer`, `entropy` may sound related but change different variables);
- missing Negative Evidence;
- Decision Utility and Top-Principle/Transfer redundancy.

Prefer narrowing stage/scope/condition over deleting one side.

## Claim lifecycle

When durable Claims use `current | superseded | contested`, report stale or contradictory currentness. Modification time alone never establishes which claim is current.

## Maintenance patch

Small evidence updates should use targeted impact analysis rather than full-project regeneration. Before applying an Agent-generated patch, compare the target's current hash to the hash seen when the patch was planned; if it changed, stop and re-read instead of overwriting concurrent edits.

## Ownership

- `origin: human` → never overwrite automatically.
- `origin: mixed` → preserve human sections; only managed regions may be regenerated when explicitly requested.
- missing `origin` → human-owned.

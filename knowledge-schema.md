# KnowledgeOS Schema

This document defines the small durable schema. Markdown and primary source files are durable; tools generate rebuildable projections.

## Durable Knowledge Roles

- **Evidence**: repository, commit, file, writeup, paper, experiment, benchmark, or configuration under `sources/`.
- **Project**: a concrete task/codebase under `vault/projects/<ProjectName>/`.
- **Solution**: a project-specific case study, normally reconstructed inside `solutions.md`.
- **Synthesis**: multi-solution comparison and solution-space understanding, normally in `solution-space.md`.
- **Focused Project Doc**: one project direction such as training, representation, evaluation, or inference.
- **Learning**: reusable cross-project mechanism/principle under `vault/learning/`.

`Solution` and `Synthesis` are logical roles; they do not require new frontmatter types.

## Human Notes

```yaml
type: project | project-doc | learning | paper
projects:
  - "[[ProjectName]]"
domains: []
topics: []
parents:
  - "[[ParentProject]]"
derived_from:
  - "[[Source Knowledge]]"
source_refs:
  - "source:<stable-id>"
origin: human | codex | mixed
status: active | studied | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
```

`parents`, `projects`, `derived_from`, and `source_refs` are structured relation fields. Empty fields may be omitted. Physical directory hierarchy does not represent Project hierarchy.

## Project Map and Knowledge Graph

Project Map:

- includes only `type: project` nodes;
- uses only `parents` for hierarchy;
- supports multiple parents and must remain a DAG;
- derives child edges instead of storing `children`.

Knowledge Graph:

- includes Projects, Project Docs, Learning, Papers, Wikilinks, and provenance relations;
- supports search, trace, learning promotion, and maintenance.

## Canonical Human Ownership

```text
Project Home      = orientation + navigation + compressed conclusions
solutions.md      = per-solution Reality canonical source
solution-space.md = project-wide Mechanism / Principle canonical source
Focused Docs      = focus-specific Reality + Mechanism canonical source
Learning          = cross-project reusable Principle canonical source
```

Canonical ownership prevents semantic duplication, but it never permits under-documentation. A canonical owner must contain enough supported detail to fulfill its role.

## Golden Human Document Contract

`What` means Concrete Method Reconstruction: how a Solution actually runs, including the configurations whose removal would make a domain-literate reader misunderstand the method. Paths may be hidden; facts may not.

A Project-wide `solutions.md` should normally contain:

```text
Problem Model
→ Comparison Matrix
→ every expected Solution:
   Thesis
   What — Concrete Method
   Why
   Mechanism
   important Negative/Boundary
→ Evidence Map
```

A `solution-space.md` should normally contain, when supported:

```text
First-principles Problem Model
Normalized Comparison
Cross-solution Convergence
Alternative Routes
Negative Evidence
Open Questions
Mechanism Synthesis
Decision Guide
Top Principles
Transfer
Evidence Map
```

A Focused Project Doc should normally contain:

```text
Scope
Core Problem
Concrete Landscape / Matrix
Key Design Axes
Convergence / Alternatives / Negative Evidence
Mechanism Synthesis
Trade-offs
Focused Top Principles
Transfer
Evidence Map
```

These are knowledge roles, not rigid heading templates.

## Research Run Artifacts

Formal research machine state lives under:

```text
.knowledgeos/runs/<run-id>/
```

A run may contain:

```text
run.json
evidence-manifest.json
coverage-plan.json
evidence-bindings.jsonl
facts.jsonl
facts.verify.jsonl
claims.jsonl
claims.verify.jsonl
mechanisms.jsonl
mechanisms.verify.jsonl
gate.json
draft.md
draft-trace.json
draft.verify.json
report.json
```

All are derived and rebuildable.

### Coverage Plan

`coverage-plan.json` is the anti-under-documentation contract. Minimal shape:

```json
{
  "document_kind": "solutions",
  "expected_entities": ["R1", "R2"],
  "required_axes_by_entity": {
    "R1": ["model", "action", "training"],
    "R2": ["model", "action", "training"]
  },
  "min_facts_per_entity": 3,
  "output_contract": {
    "required_sections": ["Evidence Map"],
    "required_entity_labels": ["R1", "R2"],
    "min_chars_warning": 3000
  }
}
```

The tool checks expected entity and required-axis Fact coverage before Facts can pass. Required axes must be selected from the actual task/Evidence; irrelevant axes should not be invented.

`min_chars_warning` is only a smoke-test tripwire, never a quality target.

### Fact Coverage

Facts may include an optional `axis` field used by the Coverage Gate:

```json
{
  "fact_id": "F-R3-014",
  "solution_id": "R3",
  "axis": "action",
  "subject": "action.semantic_intent",
  "statement": "...",
  "evidence_ids": ["EV-R3-014"],
  "evidence_type": "author_stated"
}
```

Important descriptive Facts remain useful even if they never become cross-solution Claims.

## Provenance Contract

Human Markdown uses stable source identities only:

```yaml
source_refs:
  - source:<stable-id>
```

Machine provenance stores source ID, repository revision, path, line range, excerpt hash, Fact, and Claim under Research Runs, registry metadata, and derived provenance indexes. Human notes do not use `repo://<commit>/<path>` as canonical `source_refs`.

Permanent **machine** provenance may use:

```text
repo: <registry-id>
commit: <hash>
path: relative/path
symbol: optional-symbol
lines: optional-line-range
```

Machine-only repository references may use `repo://<registry-id>@<commit>/<path>#L<line>`. Legacy Human refs remain readable for migration and may trigger warnings.

## Claim Schema and Lifecycle

Important machine Claims reference Facts, not raw Evidence. Durable high-value Claims may include:

```text
claim_id
claim_type
statement
support_fact_ids
counter_fact_ids
eligible_entities
coverage_mode
boundary
durable
status: current | superseded | contested
superseded_by: optional claim_id
```

Claim currentness is semantic lifecycle metadata, not file modification time.

`claims.yaml` is not independently authored knowledge. When present, it is generated from the latest active verified canonical `solution-space` run and carries run/hash metadata. A newer canonical finalization makes an older ledger stale even if its timestamp is recent; manual content edits make it drift. Absence is preferable to a stale ledger.

## Rebuildability

Indexes, Research Runs, caches, Graph/Vector/BM25 state, and lint reports belong in `.knowledgeos/`. Deleting `.knowledgeos/` must never delete durable knowledge, Evidence, registry identity, or the tools required to rebuild them.

# KnowledgeOS Schema

This document defines the small durable schema. Markdown and source files are the facts; tools generate projections.

## Durable Nodes

- Evidence: repository, commit, file, writeup, paper, experiment, benchmark, or configuration under `sources/`.
- Project: a concrete task or codebase under `vault/projects/<ProjectName>/`.
- Solution: a project-specific case study, normally in `solutions.md`.
- Synthesis: multi-solution comparison and solution-space understanding, normally in `solution-space.md`.
- Learning: reusable mechanism or principle under `vault/learning/`.

`Solution` and `Synthesis` are logical knowledge roles. They may remain sections in project-doc notes and do not require standalone frontmatter `type` values.

Project notes should optimize for human understanding: What, Why, Mechanism, principles, transfer. Detailed repository, commit, path, symbol, line, source type, confidence, and verification state belong to structured provenance and derived indexes. Generated project Markdown ends with a concise Evidence Map that names sources without path dumps.

Workspace output preference is stored in `knowledge-config.yaml`; it is presentation configuration, not a durable node property. `output_style` may be `english` or `zh_en_terms` and does not affect canonical IDs, relationships, or provenance.


Project Map:
- includes only `type: project` nodes;
- uses only `parents` for hierarchy;
- supports multiple parents and must remain a DAG;
- derives child edges rather than storing children.

Knowledge Graph:
- includes all knowledge nodes and provenance relations;
- supports search, trace, learning promotion, and maintenance.

Physical directory hierarchy does not represent project hierarchy. Project hierarchy is expressed only by `parents`.


## Human and Evidence Layers

Human Knowledge Layer is Project, Solution, Synthesis, and Learning Markdown. Machine Evidence Layer is registry, source_refs, graph, provenance-index, and source anchors. They describe the same evidence without requiring detailed anchors in the reading flow.

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
  - "repo://<id>@<commit>/<path>#L<line>"
origin: human | codex | mixed
status: active | studied | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
```

`parents`, `projects`, `derived_from`, and `source_refs` are the structured relation fields. Empty fields may be omitted. Do not create duplicate notes for classification.


## Portable Provenance

Permanent notes use repository-relative references:

```text
repo: <registry-id>
commit: <hash>
path: relative/path
symbol: optional-symbol
lines: optional-line-range
```

or `repo://<registry-id>@<commit>/<path>#L<line>`. Machine-local paths belong only in `registry/`.

## Provenance Authority

`source_refs` in frontmatter is the authoritative machine-readable provenance. Inline `repo://`, `writeup://`, `paper://`, and `experiment://` references in note bodies are informative reading aids and are linted separately; they do not create reverse-provenance edges. Canonical repository references use:

```text
repo://<registry-id>@<commit>/<relative-path>
repo://<registry-id>@<commit>/<relative-path>::<symbol>#L10-L30
writeup://<source-id>
paper://<source-id>
experiment://<source-id>
```

Legacy `writeup:<id>` and similar forms may be read for compatibility, but new durable notes should use the canonical form.


Rebuildable indexes and caches belong in `.knowledgeos/`. Deleting `.knowledgeos/` must not delete knowledge or evidence.

---
name: maintain
description: Run a report-first KnowledgeOS integrity and source-drift audit when the user asks to check, update, sync, lint, stale, or maintain knowledge.
---

# Maintain

## Language Mode

Read `knowledge-config.yaml` when composing report text. Follow `output_style: english` or `output_style: zh_en_terms`; an explicit user instruction overrides it. Keep machine-readable report fields stable.

Maintain is report-first. Do not silently modify notes, registry, sources, or Obsidian files.

1. Run `python3 tools/knowledgeos.py lint` for link, frontmatter, provenance, and path issues.
2. Run `python3 tools/knowledgeos.py maintain` for registry ingested-head versus local Git HEAD drift.
3. For drift, report changed files, direct impacted notes from authoritative `source_refs`, and transitive impacts through `derived_from`.
4. Check duplicate Learning, missing promotion evidence, unresolved claims, and human-owned note boundaries as review items; do not pretend deterministic lint proves semantic freshness.
6. Run output-style review items in report-only mode: Evidence Map position, legacy `Evidence and limits`, path-heavy prose, missing Project Home sections, and missing Top 3 Principles.

Structured `source_refs` are authoritative; inline source references are reading aids. Use the deterministic tool rather than implementing Git diff, provenance indexing, or graph parsing here.

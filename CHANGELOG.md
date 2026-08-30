# Changelog

All notable changes to KnowledgeOS are documented here.

## [0.2.1] - 2026-08-30

- Calibrated OrbitWars historical-opponent claims: SimJeg is recorded as having experimented with a frozen-checkpoint pool and removing it from the final run, not as explicitly regretting its removal.
- Reworded simulator-throughput synthesis to preserve the strong engineering convergence without unsupported universal/causal claims such as “no rewrite means no large-scale training.”
- Removed the Human-facing `范围限制` audit section from `solutions.md`; source-coverage and verification details remain machine/provenance concerns while knowledge-relevant caveats stay local to the relevant method.
- Hardened `claims.yaml` lifecycle: the ledger is generated only from a verified canonical `solution-space` run, stale ledgers are detected against the latest active finalization, and a newer canonical run with no durable Claims removes any older generated ledger.
- Added Golden Reference regression checks for the above content and lifecycle rules.

## [0.2.0] - 2026-08-29

- Added Research `coverage-plan.json`, Fact Coverage Gate, and Human Draft Completeness Gate to prevent verification-induced under-documentation.
- Added `Precision + Coverage + Synthesis` as the formal knowledge-quality objective.
- Added suspiciously-thin output warnings as smoke tests without turning word count into a target.
- Updated `summarize`, `compare`, `maintain`, and `search` Skills for dense Human reconstruction, canonical ownership, claim lifecycle, and read-only graph context.
- Restored OrbitWars `solutions.md`, `solution-space.md`, `ppo-training.md`, and `representation-design.md` as high-density Golden Reference documents while preserving calibrated claims and stable source IDs.
- Added tests for missing entity/axis coverage and Human draft completeness.

## [0.1.0] - 2026-08-26

- Initial public release of the KnowledgeOS design and deterministic tooling.
- Added four focused Agent Skills: `search`, `summarize`, `compare`, and `maintain`.
- Added Markdown-first schema, provenance rules, Project Map, Knowledge Graph, BM25 search, and rebuildable projections.
- Added optional Hybrid Vector Search V1 with local provider support.
- Added MIT and Apache-2.0 licensing options.

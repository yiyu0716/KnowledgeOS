# KnowledgeOS

KnowledgeOS is a long-term evidence-backed personal knowledge system. Its core loop is:

```text
Evidence -> Understanding -> Mechanism -> Transfer -> Reusable Learning
```

Workspace: `.`

## Web Research

Use Exa MCP proactively when current or external information materially improves a task. Prefer `web_search_exa` for discovery and `web_fetch_exa` when full source contents are needed. Prefer primary sources and cross-check important technical claims. Do not rely on memory for changeable facts. If Exa is unavailable, use the best available read-only web tool and state the limitation.

## Core Layout

```text
vault/{inbox,learning,papers,projects,archive}
sources/{repos,papers}
registry/
.knowledgeos/        # rebuildable derived state only
```

Folder is content type; Properties classify; Wikilinks express relationships; Bases are views. Do not create domain folders such as `agent/`, `kaggle/`, or `rl/`.

## Source of Truth and Safety

Read [`knowledge-policy.md`](knowledge-policy.md) for source authority, write boundary, human knowledge protection, repository safety, and four-skill routing. Read [`knowledge-schema.md`](knowledge-schema.md) for the durable node, relation, Properties, provenance, and derived-state schema.

- `sources/` is primary evidence; generated Markdown is not a replacement for it.
- `sources/repos/` repositories are read-only by default. Do not edit, commit, push, reset, clean, or change dependencies during learning.
- Before durable repository knowledge, record remote, branch, HEAD, and working-tree state. Do not imply a commit fully describes dirty code.
- Never store secrets or credentials.
- Preserve human-owned notes. Missing `origin` is human-owned; never silently overwrite `origin: human` or mixed content.
- Do not modify `.obsidian/` or existing `.base` files unless explicitly requested.
- Do not use ranking differences as causal evidence; label Verified, Inferred, and Unverified.

## KnowledgeOS Write Boundary

Inspection, explanation, comparison, and discussion are read-only. Write to KnowledgeOS only when the user explicitly asks to save, record, ingest, summarize into KnowledgeOS, create/update project knowledge or learning, or synchronize knowledge. Do not commit or push KnowledgeOS changes unless explicitly requested.

## Four Skills

KnowledgeOS has four focused workflows: `search`, `summarize`, `compare`, and `maintain`. Load the matching Skill for the task; do not duplicate their workflows here. Read `knowledge-config.yaml` for the user's Human-facing output language. Concrete schema is in `knowledge-schema.md`; safety rules are in `knowledge-policy.md`.

## Multi-Solution Output

For a complex project, prefer a few high-value files. **Do not optimize for shortness**: formal research must satisfy Precision + Coverage + Synthesis, with a coverage plan before Fact freeze and a completeness check before finalize.


- `<ProjectName>.md`: Problem Model, evidence map, Solutions, Synthesis, Related Learning.
- `solutions.md`: unified individual Solution reconstruction; every expected Solution must remain concretely understandable.
- `solution-space.md`: Convergence, Alternatives, Negative Evidence, Open Questions, Mechanism Synthesis, Decision Guide, Top Principles, and Transfer.
- `claims.yaml`: optional claim-level ledger for important or controversial cross-solution claims.

Use a compact comparison matrix **plus** dense per-solution reconstruction. Track implementation, motivation, effectiveness, and transfer confidence separately. Run Evidence, Coverage, Synthesis, Red-team, and Human Completeness passes. Do not create one file per solution unless it materially improves understanding.

## Learning Promotion

Learning is the system center and should answer: “What should I remember for a future problem?” Promote only when a mechanism has a recognizable problem signature, real evidence, use conditions, boundaries/failure conditions, and cross-project potential. Update an existing Learning note when the mechanism recurs; do not create duplicate Learning notes.

## Deterministic Tools

Tools are projections over Markdown and source metadata, not facts. Keep them dependency-light and independently rebuildable:

- local BM25 search;
- Markdown/Properties/Wikilink graph parsing;
- reverse source provenance index;
- lint for links, frontmatter, absolute paths, source references, and stale commits.

No PostgreSQL, vector database, Neo4j, Redis, MCP server, web UI, complex ontology, repo watcher, or automatic web research in the core system unless explicitly requested.

## Completion

For repository learning or ingestion, report analyzed repository/commit, inspected areas, KnowledgeOS files changed, unresolved/unverified areas, and whether source repositories were modified. Do not claim complete coverage unless achieved.

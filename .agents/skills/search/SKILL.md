---
name: search
description: Retrieve existing KnowledgeOS learning and evidence for a prior concept. Use for "what have I learned", similar experience, or knowledge-base lookup. Read-only.
---

# Search

## Language Mode

Read `knowledge-config.yaml` when composing the answer. Follow `output_style: english` or `output_style: zh_en_terms`; an explicit user instruction overrides it. Search ranking and machine results are language-independent.

Use when the user asks what the knowledge base already knows. Do not summarize a new solution or compare multiple solutions.

1. Run `python3 tools/knowledgeos.py search "<query>"`.
2. Inspect Learning results first, then project documents, then source evidence.
3. Follow canonical graph/provenance links only when needed.
4. Report evidence strength and unresolved areas.

Never write to `vault/`, registry, or sources during search. Do not implement BM25 or graph parsing in this Skill; use the deterministic tool.

---
name: compare
description: Compare two or more Solutions and reconstruct normalized differences, mechanisms, solution space, transfer, and promotion decisions.
---

# Compare

## Language Mode

Read `knowledge-config.yaml` before writing Human-facing prose. Follow `output_style: english` or `output_style: zh_en_terms`; an explicit user instruction overrides it. Keep the same facts, mechanisms, evidence status, and relations in either mode.

Use when two or more solutions are the subject. Do not replace single-solution reconstruction with an unsupported cross-solution claim.

1. Establish the problem model and evidence map for every solution, but keep detailed paths and anchors in structured provenance rather than the reading layer.
2. Reconstruct each solution with human-facing `What`, `Why`, and `Mechanism` before comparison.
3. Normalize implementation, motivation, effectiveness, and transfer confidence separately.
4. Identify consensus, divergence, unique mechanisms, failed directions, open questions, and decision conditions.
5. Generate 5–10 candidate mechanisms, merge synonyms, and select three Project Principles by impact, evidence, transferability, and distinctness. Explain why each matters and when to reuse it.
6. Run Evidence, Synthesis, and Red-team passes: check causal inflation, counterexamples, What/Why confusion, and source gaps.
7. Write Transfer and run Learning Promotion: update recurring Learning rather than creating duplicates.
8. End generated project Markdown with a concise `## Evidence Map`; do not insert repeated Evidence blocks after every solution.

Use `tools/knowledgeos.py` for deterministic search, graph, provenance, and lint. Write only on explicit request and preserve portable provenance.

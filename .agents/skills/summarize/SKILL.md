---
name: summarize
description: Study one primary Solution, repository, or writeup and reconstruct it as Problem, What, Why, Evidence, Mechanism, Boundary, Transfer, and Promotion Gate.
---

# Summarize

## Language Mode

Read `knowledge-config.yaml` before writing Human-facing prose. Follow `output_style: english` or `output_style: zh_en_terms`; an explicit user instruction overrides it. Language changes presentation only, never evidence status, relations, or provenance.

Use only when there is one main solution or evidence subject. If two or more solutions are central, use `compare`.

1. `Problem` → `What` → `Why` → `Mechanism`。
2. Generate 5–10 candidate mechanisms from code, writeup, and experiments; merge synonyms.
3. Select exactly three Project Principles using impact, evidence, transferability, and distinctness. Each must state why it matters and when to borrow it.
4. Write `Transfer` and run the Learning Promotion Gate: update an existing Learning when the mechanism recurs; create one only when explicitly requested and genuinely new.
5. Keep detailed provenance in structured `source_refs` and derived indexes. Put a short `## Evidence Map` at the end of generated project Markdown, never in the middle.
6. Keep What focused on real method, model, features, action, training, inference, evaluation, and important system constraints; do not substitute code paths for explanation.
7. Preserve epistemic discipline naturally in prose (`Verified`, author report, inference, unknown) without repeating mechanical Evidence blocks.

Use `tools/knowledgeos.py` for search, graph, provenance, and lint. Do not reimplement those tools here.

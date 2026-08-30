---
name: compare
description: Reconstruct and compare two or more Solutions, or synthesize a project Solution Space, with evidence coverage, deterministic Research Gate verification, and a high-density Human completeness contract.
---

# Compare

Use when two or more Solutions are central. Do not write project research Markdown directly from raw sources.

## Objective

```text
Precision + Coverage + Synthesis
```

The Gate must prevent both unsupported claims **and** verification-induced under-documentation. A short document is not automatically a good document.

## Required Research Run

```bash
python3 tools/knowledgeos.py research init <run-id> --project <project> --scope <scope>
python3 tools/knowledgeos.py research verify <run-id>        # repeat until WRITE_ALLOWED
python3 tools/knowledgeos.py research verify-draft <run-id>  # structural pass, then full pass
python3 tools/knowledgeos.py research finalize <run-id> <target.md>
```

### 1. Coverage Plan first

Before Fact extraction, write `coverage-plan.json` from the task and Evidence:

- expected Solutions/entities;
- important axes for each entity where Evidence exists;
- a reasonable minimum Fact floor;
- Human output contract: required knowledge roles/sections and expected entity labels;
- optional `min_chars_warning` only as a smoke-test tripwire.

Do **not** use word count as the research target. Use knowledge units.

### 2. Evidence / Reality pass

1. Build `evidence-manifest.json` from stable source IDs.
2. Inspect real code, tests, configs, writeups, experiments, and evaluation artifacts.
3. Extract dense `facts.jsonl`; no synthesis yet.
4. Every expected Solution must have enough supported Facts to recover its mental model. Important axes must not be skipped because they increase verification work.
5. Semantically verify high-risk/Core Facts against bound Evidence, satisfy the Coverage Gate, and freeze Facts.

Typical axes may include `thesis`, `representation`, `model`, `action`, `training`, `opponent/data distribution`, `inference/system`, `why`, `mechanism`, and `negative/boundary`. Use only the axes relevant to the actual project.

### 3. Synthesis pass

Using verified Facts only:

- build normalized comparison;
- classify Cross-solution Convergence / Alternative Routes / Negative Evidence / Open Questions;
- map `intervention → changed_variable → expected_effect`;
- build Decision Guide / cheapest falsification experiments where useful;
- generate bounded Top Principles and Transfer.

Implementation similarity is not mechanism similarity. Do not infer causality from rank or co-occurrence.

### 4. Human completeness

Canonical owners must be independently useful:

- `solutions.md` = full per-solution Reality. Every expected Solution gets Thesis + concrete What + Why + Mechanism; useful details do not need to become Claims to remain in the document.
- `solution-space.md` = project-wide synthesis. Preserve Convergence, Alternatives, Negative Evidence, Open Questions, Mechanism Synthesis, Decision Guide, Top Principles, and Transfer when Evidence supports them.
- Focused docs = high-density scoped comparison, not summary cards. Preserve Scope, concrete matrix/landscape, key axes, mechanisms, trade-offs, focused principles, and Transfer.

The exact headings may vary, but missing expected entities/roles is `DOCUMENT_COMPLETENESS_FAIL`.

### 5. Red-team / finalization

Before finalization check unsupported facts, attribution, universal wording, missing counterexamples, contradictions, mechanism conflation, stale hashes, machine-path leakage, canonical duplication, and **under-documentation**. `SUSPICIOUSLY_THIN_OUTPUT` is a warning that requires review, not a target to game.

Only `research finalize` may write formal target Markdown. Final Markdown is Human-first and never exposes Fact/Claim IDs, hashes, run IDs, registry paths, or verification prose.

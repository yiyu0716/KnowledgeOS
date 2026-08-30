---
name: summarize
description: Reconstruct one primary Solution, repository, writeup, paper, or project subtopic into a faithful, high-density, provenance-backed Human summary; use the Research Gate for durable complex writes.
---

# Summarize

Use for one main evidence subject. If two or more Solutions are central, route to `compare`.

## Modes

- Standard: one solution/repository/writeup/paper.
- Focused: one subject and one direction such as training, representation, or evaluation.

## Quality objective

Do not optimize for the shortest safe answer. Optimize:

```text
Precision + Coverage + Synthesis
```

A summary that omits important supported facts to reduce verification work is a failure. `Paths may be hidden; facts may not.`

## Formal durable run

For high-value, complex, multi-source Project Knowledge, use the Research Gate:

```bash
python3 tools/knowledgeos.py research init <run-id> --project <project> --scope <scope>
python3 tools/knowledgeos.py research verify <run-id>        # repeat through WRITE_ALLOWED
python3 tools/knowledgeos.py research verify-draft <run-id>  # structure, then final verification
python3 tools/knowledgeos.py research finalize <run-id> <target.md>
```

Required sequence:

1. Read the parent Project and primary Evidence.
2. Write `evidence-manifest.json` and a `coverage-plan.json` before extracting Facts.
3. Extract **dense** concrete Facts. Preserve the method/configuration details required to recover how the Solution works; group low-risk descriptive details coherently rather than atomizing every sentence.
4. Satisfy the Coverage Gate, then semantically verify high-risk/Core Facts against bound Evidence and freeze Facts.
5. Build Claims/Mechanisms only from verified Facts; keep Facts that are useful for Reality even when they do not support a cross-solution Claim.
6. Require `WRITE_ALLOWED`.
7. Write the Human Draft from verified artifacts only.
8. Pass the Completeness Gate; required knowledge roles/entities may not disappear merely to make the draft shorter.
9. Finalize.

If any stage fails, stop and repair that stage.

## Human summary

Build:

```text
Problem → Thesis → What → Why → Mechanism → Negative/Boundary → Transfer
```

For a durable one-solution note, prefer:

```markdown
# <Solution>
## Thesis
## Problem
## What — Concrete Method
## Why
## Mechanism
## Negative Evidence / Trade-offs
## Transfer
## Evidence Map
```

`What` is concrete method reconstruction. Include real model/action/data/training/inference/system configurations whose removal would make a domain-literate reader misunderstand the solution. `Why` distinguishes author statement, code observation, inference, and unknown.

A Focused summary must retain enough concrete facts to be independently useful; it is not a compressed pointer to `solutions.md`.

Keep detailed provenance in machine state, not path dumps in the body. Learning Promotion runs only after the Human document is complete.

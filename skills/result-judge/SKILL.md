---
name: result-judge
description: "Trusted workflow stage for judging experimental results. Use after implementation_plan when experiment results are available."
argument-hint: [research/current/experiment_results.md]
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# /result-judge

## What it is

`/result-judge` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not call models directly, and does not produce trusted conclusions on its own.

It maps to the `result_judge` workflow stage defined in `configs/workflows/research_default.yaml`.

## How it works

The skill guides result judgment through the trusted workflow chain. The stage must validate PASS before any downstream paper writing or result claiming.

```
experiment_results.md (temporary human/experiment input)
  → result_judge stage
  → research/current/trusted_outputs/result_judge.md (validate PASS)
  → (if allowed_next_stage=true → paper writing or next phase)
```

Each step uses `tools/research_workflow.py prepare result_judge` followed by `tools/trusted_role_runner.py` and `validate_model_invocation.py --role result_judge`. No stage may be skipped or bypassed.

## What the skill does NOT do

- Does NOT run experiments directly
- Does NOT modify code directly
- Does NOT write papers directly
- Does NOT beautify or polish results
- Does NOT produce paper claims directly
- Does NOT call any model except through trusted_role_runner
- Does NOT bypass `validate_model_invocation.py`
- Does NOT treat mock/dry-run as real experimental results
- Does NOT cherry-pick favorable metrics
- Does NOT loosen judgment because user wants to publish

## Hard rules

- Result insufficient → output `inconclusive`
- Do NOT treat mock/dry-run as real experimental results
- Do NOT cherry-pick only favorable metrics
- Do NOT loosen judgment because user wants to publish a paper
- `allowed_next_stage=false` → stop immediately
- No `validate_model_invocation.py PASS` = no trusted output

## Output structure

`research/current/trusted_outputs/result_judge.md` must contain:

### Result Summary
Brief neutral summary of what the experiment produced.

### Metrics Checked
List of all metrics evaluated (not just favorable ones).

### Comparison Against Experiment Plan
How results compare to what experiment_plan predicted or targeted.

### Supports Claim: yes / no / inconclusive
Binary judgment on whether results support the research claim.

### Failure Modes
What could explain a negative or inconclusive result (experiment design, implementation bug, assumption violated, etc.).

### Evidence Gaps
What evidence is missing to make a firm judgment.

### Allowed Next Step
What the workflow recommends next (if any), given the judgment.

## Resume / Interruption

If the workflow is interrupted, recovery must use artifact file state, not chat memory. Check `research/current/trusted_outputs/result_judge.md` for the last validated stage. Do not re-run completed stages unless the user explicitly requests it.

## Legacy Artifacts

Old experiment summaries, external agent result claims, or chat-based result assessments are **not** part of the current trusted workflow. They must not be mixed into new workflow runs unless the user explicitly imports specific content.

## Key Rules

- Each stage requires `validate_model_invocation.py PASS` before proceeding
- `allowed_next_stage=false` stops the workflow immediately
- Do not substitute chat memory or external agent summaries for trusted outputs
- External agents must not bypass `tools/research_workflow.py` to call models directly

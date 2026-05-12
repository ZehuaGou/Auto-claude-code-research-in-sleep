---
name: paper-writing
description: "Trusted workflow stage for drafting papers from verified artifacts and judged results. Use after result_judge when results have been validated."
argument-hint: [research/current/trusted_outputs/result_judge.md]
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# /paper-writing

## What it is

`/paper-writing` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not call models directly, and does not produce trusted conclusions on its own.

It maps to the `paper_writing` workflow stage defined in `configs/workflows/research_default.yaml`.

## How it works

The skill drafts a paper only from verified research artifacts. The stage must validate PASS before the paper can be treated as trusted.

```
research/current/trusted_outputs/ (all verified stages)
  → paper_writing stage
  → research/current/trusted_outputs/paper_draft.md (validate PASS)
```

Each step uses `tools/research_workflow.py prepare paper_writing` followed by `tools/trusted_role_runner.py` and `validate_model_invocation.py --role paper_writer`. No stage may be skipped or bypassed.

## What the skill does NOT do

- Does NOT directly judge results — that is the `result_judge` stage
- Does NOT directly run additional experiments
- Does NOT fabricate contributions not present in trusted outputs
- Does NOT cite papers not recorded in `literature_search.md`
- Does NOT rewrite inconclusive or negative results as positive
- Does NOT treat user preference, chat summary, or external agent summary as paper facts
- Does NOT call any model except through trusted_role_runner
- Does NOT bypass `validate_model_invocation.py`

## Hard rules

- If `result_judge` output is `no` or `inconclusive`, the paper must honestly report negative or inconclusive results — no packaging as success
- Do NOT introduce core claims not present in any trusted output
- Do NOT treat user preference, chat summary, or external agent summary as facts
- Do NOT cite papers not recorded in `literature_search.md`
- Do NOT rewrite inconclusive results as positive
- `allowed_next_stage=false` → stop immediately
- No `validate_model_invocation.py PASS` = no trusted output

## Output structure

`research/current/trusted_outputs/paper_draft.md` must contain:

### Title
Paper title reflecting the actual contribution.

### Abstract
Neutral summary of problem, method, and findings.

### Introduction
Motivation, gap, and contribution statement grounded in research_contract and novelty_check.

### Related Work
Literature from `literature_search.md` only — no uncited prior work.

### Method
Description drawn from experiment_plan and implementation_plan.

### Experiments
Results drawn from `result_judge.md` — honest reporting, not cherry-picked.

### Results
Objective reporting of metrics checked in result_judge.

### Limitations
Honest limitations identified by result_judge or experiment_plan.

### Conclusion
Conclusion consistent with Supports Claim judgment in result_judge.

### Claims Checklist
Each claim must trace to a verified trusted output source.

## Resume / Interruption

If the workflow is interrupted, recovery must use artifact file state, not chat memory. Check `research/current/trusted_outputs/paper_draft.md` for the last validated stage. Do not re-run completed stages unless the user explicitly requests it.

## Legacy Artifacts

Old external agent paper drafts, chat-based result summaries, or unverified claims are **not** part of the current trusted workflow. They must not be mixed into new workflow runs.

## Key Rules

- Each stage requires `validate_model_invocation.py PASS` before proceeding
- `allowed_next_stage=false` stops the workflow immediately
- Do not substitute chat memory or external agent summaries for trusted outputs
- External agents must not bypass `tools/research_workflow.py` to call models directly

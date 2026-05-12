---
name: idea-discovery
description: "Trusted workflow entry for turning a raw research direction into controlled research artifacts. Use when user says \"找idea\"、\"idea discovery\"、\"从零开始找方向\"."
argument-hint: [research-direction]
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# /idea-discovery

## What it is

`/idea-discovery` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not directly call any model, and does not produce trusted conclusions on its own.

It maps to the trusted research workflow stages defined in `configs/workflows/research_default.yaml`.

## How it works

The skill guides a raw user research direction through the trusted workflow chain. Each stage must validate PASS before the next stage can begin.

```
用户研究方向
  → 写入 research/current/raw_user_input.md
  → /input-normalization
  → research/current/input_normalization.md (validate PASS)
  → /research-contract
  → research/current/trusted_outputs/research_contract.md (validate PASS)
  → /literature-search
  → research/current/trusted_outputs/literature_search.md (validate PASS)
  → /novelty-check
  → research/current/trusted_outputs/novelty_check.md (validate PASS)
  → /experiment-plan
  → research/current/trusted_outputs/experiment_plan.md (validate PASS)
  → /implementation-plan
  → research/current/trusted_outputs/implementation_plan.md (validate PASS)
```

Each step uses `tools/research_workflow.py prepare <stage>` followed by `tools/trusted_role_runner.py` and `validate_model_invocation.py --role <role>`. No stage may be skipped or bypassed.

## What the skill does NOT do

- Does NOT organize the final prompt sent to any model
- Does NOT directly call DeepSeek, Codex, OpenAI, or any other model
- Does NOT directly perform literature search — that is the `literature_search` stage
- Does NOT directly make novelty judgments — that is the `novelty_check` stage
- Does NOT directly generate ideas — current MVP workflow does not include an `idea_generation` stage
- Does NOT produce trusted conclusions on its own
- Does NOT bypass `validate_model_invocation.py`

## Current MVP limitations

The current trusted workflow covers these stages:

1. `input_normalization` — normalize raw user input
2. `research_contract` — lock research boundaries
3. `literature_search` — gather literature evidence
4. `novelty_check` — verify novelty
5. `experiment_plan` — design experiment
6. `implementation_plan` — plan implementation

**The MVP does NOT yet include:**
- `idea_generation` stage (generating candidate ideas from scratch)
- `final_selection` stage (selecting the best idea among candidates)

Until those stages exist in `configs/workflows/research_default.yaml`, `/idea-discovery` cannot produce candidate ideas through the trusted workflow. Extending the workflow requires updating the config, not modifying this skill.

## Method Notes

The following principles are retained as research guidance. They do not replace or execute the old phases pipeline.

### Gap Finding Principles

- Identify structural gaps: missing combinations, failed approaches, underexplored sub-problems
- Look for recurring limitations in existing work that suggest open problems
- Cross-domain analogies can reveal gaps in one field from solutions in another

### Candidate Idea Quality Criteria

- Hypothesis must be falsifiable
- Scope must be bounded (not "improve NLP")
- Method approach must be specified at least at intuition level
- Risk must be acknowledged (what could make this fail)

### Review Criteria (for stages that support it)

- Verify each claim has supporting evidence or clear reasoning
- Reject ideas where method overlap with prior work is too high
- Accept `already_done` or `insufficient_evidence` verdicts without resistance

### Novelty Caution Rules

- Absence of search results does NOT confirm novelty
- A single prior work that covers the core claim kills the idea
- `insufficient_evidence` means more literature work is needed — do NOT treat as confirmed novel
- Only `confirmed_novel` with identified delta is sufficient to proceed

### Evidence Discipline

- All literature evidence must cite: title, authors, year, source URL
- Search results are candidate evidence, not confirmed evidence
- Claims must be backed by method sections, not just abstracts

### Failure Is Valid Output

- `no strong idea found` is a legitimate workflow output
- Better to kill a bad idea early than to proceed with a flawed one
- Document dead ends — they are valuable for future sessions

## Resume / Interruption

If the workflow is interrupted, recovery must use artifact file state, not chat memory. Check `research/current/trusted_outputs/` for the last validated stage. Do not re-run completed stages unless the user explicitly requests it.

## Legacy Artifacts

Old `idea-stage/AGENTIC/` artifacts from previous sessions are **not** part of the current trusted workflow. They should not be mixed into new workflow runs unless the user explicitly imports specific content.

## Key Rules

- Each stage requires `validate_model_invocation.py PASS` before proceeding
- `allowed_next_stage=false` stops the workflow immediately
- Do not substitute chat memory or external agent summaries for trusted outputs
- External agents must not bypass `tools/research_workflow.py` to call models directly

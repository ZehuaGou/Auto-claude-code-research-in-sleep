---
name: input-normalization
description: Normalize raw user input into structured brief and candidate idea via trusted workflow. Use when user provides a research direction or raw idea that needs structuring.
argument-hint: [research/current/raw_user_input.md]
allowed-tools: Bash(*), Read, Write, Grep, Glob
---

# /input-normalization

## What it is

`/input-normalization` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not call models, and does not produce trusted conclusions directly.

It maps to the `input_normalization` workflow stage and delegates everything to the ARIS workflow stack.

## User invocation

```
/input-normalization
```

The skill reads `research/current/raw_user_input.md` and produces `research/current/input_normalization.md`.

## How it works

1. User invokes `/input-normalization`
2. Skill maps the request to the `input_normalization` workflow stage
3. Skill calls `tools/research_workflow.py prepare input_normalization`
4. `context_isolation_check.py` scans inputs — FAIL stops execution
5. `trusted_role_runner.py` executes `input_normalizer` role (DeepSeek API)
6. `validate_model_invocation.py --role input_normalizer` — PASS means normalization is verified
7. If `allowed_next_stage=false`, the skill stops

## Output structure

`research/current/input_normalization.md` must contain these sections:

### Normalized Brief
Structured summary of the user's research direction.

### Candidate Idea
Core research idea or hypothesis extracted from user input.

### Scope Boundaries
Explicit boundaries of what the user is and is not interested in.

### Assumptions
Assumptions explicitly stated by the user.

### What Was Not Inferred
Explicit list of what the normalizer did NOT infer or add.

## What the skill does NOT do

- Does NOT organize the final prompt sent to the model
- Does NOT select the model or backend
- Does NOT directly call Codex, DeepSeek, or any other model
- Does NOT produce a trusted conclusion on its own
- Does NOT bypass `validate_model_invocation.py`
- Does NOT add external knowledge not present in raw_user_input.md
- Does NOT evaluate research merit or novelty
- Does NOT treat user preferences as research facts

## Hard rules

- No `validate_model_invocation.py` PASS = no trusted output
- `allowed_next_stage=false` = stop immediately
- Do not add key facts not said by the user
- Do not treat old experiments, old conclusions, or user preferences as research facts
- Do not produce a "brief" without going through the workflow stack

## Forbidden context (what must NOT appear in the output)

- Old conclusions
- Previous experiment results
- Mock results
- External agent direct output
- User preference shortcuts
- Unverified literature conclusions
- Generator trace
- Other candidates

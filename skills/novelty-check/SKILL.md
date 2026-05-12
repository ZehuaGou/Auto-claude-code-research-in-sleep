---
name: novelty-check
description: Verify research idea novelty against recent literature. Use when user says "查新", "novelty check", or wants to verify a research idea is novel.
argument-hint: [CAND_XXX or free-text idea description]
allowed-tools: Bash(*), Read, WebSearch, WebFetch, Grep, Glob, Skill
---

# /novelty-check

## What it is

`/novelty-check` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not call models, and does not produce a trusted verdict directly.

It maps to the `novelty_check` workflow stage and delegates everything to the ARIS workflow stack.

## User invocation

```
/novelty-check CAND_001        # canonical mode
/novelty-check "a method that..."  # ad hoc mode
```

**Canonical mode**: uses a CAND idea file as input.
**Ad hoc mode**: free-text idea description. Ad hoc output must NOT enter IDEA_BANK or produce a final verdict.

## How it works

1. User invokes `/novelty-check "..."`
2. Skill maps to the `novelty_check` workflow stage
3. Skill calls `tools/research_workflow.py prepare novelty_check`
4. `context_isolation_check.py` scans inputs — FAIL stops execution
5. `trusted_role_runner.py` executes `novelty_checker` role (Codex MCP)
6. `validate_model_invocation.py --role novelty_checker` — PASS means the novelty verdict is verified
7. If `allowed_next_stage=false`, the skill stops

## Verdict types

The `novelty_checker` role produces one of:
- `confirmed_novel` — genuinely new, proceed
- `likely_incremental` — minor variation, assess carefully
- `already_done` — already published, **stop here**
- `insufficient_evidence` — cannot determine, do NOT treat as confirmed novel

## What the skill does NOT do

- Does NOT organize the final prompt sent to the model
- Does NOT select the model or backend
- Does NOT directly call Codex or any other model
- Does NOT produce a trusted verdict on its own
- Does NOT bypass `validate_model_invocation.py`
- Does NOT treat `insufficient_evidence` as `confirmed_novel`

## Workflow stage

- **stage**: `novelty_check`
- **role**: `novelty_checker`
- **provider**: `codex` (MCP backend)

## Trusted output

Only the ledger entry produced by `trusted_role_runner.py` + `validate_model_invocation.py` PASS constitutes a trusted novelty verdict. Any output before that gate is not a trusted artifact.

## Hard rules

- No `validate_model_invocation.py` PASS = no trusted verdict
- `allowed_next_stage=false` = stop immediately
- `already_done` = stop, do not proceed to experiment
- Do not produce a verdict without going through the workflow stack

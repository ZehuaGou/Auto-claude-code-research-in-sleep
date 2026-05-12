---
name: research-contract
description: Freeze research hypothesis, success/failure signals, metrics, data split, baseline requirement, and claim boundary before full experiments.
argument-hint: [idea-card-or-experiment-plan]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# /research-contract

## What it is

`/research-contract` is a **native ARIS command wrapper**. It does not organize the final prompt, does not select models, does not call models, and does not produce trusted conclusions directly.

It maps to the `research_contract` workflow stage and delegates everything to the ARIS workflow stack.

## User invocation

```
/research-contract "idea-stage/IDEA_CARDS/idea_001.md"
```

## How it works

1. User invokes `/research-contract "..."`
2. Skill maps the request to the `research_contract` workflow stage
3. Skill calls `tools/research_workflow.py prepare research_contract`
4. `context_isolation_check.py` scans inputs — FAIL stops execution
5. `trusted_role_runner.py` executes `contract_reviewer` role (Codex MCP)
6. `validate_model_invocation.py --role contract_reviewer` — PASS means contract is verified
7. If `allowed_next_stage=false`, the skill stops without producing a trusted contract

## What the skill does NOT do

- Does NOT organize the final prompt sent to the model
- Does NOT select the model or backend
- Does NOT directly call Codex, DeepSeek, or any other model
- Does NOT produce a trusted conclusion on its own
- Does NOT bypass `validate_model_invocation.py`

## Workflow stage

- **stage**: `research_contract`
- **role**: `contract_reviewer`
- **provider**: `codex` (MCP backend)

## Trusted output

Only the ledger entry produced by `trusted_role_runner.py` + `validate_model_invocation.py` PASS constitutes a trusted contract. Any output written before that gate is not a trusted artifact.

## Hard rules

- No `validate_model_invocation.py` PASS = no trusted contract
- `allowed_next_stage=false` = stop immediately
- Do not produce a "contract" artifact without going through the workflow stack

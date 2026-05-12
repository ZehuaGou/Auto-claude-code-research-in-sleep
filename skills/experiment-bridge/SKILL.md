---
name: experiment-bridge
description: Bridge from experiment plan to implementation and code review. Use when user says "实现实验", "implement experiments", "bridge", or "从计划到跑实验".
argument-hint: [experiment-plan-path-or-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# /experiment-bridge

## What it is

`/experiment-bridge` is a **native ARIS command wrapper** for turning an experiment plan into implementation. It does not organize the final prompt, does not select models, does not directly write experiment code as a substitute, and does not produce trusted results directly.

It maps to `experiment_plan` and `implementation_plan` workflow stages. Code implementation goes through `experiment_implementer` role; code review goes through `experiment_code_reviewer` role.

## User invocation

```
/experiment-bridge "EXPERIMENT_PLAN.md"
```

## Prerequisite gates

**ALL of these must be verified before writing any experiment code:**

1. `research_contract` — must have `validate_model_invocation.py` PASS with `allowed_next_stage=true`
2. `novelty_check` — must have `validate_model_invocation.py` PASS with `allowed_next_stage=true`
3. `experiment_plan` — must have `validate_model_invocation.py` PASS with `allowed_next_stage=true`
4. `implementation_plan` — must have `validate_model_invocation.py` PASS with `allowed_next_stage=true`

**If any gate is not passed: stop. Do not write experiment code.**

## How it works

1. User invokes `/experiment-bridge "..."`
2. Skill checks all four prerequisite gates via `validate_model_invocation.py`
3. If all gates pass, skill calls `tools/research_workflow.py prepare experiment_plan`
4. `context_isolation_check.py` scans inputs — FAIL stops execution
5. `trusted_role_runner.py` executes `experiment_implementer` role (DeepSeek API)
6. After implementation, `trusted_role_runner.py` executes `experiment_code_reviewer` role (Codex MCP)
7. For Codex review: must have real `codex_thread_id` in ledger
8. `validate_model_invocation.py` PASS required for each role before proceeding
9. If `allowed_next_stage=false` at any point: stop

## What the skill does NOT do

- Does NOT write experiment code without `experiment_implementer` role
- Does NOT present code review results as final without `experiment_code_reviewer`
- Does NOT bypass `validate_model_invocation.py`
- Does NOT allow external agents to write code冒充 DeepSeek or Codex
- Does NOT proceed if any prerequisite gate is not passed

## Workflow stages

| Stage | Role | Backend |
|-------|------|---------|
| `experiment_plan` | `experiment_auditor` | Codex MCP |
| `implementation_plan` | `experiment_implementer` | DeepSeek API |

After these, code review uses `experiment_code_reviewer` (Codex MCP).

## Trusted output

Only ledger entries from `trusted_role_runner.py` + `validate_model_invocation.py` PASS constitute trusted experiment output. Any code written before these gates is not a trusted artifact.

## Hard rules

- Missing any prerequisite gate = stop immediately
- `allowed_next_stage=false` = stop immediately
- No real `codex_thread_id` for Codex review = review is not trusted
- External agents must not write experiment code冒充 models
- Do not run experiments or collect results before all gates pass

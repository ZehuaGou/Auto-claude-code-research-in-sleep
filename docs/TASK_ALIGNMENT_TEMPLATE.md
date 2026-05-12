# Task Alignment Brief

Every task MUST complete this brief before execution.
The alignment guard (`tools/alignment_guard.py`) validates this document.

---

## 1. Task Goal

One sentence describing what this task solves.

FORBIDDEN vague goals:
- "continue"
- "fix it"
- "do it"
- "optimize"
- "improve"
- "fix bugs"
- "update stuff"
- "make it better"
- "clean up"
- "refactor"

REQUIRED: a specific, bounded statement like:
- "Add stage_output_contract to literature_search stage to prevent novelty_check boundary leakage"
- "Create alignment_guard.py to enforce task-to-architecture mapping before execution"

---

## 2. Target Document Reference

Must reference: `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md`

Specify which sections apply:
- Section 4: System Architecture (five layers)
- Section 5: Native Command Layer
- Section 6: Skill Method Layer
- Section 8: Literature Search & Acquisition Layer
- Section 9: Workflow Discipline Layer
- Section 10: Trusted Execution Layer
- Section 11: Trusted Output Layer
- Section 12: Stage Flow Details
- Section 13: Permission Boundary Table
- Section 15: MVP Trim Plan

---

## 3. Target Layers

Select from this enum ONLY:
- `native_command` — user-facing command入口
- `skill_method` — research method rules, strategies, judgment criteria
- `workflow_discipline` — stage control, input control, context isolation, prompt assembly
- `literature_layer` — search, acquisition, parsing, material store
- `trusted_execution` — model routing, trusted runner, ledger, validator
- `trusted_output` — stage output files, artifact headers, handoff rules
- `status_tracking` — current stage status, validation status, blocked reasons
- `documentation_only` — docs, guides, templates (no code behavior change)

---

## 4. Why This Task Belongs To These Layers

Explain WHY each selected layer applies. Do not just list layer names.

Example:
> This task adds a content boundary check to the validator, which validates trusted execution artifacts.
> It belongs to `trusted_execution` because it extends validate_model_invocation.py.
> It belongs to `workflow_discipline` because the stage_output_contract is assembled by research_workflow.py.

---

## 5. Allowed Files

List files or directories this task may create or modify.

Example:
```
- tools/alignment_guard.py
- docs/ALIGNMENT_GUARD.md
- docs/TASK_ALIGNMENT_TEMPLATE.md
```

---

## 6. Forbidden Files

List files or directories this task MUST NOT touch.

Standard forbidden list:
```
- .env
- .env.example
- .aris/*
- tmp/*
- research/*
- literature/*
- experiments/*
- paper/*
- probes/*
- detection/*
```

Add task-specific forbidden files as needed.

---

## 7. Allowed Actions

List what this task may do:
- edit docs only
- run self-tests
- run validation commands
- commit allowed files

---

## 8. Forbidden Actions

MUST include ALL of:
- no model calls (DeepSeek / Codex / OpenAI / MiniMax)
- no mcp__codex__codex
- no WebSearch / WebFetch / curl
- no experiments
- no .env reads/writes
- no .aris/ modifications
- no tmp/ commits
- no `git add .`

---

## 9. Stop Conditions

When to stop and report:
- validator returns FAIL
- git status contains forbidden files
- target doc conflict detected
- need to modify out-of-scope files
- major target-doc deviation requires user approval

---

## 10. Validation Commands

List commands that must pass before commit:

Example:
```
python tools/alignment_guard.py --self-test
python tools/context_isolation_check.py --self-test
python tools/trusted_role_runner.py --self-test
python tools/validate_model_invocation.py --self-test
```

---

## 11. Expected Outputs

List files this task will create or modify:

Example:
```
- tools/alignment_guard.py (new)
- docs/ALIGNMENT_GUARD.md (new)
- docs/TASK_ALIGNMENT_TEMPLATE.md (new)
```

---

## 12. Commit Plan

State whether commit is allowed and what message to use.

Example:
```
commit: yes
message: add target-document alignment guard
files: tools/alignment_guard.py docs/ALIGNMENT_GUARD.md docs/TASK_ALIGNMENT_TEMPLATE.md
```

---

## 13. Target Doc Deviations

Default (no deviation):

```
deviation: none
```

If intentionally deviating from `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md`:

```
deviation: <description>
target_doc_section: <section number and name>
reason: <why deviation is necessary>
proposed_alternative: <what you propose instead>
risk_of_deviation: <what could go wrong>
risk_if_not_deviating: <what happens if we stick to target doc>
requires_user_approval: yes/no
```

Rules:
1. No deviation → write `deviation: none`
2. Deviation without explanation → alignment_guard MUST FAIL
3. Architecture changes, trust chain relaxation, evidence standard lowering, model call trust reduction → `requires_user_approval: yes`
4. Small implementation details (file names, field names, CLI flags) that preserve target principles → `requires_user_approval: no` (but must document reason)
5. Alignment guard only requires documenting deviation; it does not auto-judge whether deviation is correct

# Alignment Guard

## What It Is

`tools/alignment_guard.py` is a lightweight pre-execution discipline tool.

It is NOT:
- A replacement for `validate_model_invocation.py` (trusted execution validation)
- A replacement for `context_isolation_check.py` (context contamination detection)
- A replacement for `trusted_role_runner.py` (model call execution)
- A judge of scientific conclusions
- A literature quality checker

It IS:
- A "design alignment gate" that forces every task to map to the target document's five-layer architecture
- A guard against vague, unbounded tasks like "continue" or "fix it"
- A check that forbidden files are not touched
- A check that deviations from the target document are explicitly documented

## How It Fits In The System

```
Task arrives
  → Write Task Alignment Brief (docs/TASK_ALIGNMENT_TEMPLATE.md)
  → alignment_guard check-task (validates brief structure)
  → Execute task
  → alignment_guard check-status (validates git status against allowed/forbidden)
  → Only PASS allows commit
```

If the task involves model calls, the full trusted execution chain still applies:
- `research_workflow.py` prepare
- `trusted_role_runner.py` execute
- `validate_model_invocation.py` validate

If the task involves literature, the literature evidence chain still applies.

## Commands

### Self-test
```bash
python tools/alignment_guard.py --self-test
```

### Validate task brief
```bash
python tools/alignment_guard.py check-task --file <task_alignment_brief.md>
```

### Validate git status against task brief
```bash
python tools/alignment_guard.py check-status --file <task_alignment_brief.md>
```

## What check-task Validates

1. Target document exists: `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md`
2. Task file exists and is readable
3. All 13 required sections are present
4. Target Layers use valid enum values only
5. Task Goal is specific (not vague like "continue" or "fix bugs")
6. Target document is explicitly referenced
7. Allowed Files and Forbidden Files are specified
8. Stop Conditions are specified
9. Validation Commands are specified
10. Forbidden Actions includes "no git add ."
11. Target Doc Deviations section exists
12. If deviation is not "none", all required deviation fields are present

Output: JSON with `status`, `target_layers`, `warnings`, `errors`

## What check-status Validates

Runs `git status --short` and checks against Allowed/Forbidden Files from the brief:

- `.env` in status → FAIL
- `.aris/` in status → FAIL
- `tmp/` in status → FAIL
- `research/` in status → FAIL unless explicitly allowed
- `literature/` in status → FAIL unless explicitly allowed
- Files outside allowed scope → FAIL
- Runtime files → FAIL
- Only allowed files → PASS

## Target Layers Enum

| Layer | Description |
|-------|-------------|
| `native_command` | User-facing command entry points |
| `skill_method` | Research method rules, strategies, judgment criteria |
| `workflow_discipline` | Stage control, input control, context isolation |
| `literature_layer` | Search, acquisition, parsing, material store |
| `trusted_execution` | Model routing, trusted runner, ledger, validator |
| `trusted_output` | Stage output files, artifact headers, handoff rules |
| `status_tracking` | Current stage status, validation status |
| `documentation_only` | Docs, guides, templates |

## Target Doc Deviations

The target document (`docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md`) is v1.0 — a design blueprint, not an immutable spec.

Deviations are allowed but must be documented:
- What section is being deviated from
- Why the deviation is necessary
- What alternative is proposed
- Risk of deviating
- Risk of NOT deviating
- Whether user approval is required

Major deviations (architecture changes, trust chain relaxation, evidence standard lowering) require user approval.

Small implementation detail adjustments (file names, field names, CLI flags) that preserve target principles do not require user approval but must be recorded.

## Relationship to Other Tools

| Tool | Purpose | Alignment Guard Relationship |
|------|---------|------------------------------|
| `context_isolation_check.py` | Detect forbidden markers in input | Complementary — alignment guard checks task scope, context check checks content |
| `trusted_role_runner.py` | Execute model calls through trusted path | Separate — alignment guard does not call models |
| `validate_model_invocation.py` | Verify ledger and call authenticity | Separate — alignment guard does not verify calls |
| `research_workflow.py` | Stage orchestration | Complementary — alignment guard pre-validates task design |

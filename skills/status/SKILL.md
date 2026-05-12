---
name: status
description: Show current trusted research workflow status for each stage (inputs, outputs, verification, blockers)
argument-hint: [--json]
allowed-tools: Bash(*), Read, Grep, Glob
---

# /status

## What it is

`/status` reads the current state of the trusted research workflow without modifying any files. It does not call models, does not run experiments, and does not write anything.

## User invocation

```
/status
/status --json
```

## How it works

The skill runs:

```
python tools/research_status.py
python tools/research_status.py --json
```

`research_status.py` reads:
- `configs/workflows/research_default.yaml` — stage definitions
- Each stage's `output_file` and `allowed_input_files`

## What /status does NOT do

- Does NOT modify any files
- Does NOT call any model
- Does NOT run experiments
- Does NOT invoke `trusted_role_runner` or `validate_model_invocation`
- Does NOT read `.env`
- Does NOT read large log files

## Default scope

The default status scope covers the trusted research workflow:

```
configs/workflows/research_default.yaml
research/current/raw_user_input.md
research/current/input_normalization.md
research/current/trusted_outputs/
```

## Output contents

For each stage, `/status` reports:

| Field | Meaning |
|-------|---------|
| Stage | Stage name |
| Role | Assigned role |
| Status | One of: `blocked_missing_inputs`, `ready_to_prepare`, `untrusted_output_missing_header`, `output_unverified`, `blocked_not_allowed_next_stage`, `completed_trusted` |
| Missing Inputs | Required inputs that are not yet present |
| Output | Path to stage's trusted output file |
| Verification Status | From artifact header |
| Allowed Next Stage | From artifact header |
| Actual Backend / Model | From artifact header |
| Ledger Call ID | From artifact header |

## Status meanings

| Status | Meaning |
|--------|---------|
| `blocked_missing_inputs` | Required input files are missing — cannot run this stage |
| `ready_to_prepare` | All inputs present but output not yet generated |
| `completed_trusted` | Output exists with verified artifact header and allowed_next_stage=true |
| `output_unverified` | Output exists but verification_status is not verified |
| `blocked_not_allowed_next_stage` | Output exists but allowed_next_stage=false |
| `untrusted_output_missing_header` | Output file exists but has no artifact header |

## Recommended next action

`/status` also prints a recommended next command based on the first non-completed stage.

## Legacy status

The old `idea-stage/AGENTIC/` workflow and `resume_stage_state.py` are **not** part of the current trusted research workflow status. They are legacy artifacts from previous sessions and should not be used as the default status source.

For legacy projects, use `/status legacy` if supported, or check `idea-stage/AGENTIC/` manually.

## Example output

```
# Trusted Research Workflow Status

Stage                     Role                           Status                              Output
...
input_normalization       input_normalizer               blocked_missing_inputs              ...

## Missing Inputs
- input_normalization: research/current/raw_user_input.md
- research_contract: research/current/input_normalization.md
...

## Recommended Next Action
```
blocked_missing_inputs — missing: research/current/raw_user_input.md.
Create or place these files before running prepare.
```

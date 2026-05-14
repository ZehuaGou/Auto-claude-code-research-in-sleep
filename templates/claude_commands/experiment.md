---
description: Plan and analyze experiments
argument-hint: "experiment description --mode lightweight|full|analyze|revise"
---

Plan an experiment for the given description.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/experiment $ARGUMENTS`.
- Default: run `python tools/slash_command_adapter.py '/experiment $ARGUMENTS' --save-payload-dir research/current/user_command_payloads` (dry-run, plan only).
- If user says "execute" or "run it": add `--execute` flag to create scaffold files (no model calls, no code execution).
- Display the output to the user.
- This command NEVER calls models, runs code, executes experiments, or changes trusted_outputs.
- Supports `--mode` flag: lightweight (default), full, analyze, revise.
- lightweight = quick signal check; full = complete baseline + ablation; analyze = review results; revise = adjust method.

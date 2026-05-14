---
description: Plan and analyze experiments
argument-hint: "experiment description --mode lightweight|full|analyze|revise"
---

Plan an experiment for the given description.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/experiment $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/experiment $ARGUMENTS'`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Do NOT execute the plan. Only show what would happen.
- Supports `--mode` flag: lightweight (default), full, analyze, revise.
- lightweight = quick signal check; full = complete baseline + ablation; analyze = review results; revise = adjust method.

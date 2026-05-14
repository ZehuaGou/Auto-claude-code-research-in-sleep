---
description: Plan paper writing based on verified results
argument-hint: "paper writing instructions"
---

Plan paper writing for the given instructions.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/paper-writing $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/paper-writing $ARGUMENTS'`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Do NOT execute the plan. Only show what would happen.
- Paper writing requires verified experiment results and approved claim boundary.

---
description: Show current research workflow status
argument-hint: [--all]
---

Show the current research workflow status.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/status $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/status $ARGUMENTS' --save-payload-dir research/current/user_command_payloads`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Shows current stage, completed stages, validators, evidence summary, and next allowed action.

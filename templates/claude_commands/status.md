---
description: Show current research workflow status
argument-hint: [--all]
---

Show the current research workflow status.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/status $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/status $ARGUMENTS' --save-payload-dir research/current/user_command_payloads --execute`
- Display the status output to the user.
- This command reads state only — no model calls, no file mutations, no trusted_outputs changes.
- Shows current phase, completed phases, blocked reasons, next allowed commands, system health.

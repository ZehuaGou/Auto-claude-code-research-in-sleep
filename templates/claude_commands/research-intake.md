---
description: Input research direction and constraints
argument-hint: "research idea in quotes"
---

Parse the user's research idea into a structured plan.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/research-intake $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/research-intake $ARGUMENTS' --save-payload-dir research/current/user_command_payloads`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Do NOT execute the plan. Only show what would happen.
- If the user wants to proceed, they should run `/literature-intake` next.

---
description: Input research direction and constraints
argument-hint: "research idea in quotes"
---

Parse the user's research idea into a structured plan and optionally execute safe backend actions.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/research-intake $ARGUMENTS`.
- Default: run `python tools/slash_command_adapter.py '/research-intake $ARGUMENTS' --save-payload-dir research/current/user_command_payloads` (dry-run, plan only).
- If user says "execute" or "run it": add `--execute` flag to execute safe backend actions (create files, update state — no model calls).
- Display the plan/execution output to the user.
- This command NEVER calls models, runs experiments, or changes trusted_outputs.
- If the user wants to proceed, they should run `/literature-intake` next.

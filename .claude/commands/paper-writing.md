---
description: Plan paper writing based on verified results
argument-hint: "paper writing instructions"
---

Plan paper writing for the given instructions.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/paper-writing $ARGUMENTS`.
- Default: run `python tools/slash_command_adapter.py '/paper-writing $ARGUMENTS' --save-payload-dir research/current/user_command_payloads` (dry-run, plan only).
- If user says "execute" or "run it": add `--execute` flag to create scaffold files (no model calls).
- Display the output to the user.
- This command NEVER calls models, writes paper sections, fabricates results, or changes trusted_outputs.
- Paper writing requires verified experiment results and approved claim boundary — will be blocked otherwise.

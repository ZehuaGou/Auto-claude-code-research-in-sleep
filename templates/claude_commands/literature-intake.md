---
description: Literature survey and domain understanding
argument-hint: "literature search focus area"
---

Plan a literature search for the given topic.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/literature-intake $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/literature-intake $ARGUMENTS' --save-payload-dir research/current/user_command_payloads`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Do NOT execute the plan. Only show what would happen.
- The underlying literature pipeline uses multi-source search (arXiv + Crossref + OpenAlex).

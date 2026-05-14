---
description: Literature survey and domain understanding
argument-hint: "literature search focus area"
---

Plan a literature search for the given topic.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/literature-intake $ARGUMENTS`.
- Default: run `python tools/slash_command_adapter.py '/literature-intake $ARGUMENTS' --save-payload-dir research/current/user_command_payloads` (dry-run, plan only).
- If user says "execute" or "run it": add `--execute` flag to create scaffold files (no model calls, no PDF downloads).
- Display the output to the user.
- This command NEVER calls models, downloads PDFs, or changes trusted_outputs.
- The underlying literature pipeline uses multi-source search (arXiv + Crossref + OpenAlex).

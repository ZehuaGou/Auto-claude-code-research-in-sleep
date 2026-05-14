---
description: Generate candidate research ideas
argument-hint: "idea generation focus or constraints"
---

Plan idea synthesis for the given direction.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-synthesis $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/idea-synthesis $ARGUMENTS'`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Do NOT execute the plan. Only show what would happen.
- Supports `--num-candidates N` flag (default: 5).

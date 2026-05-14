---
description: Verify idea novelty and lock research boundaries
argument-hint: "idea to audit or check"
---

Plan a novelty check and method refinement for the given idea.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-audit $ARGUMENTS`.
- Run: `python tools/slash_command_adapter.py '/idea-audit $ARGUMENTS'`
- Display the plan output to the user.
- This is DRY-RUN only: no model calls, no trusted runner execution, no trusted_outputs changes.
- Do NOT execute the plan. Only show what would happen.
- This runs novelty_check + method_refinement + research_contract internally.

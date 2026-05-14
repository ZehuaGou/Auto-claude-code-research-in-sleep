---
description: Verify idea novelty and lock research boundaries
argument-hint: "idea to audit or check"
---

Plan a novelty check and method refinement for the given idea.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-audit $ARGUMENTS`.
- Default: run `python tools/slash_command_adapter.py '/idea-audit $ARGUMENTS' --save-payload-dir research/current/user_command_payloads` (dry-run, plan only).
- If user says "execute" or "run it": add `--execute` flag to create scaffold files (no model calls).
- Display the output to the user.
- This command NEVER calls models, runs experiments, or changes trusted_outputs.
- This runs novelty_check + method_refinement + research_contract internally.
- Cannot write confirmed_novel without model verification.

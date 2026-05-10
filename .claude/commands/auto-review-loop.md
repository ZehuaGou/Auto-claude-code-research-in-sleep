---
description: Execute ARIS skill auto-review-loop
argument-hint: arguments
---

Load and execute `skills/auto-review-loop/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/auto-review-loop $ARGUMENTS`.
- Follow `skills/auto-review-loop/SKILL.md` exactly.
- Do not bypass the skill's safety, routing, artifact, ledger, or resume rules.
- If this skill is a critical gate, resolve routing through the configured model route and write artifact headers/ledger as required by the skill.
- If interrupted or existing artifacts are incomplete, use the relevant validator/resume tool before continuing.

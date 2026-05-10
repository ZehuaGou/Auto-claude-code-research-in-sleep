---
description: Execute ARIS skill comm-lit-review
argument-hint: arguments
---

Load and execute `skills/comm-lit-review/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/comm-lit-review $ARGUMENTS`.
- Follow `skills/comm-lit-review/SKILL.md` exactly.
- Do not bypass the skill's safety, routing, artifact, ledger, or resume rules.
- If this skill is a critical gate, resolve routing through the configured model route and write artifact headers/ledger as required by the skill.
- If interrupted or existing artifacts are incomplete, use the relevant validator/resume tool before continuing.

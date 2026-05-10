---
description: Execute ARIS skill kill-argument
argument-hint: arguments
---

Load and execute `skills/kill-argument/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/kill-argument $ARGUMENTS`.
- Follow `skills/kill-argument/SKILL.md` exactly.
- Do not bypass the skill's safety, routing, artifact, ledger, or resume rules.
- If this skill is a critical gate, resolve routing through the configured model route and write artifact headers/ledger as required by the skill.
- If interrupted or existing artifacts are incomplete, use the relevant validator/resume tool before continuing.

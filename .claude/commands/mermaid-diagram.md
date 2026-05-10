---
description: Execute ARIS skill mermaid-diagram
argument-hint: arguments
---

Load and execute `skills/mermaid-diagram/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/mermaid-diagram $ARGUMENTS`.
- Follow `skills/mermaid-diagram/SKILL.md` exactly.
- Do not bypass the skill's safety, routing, artifact, ledger, or resume rules.
- If this skill is a critical gate, resolve routing through the configured model route and write artifact headers/ledger as required by the skill.
- If interrupted or existing artifacts are incomplete, use the relevant validator/resume tool before continuing.

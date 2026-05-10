---
description: Show ARIS idea discovery workflow status (AGENTIC scope by default)
argument-hint: [--all | legacy | experiments]
---

Load and execute `skills/status/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/status $ARGUMENTS`.
- Follow `skills/status/SKILL.md` exactly.
- Default scope is `idea-stage/AGENTIC` — do NOT read review-stage/, experiment_queue/, or old EXPERIMENT_LOG.md unless `--all`, `legacy`, or `experiments` is passed.
- Prefer filesystem status from tools/resume_stage_state.py and validators over chat memory.
- Hide TEST ONLY sessions by default.
- Next steps must come from resume_stage_state.py, not from old project state.

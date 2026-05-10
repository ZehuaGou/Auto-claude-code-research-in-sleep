---
description: Generate canonical ideas from verified literature artifacts
argument-hint: research direction
---

Load and execute `skills/idea-creator/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-creator "$ARGUMENTS"`.
- Follow `skills/idea-creator/SKILL.md` exactly.
- Require Phase 1 artifacts first.
- Generate IDEA_CARDS, IDEA_BANK, CANONICAL_IDEAS.
- Run Codex shortlist audit gate.
- Do not do novelty-check, independent review, final selection, pilot, or experiment.
- On resume intent, use `python tools/resume_stage_state.py idea-creator`.

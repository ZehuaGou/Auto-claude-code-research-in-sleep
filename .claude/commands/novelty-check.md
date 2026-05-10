---
description: Run canonical or ad hoc novelty check with clean evidence isolation
argument-hint: CAND_001
---

Load and execute `skills/novelty-check/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/novelty-check $ARGUMENTS`.
- Follow `skills/novelty-check/SKILL.md` exactly.
- If `$ARGUMENTS` is a CAND id, run canonical_pipeline mode.
- If `$ARGUMENTS` is free text, run ad_hoc mode only.
- Do not let ad_hoc output enter IDEA_BANK or FINAL_SELECTION.
- Use Codex thread when required by the skill.
- Write artifact header and ledger as required by the skill.
- If interrupted or existing artifact is incomplete, use `python tools/resume_stage_state.py novelty-check <candidate>` before continuing.

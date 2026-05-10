---
description: Run isolated executive review for one canonical research candidate
argument-hint: CAND_001
---

Load and execute `skills/exec-review/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/exec-review $ARGUMENTS`.
- Follow `skills/exec-review/SKILL.md` exactly.
- Do not perform ad hoc review outside the skill.
- Parse `$ARGUMENTS` as exactly one canonical candidate, e.g. `CAND_001`.
- Use the skill's clean evidence gate rules.
- Use Codex thread when required by the skill.
- Write artifact header and ledger as required by the skill.
- If interrupted or existing artifact is incomplete, use `python tools/resume_stage_state.py exec-review <candidate>` before continuing.

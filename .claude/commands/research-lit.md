---
description: Run literature survey, paper ingest, gap map, and evidence audit
argument-hint: research direction
---

Load and execute `skills/research-lit/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/research-lit "$ARGUMENTS"`.
- Follow `skills/research-lit/SKILL.md` exactly.
- Do not stop after narrative survey.
- The command is incomplete until LITERATURE_INDEX, GAP_MAP, and PHASE1_EVIDENCE_AUDIT exist.
- Run evidence_integrity_auditor gate as required.
- Write artifact header and ledger.
- On resume intent, use `python tools/resume_stage_state.py research-lit`.

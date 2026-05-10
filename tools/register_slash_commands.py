#!/usr/bin/env python3
"""
Register local ARIS skills as .claude/commands/*.md slash command wrappers.

Scans skills/*/SKILL.md, generates a minimal wrapper that delegates to
the corresponding SKILL.md, and writes it to .claude/commands/<name>.md.

Does NOT overwrite existing wrappers unless --force is passed.

Usage:
    python tools/register_slash_commands.py              # safe mode
    python tools/register_slash_commands.py --force      # overwrite all
    python tools/register_slash_commands.py --check-only  # verify only

Exit code: 0 if all required commands exist, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = PROJECT_ROOT / ".claude" / "commands"
SKILLS_DIR = PROJECT_ROOT / "skills"

# Skills that need slash command wrappers
REQUIRED_COMMANDS = [
    "research-lit",
    "idea-creator",
    "exec-review",
    "novelty-check",
    "idea-bank",
    "idea-discovery",
    "status",
]

WRAPPER_TEMPLATES = {
    "exec-review": """\
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
""",
    "novelty-check": """\
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
""",
    "research-lit": """\
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
""",
    "idea-creator": """\
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
""",
    "idea-bank": """\
---
description: Manage IDEA_BANK and canonical candidates
argument-hint: action
---

Load and execute `skills/idea-bank/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-bank $ARGUMENTS`.
- Follow `skills/idea-bank/SKILL.md` exactly.
- Manage IDEA_BANK, IDEA_BANK.json, CANONICAL_IDEAS.
- Do not run experiments.
- Do not bypass Codex gates when performing audit-like actions.
""",
    "idea-discovery": """\
---
description: Run full gated idea discovery workflow
argument-hint: research direction
---

Load and execute `skills/idea-discovery/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-discovery "$ARGUMENTS"`.
- Follow `skills/idea-discovery/SKILL.md` exactly.
- Run gated workflow only up to final idea selection.
- Do not auto-run research-contract, baseline-repro, experiment-bridge, pilot, or paper writing.
- Respect resume/checkpoint rules.
""",
    "status": """\
---
description: Show ARIS workflow and session status
argument-hint: optional stage or candidate
---

Load and execute `skills/status/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/status $ARGUMENTS`.
- Follow `skills/status/SKILL.md` exactly.
- Prefer filesystem status from tools/resume_stage_state.py and validators over chat memory.
""",
}


def check_required_commands() -> list[str]:
    """Return a list of missing required commands."""
    missing = []
    for name in REQUIRED_COMMANDS:
        path = COMMANDS_DIR / f"{name}.md"
        if not path.exists():
            missing.append(name)
    return missing


def register_command(name: str, force: bool = False) -> bool:
    """Write a slash command wrapper for the given skill. Returns True if written."""
    path = COMMANDS_DIR / f"{name}.md"
    if path.exists() and not force:
        print(f"  SKIP    {name}.md (exists, use --force to overwrite)")
        return False

    template = WRAPPER_TEMPLATES.get(name)
    if template is None:
        print(f"  SKIP    {name}.md (no template defined)")
        return False

    path.write_text(template, encoding="utf-8")
    print(f"  WRITE   {name}.md")
    return True


def check_skill_exists(name: str) -> bool:
    """Verify the corresponding skills/<name>/SKILL.md exists."""
    skill_path = SKILLS_DIR / name / "SKILL.md"
    exists = skill_path.exists()
    if not exists:
        print(f"  WARN    skills/{name}/SKILL.md not found on disk")
    return exists


def main():
    parser = argparse.ArgumentParser(
        description="Register local ARIS skills as .claude/commands/*.md wrappers"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing command wrappers"
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="Only check which required commands are missing, do not write"
    )
    args = parser.parse_args()

    # Ensure commands directory exists
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ARIS Slash Command Registration")
    print("=" * 60)

    if args.check_only:
        missing = check_required_commands()
        if missing:
            print(f"\nMissing required command wrappers: {missing}")
            for name in missing:
                check_skill_exists(name)
            print("\nResult: MISSING")
            sys.exit(1)
        else:
            print("\nAll required command wrappers are present.")
            for name in REQUIRED_COMMANDS:
                path = COMMANDS_DIR / f"{name}.md"
                skill_exists = check_skill_exists(name)
                status = "OK" if skill_exists else "MISSING SKILL"
                print(f"  [{status}] {name}.md -> skills/{name}/SKILL.md")
            print("\nResult: ALL OK")
            sys.exit(0)

    # Register commands
    written = 0
    for name in REQUIRED_COMMANDS:
        if register_command(name, force=args.force):
            written += 1
        check_skill_exists(name)

    # Summary
    missing = check_required_commands()
    if missing:
        print(f"\nWARNING: Some required commands are still missing: {missing}")
        sys.exit(1)
    else:
        print(f"\nAll {len(REQUIRED_COMMANDS)} required slash commands are registered.")
        print("Restart Claude Code session for changes to take effect.")
        sys.exit(0)


if __name__ == "__main__":
    main()

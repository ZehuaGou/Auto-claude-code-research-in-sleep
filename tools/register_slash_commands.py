#!/usr/bin/env python3
"""
Register ALL local ARIS skills as .claude/commands/*.md slash command wrappers.

Auto-scans skills/*/SKILL.md and generates a wrapper for each one.
Skills with a dedicated template get a specialized wrapper; all others
get a generic wrapper that delegates to skills/<name>/SKILL.md.

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

# Directories under skills/ that are NOT user-invocable commands
SKIP_DIRS = {
    "shared-references",
    "skills-codex",
    "skills-codex-claude-review",
    "skills-codex-gemini-review",
}

# ---- Specialized templates for core pipeline skills ----
SPECIAL_TEMPLATES: dict[str, str] = {}

SPECIAL_TEMPLATES["exec-review"] = """\
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
"""

SPECIAL_TEMPLATES["novelty-check"] = """\
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
"""

SPECIAL_TEMPLATES["research-lit"] = """\
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
"""

SPECIAL_TEMPLATES["idea-creator"] = """\
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
"""

SPECIAL_TEMPLATES["idea-bank"] = """\
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
"""

SPECIAL_TEMPLATES["idea-discovery"] = """\
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
"""

SPECIAL_TEMPLATES["research-contract"] = """\
---
description: Freeze hypothesis, signals, metrics, baselines, kill conditions, and protocol before experiments
argument-hint: CAND_001
---

Load and execute `skills/research-contract/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/research-contract $ARGUMENTS`.
- Follow `skills/research-contract/SKILL.md` exactly.
- Must read the completed FINAL_SELECTION/IDEA_SELECTION_REPORT.md before proceeding.
- Only allow selected candidate to enter contract.
- Do not run experiments.
- Do not write paper.
- Only freeze hypothesis / signals / metrics / baselines / kill conditions / protocol.
- If final selection is not codex_gate or llm_fallback_gate, stop.
- If selected candidate is not CAND_001, stop.
"""

SPECIAL_TEMPLATES["status"] = """\
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
"""

# ---- Generic template for all other skills ----
GENERIC_TEMPLATE = """\
---
description: Execute ARIS skill {name}
argument-hint: arguments
---

Load and execute `skills/{name}/SKILL.md`.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/{name} $ARGUMENTS`.
- Follow `skills/{name}/SKILL.md` exactly.
- Do not bypass the skill's safety, routing, artifact, ledger, or resume rules.
- If this skill is a critical gate, resolve routing through the configured model route and write artifact headers/ledger as required by the skill.
- If interrupted or existing artifacts are incomplete, use the relevant validator/resume tool before continuing.
"""


def get_all_skills() -> list[str]:
    """Return sorted list of skill names that have SKILL.md."""
    names: list[str] = []
    for p in SKILLS_DIR.iterdir():
        if not p.is_dir():
            continue
        if p.name in SKIP_DIRS:
            continue
        if (p / "SKILL.md").exists():
            names.append(p.name)
    return sorted(names)


def get_existing_wrappers() -> set[str]:
    """Return set of skill names that already have a wrapper .md file."""
    if not COMMANDS_DIR.exists():
        return set()
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


def generate_wrapper(name: str) -> str:
    """Generate wrapper content for a given skill name."""
    if name in SPECIAL_TEMPLATES:
        return SPECIAL_TEMPLATES[name]
    return GENERIC_TEMPLATE.format(name=name)


def register_command(name: str, force: bool = False) -> bool:
    """Write a slash command wrapper for the given skill. Returns True if written."""
    path = COMMANDS_DIR / f"{name}.md"
    if path.exists() and not force:
        print(f"  SKIP    {name}.md (exists, use --force to overwrite)")
        return False

    content = generate_wrapper(name)
    path.write_text(content, encoding="utf-8")
    print(f"  WRITE   {name}.md")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Register ALL local ARIS skills as .claude/commands/*.md wrappers"
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

    all_skills = get_all_skills()
    existing_wrappers = get_existing_wrappers()

    print("=" * 60)
    print("ARIS Slash Command Registration")
    print("=" * 60)
    print(f"Skills found: {len(all_skills)}")
    print(f"Wrappers found: {len(existing_wrappers)}")

    if args.check_only:
        missing = [s for s in all_skills if s not in existing_wrappers]
        if missing:
            print(f"\nMissing wrappers ({len(missing)}):")
            for name in missing:
                print(f"  /{name}  -> skills/{name}/SKILL.md (missing wrapper)")
            print("\nResult: MISSING")
            sys.exit(1)
        else:
            print(f"\nAll {len(all_skills)} skills have wrappers.")
            for name in all_skills:
                wrapper_path = COMMANDS_DIR / f"{name}.md"
                content = wrapper_path.read_text(encoding="utf-8", errors="ignore")
                ref_ok = f"skills/{name}/SKILL.md" in content
                status = "OK" if ref_ok else "WRONG REF"
                if not ref_ok:
                    print(f"  [WARN] {name}.md does not reference skills/{name}/SKILL.md")
                else:
                    print(f"  [OK]   {name}.md -> skills/{name}/SKILL.md")
            print("\nResult: ALL OK")
            sys.exit(0)

    # Register commands for ALL skills
    written = 0
    skipped = 0
    for name in all_skills:
        if register_command(name, force=args.force):
            written += 1
        else:
            skipped += 1

    # Re-check
    existing_after = get_existing_wrappers()
    missing_after = [s for s in all_skills if s not in existing_after]

    print(f"\nWritten: {written}, Skipped: {skipped}")
    if missing_after:
        print(f"WARNING: Still missing wrappers for: {missing_after}")
        sys.exit(1)
    else:
        print(f"All {len(all_skills)} slash commands are registered.")
        print("Restart Claude Code session for changes to take effect.")
        sys.exit(0)


if __name__ == "__main__":
    main()

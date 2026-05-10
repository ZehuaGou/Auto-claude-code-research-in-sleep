#!/usr/bin/env python3
"""
Register local ARIS skills into skills-lock.json.

Scans skills/*/SKILL.md, generates a registration entry for each,
preserves existing non-local skills (e.g. claude-to-im from GitHub),
and writes the merged result back to skills-lock.json.

Usage:
    python tools/register_local_skills.py

Output: prints the list of registered skills and any warnings.
"""

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
LOCK_FILE = PROJECT_ROOT / "skills-lock.json"

# Directories that exist under skills/ but are NOT individual skills
# (no SKILL.md, or are shared libraries rather than invocable skills)
SKIP_DIRS = {
    "shared-references",
    "skills-codex",
    "skills-codex-claude-review",
    "skills-codex-gemini-review",
}


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 of file contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def scan_local_skills() -> dict:
    """Scan skills/*/SKILL.md and return a dict of registration entries."""
    registered = {}
    warnings = []

    if not SKILLS_DIR.is_dir():
        print(f"ERROR: skills directory not found at {SKILLS_DIR}")
        sys.exit(1)

    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir():
            continue
        name = child.name

        if name in SKIP_DIRS:
            continue

        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            warnings.append(f"WARNING: {name}/ has no SKILL.md, skipping")
            continue

        try:
            file_hash = sha256_file(skill_md)
        except Exception as e:
            warnings.append(f"WARNING: {name}/SKILL.md read error: {e}, skipping")
            continue

        registered[name] = {
            "source": ".",
            "sourceType": "local",
            "skillPath": f"skills/{name}/SKILL.md",
            "computedHash": file_hash,
        }

    return registered, warnings


def load_existing_lock() -> dict:
    """Load existing skills-lock.json, or return a default structure."""
    if LOCK_FILE.is_file():
        try:
            with open(LOCK_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: failed to parse {LOCK_FILE}: {e}, starting fresh")
    return {"version": 1, "skills": {}}


def write_lock(data: dict):
    """Write lock file with consistent formatting."""
    with open(LOCK_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    print("=" * 60)
    print("ARIS Local Skill Registration")
    print("=" * 60)

    # Scan local skills
    local_skills, warnings = scan_local_skills()

    for w in warnings:
        print(w)

    print(f"\nFound {len(local_skills)} local skills with SKILL.md\n")

    # Load existing lock
    lock = load_existing_lock()
    existing_skills = lock.get("skills", {})

    # Separate existing entries into local vs non-local
    preserved = {}
    overwritten = []
    for name, entry in existing_skills.items():
        if entry.get("sourceType") == "local" and entry.get("source") == ".":
            # Will be overwritten
            overwritten.append(name)
        else:
            preserved[name] = entry

    # Merge: non-local preserved + fresh local scan
    merged_skills = dict(preserved)
    merged_skills.update(local_skills)

    lock["version"] = 1
    lock["skills"] = merged_skills
    write_lock(lock)

    # Report
    print(f"Preserved non-local skills: {len(preserved)}")
    for name in preserved:
        print(f"  KEPT    {name} ({preserved[name].get('sourceType', '?')})")

    print(f"\nRegistered local skills: {len(local_skills)}")
    for name in local_skills:
        print(f"  REGISTER {name}")

    if overwritten:
        print(f"\nOverwritten (re-scanned): {len(overwritten)}")
        for name in overwritten:
            if name not in local_skills:
                print(f"  REMOVED {name} (no longer has SKILL.md)")
            else:
                print(f"  UPDATED {name}")

    print("\n" + "=" * 60)
    print("Done. skills-lock.json updated.")
    print("=" * 60)

    # Quick check for required skills
    required = [
        "idea-discovery",
        "research-lit",
        "idea-creator",
        "exec-review",
        "novelty-check",
        "idea-bank",
        "session-orchestrator",
        "session-handoff",
        "status",
    ]
    missing = [r for r in required if r not in merged_skills]
    if missing:
        print(f"\nWARNING: Required skills not found on disk: {missing}")
    else:
        print("\nAll required skills are registered.")


if __name__ == "__main__":
    main()

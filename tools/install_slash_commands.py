"""Install slash command templates into .claude/commands/.

Copies templates/claude_commands/*.md to .claude/commands/.
Does not overwrite existing files unless --force is passed.
Does not commit .claude/ (it is gitignored).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "claude_commands"
TARGET_DIR = Path(__file__).resolve().parent.parent / ".claude" / "commands"


def install(force: bool = False) -> list[str]:
    """Copy template commands to .claude/commands/. Returns list of installed files."""
    if not TEMPLATE_DIR.exists():
        print(f"ERROR: Template directory not found: {TEMPLATE_DIR}")
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    installed = []
    skipped = []

    for src in sorted(TEMPLATE_DIR.glob("*.md")):
        dst = TARGET_DIR / src.name
        if dst.exists() and not force:
            skipped.append(src.name)
            continue
        shutil.copy2(src, dst)
        installed.append(src.name)

    return installed, skipped


def check_gitignore() -> bool:
    """Check that .claude/ is in .gitignore."""
    gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
    if not gitignore.exists():
        return False
    content = gitignore.read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == ".claude/" or stripped == ".claude":
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Install slash command templates into .claude/commands/"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing command files"
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="Run self-tests"
    )

    args = parser.parse_args()

    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)

    print(f"Template source:  {TEMPLATE_DIR}")
    print(f"Install target:   {TARGET_DIR}")
    print()

    installed, skipped = install(force=args.force)

    if installed:
        print(f"Installed {len(installed)} command(s):")
        for name in installed:
            print(f"  + {name}")
    else:
        print("No new commands installed (all already exist).")

    if skipped:
        print(f"\nSkipped {len(skipped)} (already exist, use --force to overwrite):")
        for name in skipped:
            print(f"  - {name}")

    # Check gitignore
    if check_gitignore():
        print("\n.gitignore: .claude/ is properly ignored (will not be committed).")
    else:
        print("\nWARNING: .claude/ not found in .gitignore! Add '.claude/' to .gitignore.")

    print("\nDone. Restart Claude/Happy session to use new commands.")


def _self_test() -> bool:
    """Run self-tests for the install script."""
    tests_passed = 0
    tests_failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal tests_passed, tests_failed
        if condition:
            print(f"  [PASS] {name}")
            tests_passed += 1
        else:
            print(f"  [FAIL] {name} — {detail}")
            tests_failed += 1

    import tempfile

    # Test 1: Template dir exists and has files
    check("1. template dir exists", TEMPLATE_DIR.exists() and len(list(TEMPLATE_DIR.glob("*.md"))) == 7,
          f"found {len(list(TEMPLATE_DIR.glob('*.md'))) if TEMPLATE_DIR.exists() else 0} files")

    # Test 2: install creates target dir and copies files
    with tempfile.TemporaryDirectory() as td:
        fake_target = Path(td) / ".claude" / "commands"
        # Monkey-patch TARGET_DIR via module reference
        import sys
        _mod = sys.modules[__name__]
        orig = _mod.TARGET_DIR
        _mod.TARGET_DIR = fake_target
        try:
            installed, skipped = install(force=False)
            check("2. install copies files", len(installed) == 7 and fake_target.exists(),
                  f"installed={len(installed)}, target_exists={fake_target.exists()}")
            check("2b. all 7 commands present", sorted([f.name for f in fake_target.glob("*.md")]) ==
                  ["experiment.md", "idea-audit.md", "idea-synthesis.md", "literature-intake.md",
                   "paper-writing.md", "research-intake.md", "status.md"])
        finally:
            _mod.TARGET_DIR = orig

    # Test 3: install with force overwrites
    with tempfile.TemporaryDirectory() as td:
        fake_target = Path(td) / ".claude" / "commands"
        _mod.TARGET_DIR = fake_target
        try:
            install(force=False)  # first install
            installed2, skipped2 = install(force=False)  # second without force
            check("3. skip existing without force", len(installed2) == 0 and len(skipped2) == 7,
                  f"installed={len(installed2)}, skipped={len(skipped2)}")
            installed3, skipped3 = install(force=True)  # with force
            check("3b. overwrite with force", len(installed3) == 7 and len(skipped3) == 0,
                  f"installed={len(installed3)}, skipped={len(skipped3)}")
        finally:
            _mod.TARGET_DIR = orig

    # Test 4: gitignore check
    check("4. .claude/ in .gitignore", check_gitignore())

    # Test 5: templates have no absolute paths
    safe = True
    for f in TEMPLATE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        if "C:\\" in content or "/home/" in content or "Users/" in content:
            safe = False
            break
    check("5. no absolute paths in templates", safe)

    # Test 6: templates have no API keys
    safe2 = True
    for f in TEMPLATE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        if "api_key" in content.lower() or "sk-" in content or "token" in content.lower():
            safe2 = False
            break
    check("6. no API keys in templates", safe2)

    # Test 7: all templates call slash_command_adapter.py
    all_call_adapter = True
    for f in TEMPLATE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        if "slash_command_adapter.py" not in content:
            all_call_adapter = False
            break
    check("7. all templates call slash_command_adapter.py", all_call_adapter)

    # Test 8: all templates are plan-only (DRY-RUN)
    all_dry_run = True
    for f in TEMPLATE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        if "DRY-RUN" not in content:
            all_dry_run = False
            break
    check("8. all templates are DRY-RUN", all_dry_run)

    print(f"\nSelf-test results: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == "__main__":
    main()

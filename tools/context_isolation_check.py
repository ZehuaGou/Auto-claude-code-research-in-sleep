#!/usr/bin/env python3
"""
Context Isolation Check Script.

Validates that a prompt file contains only content from allowed_input_files
and contains no forbidden context markers.

Usage:
    python tools/context_isolation_check.py --manifest <manifest.json> --input <input.md>
    python tools/context_isolation_check.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FORBIDDEN_MARKERS = [
    "old conclusion",
    "old conclusions",
    "previous optimistic summary",
    "unverified experiment result",
    "mock result",
    "dry-run artifact",
    "external_agent_direct",
    "user preference",
    "other candidates",
    "generator trace",
    # Additional explicit markers from forbidden_context lists
    "unverified results",
    "old failure narratives",
    "diffad claims",
    "tokentr claims",
    "ah_uh results",
    "external agent endorsement",
    "idea generator feedback",
]


def check(manifest_path: Path, input_path: Path) -> dict:
    """Run context isolation check. Returns result dict."""
    result = {
        "status": "FAIL",
        "contamination_scan_status": "failed",
        "reason": "",
        "allowed_files_checked": 0,
        "forbidden_hits": [],
        "unexpected_file_markers": [],
    }

    # 1. Manifest must exist
    if not manifest_path.exists():
        result["reason"] = f"Manifest file not found: {manifest_path}"
        return result

    # 2. Input file must exist
    if not input_path.exists():
        result["reason"] = f"Input file not found: {input_path}"
        return result

    # Load manifest
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        result["reason"] = f"Failed to parse manifest JSON: {e}"
        return result

    # 3. Manifest must contain allowed_input_files
    allowed_input_files = manifest.get("allowed_input_files", [])
    if not allowed_input_files:
        result["reason"] = "Manifest missing 'allowed_input_files'"
        return result

    # 4. Manifest must contain forbidden_context
    forbidden_context = manifest.get("forbidden_context", [])
    if not forbidden_context:
        result["reason"] = "Manifest missing 'forbidden_context'"
        return result

    # 5. Verify allowed_input_files exist (only for real source files, not tmp/staging paths)
    # Skip existence check for placeholder/staging paths — those are caught by
    # _load_stage input check before prepare is called.
    checked = 0
    missing_real = []
    for f in allowed_input_files:
        p = Path(f)
        # Normalize to forward slashes for prefix check (Windows compat)
        pf = Path(f).as_posix()
        # Skip tmp/ and research/current/ placeholders — checked separately by workflow
        if any(pf.startswith(pre) for pre in ("tmp/", "research/current/", "idea-stage/", "novelty-stage/", "review-stage/")):
            continue
        if p.exists():
            checked += 1
        else:
            missing_real.append(str(f))
    result["allowed_files_checked"] = checked
    # Only fail if there are real files that should exist but don't
    if missing_real:
        result["reason"] = f"Allowed input file(s) not found: {missing_real}"
        return result

    # Read input content
    try:
        input_content = input_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        result["reason"] = f"Failed to read input file: {e}"
        return result

    # 6. Check for forbidden markers in input
    hits = []
    for marker in FORBIDDEN_MARKERS:
        if marker.lower() in input_content.lower():
            # Count occurrences
            count = input_content.lower().count(marker.lower())
            hits.append(f"'{marker}' ({count}x)")

    if hits:
        result["forbidden_hits"] = hits
        result["reason"] = f"Found {len(hits)} forbidden marker(s) in input"
        return result

    # 7. Check for unexpected file path markers in input
    # Extract lines that reference file paths
    unexpected = []
    input_lines = input_content.split("\n")
    for line in input_lines:
        if line.startswith("# File:") or line.startswith("## File:"):
            # Extract the path after "# File:" (split on ":" once, then strip)
            parts = line.split(":", 1)
            if len(parts) >= 2:
                ref_path = parts[1].strip().strip("'\"")
                # Check if this path is in allowed_input_files
                allowed_any = any(
                    ref_path == f or (f.split("/")[-1] and ref_path.endswith("/" + f.split("/")[-1]))
                    for f in allowed_input_files
                )
                if not allowed_any and ref_path and not ref_path.startswith("/tmp/") and not ref_path.startswith("tmp/") and not any(ref_path.startswith(pre.rstrip('/')) for pre in ("research/current", "idea-stage", "novelty-stage", "review-stage")):
                    unexpected.append(ref_path)

    if unexpected:
        result["unexpected_file_markers"] = unexpected
        result["reason"] = f"Input references files not in allowed_input_files: {unexpected}"
        return result

    # All checks passed
    result["status"] = "PASS"
    result["contamination_scan_status"] = "checked"
    result["reason"] = "All context isolation checks passed"
    return result


def self_test() -> bool:
    """Run self-test with synthetic fixtures. Returns True if all pass."""
    import tempfile, os

    print("Running self-test...")
    passed = 0
    failed = 0

    # Test 1: manifest missing allowed_input_files
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"forbidden_context": []}, f)
        bad_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("some content")
        bad_input = f.name
    result = check(Path(bad_manifest), Path(bad_input))
    if result["status"] == "FAIL" and "allowed_input_files" in result["reason"]:
        print("  [PASS] 1. Detects missing allowed_input_files")
        passed += 1
    else:
        print(f"  [FAIL] 1. Expected FAIL for missing allowed_input_files, got: {result}")
        failed += 1
    os.unlink(bad_manifest)
    os.unlink(bad_input)

    # Test 2: Clean manifest and input passes
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/brief.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        good_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/brief.md\n\nSome clean research content.")
        good_input = f.name
    result = check(Path(good_manifest), Path(good_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 2. Clean manifest/input passes")
        passed += 1
    else:
        print(f"  [FAIL] 2. Expected PASS for clean input, got: {result}")
        failed += 1
    os.unlink(good_manifest)
    os.unlink(good_input)

    # Test 3: Forbidden marker detected
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/brief.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        dirty_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/brief.md\n\nOld conclusion found in prior runs.")
        dirty_input = f.name
    result = check(Path(dirty_manifest), Path(dirty_input))
    if result["status"] == "FAIL" and result["forbidden_hits"]:
        print("  [PASS] 3. Detects forbidden marker 'old conclusion'")
        passed += 1
    else:
        print(f"  [FAIL] 3. Expected FAIL for forbidden marker, got: {result}")
        failed += 1
    os.unlink(dirty_manifest)
    os.unlink(dirty_input)

    # Test 4: Unexpected file reference detected
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/brief.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        ref_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/brief.md\n\n# File: /forbidden/path.md\n\nclean content")
        ref_input = f.name
    result = check(Path(ref_manifest), Path(ref_input))
    if result["status"] == "FAIL" and result["unexpected_file_markers"]:
        print("  [PASS] 4. Detects unexpected file reference")
        passed += 1
    else:
        print(f"  [FAIL] 4. Expected FAIL for unexpected file ref, got: {result}")
        failed += 1
    os.unlink(ref_manifest)
    os.unlink(ref_input)

    print(f"\nSelf-test results: {passed} passed, {failed} failed")
    return failed == 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        ok = self_test()
        sys.exit(0 if ok else 1)

    import argparse
    parser = argparse.ArgumentParser(description="Context Isolation Check")
    parser.add_argument("--manifest", required=True, help="Path to context manifest JSON")
    parser.add_argument("--input", required=True, help="Path to input prompt file")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    input_path = Path(args.input)

    result = check(manifest_path, input_path)
    print(json.dumps(result, indent=2))

    if result["status"] == "PASS":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
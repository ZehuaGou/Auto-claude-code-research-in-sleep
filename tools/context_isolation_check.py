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

def normalize_context_path(path: str) -> tuple[str, bool]:
    """Normalize a path for cross-platform context isolation comparison.

    Returns (normalized_path, is_safe):
      - normalized_path: forward-slashes, no duplicate slashes, no leading ./, no trailing slash
      - is_safe: False if the path contains parent traversal (..) that could escape allowed scope
    """
    p = path.strip().strip("'\"")
    p = p.replace("\\", "/")
    # Collapse duplicate slashes
    while "//" in p:
        p = p.replace("//", "/")
    # Strip leading ./ repeatedly
    while p.startswith("./"):
        p = p[2:]
    # Strip trailing slash (but not root "/")
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/")
    # Reject parent traversal
    if p == ".." or p.startswith("../") or "/../" in p:
        return p, False
    return p, True


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


def strip_yaml_frontmatter_blocks(text: str) -> str:
    """Remove YAML frontmatter blocks from each file section in a combined input.

    A combined input.md from workflow prepare contains one or more file sections:
        # File: path/to/file.md
        ---
        yaml header
        ---
        body
        ---
        (next file...)

    This function strips the YAML frontmatter (between the first '---' after
    '# File:' or at the very start, and its closing '---') from each file
    section, so that forbidden-marker scanning only hits the actual body
    content and not the artifact metadata in headers.

    Rules:
    - Handles '# File:' section headers with optional leading blank lines.
    - Handles file blocks that start with a frontmatter at the very beginning.
    - Returns the stripped text with frontmatter lines removed.
    - Does NOT remove markdown dividers ('---') that appear in body content.
    """
    lines = text.split("\n")
    result_lines = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Detect start of a file section
        if line.startswith("# File:") or (line == "---" and i == 0):
            # Collect the header line(s) before frontmatter
            header_lines = [line]
            i += 1

            # Skip leading blank lines before potential frontmatter
            while i < n and lines[i].strip() == "":
                header_lines.append(lines[i])
                i += 1

            # Check if next non-blank line opens a frontmatter
            if i < n and lines[i] == "---":
                # Consume the opening ---
                header_lines.append(lines[i])
                i += 1
                # Skip until closing ---
                depth = 1
                while i < n and depth > 0:
                    if lines[i] == "---":
                        depth -= 1
                        if depth == 0:
                            break
                        header_lines.append(lines[i])  # include closing line in header_lines so we skip it
                    elif lines[i].startswith("---") and len(lines[i]) == 3:
                        # Could be a nested or consecutive divider
                        pass
                    i += 1
                # i now points to line after closing --- (or end)
                # header_lines contains everything we want to skip
                # Don't add frontmatter lines to result
                result_lines.extend(header_lines[:-1])  # keep everything before closing ---
                # Skip the closing --- line itself
                # result_lines stays at header_lines[-1] which was skipped
                # Now continue to add body lines
            else:
                # No frontmatter found; add all collected header_lines
                result_lines.extend(header_lines)
                header_lines = []

            # Now add body lines until next '# File:' or end
            while i < n:
                if lines[i].startswith("# File:"):
                    break
                result_lines.append(lines[i])
                i += 1
        else:
            # Standalone line not part of a '# File:' section
            result_lines.append(lines[i])
            i += 1

    return "\n".join(result_lines)


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
    # Strip YAML frontmatter from file sections so metadata doesn't trigger false positives
    scan_content = strip_yaml_frontmatter_blocks(input_content)
    hits = []
    for marker in FORBIDDEN_MARKERS:
        if marker.lower() in scan_content.lower():
            # Count occurrences
            count = scan_content.lower().count(marker.lower())
            hits.append(f"'{marker}' ({count}x)")

    if hits:
        result["forbidden_hits"] = hits
        result["reason"] = f"Found {len(hits)} forbidden marker(s) in input"
        return result

    # 7. Check for unexpected file path markers in input
    # Extract lines that reference file paths
    unexpected = []
    # Build normalized allowed set for O(1) lookup
    allowed_norms = set()
    for f in allowed_input_files:
        norm_f, safe_f = normalize_context_path(f)
        if safe_f:
            allowed_norms.add(norm_f)

    input_lines = input_content.split("\n")
    for line in input_lines:
        if line.startswith("# File:") or line.startswith("## File:"):
            # Extract the path after "# File:" (split on ":" once, then strip)
            parts = line.split(":", 1)
            if len(parts) >= 2:
                ref_path = parts[1].strip().strip("'\"")
                if not ref_path:
                    continue
                norm_ref, safe_ref = normalize_context_path(ref_path)
                # Reject traversal in ref_path
                if not safe_ref:
                    unexpected.append(ref_path)
                    continue
                # Exact match against normalized allowed set
                if norm_ref in allowed_norms:
                    continue
                # Allow tmp/ staging prefix only
                if norm_ref.startswith("tmp/"):
                    continue
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

    # Test 5: Forbidden context markers in YAML header should NOT cause false positive
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        header_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/input_normalization.md\n")
        f.write("---\n")
        f.write("forbidden_context: [\"old conclusions\", \"mock results\", \"external_agent_direct\"]\n")
        f.write("verification_status: verified_routed_call\n")
        f.write("---\n")
        f.write("# Normalized Brief\n")
        f.write("Clean body.\n")
        header_input = f.name
    result = check(Path(header_manifest), Path(header_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 5. YAML header forbidden_context does not cause false positive")
        passed += 1
    else:
        print(f"  [FAIL] 5. Expected PASS (header should not trigger), got: {result}")
        failed += 1
    os.unlink(header_manifest)
    os.unlink(header_input)

    # Test 6: Same YAML header but body contains forbidden marker → should still FAIL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        body_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/input_normalization.md\n")
        f.write("---\n")
        f.write("forbidden_context: [\"old conclusions\", \"mock results\", \"external_agent_direct\"]\n")
        f.write("verification_status: verified_routed_call\n")
        f.write("---\n")
        f.write("# Normalized Brief\n")
        f.write("Old conclusion found in body.\n")
        body_input = f.name
    result = check(Path(body_manifest), Path(body_input))
    if result["status"] == "FAIL" and result["forbidden_hits"]:
        print("  [PASS] 6. Forbidden marker in body still detected after header strip")
        passed += 1
    else:
        print(f"  [FAIL] 6. Expected FAIL (body has forbidden marker), got: {result}")
        failed += 1
    os.unlink(body_manifest)
    os.unlink(body_input)

    # Test 7: Windows backslash in manifest, forward slash in input → should PASS
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research\\current\\brief.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        win_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/brief.md\n\nClean content.")
        fwd_input = f.name
    result = check(Path(win_manifest), Path(fwd_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 7. Windows backslash in manifest matches forward slash in input")
        passed += 1
    else:
        print(f"  [FAIL] 7. Expected PASS for mixed separators, got: {result}")
        failed += 1
    os.unlink(win_manifest)
    os.unlink(fwd_input)

    # Test 8: Forward slash in manifest, backslash in input → should PASS
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/brief.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        fwd_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research\\current\\brief.md\n\nClean content.")
        win_input = f.name
    result = check(Path(fwd_manifest), Path(win_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 8. Forward slash in manifest matches backslash in input")
        passed += 1
    else:
        print(f"  [FAIL] 8. Expected PASS for mixed separators, got: {result}")
        failed += 1
    os.unlink(fwd_manifest)
    os.unlink(win_input)

    # Test 9: Mixed backslash subpath in manifest, forward slash in input → should PASS
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["literature\\search_runs\\current\\top_k.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        deep_win_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: literature/search_runs/current/top_k.md\n\nClean content.")
        deep_fwd_input = f.name
    result = check(Path(deep_win_manifest), Path(deep_fwd_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 9. Deep Windows subpath matches forward slash in input")
        passed += 1
    else:
        print(f"  [FAIL] 9. Expected PASS for mixed deep subpath, got: {result}")
        failed += 1
    os.unlink(deep_win_manifest)
    os.unlink(deep_fwd_input)

    # Test 10: Leading ./ normalized away → should PASS
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        t10_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: ./research/current/input_normalization.md\n\nClean content.")
        t10_input = f.name
    result = check(Path(t10_manifest), Path(t10_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 10. Leading ./ normalized away matches allowed path")
        passed += 1
    else:
        print(f"  [FAIL] 10. Expected PASS for leading ./ normalization, got: {result}")
        failed += 1
    os.unlink(t10_manifest)
    os.unlink(t10_input)

    # Test 11: Duplicate slashes normalized away → should PASS
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research//current//input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        t11_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/input_normalization.md\n\nClean content.")
        t11_input = f.name
    result = check(Path(t11_manifest), Path(t11_input))
    if result["status"] == "PASS" and result["contamination_scan_status"] == "checked":
        print("  [PASS] 11. Duplicate slashes normalized away matches allowed path")
        passed += 1
    else:
        print(f"  [FAIL] 11. Expected PASS for duplicate slash normalization, got: {result}")
        failed += 1
    os.unlink(t11_manifest)
    os.unlink(t11_input)

    # Test 12: Different file name, same directory → should FAIL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        t12_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/other.md\n\nClean content.")
        t12_input = f.name
    result = check(Path(t12_manifest), Path(t12_input))
    if result["status"] == "FAIL" and result["unexpected_file_markers"]:
        print("  [PASS] 12. Different filename in same directory rejected")
        passed += 1
    else:
        print(f"  [FAIL] 12. Expected FAIL for different filename, got: {result}")
        failed += 1
    os.unlink(t12_manifest)
    os.unlink(t12_input)

    # Test 13: Same basename with .bak suffix → should FAIL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        t13_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/input_normalization.md.bak\n\nClean content.")
        t13_input = f.name
    result = check(Path(t13_manifest), Path(t13_input))
    if result["status"] == "FAIL" and result["unexpected_file_markers"]:
        print("  [PASS] 13. .bak suffix spoof rejected")
        passed += 1
    else:
        print(f"  [FAIL] 13. Expected FAIL for .bak spoof, got: {result}")
        failed += 1
    os.unlink(t13_manifest)
    os.unlink(t13_input)

    # Test 14: Same basename in different directory → should FAIL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        t14_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: some/other/input_normalization.md\n\nClean content.")
        t14_input = f.name
    result = check(Path(t14_manifest), Path(t14_input))
    if result["status"] == "FAIL" and result["unexpected_file_markers"]:
        print("  [PASS] 14. Same basename in different directory rejected")
        passed += 1
    else:
        print(f"  [FAIL] 14. Expected FAIL for basename spoof, got: {result}")
        failed += 1
    os.unlink(t14_manifest)
    os.unlink(t14_input)

    # Test 15: Parent traversal (../secrets.md) → should FAIL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "allowed_input_files": ["research/current/input_normalization.md"],
            "forbidden_context": ["old conclusions"]
        }, f)
        t15_manifest = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# File: research/current/../secrets.md\n\nClean content.")
        t15_input = f.name
    result = check(Path(t15_manifest), Path(t15_input))
    if result["status"] == "FAIL" and result["unexpected_file_markers"]:
        print("  [PASS] 15. Parent traversal rejected")
        passed += 1
    else:
        print(f"  [FAIL] 15. Expected FAIL for traversal, got: {result}")
        failed += 1
    os.unlink(t15_manifest)
    os.unlink(t15_input)

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
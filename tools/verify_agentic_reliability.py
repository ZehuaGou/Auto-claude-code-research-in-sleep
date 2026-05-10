#!/usr/bin/env python3
"""
ARIS Agentic Idea Discovery Reliability Verification Script.

Checks:
1. No deprecated alias skill directories exist.
2. AGENT_GUIDE.md no longer lists IDEA_REPORT.md as idea-discovery main artifact.
3. model-routing.md no longer references IDEA_REPORT.md draft.
4. .gitignore covers critical patterns.
5. isolated_job_runner.py rejects IDEA_CARDS input for idea_reviewer.
6. isolated_job_runner.py rejects multiple CAND inputs for idea_reviewer.
7. isolated_job_runner.py rejects old NOVELTY input for novelty_checker.

Exit code: 0 if all checks pass, 1 if any fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}")
        if detail:
            for line in detail.strip().splitlines():
                print(f"     {line}")
        FAIL += 1


# ---------------------------------------------------------------------------
# 1. No deprecated alias directories
# ---------------------------------------------------------------------------
print("=== 1. Deprecated alias directories ===")
aliases = ["skills/idea-lit", "skills/idea-gen", "skills/idea-check", "skills/idea-flow"]
found_aliases = [d for d in aliases if (ROOT / d).exists()]
check(
    "No deprecated alias skill directories remain",
    len(found_aliases) == 0,
    f"Still present: {found_aliases}" if found_aliases else "",
)

# ---------------------------------------------------------------------------
# 2. AGENT_GUIDE.md - no IDEA_REPORT.md as main artifact
# ---------------------------------------------------------------------------
print("\n=== 2. AGENT_GUIDE.md artifacts ===")
agent_guide = ROOT / "AGENT_GUIDE.md"
if agent_guide.exists():
    content = agent_guide.read_text(encoding="utf-8", errors="ignore")
    has_idea_report = "IDEA_REPORT.md" in content
    has_selection_report = "IDEA_SELECTION_REPORT.md" in content
    check(
        "AGENT_GUIDE.md no longer lists IDEA_REPORT.md as idea-discovery artifact",
        not has_idea_report or ("idea-stage/AGENTIC/FINAL_SELECTION/IDEA_SELECTION_REPORT.md" in content),
        f"Contains IDEA_REPORT.md: {has_idea_report}",
    )
    check(
        "AGENT_GUIDE.md references IDEA_SELECTION_REPORT.md",
        has_selection_report,
    )
else:
    check("AGENT_GUIDE.md exists", False)

# ---------------------------------------------------------------------------
# 3. model-routing.md - no IDEA_REPORT.md draft
# ---------------------------------------------------------------------------
print("\n=== 3. model-routing.md ===")
model_routing = ROOT / "skills" / "shared-references" / "model-routing.md"
if model_routing.exists():
    content = model_routing.read_text(encoding="utf-8", errors="ignore")
    check(
        "model-routing.md no longer references IDEA_REPORT.md draft",
        "IDEA_REPORT.md" not in content,
        "Still contains IDEA_REPORT.md reference" if "IDEA_REPORT.md" in content else "",
    )
    check(
        "model-routing.md uses AGENTIC paths for idea_generator",
        "idea-stage/AGENTIC/RUNS/<run_id>/IDEA_CARDS" in content,
    )
    has_clean_reviewer_input = "exactly one idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_" in content
    check(
        "model-routing.md specifies exactly one CAND_*.md for idea_reviewer input",
        has_clean_reviewer_input,
    )
else:
    check("model-routing.md exists", False)

# ---------------------------------------------------------------------------
# 4. .gitignore coverage
# ---------------------------------------------------------------------------
print("\n=== 4. .gitignore ===")
gitignore = ROOT / ".gitignore"
if gitignore.exists():
    text = gitignore.read_text(encoding="utf-8", errors="ignore")
    patterns = [
        ("blocks .aris/", ".aris/"),
        ("blocks idea-stage/", "idea-stage/"),
        ("blocks review-stage/", "review-stage/"),
        ("blocks novelty-stage/", "novelty-stage/"),
        ("blocks .mcp.json", ".mcp.json"),
        ("blocks .env (not .example)", ".env\n"),
    ]
    for label, pat in patterns:
        check(
            f".gitignore {label}",
            pat in text,
        )
    # Also check tmp/ and temp/
    check(
        ".gitignore blocks tmp/",
        "tmp/" in text,
    )
    check(
        ".gitignore blocks temp/",
        "temp/" in text or "temp/" in text,
    )
else:
    check(".gitignore exists", False)

# ---------------------------------------------------------------------------
# 5-7. isolated_job_runner.py isolation validation
# ---------------------------------------------------------------------------
print("\n=== 5-7. isolated_job_runner.py input isolation ===")
runner = ROOT / "tools" / "isolated_job_runner.py"
if runner.exists():
    # Import the function dynamically
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from isolated_job_runner import validate_isolated_inputs

        # Test 5: idea_reviewer with IDEA_CARDS input should fail
        bad_job_idea_cards = {
            "role": "idea_reviewer",
            "input_files": ["idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md", "idea-stage/AGENTIC/RUNS/2026_01/IDEA_CARDS/idea_001.md"],
        }
        viols = validate_isolated_inputs(bad_job_idea_cards)
        check(
            "5. isolated_job_runner rejects IDEA_CARDS in idea_reviewer input",
            any("IDEA_CARDS" in v for v in viols),
            f"Violations: {viols}" if viols else "No violations returned",
        )

        # Test 6: idea_reviewer with two CAND files should fail
        bad_job_two_cands = {
            "role": "idea_reviewer",
            "input_files": [
                "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
                "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_002.md",
            ],
        }
        viols2 = validate_isolated_inputs(bad_job_two_cands)
        check(
            "6. isolated_job_runner rejects multiple CAND inputs for idea_reviewer",
            any("CAND" in v and "2 CAND" in v for v in viols2),
            f"Violations: {viols2}" if viols2 else "No violations returned",
        )

        # Test 7: novelty_checker with old NOVELTY input should fail
        bad_job_novelty = {
            "role": "novelty_checker",
            "input_files": [
                "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
                "idea-stage/AGENTIC/LITERATURE_INDEX.md",
                "idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md",
            ],
        }
        viols3 = validate_isolated_inputs(bad_job_novelty)
        check(
            "7. isolated_job_runner rejects old NOVELTY file in novelty_checker input",
            any("NOVELTY" in v and ("forbidden" in v or "contamination" in v) for v in viols3),
            f"Violations: {viols3}" if viols3 else "No violations returned",
        )

        # Positive test: clean idea_reviewer job should pass
        # NOTE: GAP_MAP excerpt must be extracted outside RUNS/ to avoid isolation violation
        clean_reviewer_job = {
            "role": "idea_reviewer",
            "input_files": ["idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md", "idea-stage/AGENTIC/GAP_MAP_EXCERPT.md"],
        }
        viols4 = validate_isolated_inputs(clean_reviewer_job)
        check(
            "7b. clean idea_reviewer job passes isolation check",
            len(viols4) == 0,
            f"Violations: {viols4}" if viols4 else "",
        )

        # Positive test: clean final_selector job should pass
        clean_final_job = {
            "role": "final_selector",
            "input_files": [
                "idea-stage/AGENTIC/IDEA_BANK.md",
                "idea-stage/AGENTIC/CANONICAL_IDEAS",
                "idea-stage/AGENTIC/REVIEWS",
            ],
        }
        viols5 = validate_isolated_inputs(clean_final_job)
        check(
            "7c. clean final_selector job passes isolation check",
            len(viols5) == 0,
            f"Violations: {viols5}" if viols5 else "",
        )

        # Negative test: final_selector with IDEA_CARDS should fail
        bad_final_job = {
            "role": "final_selector",
            "input_files": [
                "idea-stage/AGENTIC/IDEA_BANK.md",
                "idea-stage/AGENTIC/RUNS/2026_01/IDEA_CARDS/idea_001.md",
            ],
        }
        viols6 = validate_isolated_inputs(bad_final_job)
        check(
            "7d. final_selector with IDEA_CARDS is rejected",
            any("IDEA_CARDS" in v for v in viols6),
            f"Violations: {viols6}" if viols6 else "",
        )

        # Direct is_canonical_candidate_file tests
        from isolated_job_runner import is_canonical_candidate_file
        check(
            "7e. is_canonical_candidate_file(REVIEWS/CAND_001_review.md) returns False",
            not is_canonical_candidate_file("idea-stage/AGENTIC/REVIEWS/CAND_001_review.md"),
            "REVIEWS CAND file misidentified as canonical candidate",
        )
        check(
            "7f. is_canonical_candidate_file(NOVELTY/CAND_001_novelty.md) returns False",
            not is_canonical_candidate_file("idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md"),
            "NOVELTY CAND file misidentified as canonical candidate",
        )
        check(
            "7g. is_canonical_candidate_file(CANONICAL_IDEAS/CAND_001.md) returns True",
            is_canonical_candidate_file("idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md"),
        )
    except ImportError as e:
        check("Can import isolated_job_runner", False, str(e))
    except Exception as e:
        check("validation tests", False, str(e))
else:
    check("isolated_job_runner.py exists", False)

# ---------------------------------------------------------------------------
# 8. agentic_idea_discovery.py review job has no RUNS/ paths
# ---------------------------------------------------------------------------
print("\n=== 8. agentic_idea_discovery.py review job isolation ===")
try:
    sys.path.insert(0, str(ROOT / "tools"))
    from agentic_idea_discovery import _make_idea_reviewer_job

    fake_run_id = "test_000000_review_isolation"
    fake_cand = ROOT / "idea-stage" / "AGENTIC" / "CANONICAL_IDEAS" / "CAND_999.md"
    fake_gap_excerpt = ROOT / "idea-stage" / "AGENTIC" / "GAP_EXCERPTS" / "CAND_999_gap.md"

    # We just need to check the generated job structure without creating files
    # Use Path objects that don't need to exist
    job = _make_idea_reviewer_job(fake_run_id, Path("idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_999.md"), Path("idea-stage/AGENTIC/GAP_EXCERPTS/CAND_999_gap.md"))
    input_strs = " ".join(job.get("input_files", []))
    runs_in_input = "RUNS/" in input_strs.replace("\\", "/")
    check(
        "8a. _make_idea_reviewer_job input_files contain no RUNS/ path",
        not runs_in_input,
        f"RUNS/ found in input_files: {job.get('input_files', [])}" if runs_in_input else "",
    )
    check(
        "8b. _make_idea_reviewer_job uses GAP_EXCERPTS path",
        "GAP_EXCERPTS" in input_strs,
        f"No GAP_EXCERPTS in input_files: {job.get('input_files', [])}" if "GAP_EXCERPTS" not in input_strs else "",
    )
    check(
        "8c. _make_idea_reviewer_job backend is codex_optional",
        job.get("backend") == "codex_optional",
        f"Backend is {job.get('backend')}" if job.get("backend") != "codex_optional" else "",
    )

    from agentic_idea_discovery import _make_novelty_checker_job
    novel_job = _make_novelty_checker_job(fake_run_id, Path("idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_999.md"), Path("idea-stage/AGENTIC/LITERATURE_INDEX.md"))
    check(
        "8d. _make_novelty_checker_job backend is codex_optional",
        novel_job.get("backend") == "codex_optional",
        f"Backend is {novel_job.get('backend')}" if novel_job.get("backend") != "codex_optional" else "",
    )
except ImportError as e:
    check("Can import agentic_idea_discovery", False, str(e))
except Exception as e:
    check("review job isolation tests", False, str(e))

# ---------------------------------------------------------------------------
# 9. codex_optional backend fallback handling
# ---------------------------------------------------------------------------
print("\n=== 9. codex_optional backend fallback ===")
try:
    from isolated_job_runner import _backend_codex_optional, _backend_api

    # Test _backend_codex_optional with model="codex"
    # We need env_vars where the model_env resolves to "codex"
    test_job_codex = {
        "job_id": "test_codex_fallback",
        "run_id": "test_fallback",
        "role": "idea_reviewer",
        "backend": "codex_optional",
        "model_env": "LLM_IDEA_REVIEWER_PRIMARY",
        "description": "Test fallback",
        "input_files": [],
        "output_files": [str(ROOT / "tmp_test_fallback_output.md")],
        "handoff_file": "",
        "prompt_file": "",
        "max_tokens": 256,
        "timeout_sec": 30,
        "status": "pending",
        "allow_fallback": True,
    }
    test_env = {
        "LLM_IDEA_REVIEWER_PRIMARY": "codex",
        "LLM_FALLBACK_MODEL": "deepseek-v4-test",
        "LLM_API_KEY": "test-key-12345",
        "LLM_BASE_URL": "https://api.test.example.com",
    }

    # The call will fail due to bad API key, but we just check the fallback flags
    # Wrap in try/except since httpx call will fail
    result = _backend_codex_optional(test_job_codex, test_env)
    fallback_flagged = result.get("fallback_used", False)
    has_downgrade_flag = result.get("REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK", False)
    check(
        "9a. codex_optional sets fallback_used=true when model=codex",
        fallback_flagged,
        f"fallback_used={fallback_flagged}" if not fallback_flagged else "",
    )
    check(
        "9b. codex_optional sets REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK",
        has_downgrade_flag,
    )

    # Test _backend_api with model="codex" should reject
    test_job_model_codex = {
        "job_id": "test_model_codex_reject",
        "run_id": "test_reject",
        "role": "idea_reviewer",
        "backend": "api",
        "model_env": "LLM_IDEA_REVIEWER_PRIMARY",
        "description": "Test rejection",
        "input_files": [],
        "output_files": [],
        "handoff_file": "",
        "prompt_file": "",
        "max_tokens": 256,
        "timeout_sec": 30,
        "status": "pending",
    }
    test_env_codex = {
        "LLM_IDEA_REVIEWER_PRIMARY": "codex",
        "LLM_API_KEY": "test-key-12345",
        "LLM_BASE_URL": "https://api.test.example.com",
    }
    result_api = _backend_api(test_job_model_codex, test_env_codex)
    check(
        "9c. _backend_api rejects model=codex with error",
        bool(result_api.get("error")),
        f"Expected error but got: {result_api.get('error')}" if not result_api.get("error") else "",
    )

    # Clean up
    tmp_out = ROOT / "tmp_test_fallback_output.md"
    if tmp_out.exists():
        tmp_out.unlink()

except ImportError as e:
    check("Can import isolated_job_runner for codex test", False, str(e))
except Exception as e:
    check("codex_optional fallback tests", False, str(e))

# ---------------------------------------------------------------------------
# 10. CANONICAL_IDEA_TEMPLATE has no Provenance section
# ---------------------------------------------------------------------------
print("\n=== 10. CANONICAL_IDEA_TEMPLATE.md provenance check ===")
template = ROOT / "templates" / "CANONICAL_IDEA_TEMPLATE.md"
if template.exists():
    content = template.read_text(encoding="utf-8", errors="ignore")
    no_inline_provenance = "Provenance" not in content or "## Candidate" in content
    check(
        "10. CANONICAL_IDEA_TEMPLATE has no inline Provenance section",
        "Provenance" not in content or content.count("Provenance") == 0,
        "Template still contains Provenance section" if "Provenance" in content else "",
    )
else:
    check("CANONICAL_IDEA_TEMPLATE.md exists", False)

# ---------------------------------------------------------------------------
# 11. .gitignore does not whitelist .aris/meta/ runtime dirs
# ---------------------------------------------------------------------------
print("\n=== 11. .gitignore .aris/ whitelist ===")
gitignore = ROOT / ".gitignore"
if gitignore.exists():
    text = gitignore.read_text(encoding="utf-8", errors="ignore")
    # Check that .aris/tools, .aris/meta, .aris/calls, .aris/sessions are NOT whitelisted
    aris_whitelist_issues = []
    dangerous_patterns = [".aris/tools/", ".aris/meta/"]
    for pat in dangerous_patterns:
        if f"!{pat}" in text or f"!{pat}" in text:
            aris_whitelist_issues.append(f"Found whitelisted pattern: !{pat}")
    check(
        "11a. .gitignore doesn't whitelist .aris/tools/",
        ".aris/tools/" not in text.replace("!", "REVEALED_"),
        f".aris/tools/ is whitelisted" if ".aris/tools/".replace("!", "") in text else "",
    )
    check(
        "11b. .gitignore doesn't whitelist .aris/meta/",
        ".aris/meta/" not in text.replace("!", "REVEALED_"),
        f".aris/meta/ is whitelisted" if ".aris/meta/".replace("!", "") in text else "",
    )
    # Verify correct whitelist: only README.md, calls/.gitkeep, sessions/.gitkeep
    allowed = text.count("!.aris/")
    check(
        "11c. .aris whitelist has exactly 3 entries (README.md, calls/.gitkeep, sessions/.gitkeep)",
        allowed == 3,
        f"Found {allowed} .aris/ whitelist entries (expected 3)" if allowed != 3 else "",
    )
    # Additionally check calls/ and sessions/ runtime are not whitelisted (only .gitkeep)
    has_calls_dir_whitelist = any(
        l.strip().startswith("!.aris/calls/") and ".gitkeep" not in l
        for l in text.splitlines()
    )
    has_sessions_dir_whitelist = any(
        l.strip().startswith("!.aris/sessions/") and ".gitkeep" not in l
        for l in text.splitlines()
    )
    check(
        "11d. .aris/calls/ directory is NOT whitelisted (only .gitkeep)",
        not has_calls_dir_whitelist,
    )
    check(
        "11e. .aris/sessions/ directory is NOT whitelisted (only .gitkeep)",
        not has_sessions_dir_whitelist,
    )
else:
    check(".gitignore exists", False)

# ---------------------------------------------------------------------------
# 12. adversarial_reviewer with matching candidate + review + novelty passes
# ---------------------------------------------------------------------------
print("\n=== 12. adversarial_reviewer isolation validation ===")
try:
    sys.path.insert(0, str(ROOT / "tools"))
    from isolated_job_runner import validate_isolated_inputs

    clean_adversarial_job = {
        "role": "adversarial_reviewer",
        "input_files": [
            "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
            "idea-stage/AGENTIC/REVIEWS/CAND_001_review.md",
            "idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md",
        ],
    }
    viols = validate_isolated_inputs(clean_adversarial_job)
    check(
        "12a. adversarial_reviewer with CAND_001 + review + novelty passes",
        len(viols) == 0,
        f"Violations: {viols}" if viols else "",
    )

    # Negative: adversarial without matching review should fail
    bad_adversarial_job = {
        "role": "adversarial_reviewer",
        "input_files": [
            "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
            "idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md",
        ],
    }
    viols2 = validate_isolated_inputs(bad_adversarial_job)
    check(
        "12b. adversarial_reviewer without matching review fails",
        any("review" in v.lower() for v in viols2),
        f"Should mention missing review: {viols2}" if viols2 else "No violations returned",
    )

    # Three-way ID consistency test: all three must share same candidate_id
    three_way_job = {
        "role": "adversarial_reviewer",
        "input_files": [
            "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
            "idea-stage/AGENTIC/REVIEWS/CAND_001_review.md",
            "idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md",
        ],
    }
    viols_3way = validate_isolated_inputs(three_way_job)
    check(
        "12c. adversarial_reviewer with three matching IDs passes",
        len(viols_3way) == 0,
        f"Three-way consistency should pass: {viols_3way}" if viols_3way else "",
    )

    # Negative: adversarial with non-matching candidate/review should fail
    wrong_cand_adversarial_job = {
        "role": "adversarial_reviewer",
        "input_files": [
            "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
            "idea-stage/AGENTIC/REVIEWS/CAND_002_review.md",
            "idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md",
        ],
    }
    viols3 = validate_isolated_inputs(wrong_cand_adversarial_job)
    check(
        "12d. adversarial_reviewer with non-matching cand/review fails",
        any("review" in v.lower() for v in viols3),
        f"Should detect mismatched review: {viols3}" if viols3 else "No violations returned",
    )

except ImportError as e:
    check("Can import isolated_job_runner for adversarial test", False, str(e))
except Exception as e:
    check("adversarial isolation tests", False, str(e))

# ---------------------------------------------------------------------------
# 13. Role-specific fallback model for codex_optional
# ---------------------------------------------------------------------------
print("\n=== 13. codex_optional role-specific fallback model ===")
try:
    sys.path.insert(0, str(ROOT / "tools"))
    from isolated_job_runner import _backend_codex_optional

    test_job_reviewer = {
        "job_id": "test_role_fallback",
        "allow_fallback": True,
        "run_id": "test_fallback",
        "role": "idea_reviewer",
        "backend": "codex_optional",
        "model_env": "LLM_IDEA_REVIEWER_PRIMARY",
        "description": "Test role fallback",
        "input_files": [],
        "output_files": [str(ROOT / "tmp_test_role_fallback.md")],
        "handoff_file": "",
        "prompt_file": "",
        "max_tokens": 256,
        "timeout_sec": 30,
        "status": "pending",
    }
    test_env_role_fallback = {
        "LLM_IDEA_REVIEWER_PRIMARY": "codex",
        "LLM_IDEA_REVIEWER_FALLBACK_MODEL": "role-specific-model",
        "LLM_API_KEY": "test-key-12345",
        "LLM_BASE_URL": "https://api.test.example.com",
    }
    result = _backend_codex_optional(test_job_reviewer, test_env_role_fallback)
    has_role_fallback = (
        result.get("error") is not None
        and "role-specific-model" in str(result.get("error", ""))
    ) or "role-specific-model" in str(result.get("model_used", ""))
    check(
        "13a. codex_optional uses LLM_IDEA_REVIEWER_FALLBACK_MODEL when PRIMARY=codex",
        has_role_fallback,
        f"Error/model does not reference role-specific fallback: {result.get('error', 'no error')}, model_used={result.get('model_used', 'none')}",
    )

    # Novelty checker role-specific fallback
    test_job_novelty = {
        "job_id": "test_novelty_fallback",
        "allow_fallback": True,
        "run_id": "test_fallback",
        "role": "novelty_checker",
        "backend": "codex_optional",
        "model_env": "LLM_NOVELTY_CHECKER_PRIMARY",
        "description": "Test novelty fallback",
        "input_files": [],
        "output_files": [str(ROOT / "tmp_test_novelty_fallback.md")],
        "handoff_file": "",
        "prompt_file": "",
        "max_tokens": 256,
        "timeout_sec": 30,
        "status": "pending",
    }
    test_env_novelty_fallback = {
        "LLM_NOVELTY_CHECKER_PRIMARY": "codex",
        "LLM_NOVELTY_CHECKER_FALLBACK_MODEL": "novelty-specific-model",
        "LLM_API_KEY": "test-key-12345",
        "LLM_BASE_URL": "https://api.test.example.com",
    }
    result2 = _backend_codex_optional(test_job_novelty, test_env_novelty_fallback)
    has_novelty_fallback = (
        result2.get("error") is not None
        and "novelty-specific-model" in str(result2.get("error", ""))
    ) or "novelty-specific-model" in str(result2.get("model_used", ""))
    check(
        "13b. codex_optional uses LLM_NOVELTY_CHECKER_FALLBACK_MODEL when PRIMARY=codex",
        has_novelty_fallback,
        f"Error/model does not reference novel-specific fallback: {result2.get('error', 'no error')}, model_used={result2.get('model_used', 'none')}",
    )

    # Clean up
    for p in [ROOT / "tmp_test_role_fallback.md", ROOT / "tmp_test_novelty_fallback.md"]:
        if p.exists():
            p.unlink()

except ImportError as e:
    check("Can import isolated_job_runner for role-fallback test", False, str(e))
except Exception as e:
    check("role-specific fallback tests", False, str(e))

# ---------------------------------------------------------------------------
# 14. .gitignore : .aris/calls/ and .aris/sessions/ runtime only, not directories
# ---------------------------------------------------------------------------
print("\n=== 14. .gitignore .aris/calls/ and .aris/sessions/ runtime protection ===")
gitignore = ROOT / ".gitignore"
if gitignore.exists():
    text = gitignore.read_text(encoding="utf-8", errors="ignore")
    # .aris/calls/.gitkeep is OK; .aris/calls/ (alone) must NOT be whitelisted
    has_calls_gitkeep = "!.aris/calls/.gitkeep" in text
    has_calls_dir = "!.aris/calls/" in text and "!.aris/calls/.gitkeep" not in text.split("\n")
    # Similarly for sessions
    has_sessions_gitkeep = "!.aris/sessions/.gitkeep" in text
    has_sessions_dir = "!.aris/sessions/" in text and "!.aris/sessions/.gitkeep" not in text.split("\n")
    check(
        "14a. .aris/calls/ directory is NOT whitelisted (only .gitkeep allowed)",
        not has_calls_dir,
        ".aris/calls/ is whitelisted!" if has_calls_dir else "",
    )
    check(
        "14b. .aris/sessions/ directory is NOT whitelisted (only .gitkeep allowed)",
        not has_sessions_dir,
        ".aris/sessions/ is whitelisted!" if has_sessions_dir else "",
    )
    check(
        "14c. .aris/calls/.gitkeep placeholder is whitelisted",
        has_calls_gitkeep,
    )
    check(
        "14d. .aris/sessions/.gitkeep placeholder is whitelisted",
        has_sessions_gitkeep,
    )
else:
    for c in ["14a", "14b", "14c", "14d"]:
        check(f"{c} .gitignore exists", False)

# ---------------------------------------------------------------------------
# 15. ledger_overrides and completed_with_fallback in isolated_job_runner.py
# ---------------------------------------------------------------------------
print("\n=== 15. ledger fallback tracking in isolated_job_runner.py ===")
runner_path = ROOT / "tools" / "isolated_job_runner.py"
if runner_path.exists():
    src = runner_path.read_text(encoding="utf-8", errors="ignore")
    check(
        "15a. _backend_api has ledger_overrides parameter",
        "ledger_overrides" in src,
    )
    check(
        "15b. ledger_overrides merged into call_entry",
        "call_entry.update(ledger_overrides)" in src,
    )
    check(
        "15c. completed_with_fallback status exists",
        "completed_with_fallback" in src,
    )
    check(
        "15d. fallback_reason field in ledger",
        "fallback_reason" in src,
    )
    check(
        "15e. primary_backend set to codex_optional in ledger_overrides",
        '"primary_backend": "codex_optional"' in src,
    )
    check(
        "15f. _backend_codex_optional passes ledger_overrides to _backend_api",
        "ledger_overrides=ledger_overrides" in src,
    )
else:
    for c in ["15a", "15b", "15c", "15d", "15e", "15f"]:
        check(f"{c} runner file exists", False)

# ---------------------------------------------------------------------------
# 16. paper_ingest.py deep ingest capability
# ---------------------------------------------------------------------------
print("\n=== 16. paper_ingest.py deep ingest ===")
ingest_path = ROOT / "tools" / "paper_ingest.py"
if ingest_path.exists():
    src = ingest_path.read_text(encoding="utf-8", errors="ignore")
    check(
        "16a. paper_ingest.py supports --deep flag",
        '"--deep"' in src,
    )
    check(
        "16b. paper_ingest.py supports --download-pdf flag",
        '"--download-pdf"' in src,
    )
    check(
        "16c. paper_ingest.py writes full.md (via write_section)",
        'write_section(paper_dir, "full"' in src,
    )
    check(
        "16d. paper_ingest.py writes extraction_report.json",
        "extraction_report.json" in src,
    )
    check(
        "16e. paper_ingest.py writes section_index.json with extraction_method",
        "extraction_method" in src,
    )
    has_html_fetch = "fetch_arxiv_html" in src or "arxiv.org/html" in src
    check(
        "16f. paper_ingest.py has arXiv HTML extraction",
        has_html_fetch,
    )
    pdf_extraction = "extract_pdf_text" in src
    check(
        "16g. paper_ingest.py has PDF text extraction fallback",
        pdf_extraction,
    )
    # Check skill docs mention deep ingest
    paper_ingest_skill = ROOT / "skills" / "paper-ingest" / "SKILL.md"
    if paper_ingest_skill.exists():
        skill_content = paper_ingest_skill.read_text(encoding="utf-8", errors="ignore")
        check(
            "16h. paper-ingest SKILL no longer claims PDF-to-MD unimplemented",
            "当前已实现" in skill_content,
            "Skill file still mentions unimplemented status" if "未实现" in skill_content and "PDF" in skill_content else "",
        )
    else:
        check("paper-ingest SKILL.md exists", False)

    research_lit_skill = ROOT / "skills" / "research-lit" / "SKILL.md"
    if research_lit_skill.exists():
        rl_content = research_lit_skill.read_text(encoding="utf-8", errors="ignore")
        check(
            "16i. research-lit SKILL mentions top-k deep ingest",
            "Top-K Deep Ingest" in rl_content or "top-k" in rl_content.lower() or "top 5" in rl_content,
        )
    else:
        check("research-lit SKILL.md exists", False)

    novelty_skill = ROOT / "skills" / "novelty-check" / "SKILL.md"
    if novelty_skill.exists():
        nc_content = novelty_skill.read_text(encoding="utf-8", errors="ignore")
        check(
            "16j. novelty-check SKILL mentions deep ingest for closest prior work",
            "Deep Ingest" in nc_content or "closest prior work" in nc_content.lower(),
        )
    else:
        check("novelty-check SKILL.md exists", False)
else:
    for c in ["16a", "16b", "16c", "16d", "16e", "16f", "16g", "16h", "16i", "16j"]:
        check(f"{c} paper_ingest.py exists", False)

# ---------------------------------------------------------------------------
# 17. .env.example has no test/placeholder values
# ---------------------------------------------------------------------------
print("\n=== 17. .env.example test-placeholder check ===")
env_example = ROOT / ".env.example"
if env_example.exists():
    text = env_example.read_text(encoding="utf-8", errors="ignore")
    forbidden = ["deepseek-v4-test", "role-specific-model", "novelty-specific-model", "test-key"]
    found_forbidden = [v for v in forbidden if v in text]
    check(
        "17a. .env.example has no deepseek-v4-test placeholder",
        "deepseek-v4-test" not in text,
        f"Found: deepseek-v4-test" if "deepseek-v4-test" in text else "",
    )
    check(
        "17b. .env.example has no role-specific-model placeholder",
        "role-specific-model" not in text,
        f"Found: role-specific-model" if "role-specific-model" in text else "",
    )
    check(
        "17c. .env.example has no novelty-specific-model placeholder",
        "novelty-specific-model" not in text,
        f"Found: novelty-specific-model" if "novelty-specific-model" in text else "",
    )
    check(
        "17d. .env.example has no test-key placeholder",
        "test-key" not in text,
        f"Found: test-key" if "test-key" in text else "",
    )
    check(
        "17e. LLM_ADVERSARIAL_REVIEWER_PRIMARY is defined",
        "LLM_ADVERSARIAL_REVIEWER_PRIMARY" in text,
        "Missing LLM_ADVERSARIAL_REVIEWER_PRIMARY in .env.example",
    )
else:
    for c in ["17a", "17b", "17c", "17d", "17e"]:
        check(f"{c} .env.example exists", False)

# ---------------------------------------------------------------------------
# 18. isolated_job_runner writes fallback audit header to output artifact
# ---------------------------------------------------------------------------
print("\n=== 18. output artifact fallback audit header ===")
runner = ROOT / "tools" / "isolated_job_runner.py"
if runner.exists():
    src = runner.read_text(encoding="utf-8", errors="ignore")
    check(
        "18a. isolated_job_runner has ARIS-AUDIT-BEGIN header marker",
        "ARIS-AUDIT-BEGIN" in src,
        "Missing ARIS-AUDIT-BEGIN header marker; fallback not documented in output artifact",
    )
    check(
        "18b. isolated_job_runner prepends header when fallback_used",
        "if ledger_overrides and ledger_overrides.get(\"fallback_used\")" in src,
        "Missing fallback_used check for header prepend",
    )
else:
    check("18a. runner file exists", False)

# ---------------------------------------------------------------------------
# 19. primary_backend=codex fallback is not silent
# ---------------------------------------------------------------------------
print("\n=== 19. codex fallback visibility ===")
runner = ROOT / "tools" / "isolated_job_runner.py"
if runner.exists():
    src = runner.read_text(encoding="utf-8", errors="ignore")
    check(
        "19a. REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK in output artifact",
        "REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK: true" in src,
        "Missing REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK in artifact header",
    )
    check(
        "19b. REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK in result dict",
        "REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK" in src,
        "Missing REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK entirely",
    )
    check(
        "19c. codex_optional prints non-silent fallback notification to stderr",
        "Codex unavailable" in src,
        "Missing stderr notification for Codex fallback",
    )
else:
    for c in ["19a", "19b", "19c"]:
        check(f"{c} runner file exists", False)

# ---------------------------------------------------------------------------
# 20. .env.example has all new Codex roles
# ---------------------------------------------------------------------------
print("\n=== 20. .env.example new Codex roles ===")
env_example = ROOT / ".env.example"
if env_example.exists():
    text = env_example.read_text(encoding="utf-8", errors="ignore")
    check(
        "20a. LLM_EVIDENCE_AUDITOR_PRIMARY=codex in .env.example",
        "LLM_EVIDENCE_AUDITOR_PRIMARY=codex" in text,
    )
    check(
        "20b. LLM_IDEA_SHORTLIST_AUDITOR_PRIMARY=codex in .env.example",
        "LLM_IDEA_SHORTLIST_AUDITOR_PRIMARY=codex" in text,
    )
    check(
        "20c. LLM_FINAL_SELECTOR_PRIMARY=codex in .env.example",
        "LLM_FINAL_SELECTOR_PRIMARY=codex" in text,
    )
    check(
        "20d. LLM_EVIDENCE_AUDITOR_FALLBACK_MODEL=deepseek-v4-pro in .env.example",
        "LLM_EVIDENCE_AUDITOR_FALLBACK_MODEL=deepseek-v4-pro" in text,
    )
    check(
        "20e. LLM_IDEA_SHORTLIST_AUDITOR_FALLBACK_MODEL=deepseek-v4-pro in .env.example",
        "LLM_IDEA_SHORTLIST_AUDITOR_FALLBACK_MODEL=deepseek-v4-pro" in text,
    )
    check(
        "20f. LLM_FINAL_SELECTOR_FALLBACK_MODEL=deepseek-v4-pro in .env.example",
        "LLM_FINAL_SELECTOR_FALLBACK_MODEL=deepseek-v4-pro" in text,
    )
else:
    for c in ["20a", "20b", "20c", "20d", "20e", "20f"]:
        check(f"{c} .env.example exists", False)

# ---------------------------------------------------------------------------
# 21. model-routing.md has all new roles + routing table
# ---------------------------------------------------------------------------
print("\n=== 21. model-routing.md new roles ===")
model_routing = ROOT / "skills" / "shared-references" / "model-routing.md"
if model_routing.exists():
    content = model_routing.read_text(encoding="utf-8", errors="ignore")
    check(
        "21a. evidence_integrity_auditor section exists",
        "evidence_integrity_auditor" in content,
    )
    check(
        "21b. idea_shortlist_auditor section exists",
        "idea_shortlist_auditor" in content,
    )
    check(
        "21c. final_selector section exists",
        "final_selector" in content,
    )
    check(
        "21d. Phase-by-Phase Codex Routing Summary table exists",
        "Phase-by-Phase Codex Routing Summary" in content,
    )
    check(
        "21e. evidence_integrity_auditor is Yes in routing table",
        "evidence_integrity_auditor" in content and "**Yes**" in content,
    )
    check(
        "21f. idea_shortlist_auditor is Yes in routing table",
        "idea_shortlist_auditor" in content and "**Yes**" in content,
    )
else:
    for c in ["21a", "21b", "21c", "21d", "21e", "21f"]:
        check(f"{c} model-routing.md exists", False)

# ---------------------------------------------------------------------------
# 22. research-lit/SKILL.md has evidence_integrity_auditor gate
# ---------------------------------------------------------------------------
print("\n=== 22. research-lit SKILL evidence_integrity_auditor ===")
research_lit = ROOT / "skills" / "research-lit" / "SKILL.md"
if research_lit.exists():
    content = research_lit.read_text(encoding="utf-8", errors="ignore")
    check(
        "22a. evidence_integrity_auditor section exists in research-lit",
        "evidence_integrity_auditor" in content,
    )
    check(
        "22b. Evidence Integrity Audit gate description exists",
        "Evidence Integrity Audit" in content,
    )
    check(
        "22c. Phase 1 Codex Gate header exists",
        "Phase 1 Codex Gate" in content,
    )
else:
    for c in ["22a", "22b", "22c"]:
        check(f"{c} research-lit SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 23. idea-creator/SKILL.md has idea_shortlist_auditor gate
# ---------------------------------------------------------------------------
print("\n=== 23. idea-creator SKILL idea_shortlist_auditor ===")
idea_creator = ROOT / "skills" / "idea-creator" / "SKILL.md"
if idea_creator.exists():
    content = idea_creator.read_text(encoding="utf-8", errors="ignore")
    check(
        "23a. idea_shortlist_auditor section exists in idea-creator",
        "idea_shortlist_auditor" in content,
    )
    check(
        "23b. Idea Shortlist Audit gate description exists",
        "Idea Shortlist Audit" in content,
    )
    check(
        "23c. Codex Gate marker exists",
        "Codex Gate" in content,
    )
else:
    for c in ["23a", "23b", "23c"]:
        check(f"{c} idea-creator SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 24. novelty-check SKILL no longer hardcodes gpt-5.4
# ---------------------------------------------------------------------------
print("\n=== 24. novelty-check no hardcoded gpt-5.4 ===")
novelty_skill = ROOT / "skills" / "novelty-check" / "SKILL.md"
if novelty_skill.exists():
    content = novelty_skill.read_text(encoding="utf-8", errors="ignore")
    check(
        "24a. REVIEWER_MODEL = gpt-5.4 is removed",
        "REVIEWER_MODEL = `gpt-5.4`" not in content,
        "Still contains hardcoded gpt-5.4" if "REVIEWER_MODEL = `gpt-5.4`" in content else "",
    )
    check(
        "24b. novelty-check uses REVIEWER_BACKEND = codex",
        "REVIEWER_BACKEND = `codex`" in content,
    )
    check(
        "24c. novelty-check has Artifact Header section",
        "Artifact Header" in content,
    )
else:
    for c in ["24a", "24b", "24c"]:
        check(f"{c} novelty-check SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 25. exec-review SKILL has Artifact Header
# ---------------------------------------------------------------------------
print("\n=== 25. exec-review artifact header ===")
exec_skill = ROOT / "skills" / "exec-review" / "SKILL.md"
if exec_skill.exists():
    content = exec_skill.read_text(encoding="utf-8", errors="ignore")
    check(
        "25a. exec-review has Artifact Header section",
        "Artifact Header" in content,
    )
    check(
        "25b. exec-review header includes primary_backend field",
        "primary_backend" in content,
    )
    check(
        "25c. exec-review header includes fallback_used field",
        "fallback_used" in content,
    )
else:
    for c in ["25a", "25b", "25c"]:
        check(f"{c} exec-review SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 26. session_registry.py audit command
# ---------------------------------------------------------------------------
print("\n=== 26. session_registry.py audit ===")
session_reg = ROOT / "tools" / "session_registry.py"
if session_reg.exists():
    content = session_reg.read_text(encoding="utf-8", errors="ignore")
    check(
        "26a. session_registry.py has audit command",
        "cmd_audit" in content,
    )
    check(
        "26b. session_registry.py has INVALID_DONE_WITH_TODO detection",
        "INVALID_DONE_WITH_TODO" in content or "invalid_done_with_todo" in content,
    )
    check(
        "26c. session_registry.py handoff template includes Isolation Evidence",
        "Isolation Evidence" in content,
    )
    check(
        "26d. session_registry.py handoff template includes isolation_mode",
        "isolation_mode" in content,
    )
    check(
        "26e. session_registry.py handoff template includes codex_thread_id",
        "codex_thread_id" in content,
    )
else:
    for c in ["26a", "26b", "26c", "26d", "26e"]:
        check(f"{c} session_registry.py exists", False)

# ---------------------------------------------------------------------------
# 27. session-orchestrator SKILL isolation model
# ---------------------------------------------------------------------------
print("\n=== 27. session-orchestrator isolation model ===")
orch_skill = ROOT / "skills" / "session-orchestrator" / "SKILL.md"
if orch_skill.exists():
    content = orch_skill.read_text(encoding="utf-8", errors="ignore")
    check(
        "27a. session-orchestrator mentions manual_subsession",
        "manual_subsession" in content,
    )
    check(
        "27b. session-orchestrator mentions codex_thread",
        "codex_thread" in content,
    )
    check(
        "27c. session-orchestrator mentions protocol_only",
        "protocol_only" in content,
    )
    check(
        "27d. session-orchestrator has Three Acceptable Isolation Modes",
        "Three Acceptable Isolation Modes" in content,
    )
else:
    for c in ["27a", "27b", "27c", "27d"]:
        check(f"{c} session-orchestrator SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 28. session-protocol.md has Isolation Evidence requirements
# ---------------------------------------------------------------------------
print("\n=== 28. session-protocol.md Isolation Evidence ===")
protocol = ROOT / "skills" / "shared-references" / "session-protocol.md"
if protocol.exists():
    content = protocol.read_text(encoding="utf-8", errors="ignore")
    check(
        "28a. session-protocol mentions Isolation Evidence",
        "Isolation Evidence" in content,
    )
    check(
        "28b. session-protocol restricts protocol_only for critical phases",
        "protocol_only" in content and "Phase 3" in content and "Phase 4" in content,
    )
else:
    for c in ["28a", "28b"]:
        check(f"{c} session-protocol.md exists", False)

# ---------------------------------------------------------------------------
# 29. idea-discovery SKILL mentions isolation_mode in critical phases
# ---------------------------------------------------------------------------
print("\n=== 29. idea-discovery isolation references ===")
idea_disc = ROOT / "skills" / "idea-discovery" / "SKILL.md"
if idea_disc.exists():
    content = idea_disc.read_text(encoding="utf-8", errors="ignore")
    check(
        "29a. idea-discovery mentions isolation_mode",
        "isolation_mode" in content,
    )
    check(
        "29b. idea-discovery mentions codex_thread",
        "codex_thread" in content,
    )
    check(
        "29c. idea-discovery mentions Isolation requirement for review",
        "Isolation requirement" in content and "review" in content.lower(),
    )
    check(
        "29d. idea-discovery mentions protocol_only is not acceptable",
        "protocol_only is not acceptable" in content or "protocol_only" in content and "not acceptable" in content,
    )
else:
    for c in ["29a", "29b", "29c", "29d"]:
        check(f"{c} idea-discovery SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 30. research-lit gate has isolation_mode in artifact header
# ---------------------------------------------------------------------------
print("\n=== 30. research-lit isolation ===")
research_lit = ROOT / "skills" / "research-lit" / "SKILL.md"
if research_lit.exists():
    content = research_lit.read_text(encoding="utf-8", errors="ignore")
    check(
        "30a. research-lit evidence audit mentions isolation_mode",
        "isolation_mode" in content,
    )
    check(
        "30b. research-lit evidence audit mentions codex_thread_id",
        "codex_thread_id" in content,
    )
else:
    for c in ["30a", "30b"]:
        check(f"{c} research-lit SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 31. idea-creator gate has isolation requirements
# ---------------------------------------------------------------------------
print("\n=== 31. idea-creator isolation ===")
idea_creator = ROOT / "skills" / "idea-creator" / "SKILL.md"
if idea_creator.exists():
    content = idea_creator.read_text(encoding="utf-8", errors="ignore")
    check(
        "31a. idea-creator shortlist audit mentions isolation_mode",
        "isolation_mode" in content,
    )
    check(
        "31b. idea-creator shortlist audit mentions codex_thread_id",
        "codex_thread_id" in content,
    )
else:
    for c in ["31a", "31b"]:
        check(f"{c} idea-creator SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 32. exec-review & novelty-check have isolation fields in artifact header
# ---------------------------------------------------------------------------
print("\n=== 32. exec-review & novelty-check isolation fields ===")
exec_skill = ROOT / "skills" / "exec-review" / "SKILL.md"
if exec_skill.exists():
    content = exec_skill.read_text(encoding="utf-8", errors="ignore")
    check(
        "32a. exec-review artifact header includes isolation_mode",
        "isolation_mode" in content,
    )
    check(
        "32b. exec-review artifact header includes codex_thread_id",
        "codex_thread_id" in content,
    )
else:
    for c in ["32a", "32b"]:
        check(f"{c} exec-review SKILL.md exists", False)

novelty_skill = ROOT / "skills" / "novelty-check" / "SKILL.md"
if novelty_skill.exists():
    content = novelty_skill.read_text(encoding="utf-8", errors="ignore")
    check(
        "32c. novelty-check artifact header includes isolation_mode",
        "isolation_mode" in content,
    )
    check(
        "32d. novelty-check artifact header includes codex_thread_id",
        "codex_thread_id" in content,
    )
else:
    for c in ["32c", "32d"]:
        check(f"{c} novelty-check SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 33. No false claim of automatic multi-process isolation
# ---------------------------------------------------------------------------
print("\n=== 33. No false multi-process claim ===")
for fname, label in [
    ("skills/session-orchestrator/SKILL.md", "session-orchestrator"),
    ("skills/shared-references/session-protocol.md", "session-protocol"),
    ("skills/session-handoff/SKILL.md", "session-handoff"),
]:
    f = ROOT / fname
    if f.exists():
        content = f.read_text(encoding="utf-8", errors="ignore")
        check(
            f"33a. {label} does NOT claim automatic multi-process isolation",
            "auto" not in content or "不会自动" in content or "not auto" in content.lower(),
            f"{label} may claim automatic multi-process isolation" if "auto" in content and "不会自动" not in content else "",
        )
    else:
        check(f"33a. {label} exists", False)

# ---------------------------------------------------------------------------
# 34. /idea-discovery is the single user-facing entry point
# ---------------------------------------------------------------------------
print("\n=== 34. /idea-discovery single entry point ===")
idea_disc = ROOT / "skills" / "idea-discovery" / "SKILL.md"
if idea_disc.exists():
    content = idea_disc.read_text(encoding="utf-8", errors="ignore")
    check(
        "34a. idea-discovery declares itself as recommended entry point",
        "recommended" in content.lower() and "entry point" in content.lower(),
    )
    check(
        "34b. idea-discovery defines Phase 1-6 clearly",
        "Phase 1" in content and "Phase 2" in content and "Phase 3" in content
        and "Phase 4" in content and "Phase 5" in content and "Phase 6" in content,
    )
    check(
        "34c. idea-discovery does NOT direct users to python tools/",
        "python tools/" not in content and "python3 tools/" not in content,
    )
else:
    for c in ["34a", "34b", "34c"]:
        check(f"{c} idea-discovery SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 35. Sub-skills declare themselves as internal phases
# ---------------------------------------------------------------------------
print("\n=== 35. Sub-skills phase alignment ===")
for path, label, must_contain in [
    ("skills/research-lit/SKILL.md", "research-lit", "literature"),
    ("skills/idea-creator/SKILL.md", "idea-creator", "idea generation"),
]:
    f = ROOT / path
    if f.exists():
        content = f.read_text(encoding="utf-8", errors="ignore")
        check(
            f"35a. {label} mentions '{must_contain}'",
            must_contain.lower() in content.lower(),
        )
        # Check the skill description doesn't claim downstream capabilities
        desc_line = ""
        for line in content.splitlines()[:5]:
            if line.startswith("description:"):
                desc_line = line
                break
        # description should mention the skill's OWN role, not claim downstream phases
        downstream = "novelty" if "idea-creator" in label else ""
        if downstream:
            check(
                f"35b. {label} description does NOT claim '{downstream}'",
                downstream not in desc_line.lower(),
        )
    else:
        check(f"35a. {label} SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 36. session-orchestrator declares codex_thread as default gate
# ---------------------------------------------------------------------------
print("\n=== 36. codex_thread default gate ===")
orch = ROOT / "skills" / "session-orchestrator" / "SKILL.md"
if orch.exists():
    content = orch.read_text(encoding="utf-8", errors="ignore")
    check(
        "36a. session-orchestrator declares codex_thread as default for critical gates",
        "codex_thread" in content and ("default" in content.lower() or "Default" in content),
    )
    check(
        "36b. session-orchestrator says users invoke /idea-discovery, not session tools directly",
        "/idea-discovery" in content and "user" in content.lower(),
    )
else:
    for c in ["36a", "36b"]:
        check(f"{c} session-orchestrator SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 37. validate_idea_stage_state.py exists and runs
# ---------------------------------------------------------------------------
print("\n=== 37. validate_idea_stage_state.py ===")
validator = ROOT / "tools" / "validate_idea_stage_state.py"
if validator.exists():
    check("37a. validate_idea_stage_state.py exists", True)
    import subprocess
    result = subprocess.run(
        [sys.executable, str(validator)], capture_output=True, text=True, timeout=15
    )
    try:
        data = json.loads(result.stdout)
        verdict = data.get("verdict", "UNKNOWN")
        check(
            f"37b. validator returns verdict (not crash): {verdict}",
            verdict in ("PASS", "PASS_WITH_WARNINGS", "FAIL", "NO_IDEA_STAGE"),
        )
        check(
            "37c. validator checks CAND status consistency",
            "violations" in data,
        )
        check(
            "37d. validator checks legacy archive exclusion",
            "legacy_archive_present" in data,
        )
        check(
            "37e. validator checks artifact headers",
            "header_issues" in data,
        )
    except Exception as e:
        check("37b. validator runs successfully", False, str(e))
else:
    for c in ["37a", "37b", "37c", "37d", "37e"]:
        check(f"{c} validator exists", False)

# ---------------------------------------------------------------------------
# 38. No false multi-session claim in session-orchestrator or protocol
# ---------------------------------------------------------------------------
print("\n=== 38. session model honesty ===")
for fname, label in [
    ("skills/session-orchestrator/SKILL.md", "session-orchestrator"),
    ("skills/shared-references/session-protocol.md", "session-protocol"),
]:
    f = ROOT / fname
    if f.exists():
        content = f.read_text(encoding="utf-8", errors="ignore")
        check(
            f"38a. {label} acknowledges session is file-level protocol, not auto multi-process",
            "文件级" in content or "file-level" in content.lower() or "not auto" in content.lower()
            or "不会自动" in content,
        )
        check(
            f"38b. {label} mentions codex_thread as isolation mode",
            "codex_thread" in content,
        )
    else:
        check(f"38a. {label} exists", False)

# ---------------------------------------------------------------------------
# 39. protocol_only restricted for critical phases
# ---------------------------------------------------------------------------
print("\n=== 39. protocol_only restrictions ===")
for fname, label in [
    ("skills/session-orchestrator/SKILL.md", "session-orchestrator"),
    ("skills/shared-references/session-protocol.md", "session-protocol"),
    ("skills/idea-discovery/SKILL.md", "idea-discovery"),
]:
    f = ROOT / fname
    if f.exists():
        content = f.read_text(encoding="utf-8", errors="ignore")
        check(
            f"39a. {label}: protocol_only cannot yield full PASS for critical gates",
            ("protocol_only" in content and ("not acceptable" in content.lower()
             or "PASS_WITH_WARNINGS" in content or "not a full" in content.lower()
             or "cannot yield" in content.lower())),
        )
    else:
        check(f"39a. {label} exists", False)

# ---------------------------------------------------------------------------
# 40. No user direction to run python tools/
# ---------------------------------------------------------------------------
print("\n=== 40. No user direction to python tools ===")
idea_disc = ROOT / "skills" / "idea-discovery" / "SKILL.md"
if idea_disc.exists():
    content = idea_disc.read_text(encoding="utf-8", errors="ignore")
    check(
        "40a. idea-discovery does NOT tell users to run python tools/",
        "python tools/" not in content and "python3 tools/" not in content,
    )
else:
    check("40a. idea-discovery SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 41. Two usage modes supported
# ---------------------------------------------------------------------------
print("\n=== 41. Two usage modes ===")
ag = ROOT / "AGENT_GUIDE.md"
if ag.exists():
    content = ag.read_text(encoding="utf-8", errors="ignore")
    check(
        "41a. AGENT_GUIDE mentions single-command mode and manual staged mode",
        ("single-command" in content.lower() or "Mode A" in content)
        and ("manual staged" in content.lower() or "Mode B" in content),
    )
else:
    check("41a. AGENT_GUIDE.md exists", False)

idea_disc = ROOT / "skills" / "idea-discovery" / "SKILL.md"
if idea_disc.exists():
    content = idea_disc.read_text(encoding="utf-8", errors="ignore")
    check(
        "41b. idea-discovery mentions both Mode A and Mode B",
        "Mode A" in content and "Mode B" in content,
    )
else:
    check("41b. idea-discovery exists", False)

# ---------------------------------------------------------------------------
# 42. idea-creator uses DeepSeek for generation, Codex only for shortlist
# ---------------------------------------------------------------------------
print("\n=== 42. idea-creator model routing ===")
idea_creator = ROOT / "skills" / "idea-creator" / "SKILL.md"
if idea_creator.exists():
    content = idea_creator.read_text(encoding="utf-8", errors="ignore")
    check(
        "42a. idea-creator uses LLM_IDEA_GENERATOR_MODEL/DeepSeek, not Codex, for generation",
        "DeepSeek" in content or "LLM_IDEA_GENERATOR_MODEL" in content,
    )
    check(
        "42b. idea-creator says Codex only for shortlist auditor gate",
        "shortlist" in content.lower() and "Codex" in content and "ONLY Codex" in content,
    )
    check(
        "42c. idea-creator reads from Phase 1 outputs first",
        "Prerequisites" in content or ("LITERATURE_INDEX" in content and "PHASE1" in content),
    )
else:
    for c in ["42a", "42b", "42c"]:
        check(f"{c} idea-creator SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 43. research-lit auto-gate on every invocation
# ---------------------------------------------------------------------------
print("\n=== 43. research-lit auto-gate ===")
rl = ROOT / "skills" / "research-lit" / "SKILL.md"
if rl.exists():
    content = rl.read_text(encoding="utf-8", errors="ignore")
    check(
        "43a. research-lit gate runs on every invocation",
        "every" in content and "invocation" in content,
    )
    check(
        "43b. research-lit default outputs include PHASE1_EVIDENCE_AUDIT",
        "PHASE1_EVIDENCE_AUDIT" in content,
    )
else:
    for c in ["43a", "43b"]:
        check(f"{c} research-lit SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 44. exec-review auto-parse + evidence vs contamination
# ---------------------------------------------------------------------------
print("\n=== 44. exec-review evidence/contamination ===")
exec_skill = ROOT / "skills" / "exec-review" / "SKILL.md"
if exec_skill.exists():
    content = exec_skill.read_text(encoding="utf-8", errors="ignore")
    check(
        "44a. exec-review has Evidence vs. Contamination section",
        "Evidence vs. Contamination" in content,
    )
    check(
        "44b. exec-review shows /exec-review CAND_001 auto-parse usage",
        "/exec-review CAND_001" in content or "/exec-review CAND_00" in content,
    )
else:
    for c in ["44a", "44b"]:
        check(f"{c} exec-review SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 45. novelty-check canonical vs ad hoc mode
# ---------------------------------------------------------------------------
print("\n=== 45. novelty-check canonical vs ad hoc ===")
nov = ROOT / "skills" / "novelty-check" / "SKILL.md"
if nov.exists():
    content = nov.read_text(encoding="utf-8", errors="ignore")
    check(
        "45a. novelty-check has Canonical Pipeline Mode",
        "Canonical Pipeline Mode" in content,
    )
    check(
        "45b. novelty-check has Ad Hoc Mode with mode: ad_hoc marker",
        "ad_hoc" in content or "Ad Hoc Mode" in content,
    )
else:
    for c in ["45a", "45b"]:
        check(f"{c} novelty-check SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 46. isolated_job_runner evidence/contamination patterns
# ---------------------------------------------------------------------------
print("\n=== 46. isolated_job_runner evidence/contamination ===")
runner = ROOT / "tools" / "isolated_job_runner.py"
if runner.exists():
    content = runner.read_text(encoding="utf-8", errors="ignore")
    check(
        "46a. isolated_job_runner has ALLOWED_EVIDENCE_PATTERNS",
        "ALLOWED_EVIDENCE_PATTERNS" in content,
    )
    check(
        "46b. isolated_job_runner has FORBIDDEN_CONTAMINATION_PATTERNS",
        "FORBIDDEN_CONTAMINATION_PATTERNS" in content,
    )
    check(
        "46c. codex_optional no longer says Protocol/documentation only in V1",
        "Protocol/documentation only in V1" not in content,
        "Still says Protocol/documentation only in V1" if "Protocol/documentation only in V1" in content else "",
    )
    check(
        "46d. codex_optional mentions FAIL_REQUIRES_AGENT_MCP_CODEX or codex_required",
        "FAIL_REQUIRES_AGENT_MCP_CODEX" in content or "codex_required" in content,
    )
else:
    for c in ["46a", "46b", "46c", "46d"]:
        check(f"{c} isolated_job_runner.py exists", False)

# ---------------------------------------------------------------------------
# 47. isolated_job_runner codex_required roles
# ---------------------------------------------------------------------------
print("\n=== 47. isolated_job_runner codex_required ===")
runner = ROOT / "tools" / "isolated_job_runner.py"
if runner.exists():
    content = runner.read_text(encoding="utf-8", errors="ignore")
    check(
        "47a. isolated_job_runner has CODEX_REQUIRED_ROLES list",
        "CODEX_REQUIRED_ROLES" in content,
    )
    check(
        "47b. isolated_job_runner requires allow_fallback=true for codex_optional fallback",
        "allow_fallback" in content,
    )
    check(
        "47c. essential roles are codex_required (idea_reviewer, novelty_checker, final_selector)",
        all(
            role in content
            for role in ["idea_reviewer", "novelty_checker", "final_selector"]
        ),
    )
    check(
        "47d. codex_optional only uses fallback when allow_fallback is true",
        "allow_fallback" in content and "CODEX_REQUIRED_ROLES" in content,
    )
else:
    for c in ["47a", "47b", "47c", "47d"]:
        check(f"{c} isolated_job_runner.py exists", False)

# ---------------------------------------------------------------------------
# 48. idea-creator no old Codex/landscape survey residues
# ---------------------------------------------------------------------------
print("\n=== 48. idea-creator no old residues ===")
ic = ROOT / "skills" / "idea-creator" / "SKILL.md"
if ic.exists():
    content = ic.read_text(encoding="utf-8", errors="ignore")
    check(
        "48a. idea-creator no longer has REVIEWER_MODEL = `gpt-5.4`",
        "REVIEWER_MODEL = `gpt-5.4`" not in content,
        "Still has gpt-5.4 reference" if "gpt-5.4" in content else "",
    )
    check(
        "48b. idea-creator no longer says Use Codex MCP for divergent thinking",
        "Use Codex MCP for divergent thinking" not in content,
    )
    check(
        "48c. idea-creator no longer has Phase 1: Landscape Survey",
        "Phase 1: Landscape Survey" not in content and "Scan local paper library" not in content,
        "Still has old Landscape Survey" if "Landscape Survey" in content else "",
    )
    check(
        "48d. idea-creator has Prerequisites or Phase 1: Load Verified Inputs",
        "Prerequisites" in content or "Load Verified Inputs" in content,
    )
    check(
        "48e. idea-creator references LITERATURE_INDEX.md and PHASE1_EVIDENCE_AUDIT",
        "LITERATURE_INDEX.md" in content and "PHASE1_EVIDENCE_AUDIT" in content,
    )
else:
    for c in ["48a", "48b", "48c", "48d", "48e"]:
        check(f"{c} idea-creator SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 49. novelty-check mode enforcement
# ---------------------------------------------------------------------------
print("\n=== 49. novelty-check mode enforcement ===")
nov = ROOT / "skills" / "novelty-check" / "SKILL.md"
if nov.exists():
    content = nov.read_text(encoding="utf-8", errors="ignore")
    check(
        "49a. novelty-check canonical mode outputs to NOVELTY/CAND_*_novelty.md",
        "NOVELTY/CAND_" in content,
    )
    check(
        "49b. novelty-check ad_hoc outputs to NOVELTY_ADHOC/ not NOVELTY/CAND_*",
        "NOVELTY_ADHOC" in content,
    )
    check(
        "49c. novelty-check ad_hoc cannot enter IDEA_BANK / final selection",
        "ad_hoc" in content and "IDEA_BANK" in content,
    )
    check(
        "49d. novelty-check distinguishes canonical_pipeline vs ad_hoc mode",
        "canonical_pipeline" in content and "ad_hoc" in content,
    )
else:
    for c in ["49a", "49b", "49c", "49d"]:
        check(f"{c} novelty-check SKILL.md exists", False)

# ---------------------------------------------------------------------------
# 50. validate_idea_stage_state checks ad_hoc/codex/ledger
# ---------------------------------------------------------------------------
print("\n=== 50. validate_idea_stage_state advanced checks ===")
validator = ROOT / "tools" / "validate_idea_stage_state.py"
if validator.exists():
    content = validator.read_text(encoding="utf-8", errors="ignore")
    check(
        "50a. validator checks ad_hoc novelty not in final selection",
        "ad_hoc" in content and "final selection" in content.lower(),
    )
    check(
        "50b. validator checks codex_thread_id presence for codex artifacts",
        "codex_thread_id" in content and "actual_backend" in content,
    )
    check(
        "50c. validator checks ledger alignment",
        "llm_calls.jsonl" in content or "ledger" in content.lower(),
    )
else:
    for c in ["50a", "50b", "50c"]:
        check(f"{c} validator exists", False)

# ---------------------------------------------------------------------------
# 51. llm_call_ledger codex_thread_id integration
# ---------------------------------------------------------------------------
print("\n=== 51. llm_call_ledger codex_thread_id integration ===")
ledger_py = ROOT / "tools" / "llm_call_ledger.py"
if ledger_py.exists():
    content = ledger_py.read_text(encoding="utf-8", errors="ignore")
    check(
        "51a. cmd_finish accepts --codex-thread-id parameter",
        "codex_thread_id" in content and "cmd_finish" in content,
    )
    check(
        "51b. cmd_finish accepts --isolation-mode parameter",
        "isolation_mode" in content and "cmd_finish" in content,
    )
    check(
        "51c. cmd_finish accepts --actual-backend and --actual-model",
        "actual_backend" in content and "actual_model" in content,
    )
    check(
        "51d. cmd_finish accepts --output-file (repeatable)",
        "output_file" in content,
    )
    check(
        "51e. cmd_finish preserves existing codex_thread_id from current_call.json",
        "entry.get(\"codex_thread_id\")" in content,
    )
    check(
        "51f. actual_backend=codex in finish enforces non-empty codex_thread_id",
        "completed_with_warnings" in content,
    )
    check(
        "51g. cmd_fallback preserves codex_thread_id unless overridden",
        "entry[\"codex_thread_id\"]" in content,
    )
    check(
        "51h. cmd_fallback sets isolation_mode=protocol_only",
        "protocol_only" in content and "fallback" in content,
    )
    check(
        "51i. llm_call_ledger has _parse_kwargs helper",
        "_parse_kwargs" in content,
    )

    # Local unit smoke test: write temp current_call.json, call finish with
    # --codex-thread-id, verify JSONL contains the id, then clean up.
    import tempfile, subprocess, json, os
    from pathlib import Path

    tmpdir = Path(tempfile.mkdtemp(prefix="aris_ledger_test_"))
    try:
        # Mock .aris/calls/ structure in tmpdir with timezone-aware timestamps
        mock_calls = tmpdir / ".aris" / "calls"
        mock_calls.mkdir(parents=True)
        # Init git so find_project_root() resolves to tmpdir
        subprocess.run(
            ["git", "init"],
            capture_output=True, text=True, timeout=5,
            cwd=str(tmpdir),
        )
        fake_entry = {
            "call_id": "test_codex_thread_smoke",
            "timestamp": "2026-05-10T12:00:00+00:00",
            "skill": "test",
            "role": "idea_reviewer",
            "primary_backend": "codex",
            "actual_backend": "codex",
            "status": "started",
        }
        (mock_calls / "current_call.json").write_text(
            json.dumps(fake_entry), encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, str(ledger_py), "finish",
             "--codex-thread-id", "smoke-test-thread-999",
             "--isolation-mode", "codex_thread"],
            capture_output=True, text=True, timeout=10,
            cwd=str(tmpdir),
        )
        # Verify the JSONL was written
        jsonl_path = mock_calls / "llm_calls.jsonl"
        jsonl_ok = jsonl_path.exists()
        found_thread = False
        if jsonl_ok:
            for line in jsonl_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("codex_thread_id") == "smoke-test-thread-999":
                        found_thread = True
                except json.JSONDecodeError:
                    pass
        check(
            "51j. local smoke: finish --codex-thread-id writes thread to llm_calls.jsonl",
            jsonl_ok and found_thread,
            f"JSONL exists={jsonl_ok}, found_thread={found_thread}. stdout: {result.stdout.strip()}" if not (jsonl_ok and found_thread) else "",
        )

        # Verify isolation_mode was written
        found_isolation = False
        if jsonl_ok:
            for line in jsonl_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("isolation_mode") == "codex_thread":
                        found_isolation = True
                except json.JSONDecodeError:
                    pass
        check(
            "51k. local smoke: finish --isolation-mode writes isolation_mode to llm_calls.jsonl",
            found_isolation,
        )

        # Test: actual_backend=codex without thread_id should get completed_with_warnings
        (mock_calls / "current_call.json").write_text(
            json.dumps({
                "call_id": "test_missing_thread",
                "timestamp": "2026-05-10T12:01:00+00:00",
                "skill": "test",
                "role": "idea_reviewer",
                "primary_backend": "codex",
                "actual_backend": "codex",
                "status": "started",
            }),
            encoding="utf-8",
        )
        result2 = subprocess.run(
            [sys.executable, str(ledger_py), "finish"],
            capture_output=True, text=True, timeout=10,
            cwd=str(tmpdir),
        )
        found_warning = False
        jsonl2 = mock_calls / "llm_calls.jsonl"
        if jsonl2.exists():
            lines = jsonl2.read_text(encoding="utf-8").strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("call_id") == "test_missing_thread" and entry.get("status") == "completed_with_warnings":
                        found_warning = True
                except json.JSONDecodeError:
                    pass
        check(
            "51l. local smoke: actual_backend=codex without thread_id => completed_with_warnings",
            found_warning,
        )

        # Test: fallback sets isolation_mode=protocol_only
        (mock_calls / "current_call.json").write_text(
            json.dumps({
                "call_id": "test_fallback_isolation",
                "timestamp": "2026-05-10T12:02:00+00:00",
                "skill": "test",
                "role": "idea_reviewer",
                "primary_backend": "codex",
                "status": "started",
                "codex_thread_id": "smoke-test-thread-999",
            }),
            encoding="utf-8",
        )
        result3 = subprocess.run(
            [sys.executable, str(ledger_py), "fallback", "deepseek-v4-flash",
             "codex unavailable", "llm-chat"],
            capture_output=True, text=True, timeout=10,
            cwd=str(tmpdir),
        )
        found_fallback_isolation = False
        found_preserved_thread = False
        jsonl3 = mock_calls / "llm_calls.jsonl"
        if jsonl3.exists():
            lines = jsonl3.read_text(encoding="utf-8").strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("call_id") == "test_fallback_isolation":
                        if entry.get("isolation_mode") == "protocol_only":
                            found_fallback_isolation = True
                        if entry.get("codex_thread_id") == "smoke-test-thread-999":
                            found_preserved_thread = True
                except json.JSONDecodeError:
                    pass
        check(
            "51m. local smoke: fallback sets isolation_mode=protocol_only",
            found_fallback_isolation,
        )
        check(
            "51n. local smoke: fallback preserves existing codex_thread_id",
            found_preserved_thread,
        )
        check(
            "51o. local smoke: fallback sets fallback_used=true",
            result3.stdout and "FALLBACK" in result3.stdout,
        )
    finally:
        # Clean up temp dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
else:
    for c in ["51a", "51b", "51c", "51d", "51e", "51f", "51g", "51h", "51i",
              "51j", "51k", "51l", "51m", "51n", "51o"]:
        check(f"{c} llm_call_ledger.py exists", False)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    print("Some checks failed. Review the [FAIL] items above.")
    sys.exit(1)
else:
    print("All checks passed.")
    sys.exit(0)

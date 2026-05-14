"""Slash command adapter — Agent-facing parser and safe executor for user-facing slash commands.

Maps user slash commands to underlying research_cli plans.
Supports dry-run (default) and execute_safe mode.
No model calls, no trusted runner execution, no trusted_outputs changes.

Gate 2: literature-intake now calls run_multisource_pipeline for real metadata search.
Gate 3: idea-synthesis creates evidence-aware scaffold referencing real metadata.
Gate 4: idea-audit creates evidence-aware audit scaffold.
Gate 5: experiment has mode-specific logic with proper blocking.
Gate 6: paper-writing blocks unless experiment results + claim boundary exist.
Gate 7: status shows enhanced runtime/literature/trusted output summaries.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research" / "current"
RUNTIME_DIR = RESEARCH_DIR / "runtime"
PAYLOAD_DIR = RESEARCH_DIR / "user_command_payloads"
WORKFLOW_STATE_FILE = RUNTIME_DIR / "workflow_state.json"
# Fallback: read-only path for legacy workflow_state.json (never written here)
LEGACY_WORKFLOW_STATE_FILE = RESEARCH_DIR / "workflow_state.json"

# Literature search output location (gitignored via literature/*)
LITERATURE_SEARCH_DIR = ROOT / "literature" / "search_runs" / "current"
# Runtime literature search for slash commands (tmp/ is gitignored, avoids pipeline forbidden path check)
RUNTIME_LIT_DIR = ROOT / "tmp" / "slash_lit_search"

# ---- Execution modes ----

EXECUTION_MODES = ("dry_run", "execute_safe", "blocked", "plan_only")

# ---- User-facing phase mapping ----

USER_PHASES = {
    "research-intake": "research_direction_intake",
    "literature-intake": "literature_intake",
    "idea-synthesis": "idea_synthesis",
    "idea-audit": "idea_audit",
    "experiment": "experiment_and_analysis",
    "paper-writing": "paper_writing",
    "status": "status_check",
}

# ---- Supported commands and their mappings ----

COMMAND_MAP = {
    "research-intake": {
        "description": "输入研究方向和约束",
        "maps_to": "research_cli_start",
        "internal_stages": ["raw_user_input", "input_normalization", "brief_generation", "candidate_idea_extraction", "payload_parsing"],
        "flags": [],
        "execution_mode": "execute_safe",
    },
    "literature-intake": {
        "description": "文献调研与领域理解",
        "maps_to": "continue_literature_search",
        "internal_stages": ["query_planning", "multi_source_search", "dedup_ranking", "top_k_selection", "full_text_acquisition", "full_text_review", "evidence_map"],
        "flags": [],
        "execution_mode": "execute_safe",
    },
    "idea-synthesis": {
        "description": "创新点生成",
        "maps_to": "continue_idea_pivot",
        "internal_stages": ["idea_discovery", "idea_pivot", "transfer_hypothesis_generation", "contribution_chain_construction"],
        "flags": ["--num-candidates"],
        "execution_mode": "execute_safe",
    },
    "idea-audit": {
        "description": "创新点验证、查新与研究边界锁定",
        "maps_to": "continue_novelty_check",
        "internal_stages": ["novelty_check", "transfer_check", "method_refinement", "research_contract"],
        "flags": [],
        "execution_mode": "execute_safe",
    },
    "experiment": {
        "description": "实验与结果分析",
        "maps_to": "experiment_plan",
        "internal_stages": ["experiment_plan", "implementation_plan", "experiment_bridge", "code_review", "lightweight_experiment", "full_experiment", "result_judge", "claim_boundary_update"],
        "flags": ["--mode"],
        "modes": ["lightweight", "full", "analyze", "revise"],
        "execution_mode": "execute_safe",
    },
    "paper-writing": {
        "description": "论文撰写",
        "maps_to": "paper_writing",
        "internal_stages": ["paper_outline", "contribution_framing", "related_work", "method_writing", "experiment_writing", "limitation_writing", "auto_review_loop"],
        "flags": [],
        "execution_mode": "execute_safe",
    },
    "status": {
        "description": "显示当前研究状态",
        "maps_to": "research_cli_status",
        "internal_stages": [],
        "flags": [],
        "execution_mode": "execute_safe",
    },
}


# ---- Parser ----

def parse_slash_command(input_text: str) -> dict:
    """Parse a slash command string into structured components.

    Returns:
        {
            "command": str,
            "payload": str,
            "flags": dict,
            "raw": str,
            "valid": bool,
            "error": str | None,
        }
    """
    raw = input_text.strip()
    if not raw.startswith("/"):
        return {"command": "", "payload": "", "flags": {}, "raw": raw, "valid": False, "error": "must start with /"}

    # Extract command name (before first space or quote)
    parts = raw[1:].split(None, 1)
    if not parts:
        return {"command": "", "payload": "", "flags": {}, "raw": raw, "valid": False, "error": "empty command"}

    command = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    if command not in COMMAND_MAP:
        return {"command": command, "payload": rest, "flags": {}, "raw": raw, "valid": False, "error": f"unknown command: /{command}"}

    # Parse quoted payload and flags
    payload, flags = _extract_payload_and_flags(rest)

    return {"command": command, "payload": payload, "flags": flags, "raw": raw, "valid": True, "error": None}


def _extract_payload_and_flags(text: str) -> tuple[str, dict]:
    """Extract quoted payload and --flag value pairs from text."""
    payload = ""
    flags = {}

    # Try to extract quoted payload
    m = re.match(r'"([^"]*)"', text)
    if m:
        payload = m.group(1)
        remainder = text[m.end():].strip()
    elif text.startswith("'"):
        m = re.match(r"'([^']*)'", text)
        if m:
            payload = m.group(1)
            remainder = text[m.end():].strip()
        else:
            remainder = text
    else:
        # No quotes — everything before first --flag is payload
        flag_match = re.search(r'\s+--', text)
        if flag_match:
            payload = text[:flag_match.start()].strip()
            remainder = text[flag_match.start():].strip()
        else:
            payload = text.strip()
            remainder = ""

    # Parse --flag value pairs
    flag_pattern = re.findall(r'--(\S+)(?:\s+(\S+))?', remainder)
    for name, value in flag_pattern:
        flags[name] = value if value else "true"

    return payload, flags


# ---- Payload persistence ----

def save_payload(command: str, payload: str, output_dir: Path) -> Path:
    """Save command payload to a markdown file. Returns the file path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{command.replace('-', '_')}.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename

    content = f"""---
command: /{command}
timestamp: {datetime.now(timezone.utc).isoformat()}
raw_payload: |
  {payload}
---

# Command Payload: /{command}

## User Input

{payload}

## Parsed Fields

- command: /{command}
- timestamp: {datetime.now(timezone.utc).isoformat()}
"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ---- Workflow state ----

def load_workflow_state() -> dict:
    """Load workflow state from runtime/workflow_state.json.

    Falls back to legacy research/current/workflow_state.json (read-only).
    """
    for path in (WORKFLOW_STATE_FILE, LEGACY_WORKFLOW_STATE_FILE):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {
        "current_user_phase": None,
        "completed_user_phases": [],
        "latest_command": None,
        "latest_payload_file": None,
        "blocked_reason": None,
        "next_allowed_commands": ["research-intake"],
        "system_health": "healthy",
        "case_status": "not_started",
        "model_calls_made": False,
        "trusted_outputs_changed": False,
        "last_updated": None,
    }


def save_workflow_state(state: dict) -> None:
    """Save workflow state to runtime/workflow_state.json."""
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    WORKFLOW_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def update_workflow_state(command: str, payload_file: str | None = None) -> dict:
    """Update workflow state after a command execution. Returns updated state."""
    state = load_workflow_state()
    phase = USER_PHASES.get(command)
    state["latest_command"] = command
    if payload_file:
        state["latest_payload_file"] = payload_file
    if phase and phase != "status_check":
        state["current_user_phase"] = phase
        if phase not in state["completed_user_phases"]:
            state["completed_user_phases"].append(phase)
    # Compute next allowed commands
    state["next_allowed_commands"] = _compute_next_commands(state)
    save_workflow_state(state)
    return state


def _compute_next_commands(state: dict) -> list[str]:
    """Compute which commands are allowed next based on current phase."""
    completed = set(state.get("completed_user_phases", []))
    phase_order = [
        "research_direction_intake",
        "literature_intake",
        "idea_synthesis",
        "idea_audit",
        "experiment_and_analysis",
        "paper_writing",
    ]
    # Find first uncompleted phase
    for phase in phase_order:
        if phase not in completed:
            # Map phase back to commands
            phase_to_cmd = {v: k for k, v in USER_PHASES.items() if k != "status"}
            cmd = phase_to_cmd.get(phase, "research-intake")
            return [cmd, "status"]
    return ["status"]


# ---- Evidence detection helpers ----

def _has_literature_metadata() -> bool:
    """Check if literature metadata exists (from slash runtime or prior runs)."""
    # Check runtime literature search
    if RUNTIME_LIT_DIR.exists() and (RUNTIME_LIT_DIR / "top_k.md").exists():
        return True
    # Check committed search runs
    if LITERATURE_SEARCH_DIR.exists() and (LITERATURE_SEARCH_DIR / "top_k.md").exists():
        return True
    return False


def _get_literature_metadata_path() -> Path | None:
    """Return the path to the best available literature metadata."""
    if RUNTIME_LIT_DIR.exists() and (RUNTIME_LIT_DIR / "top_k.md").exists():
        return RUNTIME_LIT_DIR
    if LITERATURE_SEARCH_DIR.exists() and (LITERATURE_SEARCH_DIR / "top_k.md").exists():
        return LITERATURE_SEARCH_DIR
    return None


def _has_idea_synthesis_scaffold() -> bool:
    """Check if idea synthesis scaffold exists in runtime."""
    return (RUNTIME_DIR / "idea_synthesis_scaffold.md").exists()


def _has_experiment_results() -> bool:
    """Check if experiment results exist."""
    # Check runtime
    if list(RUNTIME_DIR.glob("experiment_results*")):
        return True
    # Check research/current
    if list(RESEARCH_DIR.glob("experiment_results*")):
        return True
    return False


def _has_claim_boundary() -> bool:
    """Check if claim boundary / method_refinement exists."""
    return (RESEARCH_DIR / "trusted_outputs" / "method_refinement.md").exists()


def _read_top_k_summary() -> str:
    """Read a brief summary of top_k papers if available."""
    meta_path = _get_literature_metadata_path()
    if meta_path is None:
        return "No literature metadata available."
    top_k_file = meta_path / "top_k.md"
    if not top_k_file.exists():
        return "No top_k.md found."
    content = top_k_file.read_text(encoding="utf-8")
    # Return first 2000 chars as summary
    return content[:2000] if len(content) > 2000 else content


def _count_jsonl_lines(path: Path) -> int:
    """Count non-empty lines in a JSONL file."""
    if not path.exists():
        return 0
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _count_top_k_papers(path: Path) -> int:
    """Count paper entries in top_k.md (lines starting with '## ' or '- **')."""
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    return content.count("## ") + content.count("- **")


# ---- Safe execution functions ----

def _ensure_research_dir() -> None:
    """Ensure research/current/runtime/ directory exists."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def execute_research_intake(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /research-intake. Creates files, no model calls."""
    _ensure_research_dir()
    payload = parsed["payload"]
    results = []

    # 1. Save raw_user_input.md to runtime/
    raw_file = RUNTIME_DIR / "raw_user_input.md"
    content = f"""---
command: /research-intake
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: scaffold
model_not_called: true
---

# Raw User Input

{payload}
"""
    raw_file.write_text(content, encoding="utf-8")
    results.append(f"Created runtime/{raw_file.name}")

    # 2. Create intake scaffold (not real normalization — no model)
    scaffold_file = RUNTIME_DIR / "input_normalization_scaffold.md"
    scaffold_content = f"""---
command: /research-intake
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: scaffold
model_not_called: true
status: scaffold
---

# Input Normalization Scaffold

## Raw Input

{payload}

## Parsed Components (scaffold — model not called)

- research_direction: [requires model normalization]
- constraints: [requires model normalization]
- methodology_preference: [requires model normalization]
- novelty_requirements: [requires model normalization]

## Next Action

Run input_normalization via trusted_role_runner to produce normalized brief.
This scaffold is a placeholder — no model conclusions have been drawn.
"""
    scaffold_file.write_text(scaffold_content, encoding="utf-8")
    results.append(f"Created runtime/{scaffold_file.name}")

    # 3. Update workflow state
    state = update_workflow_state("research-intake", payload_file)
    results.append(f"Updated runtime/workflow_state.json")

    return {
        "status": "execute_safe",
        "command": "/research-intake",
        "files_created": results,
        "workflow_state": state,
        "model_called": False,
        "trusted_outputs_changed": False,
        "next_action": "Run /literature-intake to begin literature survey",
    }


def execute_literature_intake(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /literature-intake. Runs metadata-only literature search.

    Calls run_multisource_pipeline for real metadata search across arXiv, OpenAlex, Crossref.
    No PDF downloads, no model calls, no trusted_outputs changes.
    """
    _ensure_research_dir()
    payload = parsed["payload"]
    results = []

    # Check prerequisites
    raw_file = RUNTIME_DIR / "raw_user_input.md"
    if not raw_file.exists():
        return {
            "status": "blocked",
            "command": "/literature-intake",
            "blocked_reason": "No raw_user_input.md found. Run /research-intake first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Determine search topic: use payload if provided, else read from raw_user_input
    search_topic = payload
    if not search_topic and raw_file.exists():
        raw_content = raw_file.read_text(encoding="utf-8")
        # Extract text after frontmatter
        parts = raw_content.split("---", 2)
        if len(parts) >= 3:
            search_topic = parts[2].strip()[:500]
        else:
            search_topic = raw_content.strip()[:500]

    if not search_topic:
        return {
            "status": "blocked",
            "command": "/literature-intake",
            "blocked_reason": "No search topic available. Provide payload or run /research-intake first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Run metadata-only literature search via existing pipeline
    try:
        # Ensure project root is importable
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools.literature_evidence_landing import run_multisource_pipeline

        RUNTIME_LIT_DIR.mkdir(parents=True, exist_ok=True)

        # Extract must_include keywords from topic (simple heuristic)
        must_include = _extract_keywords(search_topic)

        # Capture pipeline stdout to prevent mixing with adapter JSON output
        import io
        _old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            pipeline_result = run_multisource_pipeline(
            topic=search_topic,
            intent="novelty_check",
            must_include=must_include,
            sources=["arxiv", "crossref", "openalex"],
            run_dir=RUNTIME_LIT_DIR,
            start_year=2020,
            end_year=datetime.now().year,
            max_results_per_source=15,
            max_jobs=9,
            per_page=10,
            top_k=10,
            overwrite=True,
            exclude="supply chain,medical",
            dry_run=False,
            json_output=True,
        )
        finally:
            sys.stdout = _old_stdout

        if pipeline_result.get("status") == "PASS":
            # Read actual counts from output files (pipeline summary may be stale)
            n_raw = _count_jsonl_lines(RUNTIME_LIT_DIR / "raw_results.jsonl")
            n_candidates = _count_jsonl_lines(RUNTIME_LIT_DIR / "candidates.jsonl")
            n_top_k = _count_top_k_papers(RUNTIME_LIT_DIR / "top_k.md")

            # Write summary.json
            summary_file = RUNTIME_LIT_DIR / "summary.json"
            summary_file.write_text(json.dumps({
                "status": "success",
                "topic": search_topic,
                "sources": ["arxiv", "crossref", "openalex"],
                "total_raw_records": n_raw,
                "total_candidates": n_candidates,
                "top_k_selected": n_top_k,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_called": False,
            }, indent=2, ensure_ascii=False), encoding="utf-8")

            # Create literature intake summary scaffold
            scaffold_file = RUNTIME_DIR / "literature_intake_scaffold.md"
            scaffold_content = f"""---
command: /literature-intake
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: live_metadata_search
model_not_called: true
status: success
search_topic: {search_topic}
total_raw_records: {n_raw}
total_candidates: {n_candidates}
top_k_selected: {n_top_k}
---

# Literature Intake — Metadata Search Complete

## Search Topic

{search_topic}

## Sources Queried

- arXiv (Atom XML API)
- Crossref (REST API)
- OpenAlex (REST API)

## Results Summary

- Raw records fetched: {n_raw}
- Deduplicated candidates: {n_candidates}
- Top-k selected: {n_top_k}

## Output Files

- Search plan: runtime/literature_search/search_plan.yaml
- Raw results: runtime/literature_search/raw_results.jsonl
- Candidates: runtime/literature_search/candidates.jsonl
- Top-k papers: runtime/literature_search/top_k.md
- Summary: runtime/literature_search/summary.json

## Next Action

Run /idea-synthesis to generate candidate research ideas based on this literature evidence.

## Notes

- No PDFs downloaded
- No models called
- No trusted_outputs changed
- Metadata-only search — full-text review deferred
"""
            scaffold_file.write_text(scaffold_content, encoding="utf-8")
            results.append(f"Created runtime/{scaffold_file.name}")
            results.append(f"Created runtime/literature_search/ ({n_raw} raw, {n_candidates} candidates, {n_top_k} top-k)")

            # Update workflow state
            state = update_workflow_state("literature-intake", payload_file)
            results.append(f"Updated runtime/workflow_state.json")

            return {
                "status": "execute_safe",
                "command": "/literature-intake",
                "files_created": results,
                "workflow_state": state,
                "model_called": False,
                "trusted_outputs_changed": False,
                "next_action": "Run /idea-synthesis to generate candidate ideas",
                "note": f"Metadata search complete: {n_raw} raw records, {n_candidates} candidates, {n_top_k} top-k.",
                "search_summary": {
                    "raw_records": n_raw,
                    "candidates": n_candidates,
                    "top_k": n_top_k,
                    "run_dir": str(RUNTIME_LIT_DIR),
                },
            }
        else:
            # Pipeline failed
            error_msg = pipeline_result.get("error", "Unknown pipeline error")
            return {
                "status": "blocked",
                "command": "/literature-intake",
                "blocked_reason": f"Metadata search failed: {error_msg}",
                "model_called": False,
                "trusted_outputs_changed": False,
                "pipeline_result": pipeline_result,
            }

    except ImportError:
        return {
            "status": "blocked",
            "command": "/literature-intake",
            "blocked_reason": "literature_evidence_landing module not available. Cannot run metadata search.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }
    except Exception as e:
        return {
            "status": "blocked",
            "command": "/literature-intake",
            "blocked_reason": f"Metadata search error: {type(e).__name__}: {e}",
            "model_called": False,
            "trusted_outputs_changed": False,
        }


def _extract_keywords(topic: str) -> list[str]:
    """Extract must-include keywords from a research topic string."""
    # Simple heuristic: split on common delimiters, take meaningful words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "both",
        "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "don", "now", "and", "but", "or", "if", "because", "while", "about",
        "up", "it", "its", "i", "me", "my", "we", "our", "you", "your",
        "he", "him", "his", "she", "her", "they", "them", "their", "this",
        "that", "these", "those", "what", "which", "who", "whom",
    }
    words = re.findall(r'[a-zA-Z]{3,}', topic.lower())
    keywords = [w for w in words if w not in stop_words]
    # Return top 5 most distinctive words
    return keywords[:5]


def execute_idea_synthesis(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /idea-synthesis. Creates evidence-aware scaffold, no model calls.

    If literature metadata exists, scaffold references actual metadata files.
    If no metadata, blocked with next_action to run /literature-intake.
    """
    _ensure_research_dir()
    payload = parsed["payload"]
    num_candidates = parsed["flags"].get("num-candidates", "5")
    results = []

    # Check prerequisites
    raw_file = RUNTIME_DIR / "raw_user_input.md"
    if not raw_file.exists():
        return {
            "status": "blocked",
            "command": "/idea-synthesis",
            "blocked_reason": "No raw_user_input.md found. Run /research-intake first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Check for literature metadata
    has_metadata = _has_literature_metadata()
    meta_path = _get_literature_metadata_path()
    try:
        meta_rel = str(meta_path.relative_to(ROOT)) if meta_path else "none"
    except ValueError:
        meta_rel = str(meta_path) if meta_path else "none"

    # Read top_k summary for evidence-aware scaffold
    top_k_summary = _read_top_k_summary() if has_metadata else "No literature metadata available."

    # Create idea synthesis scaffold
    scaffold_file = RUNTIME_DIR / "idea_synthesis_scaffold.md"
    scaffold_content = f"""---
command: /idea-synthesis
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: scaffold
model_not_called: true
status: {"evidence_aware" if has_metadata else "blocked_no_evidence"}
num_candidates: {num_candidates}
literature_metadata: {"available" if has_metadata else "missing"}
metadata_path: {meta_rel}
---

# Idea Synthesis Scaffold

## Generation Focus

{payload}

## Literature Evidence Status

{"**Available** — top_k papers loaded from: " + meta_rel if has_metadata else "**Missing** — run /literature-intake first to collect literature metadata."}

{"### Top-K Papers Summary" if has_metadata else ""}

{top_k_summary if has_metadata else ""}

## Synthesis Modes (all require model — scaffold templates below)

### Gap-Driven Innovation
- Identify gaps in existing literature
- Propose methods that address uncovered problems
- Reference: top_k.md for existing coverage
- Status: scaffold (model not called)

### Transfer Innovation
- Transfer mature method from source domain to target domain
- **Source domain**: [requires model — identify from literature]
- **Target domain**: [requires model — from user input]
- **Direct transfer baseline**: [requires model — what happens if method applied as-is]
- **Mismatch**: [requires model — what doesn't transfer directly]
- **Adaptation opportunity**: [requires model — how to bridge the gap]
- Status: scaffold (model not called)

### Contribution Chain
- Build on existing work incrementally
- **Component contribution 1**: [requires model]
- **Component contribution 2**: [requires model]
- **Component contribution 3**: [requires model]
- **Shared core claim**: [requires model — what ties contributions together]
- **Ablation requirement**: [requires model — which components are essential]
- **Risk of patchwork**: [requires model — is this just assembly, not innovation?]
- Status: scaffold (model not called)

## Candidate Ideas Template

For each of {num_candidates} candidates:
1. **Idea Title**: [requires model]
2. **Domain**: [requires model]
3. **Innovation Type**: gap-driven / transfer / contribution-chain
4. **Key Hypothesis**: [requires model]
5. **Expected Contribution**: [requires model]
6. **Risk Level**: [requires model]
7. **Prior Work Basis**: [requires model — must reference actual papers from top_k]

## Next Action

{"Run /idea-audit to verify novelty of generated ideas." if has_metadata else "Blocked: run /literature-intake first to collect literature metadata."}

## Notes

- No models called
- No trusted_outputs changed
- {"Scaffold references actual literature metadata from " + meta_rel if has_metadata else "Cannot generate ideas without literature evidence"}
- Transfer innovation and contribution chain modes include detailed templates
"""
    scaffold_file.write_text(scaffold_content, encoding="utf-8")
    results.append(f"Created runtime/{scaffold_file.name}")

    # Update workflow state
    state = update_workflow_state("idea-synthesis", payload_file)
    results.append(f"Updated runtime/workflow_state.json")

    return {
        "status": "execute_safe",
        "command": "/idea-synthesis",
        "files_created": results,
        "workflow_state": state,
        "model_called": False,
        "trusted_outputs_changed": False,
        "next_action": "Run /idea-audit to verify novelty of generated ideas" if has_metadata else "Run /literature-intake first",
        "note": f"Evidence-aware scaffold for {num_candidates} candidates. Metadata: {'available' if has_metadata else 'missing'}.",
    }


def execute_idea_audit(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /idea-audit. Creates evidence-aware audit scaffold, no model calls.

    Checks for both literature evidence and idea synthesis scaffold.
    """
    _ensure_research_dir()
    payload = parsed["payload"]
    results = []

    # Check prerequisites
    raw_file = RUNTIME_DIR / "raw_user_input.md"
    if not raw_file.exists():
        return {
            "status": "blocked",
            "command": "/idea-audit",
            "blocked_reason": "No raw_user_input.md found. Run /research-intake first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Check for evidence
    has_metadata = _has_literature_metadata()
    meta_path = _get_literature_metadata_path()
    try:
        meta_rel = str(meta_path.relative_to(ROOT)) if meta_path else "none"
    except ValueError:
        meta_rel = str(meta_path) if meta_path else "none"

    # Check for idea synthesis scaffold
    has_synthesis = _has_idea_synthesis_scaffold()

    # Read top_k summary for evidence-aware scaffold
    top_k_summary = _read_top_k_summary() if has_metadata else "No literature metadata available."

    # Determine blocked reasons
    blocked_reasons = []
    if not has_metadata:
        blocked_reasons.append("insufficient_evidence")
    if not has_synthesis:
        blocked_reasons.append("no_candidate_ideas")

    # Create audit scaffold
    scaffold_file = RUNTIME_DIR / "idea_audit_scaffold.md"
    scaffold_content = f"""---
command: /idea-audit
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: scaffold
model_not_called: true
status: {"evidence_aware" if (has_metadata and has_synthesis) else "blocked"}
evidence_available: {"true" if has_metadata else "false"}
synthesis_available: {"true" if has_synthesis else "false"}
blocked_reasons: {json.dumps(blocked_reasons) if blocked_reasons else "none"}
metadata_path: {meta_rel}
---

# Idea Audit Scaffold

## Audit Focus

{payload}

## Prerequisites Check

- Literature evidence: {"available at " + meta_rel if has_metadata else "MISSING — run /literature-intake first"}
- Idea synthesis scaffold: {"available" if has_synthesis else "MISSING — run /idea-synthesis first"}

## Literature Evidence Summary

{top_k_summary}

## Audit Verdict Slots (all require model)

- **already_done**: [requires model] — is this idea already published?
- **direct_transfer_only**: [requires model] — is this just applying an existing method to a new domain without adaptation?
- **adaptation_gap**: [requires model] — is there a meaningful adaptation needed?
- **combination_gap**: [requires model] — is this combining existing methods in a novel way?
- **insufficient_evidence**: [requires model] — is the literature evidence too thin to judge?
- **promising_but_needs_more_evidence**: [requires model] — direction looks good but needs more support
- **worth_experiment_plan**: [requires model] — novelty verified, proceed to experiment planning

## Direct Transfer Check Template

For each candidate idea:
1. **Source method**: [requires model — what existing method is being transferred?]
2. **Target domain**: [requires model — what new domain is it applied to?]
3. **Direct applicability**: [requires model — can the method be applied as-is?]
4. **Domain mismatch**: [requires model — what differences prevent direct transfer?]
5. **Adaptation required**: [requires model — what modifications are needed?]
6. **Novelty of adaptation**: [requires model — is the adaptation itself novel?]

## Contribution Chain Coherence Check Template

For each candidate idea:
1. **Component 1**: [requires model — first building block]
2. **Component 2**: [requires model — second building block]
3. **Component 3**: [requires model — third building block]
4. **Shared claim**: [requires model — what unifying claim ties them?]
5. **Ablation test**: [requires model — which component is essential?]
6. **Patchwork risk**: [requires model — is this just assembly without novelty?]

## Evidence Status

- Literature evidence: {"available" if has_metadata else "insufficient_evidence"}
- Idea synthesis: {"available" if has_synthesis else "missing"}
- Full-text review: requires model
- Closest prior work identification: requires model

## Verdict Template

- novelty_verdict: [requires model] — DO NOT write confirmed_novel
- evidence_quality: [requires model]
- risk_level: [requires model]
- next_action: [requires model]

## Next Action

{"Run novelty_check via trusted_role_runner to perform actual audit." if (has_metadata and has_synthesis) else "Blocked: " + "; ".join(blocked_reasons) + ". Complete these prerequisites first."}

## Notes

- No models called
- No trusted_outputs changed
- Cannot write confirmed_novel without model verification
- If evidence insufficient, verdict must be insufficient_evidence
"""
    scaffold_file.write_text(scaffold_content, encoding="utf-8")
    results.append(f"Created runtime/{scaffold_file.name}")

    # Update workflow state
    state = update_workflow_state("idea-audit", payload_file)
    if blocked_reasons:
        state["blocked_reason"] = "; ".join(blocked_reasons)
    results.append(f"Updated runtime/workflow_state.json")

    return {
        "status": "blocked" if blocked_reasons else "execute_safe",
        "command": "/idea-audit",
        "files_created": results,
        "workflow_state": state,
        "model_called": False,
        "trusted_outputs_changed": False,
        "blocked_reasons": blocked_reasons if blocked_reasons else None,
        "next_action": "Run /experiment after audit passes" if not blocked_reasons else f"Blocked: {'; '.join(blocked_reasons)}",
        "note": f"Audit scaffold created. evidence={'available' if has_metadata else 'missing'}, synthesis={'available' if has_synthesis else 'missing'}.",
    }


def execute_experiment(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /experiment. Generates mode-specific scaffold, no model calls.

    Mode-specific logic:
    - lightweight: always allowed, creates sanity experiment scaffold
    - full: warns if no lightweight evidence, creates full experiment scaffold
    - analyze: blocked unless experiment results exist
    - revise: blocked unless failure/blocked reason exists
    """
    _ensure_research_dir()
    payload = parsed["payload"]
    mode = parsed["flags"].get("mode", "lightweight")
    results = []

    # Validate mode
    valid_modes = COMMAND_MAP["experiment"]["modes"]
    if mode not in valid_modes:
        return {
            "status": "blocked",
            "command": "/experiment",
            "blocked_reason": f"Invalid mode '{mode}'. Valid modes: {valid_modes}",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Check prerequisites
    raw_file = RUNTIME_DIR / "raw_user_input.md"
    if not raw_file.exists():
        return {
            "status": "blocked",
            "command": "/experiment",
            "blocked_reason": "No raw_user_input.md found. Run /research-intake first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Mode-specific blocking logic
    has_results = _has_experiment_results()
    has_lightweight = (RUNTIME_DIR / "experiment_scaffold_lightweight.md").exists()
    has_failure_info = has_results  # Simplified: if results exist, we can analyze failures

    if mode == "full" and not has_lightweight:
        # Warning but not blocked — can still create scaffold
        pass
    elif mode == "analyze" and not has_results:
        return {
            "status": "blocked",
            "command": "/experiment",
            "blocked_reason": "No experiment results to analyze. Run /experiment --mode lightweight or --mode full first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }
    elif mode == "revise" and not has_results:
        return {
            "status": "blocked",
            "command": "/experiment",
            "blocked_reason": "No experiment results or failure info to revise from. Run /experiment first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Mode-specific scaffolds
    mode_sections = {
        "lightweight": """
### Lightweight Experiment
- Design sanity check experiment
- Small dataset, quick validation
- Binary pass/fail signal
- Status: scaffold (not executed)
- Expected duration: < 1 hour
- Requirements: minimal compute
""",
        "full": """
### Full Experiment
- Complete baseline implementation
- Ablation study design
- Robustness testing
- Statistical significance checks
- Status: scaffold (not executed)
- Expected duration: hours to days
- Requirements: significant compute
""" + ("\n**Warning:** No lightweight experiment scaffold found. Consider running lightweight first." if not has_lightweight else ""),
        "analyze": """
### Result Analysis
- Read existing experiment results
- Compare against baselines
- Identify failure modes
- Status: scaffold (results available for analysis)
- Note: Results found — model should read and analyze them
""",
        "revise": """
### Method Revision
- Analyze failure causes
- Generate revision hypotheses
- Design revised experiment
- Status: scaffold (failure info available for revision)
- Note: Previous results available — model should analyze failures
""",
    }

    # Create experiment scaffold
    scaffold_file = RUNTIME_DIR / f"experiment_scaffold_{mode}.md"
    scaffold_content = f"""---
command: /experiment
mode: {mode}
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: scaffold
model_not_called: true
status: scaffold
has_lightweight_evidence: {"true" if has_lightweight else "false"}
has_experiment_results: {"true" if has_results else "false"}
---

# Experiment Scaffold — {mode.upper()} Mode

## Experiment Focus

{payload}

## Mode: {mode}

{mode_sections.get(mode, "Unknown mode")}

## Experiment Plan Template

1. **Hypothesis**: [requires model/method refinement]
2. **Baseline**: [requires model]
3. **Metrics**: [requires model]
4. **Dataset**: [requires model]
5. **Expected Duration**: [requires model]
6. **Kill Conditions**: [requires model]

## Next Action

Run experiment_plan via trusted_role_runner to generate actual experiment plan.
This scaffold is a placeholder — no experiment has been designed or executed.

## Notes

- No models called
- No code executed
- No experiments run
- No trusted_outputs changed
- No results claimed
"""
    scaffold_file.write_text(scaffold_content, encoding="utf-8")
    results.append(f"Created runtime/{scaffold_file.name}")

    # Update workflow state
    state = update_workflow_state("experiment", payload_file)
    results.append(f"Updated runtime/workflow_state.json")

    return {
        "status": "execute_safe",
        "command": "/experiment",
        "mode": mode,
        "files_created": results,
        "workflow_state": state,
        "model_called": False,
        "trusted_outputs_changed": False,
        "next_action": f"Run /experiment with --mode analyze after running {mode} experiment",
        "note": f"{mode.capitalize()} scaffold created. Actual experiment requires model + code execution.",
    }


def execute_paper_writing(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /paper-writing. Generates scaffold, checks prerequisites.

    Blocked unless:
    - Experiment results exist
    - Claim boundary (method_refinement) exists
    """
    _ensure_research_dir()
    payload = parsed["payload"]
    results = []

    # Check prerequisites
    raw_file = RUNTIME_DIR / "raw_user_input.md"
    if not raw_file.exists():
        return {
            "status": "blocked",
            "command": "/paper-writing",
            "blocked_reason": "No raw_user_input.md found. Run /research-intake first.",
            "model_called": False,
            "trusted_outputs_changed": False,
        }

    # Check for experiment results
    has_results = _has_experiment_results()

    # Check for claim boundary
    has_claim = _has_claim_boundary()

    # Check for literature evidence
    has_metadata = _has_literature_metadata()

    blocked_reasons = []
    if not has_results:
        blocked_reasons.append("No experiment results found")
    if not has_claim:
        blocked_reasons.append("No claim boundary (method_refinement) found")
    if not has_metadata:
        blocked_reasons.append("No literature evidence")

    # Create paper-writing scaffold
    scaffold_file = RUNTIME_DIR / "paper_writing_scaffold.md"
    scaffold_content = f"""---
command: /paper-writing
timestamp: {datetime.now(timezone.utc).isoformat()}
implementation_source: scaffold
model_not_called: true
status: {"blocked" if blocked_reasons else "scaffold"}
blocked_reasons: {json.dumps(blocked_reasons) if blocked_reasons else "none"}
---

# Paper Writing Scaffold

## Writing Focus

{payload}

## Prerequisites Check

- Experiment results: {"found" if has_results else "NOT FOUND — blocked"}
- Claim boundary (method_refinement): {"found" if has_claim else "NOT FOUND — blocked"}
- Literature evidence: {"found" if has_metadata else "NOT FOUND — blocked"}

## Paper Sections Template

### Title
[requires model — do not write without verified results]

### Abstract
[requires model — do not write without verified results]

### Introduction
- Problem statement: [requires model]
- Motivation: [requires model]
- Contribution list: [requires model — do not claim unverified contributions]

### Related Work
[requires model — requires literature evidence]

### Method
[requires model — requires method_refinement]

### Experiments
[requires model — requires experiment results]

### Results
[requires model — requires actual results, not fabricated]

### Discussion
[requires model — requires actual results]

### Limitations
[requires model]

## Next Action

{"Blocked: " + "; ".join(blocked_reasons) + ". Complete these before paper writing." if blocked_reasons else "Run paper_writing via trusted_role_runner to generate actual paper sections."}

## Notes

- No models called
- No paper sections written
- No results fabricated
- No trusted_outputs changed
- Cannot write paper without verified experiment results
"""
    scaffold_file.write_text(scaffold_content, encoding="utf-8")
    results.append(f"Created runtime/{scaffold_file.name}")

    # Update workflow state
    state = update_workflow_state("paper-writing", payload_file)
    if blocked_reasons:
        state["blocked_reason"] = "; ".join(blocked_reasons)
    results.append(f"Updated runtime/workflow_state.json")

    return {
        "status": "blocked" if blocked_reasons else "execute_safe",
        "command": "/paper-writing",
        "files_created": results,
        "workflow_state": state,
        "model_called": False,
        "trusted_outputs_changed": False,
        "blocked_reasons": blocked_reasons if blocked_reasons else None,
        "next_action": "Complete experiment and claim boundary before paper writing",
    }


def execute_status(parsed: dict, payload_file: str | None = None) -> dict:
    """Safe execution for /status. Reads state, no mutations.

    Enhanced output includes:
    - workflow state (phase, completed, next, blocked)
    - runtime files summary
    - literature metadata summary
    - trusted outputs summary
    """
    state = load_workflow_state()

    # Read trusted outputs summary
    trusted_outputs_summary = {}
    for stage in ["raw_user_input", "input_normalization", "research_contract",
                   "literature_search", "novelty_check", "method_refinement",
                   "experiment_plan", "result_judge", "paper_writing"]:
        path = RESEARCH_DIR / "trusted_outputs" / f"{stage}.md"
        if path.exists():
            trusted_outputs_summary[stage] = "exists"
        else:
            # Check runtime scaffold
            scaffold_path = RUNTIME_DIR / f"{stage}_scaffold.md"
            if scaffold_path.exists():
                trusted_outputs_summary[stage] = "scaffold"
            else:
                trusted_outputs_summary[stage] = "missing"

    # Runtime files summary
    runtime_files = {}
    if RUNTIME_DIR.exists():
        for f in sorted(RUNTIME_DIR.iterdir()):
            if f.is_file():
                runtime_files[f.name] = f.stat().st_size
            elif f.is_dir():
                runtime_files[f.name + "/"] = sum(1 for _ in f.iterdir())

    # Literature metadata summary
    lit_summary = {"available": False, "path": None, "top_k_count": 0}
    meta_path = _get_literature_metadata_path()
    if meta_path:
        lit_summary["available"] = True
        lit_summary["path"] = str(meta_path.relative_to(ROOT))
        top_k_file = meta_path / "top_k.md"
        if top_k_file.exists():
            content = top_k_file.read_text(encoding="utf-8")
            # Count paper entries (lines starting with "## " or "- **")
            lit_summary["top_k_count"] = content.count("## ") + content.count("- **")

    return {
        "status": "execute_safe",
        "command": "/status",
        "workflow_state": state,
        "trusted_outputs_summary": trusted_outputs_summary,
        "runtime_files": runtime_files,
        "literature_summary": lit_summary,
        "model_called": False,
        "trusted_outputs_changed": False,
    }


# ---- Plan generation ----

def generate_plan(parsed: dict, run_dir: Path | None = None) -> dict:
    """Generate a structured plan from a parsed slash command.

    Returns a plan dict with command info, mapped CLI action, and status.
    Does NOT execute anything.
    """
    if not parsed["valid"]:
        return {
            "status": "FAIL",
            "command": parsed["command"],
            "error": parsed["error"],
            "raw": parsed["raw"],
        }

    command = parsed["command"]
    payload = parsed["payload"]
    flags = parsed["flags"]
    spec = COMMAND_MAP[command]

    plan = {
        "status": "PASS",
        "command": f"/{command}",
        "description": spec["description"],
        "payload": payload,
        "flags": flags,
        "maps_to": spec["maps_to"],
        "internal_stages": spec["internal_stages"],
        "dry_run": True,
        "execution_mode": spec.get("execution_mode", "plan_only"),
    }

    # Generate specific CLI action based on command
    if command == "research-intake":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py start",
            "args": ["--idea", payload, "--mode", "novelty_risk", "--dry-run"],
            "description": "Start a new research workflow with the given idea",
        }
    elif command == "literature-intake":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "literature_search", "--dry-run"],
            "description": "Continue to literature search stage",
        }
    elif command == "idea-synthesis":
        num_candidates = flags.get("num-candidates", "5")
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "idea_pivot", "--dry-run"],
            "description": f"Generate {num_candidates} candidate ideas via idea pivot",
        }
    elif command == "idea-audit":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "novelty_check", "--dry-run"],
            "description": "Run novelty check and method refinement",
        }
    elif command == "experiment":
        mode = flags.get("mode", "lightweight")
        if mode not in spec.get("modes", []):
            plan["status"] = "FAIL"
            plan["error"] = f"invalid mode '{mode}'; valid modes: {spec['modes']}"
            return plan
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "experiment_plan", "--dry-run"],
            "description": f"Run experiment plan in '{mode}' mode",
            "mode": mode,
        }
        if mode == "lightweight":
            plan["note"] = "Lightweight mode: quick signal check, small data, small model"
        elif mode == "full":
            plan["note"] = "Full mode: complete baseline, ablation, robustness"
        elif mode == "analyze":
            plan["note"] = "Analyze mode: review existing results, determine next action"
        elif mode == "revise":
            plan["note"] = "Revise mode: adjust method based on failure analysis"
    elif command == "paper-writing":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py continue",
            "args": ["--stage", "paper_writing", "--dry-run"],
            "description": "Write paper based on verified results",
        }
        plan["note"] = "Paper writing requires verified experiment results and approved claim boundary"
    elif command == "status":
        plan["cli_action"] = {
            "command": "python tools/research_cli.py status",
            "args": [],
            "description": "Display current research status",
        }
        plan["note"] = flags.get("note", "")

    return plan


# ---- Main execution dispatcher ----

EXECUTORS = {
    "research-intake": execute_research_intake,
    "literature-intake": execute_literature_intake,
    "idea-synthesis": execute_idea_synthesis,
    "idea-audit": execute_idea_audit,
    "experiment": execute_experiment,
    "paper-writing": execute_paper_writing,
    "status": execute_status,
}


def execute_command(parsed: dict, payload_file: str | None = None) -> dict:
    """Execute a command in safe mode. Returns execution result."""
    command = parsed["command"]
    executor = EXECUTORS.get(command)
    if not executor:
        return {
            "status": "blocked",
            "command": command,
            "blocked_reason": f"No executor for command: {command}",
            "model_called": False,
            "trusted_outputs_changed": False,
        }
    return executor(parsed, payload_file)


# ---- Self-test ----

def _self_test() -> bool:
    """Run self-tests for the slash command adapter."""
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

    # Test 1: Parse quoted payload
    p = parse_slash_command('/research-intake "我想做时间序列异常检测"')
    check("1. parse quoted payload", p["valid"] and p["command"] == "research-intake" and p["payload"] == "我想做时间序列异常检测",
          f"got command={p['command']}, payload={p['payload']}")

    # Test 2: Parse flags
    p = parse_slash_command('/experiment "先做轻量实验" --mode lightweight')
    check("2. parse flags", p["valid"] and p["flags"].get("mode") == "lightweight",
          f"got flags={p['flags']}")

    # Test 3: Reject unknown command
    p = parse_slash_command('/unknown-command "test"')
    check("3. reject unknown command", not p["valid"] and "unknown" in (p["error"] or ""),
          f"got valid={p['valid']}, error={p['error']}")

    # Test 4: Status command
    p = parse_slash_command('/status')
    check("4. status command", p["valid"] and p["command"] == "status" and p["payload"] == "",
          f"got command={p['command']}, payload={p['payload']}")

    # Test 5: Status with note
    p = parse_slash_command('/status "只告诉我当前卡在哪里"')
    check("5. status with note", p["valid"] and p["payload"] == "只告诉我当前卡在哪里",
          f"got payload={p['payload']}")

    # Test 6: Experiment lightweight mode
    p = parse_slash_command('/experiment "先做轻量实验" --mode lightweight')
    plan = generate_plan(p)
    check("6. experiment lightweight mode", plan["status"] == "PASS" and plan["flags"].get("mode") == "lightweight",
          f"got status={plan['status']}, mode={plan['flags'].get('mode')}")

    # Test 7: Experiment invalid mode
    p = parse_slash_command('/experiment "test" --mode invalid')
    plan = generate_plan(p)
    check("7. experiment invalid mode", plan["status"] == "FAIL" and "invalid mode" in (plan.get("error") or ""),
          f"got status={plan['status']}, error={plan.get('error')}")

    # Test 8: Payload persistence uses safe path
    with tempfile.TemporaryDirectory() as td:
        safe_dir = Path(td) / "test_payloads"
        filepath = save_payload("research-intake", "test payload content", safe_dir)
        check("8. payload persistence", filepath.exists() and "research_intake" in filepath.name,
              f"path={filepath}, exists={filepath.exists()}")
        content = filepath.read_text(encoding="utf-8")
        check("8b. payload content", "test payload content" in content,
              f"content snippet={content[:100]}")

    # Test 9: Generate plan for research-intake
    p = parse_slash_command('/research-intake "Chain-of-Thought prompting"')
    plan = generate_plan(p)
    check("9. research-intake plan", plan["status"] == "PASS" and plan["maps_to"] == "research_cli_start",
          f"got maps_to={plan['maps_to']}")

    # Test 10: Generate plan for literature-intake
    p = parse_slash_command('/literature-intake "重点查 diffusion"')
    plan = generate_plan(p)
    check("10. literature-intake plan", plan["status"] == "PASS" and plan["maps_to"] == "continue_literature_search",
          f"got maps_to={plan['maps_to']}")

    # Test 11: Generate plan for idea-synthesis
    p = parse_slash_command('/idea-synthesis "不要只想单点创新" --num-candidates 8')
    plan = generate_plan(p)
    check("11. idea-synthesis plan", plan["status"] == "PASS",
          f"got status={plan['status']}")

    # Test 12: Generate plan for idea-audit
    p = parse_slash_command('/idea-audit "重点检查 diffusion"')
    plan = generate_plan(p)
    check("12. idea-audit plan", plan["status"] == "PASS" and plan["maps_to"] == "continue_novelty_check",
          f"got maps_to={plan['maps_to']}")

    # Test 13: Generate plan for paper-writing
    p = parse_slash_command('/paper-writing "按保守论文风格写"')
    plan = generate_plan(p)
    check("13. paper-writing plan", plan["status"] == "PASS",
          f"got status={plan['status']}")

    # Test 14: Reject empty command
    p = parse_slash_command('/')
    check("14. reject empty command", not p["valid"],
          f"got valid={p['valid']}")

    # Test 15: Reject non-slash input
    p = parse_slash_command('research-intake "test"')
    check("15. reject non-slash input", not p["valid"] and "must start with /" in (p["error"] or ""),
          f"got valid={p['valid']}, error={p['error']}")

    # Test 16: Experiment analyze mode
    p = parse_slash_command('/experiment "分析结果" --mode analyze')
    plan = generate_plan(p)
    check("16. experiment analyze mode", plan["status"] == "PASS" and plan["flags"].get("mode") == "analyze",
          f"got mode={plan['flags'].get('mode')}")

    # Test 17: Experiment revise mode
    p = parse_slash_command('/experiment "根据失败原因调整方法" --mode revise')
    plan = generate_plan(p)
    check("17. experiment revise mode", plan["status"] == "PASS" and plan["flags"].get("mode") == "revise",
          f"got mode={plan['flags'].get('mode')}")

    # Test 18: Plan includes internal stages
    p = parse_slash_command('/research-intake "test idea"')
    plan = generate_plan(p)
    check("18. plan includes internal stages", len(plan["internal_stages"]) > 0,
          f"stages={plan['internal_stages']}")

    # Test 19: All commands have plans
    all_ok = True
    for cmd in COMMAND_MAP:
        p = parse_slash_command(f'/{cmd} "test"')
        plan = generate_plan(p)
        if plan["status"] != "PASS":
            all_ok = False
            break
    check("19. all commands generate plans", all_ok)

    # Test 20: CLI help
    p = parse_slash_command('/experiment "test" --mode full')
    plan = generate_plan(p)
    check("20. experiment full mode plan", plan["status"] == "PASS" and plan["flags"].get("mode") == "full",
          f"got mode={plan['flags'].get('mode')}")

    # Test 21: execution_mode in plan
    for cmd in ("research-intake", "literature-intake", "idea-synthesis", "idea-audit", "experiment", "paper-writing", "status"):
        p = parse_slash_command(f'/{cmd} "test"')
        plan = generate_plan(p)
        check(f"21. {cmd} has execution_mode", plan.get("execution_mode") == "execute_safe",
              f"got execution_mode={plan.get('execution_mode')}")

    # Test 22: plan includes payload_file when save_payload used
    with tempfile.TemporaryDirectory() as td:
        from io import StringIO
        import contextlib
        f = StringIO()
        with contextlib.redirect_stdout(f):
            parsed = parse_slash_command('/research-intake "test idea"')
            plan = generate_plan(parsed)
            safe_dir = Path(td) / " payloads"
            filepath = save_payload(parsed["command"], parsed["payload"], safe_dir)
            plan["payload_file"] = str(filepath)
        check("22. plan has payload_file", "payload_file" in plan and plan["payload_file"].endswith(".md"),
              f"payload_file={plan.get('payload_file')}")

    # Test 23: execute research-intake creates files
    with tempfile.TemporaryDirectory() as td:
        import sys as _sys
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/research-intake "test execution"')
            result = execute_command(p)
            check("23. execute research-intake", result["status"] == "execute_safe" and not result["model_called"],
                  f"got status={result['status']}, model_called={result['model_called']}")
            check("23b. raw_user_input.md created", (mod.RUNTIME_DIR / "raw_user_input.md").exists())
            check("23c. workflow_state.json created", mod.WORKFLOW_STATE_FILE.exists())
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 24: execute status returns state
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/status')
            result = execute_command(p)
            check("24. execute status", result["status"] == "execute_safe" and "workflow_state" in result,
                  f"got status={result['status']}")
            check("24b. status has runtime_files", "runtime_files" in result,
                  f"keys={list(result.keys())}")
            check("24c. status has literature_summary", "literature_summary" in result,
                  f"keys={list(result.keys())}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 25: literature-intake blocked without raw_user_input
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/literature-intake "test"')
            result = execute_command(p)
            check("25. literature-intake blocked without input", result["status"] == "blocked",
                  f"got status={result['status']}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 26: paper-writing blocked without results
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            # Create raw_user_input in runtime so prerequisite check passes
            mod.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            (mod.RUNTIME_DIR / "raw_user_input.md").write_text("test")
            p = parse_slash_command('/paper-writing "test"')
            result = execute_command(p)
            check("26. paper-writing blocked without results", result["status"] == "blocked",
                  f"got status={result['status']}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 27: workflow state tracking
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/research-intake "test"')
            result = execute_command(p)
            state = result["workflow_state"]
            check("27. workflow state tracks phase", state["current_user_phase"] == "research_direction_intake",
                  f"got phase={state['current_user_phase']}")
            check("27b. workflow state tracks command", state["latest_command"] == "research-intake",
                  f"got command={state['latest_command']}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 28: dry-run message accurate
    src = Path(__file__).read_text(encoding="utf-8")
    dry_run_lines = [l for l in src.split("\n") if "DRY-RUN:" in l and "print(" in l]
    has_new = any("Payload files are only written" in l for l in dry_run_lines)
    check("28. dry-run message accurate", has_new, "missing new dry-run message")

    # Test 29: all executors exist
    for cmd in COMMAND_MAP:
        if cmd == "status":
            continue
        check(f"29. {cmd} has executor", cmd in EXECUTORS, f"missing executor")

    # Test 30: execute experiment with valid modes
    for mode in ("lightweight", "full", "analyze", "revise"):
        with tempfile.TemporaryDirectory() as td:
            mod = _sys.modules[__name__]
            orig_dir = mod.RESEARCH_DIR
            orig_rt = mod.RUNTIME_DIR
            orig_state = mod.WORKFLOW_STATE_FILE
            mod.RESEARCH_DIR = Path(td) / "research" / "current"
            mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
            mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
            mod.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            (mod.RUNTIME_DIR / "raw_user_input.md").write_text("test")
            p = parse_slash_command(f'/experiment "test" --mode {mode}')
            result = execute_command(p)
            if mode in ("analyze", "revise"):
                check(f"30. experiment {mode} mode", result["status"] == "blocked",
                      f"got status={result['status']} (expected blocked without results)")
            else:
                check(f"30. experiment {mode} mode", result["status"] == "execute_safe",
                      f"got status={result['status']}")

    # Test 31: runtime isolation — writes go to runtime/, not research/current/
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/research-intake "isolation test"')
            result = execute_command(p)
            # raw_user_input.md should be in runtime/, NOT in research/current/
            rt_raw = mod.RUNTIME_DIR / "raw_user_input.md"
            tracked_raw = mod.RESEARCH_DIR / "raw_user_input.md"
            check("31. runtime isolation", rt_raw.exists() and not tracked_raw.exists(),
                  f"runtime={rt_raw.exists()}, tracked={tracked_raw.exists()}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 32: legacy workflow_state.json fallback read
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        legacy_state = mod.LEGACY_WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        mod.LEGACY_WORKFLOW_STATE_FILE = mod.RESEARCH_DIR / "workflow_state.json"
        try:
            # Write to legacy path only
            mod.RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
            legacy_data = {"current_user_phase": "legacy_phase", "completed_user_phases": []}
            mod.LEGACY_WORKFLOW_STATE_FILE.write_text(json.dumps(legacy_data))
            state = load_workflow_state()
            check("32. legacy fallback read", state["current_user_phase"] == "legacy_phase",
                  f"got phase={state.get('current_user_phase')}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state
            mod.LEGACY_WORKFLOW_STATE_FILE = legacy_state

    # Test 33: idea-synthesis blocked without raw_user_input
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/idea-synthesis "test"')
            result = execute_command(p)
            check("33. idea-synthesis blocked without input", result["status"] == "blocked",
                  f"got status={result['status']}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 34: idea-audit blocked without raw_user_input
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            p = parse_slash_command('/idea-audit "test"')
            result = execute_command(p)
            check("34. idea-audit blocked without input", result["status"] == "blocked",
                  f"got status={result['status']}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 35: idea-audit blocked without evidence + synthesis
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        try:
            mod.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            (mod.RUNTIME_DIR / "raw_user_input.md").write_text("test")
            p = parse_slash_command('/idea-audit "test"')
            result = execute_command(p)
            check("35. idea-audit blocked without evidence+synthesis", result["status"] == "blocked",
                  f"got status={result['status']}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state

    # Test 36: idea-synthesis creates evidence-aware scaffold when metadata available
    with tempfile.TemporaryDirectory() as td:
        mod = _sys.modules[__name__]
        orig_dir = mod.RESEARCH_DIR
        orig_rt = mod.RUNTIME_DIR
        orig_state = mod.WORKFLOW_STATE_FILE
        orig_lit = mod.LITERATURE_SEARCH_DIR
        mod.RESEARCH_DIR = Path(td) / "research" / "current"
        mod.RUNTIME_DIR = mod.RESEARCH_DIR / "runtime"
        mod.WORKFLOW_STATE_FILE = mod.RUNTIME_DIR / "workflow_state.json"
        mod.LITERATURE_SEARCH_DIR = Path(td) / "literature" / "search_runs" / "current"
        try:
            mod.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            (mod.RUNTIME_DIR / "raw_user_input.md").write_text("test")
            # Create fake top_k.md
            mod.LITERATURE_SEARCH_DIR.mkdir(parents=True, exist_ok=True)
            (mod.LITERATURE_SEARCH_DIR / "top_k.md").write_text("## Paper 1\nTest paper")
            p = parse_slash_command('/idea-synthesis "test"')
            result = execute_command(p)
            check("36. idea-synthesis evidence-aware", result["status"] == "execute_safe",
                  f"got status={result['status']}")
            # Check scaffold references metadata
            scaffold = (mod.RUNTIME_DIR / "idea_synthesis_scaffold.md").read_text(encoding="utf-8")
            check("36b. scaffold references metadata", "evidence_aware" in scaffold,
                  f"scaffold snippet={scaffold[:200]}")
        finally:
            mod.RESEARCH_DIR = orig_dir
            mod.RUNTIME_DIR = orig_rt
            mod.WORKFLOW_STATE_FILE = orig_state
            mod.LITERATURE_SEARCH_DIR = orig_lit

    print(f"\nSelf-test results: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(description="Slash command adapter — Agent-facing parser and safe executor")
    parser.add_argument("command", nargs="?", help="Slash command to parse (e.g., /research-intake \"...\")")
    parser.add_argument("--self-test", action="store_true", help="Run self-tests")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--save-payload-dir", type=str, default=None, help="Directory to save payload files")
    parser.add_argument("--execute", action="store_true", help="Execute safe backend actions (no model calls)")

    args = parser.parse_args()

    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    parsed = parse_slash_command(args.command)
    plan = generate_plan(parsed)

    # Save payload if requested
    payload_file = None
    if args.save_payload_dir and parsed["valid"] and parsed["payload"]:
        payload_dir = Path(args.save_payload_dir)
        filepath = save_payload(parsed["command"], parsed["payload"], payload_dir)
        plan["payload_file"] = str(filepath)
        payload_file = str(filepath)

    # Execute if requested
    if args.execute and parsed["valid"]:
        result = execute_command(parsed, payload_file)
        plan["execution_result"] = result
        plan["dry_run"] = False

    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        if plan["status"] == "FAIL":
            print(f"ERROR: {plan.get('error', 'unknown error')}")
            print(f"Raw input: {plan.get('raw', '')}")
            sys.exit(1)

        print(f"=== Slash Command Plan ===")
        print(f"Command:    {plan['command']}")
        print(f"Payload:    {plan['payload']}")
        print(f"Maps to:    {plan['maps_to']}")
        print(f"Stages:     {' → '.join(plan['internal_stages'])}")
        if plan.get("note"):
            print(f"Note:       {plan['note']}")
        if plan.get("execution_mode"):
            print(f"Exec Mode:  {plan['execution_mode']}")
        if plan.get("cli_action"):
            cli = plan["cli_action"]
            args_str = " ".join(cli["args"]) if cli["args"] else ""
            print(f"CLI:        {cli['command']} {args_str}")
            print(f"  → {cli['description']}")
        if plan.get("payload_file"):
            print(f"Payload:    saved to {plan['payload_file']}")

        # Print execution results
        if plan.get("execution_result"):
            er = plan["execution_result"]
            print(f"\n=== Execution Result ===")
            print(f"Status:     {er.get('status', 'unknown')}")
            if er.get("files_created"):
                print(f"Files:")
                for f in er["files_created"]:
                    print(f"  - {f}")
            if er.get("blocked_reason"):
                print(f"Blocked:    {er['blocked_reason']}")
            if er.get("blocked_reasons"):
                print(f"Blocked:    {'; '.join(er['blocked_reasons'])}")
            if er.get("next_action"):
                print(f"Next:       {er['next_action']}")
            if er.get("note"):
                print(f"Note:       {er['note']}")
            print(f"Model called: {er.get('model_called', False)}")
            print(f"Trusted outputs changed: {er.get('trusted_outputs_changed', False)}")

        if plan.get("dry_run", True):
            print(f"\nDRY-RUN: No model calls, no trusted runner executed, no trusted_outputs changed. Payload files are only written when --save-payload-dir is provided.")
        else:
            print(f"\nSAFE EXECUTE: No model calls, no trusted runner executed, no trusted_outputs changed.")


if __name__ == "__main__":
    main()

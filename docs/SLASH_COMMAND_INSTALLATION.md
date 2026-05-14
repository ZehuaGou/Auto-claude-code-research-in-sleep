# Slash Command Installation

## Overview

This project provides 7 slash commands for Claude Code / Happy:

| Command | Description |
|---------|-------------|
| `/research-intake` | Input research direction and constraints |
| `/literature-intake` | Literature survey and domain understanding |
| `/idea-synthesis` | Generate candidate research ideas |
| `/idea-audit` | Verify idea novelty and lock research boundaries |
| `/experiment` | Plan and analyze experiments |
| `/paper-writing` | Plan paper writing based on verified results |
| `/status` | Show current research workflow status |

All commands support three modes:
- **Default (dry-run)**: Generates execution plan, saves payload. No files created.
- **`--execute`**: Creates scaffold files, updates workflow state. No model calls, no experiments, no trusted_outputs changes. Sets `phase_status = scaffold_created`.
- **`--execute --trusted`** (idea-synthesis, idea-audit only): Code path calls `trusted_role_runner` for real model-based synthesis/audit. Writes to `trusted_outputs/`. Reports `call_id`. Sets `phase_status = trusted_completed`. **Live model invocation requires explicit user action.**

**Phase status semantics:**
- `scaffold_created`: File created, no model called. Does NOT count as completed. Cannot advance to next phase.
- `safe_completed`: Safe execution completed (e.g., research-intake, experiment scaffold). Counts as completed.
- `metadata_completed`: Metadata search completed (literature-intake). Counts as completed.
- `trusted_completed`: Trusted model call completed. Counts as completed. Required for idea-synthesis, idea-audit.
- `blocked`: Phase blocked. Removed from completed phases.

## How It Works

1. **Templates** live in `templates/claude_commands/` (committed to git, safe to share).
2. **Install script** copies templates to `.claude/commands/` (local, gitignored).
3. **Slash commands** call `tools/slash_command_adapter.py` to parse input, generate plans, and optionally execute safe backend actions.
4. **Payloads** are saved to `research/current/user_command_payloads/` (gitignored).
5. **Workflow state** is tracked in `research/current/workflow_state.json` (gitignored).
6. **Python scripts** are Agent-facing backend — users only interact via slash commands.

All commands are **safe**: no model calls, no trusted runner execution, no trusted_outputs changes. When `--execute` is used, scaffold files are created as placeholders for future model-driven stages.

## Installation

```bash
python tools/install_slash_commands.py
```

This copies `templates/claude_commands/*.md` to `.claude/commands/`.

To overwrite existing commands:
```bash
python tools/install_slash_commands.py --force
```

## After Installation

Restart your Claude Code / Happy session, then use:

```
/research-intake "Chain-of-Thought prompting for mathematical reasoning"
/literature-intake "重点查 diffusion-based reasoning"
/idea-synthesis "不要只想单点创新" --num-candidates 8
/idea-audit "重点检查 CoT for math"
/experiment "先做轻量实验" --mode lightweight
/paper-writing "按保守论文风格写"
/status
```

To execute safe backend actions (create scaffold files):
```
/research-intake "my idea" --execute
```

## Architecture

```
templates/claude_commands/*.md    (committed — safe templates)
        |
        v  [install_slash_commands.py]
        |
.claude/commands/*.md             (local — gitignored)
        |
        v  [Claude/Happy slash command]
        |
tools/slash_command_adapter.py    (Agent-facing backend — parser + executor)
        |
        v  [--execute creates scaffolds, --trusted calls trusted_role_runner]
        |
research/current/runtime/         (local — gitignored, all runtime outputs)
  ├── raw_user_input.md           (created by /research-intake --execute)
  ├── input_normalization_scaffold.md
  ├── literature_intake_scaffold.md
  ├── idea_synthesis_scaffold.md  (evidence-aware, references literature metadata)
  ├── idea_audit_scaffold.md      (evidence-aware, checks for synthesis + evidence)
  ├── experiment_scaffold_*.md    (mode-specific: lightweight/full/analyze/revise)
  ├── paper_writing_scaffold.md   (blocked unless results + claim boundary)
  └── workflow_state.json         (tracks user phase + phase_status)

research/current/trusted_outputs/ (committed — trusted model outputs)
  ├── idea_synthesis.md           (created by /idea-synthesis --execute --trusted)
  └── idea_audit.md               (created by /idea-audit --execute --trusted)

tmp/slash_lit_search/             (local — gitignored, literature metadata search output)
  ├── search_plan.yaml
  ├── raw_results.jsonl
  ├── candidates.jsonl
  ├── top_k.md
  └── summary.json

research/current/user_command_payloads/  (local — gitignored, command payloads)
```

**Important:** `research/current/*.md` files (raw_user_input.md, input_normalization.md, etc.) are committed regression/test fixtures. Slash command runtime outputs go to `research/current/runtime/` and never overwrite tracked files.

## Workflow State

`research/current/runtime/workflow_state.json` tracks:
- `current_user_phase`: Which phase the user is in
- `completed_user_phases`: List of completed phases
- `latest_command`: Last command executed
- `latest_payload_file`: Path to latest payload
- `next_allowed_commands`: Which commands can run next
- `system_health`: healthy/degraded
- `case_status`: not_started/active/blocked
- `model_calls_made`: false (always — no models called)
- `trusted_outputs_changed`: false (always — no trusted outputs changed)

## Important Notes

- `.claude/` is in `.gitignore` — never committed.
- `research/current/runtime/` is in `.gitignore` — all runtime outputs go here.
- Templates in `templates/claude_commands/` are the source of truth.
- All commands are safe: no model calls, no experiments, no trusted_outputs changes.
- Python scripts (`tools/slash_command_adapter.py`, `tools/research_cli.py`) are Agent-facing backend.
- Scaffold files are placeholders — they do not contain model conclusions.
- `--execute` creates files in `runtime/`; default mode only shows plan.
- Committed `research/current/*.md` files are regression/test fixtures — never overwritten by slash commands.

## Troubleshooting

**Commands don't appear after install:**
- Restart your Claude Code / Happy session.
- Verify files exist: `ls .claude/commands/`

**Command gives "unknown command" error:**
- Run `python tools/install_slash_commands.py --force` to reinstall.
- Check that `templates/claude_commands/` contains the expected `.md` files.

**Want to customize a command:**
- Edit the file in `.claude/commands/` directly.
- Or edit the template in `templates/claude_commands/` and reinstall with `--force`.

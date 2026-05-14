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

All commands are **plan-only** (DRY-RUN). They generate execution plans but do NOT call models, run experiments, or change trusted_outputs.

## How It Works

1. **Templates** live in `templates/claude_commands/` (committed to git, safe to share).
2. **Install script** copies templates to `.claude/commands/` (local, gitignored).
3. **Slash commands** call `tools/slash_command_adapter.py` to parse input and generate plans.
4. **Python scripts** are Agent-facing backend — users only interact via slash commands.

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
tools/slash_command_adapter.py    (Agent-facing backend — parser + plan generator)
        |
        v  [plan output — dry-run only]
        |
tools/research_cli.py             (CLI execution layer — not called by slash commands)
```

## Important Notes

- `.claude/` is in `.gitignore` — never committed.
- Templates in `templates/claude_commands/` are the source of truth.
- All commands are plan-only: no model calls, no experiments, no trusted_outputs changes.
- Python scripts (`tools/slash_command_adapter.py`, `tools/research_cli.py`) are Agent-facing backend.
- Live execution requires running `tools/research_cli.py` directly (not via slash commands).

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

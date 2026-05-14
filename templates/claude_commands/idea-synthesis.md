---
description: Generate candidate research ideas
argument-hint: "idea generation focus or constraints"
---

Plan idea synthesis for the given direction.

User arguments:
`$ARGUMENTS`

Requirements:
- Treat this slash command as `/idea-synthesis $ARGUMENTS`.
- Default: run `python tools/slash_command_adapter.py '/idea-synthesis $ARGUMENTS' --save-payload-dir research/current/user_command_payloads` (dry-run, plan only).
- If user says "execute" or "run it": add `--execute` flag to create scaffold files (no model calls).
- Display the output to the user.
- This command NEVER calls models, runs experiments, or changes trusted_outputs.
- Supports `--num-candidates N` flag (default: 5).
- Supports gap-driven, transfer innovation, and contribution chain modes (in scaffold).

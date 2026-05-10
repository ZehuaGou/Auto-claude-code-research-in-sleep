# ARIS Agent Guide

> **For AI agents reading this repo.** If you are a human, see [README.md](README.md).

ARIS is a research harness: composable Markdown skills that orchestrate the ML research lifecycle through cross-model adversarial collaboration.

## How to Invoke Skills

**Claude Code / Cursor / Trae:**
```
/skill-name "arguments" — key: value, key2: value2
```

**Codex CLI:**
```
/skill-name "arguments" — key: value
```
Codex skills are in `skills/skills-codex/`.

## Common Parameters

Every skill accepts:
```
— effort: lite | balanced | max | beast      # work intensity (default: balanced)
— human checkpoint: true | false             # pause for approval (default: false)
— AUTO_PROCEED: true | false                 # auto-continue at gates (default: true)
```

Workflow-specific:
```
— difficulty: medium | hard | nightmare      # reviewer adversarial level
— venue: ICLR | NeurIPS | ICML | ...        # target venue
— sources: web, zotero, deepxiv, ...        # literature sources
— gpu: local | remote | vast | modal         # GPU backend
```

Parameters pass through workflow chains automatically.

## Usage Modes

ARIS supports two usage modes for research idea discovery:

**Mode A (Recommended): Single-command mode**
```
/idea-discovery "research direction"
```
System auto-executes Phase 1-6 internally. Each gate auto-records Codex thread, artifact header, and ledger.

**Mode B (Supported): Manual staged mode**
```
/research-lit "direction"
/idea-creator "direction"
/exec-review CAND_001
/novelty-check CAND_001
```
Each sub-skill still auto-executes its own gate, isolation evidence, and ledger.
User does NOT need to manually specify allowed_input_files or forbidden_context.

Both modes share the same reliability gates. Mode B is for debugging, incremental work, and ad hoc exploration.

## Workflow Index

### Full Pipeline
```
/research-pipeline "direction" → W1 → W1.5 → W2 → W3
```

### Individual Workflows

| Workflow | Invoke | Input | Output | When to use |
|----------|--------|-------|--------|-------------|
| W1: Idea Discovery | `/idea-discovery "direction"` | research direction | IDEA_SELECTION_REPORT.md, IDEA_BANK, CANONICAL_IDEAS | Starting new research (recommended single-command mode: lit → ideas → review → novelty → adversarial → selection). Manual staged mode also supported via individual sub-skills. |
| Idea Bank Management | `/idea-bank status` | status/dedup/candidate | IDEA_BANK summary | Inspect and manage idea candidates across runs |
| W1.5: Experiment Bridge | `/experiment-bridge` | EXPERIMENT_PLAN.md | running code, EXPERIMENT_LOG.md | Have a plan, need to implement |
| W2: Auto Review | `/auto-review-loop "scope"` | paper + results | improved paper | Iterative improvement |
| W3: Paper Writing | `/paper-writing "NARRATIVE_REPORT.md"` | narrative report | paper/main.pdf | Ready to write |
| W4: Rebuttal | `/rebuttal "paper/ + reviews"` | paper + reviews | PASTE_READY.txt | Reviews received |

### Standalone Skills

| Skill | Invoke | What it does |
|-------|--------|-------------|
| `/alphaxiv "arxiv-id"` | Paper lookup | LLM-optimized summary with tiered fallback |
| `/research-lit "topic"` | Literature survey | Finds papers, builds landscape |
| `/idea-creator "direction"` | Idea generation | Brainstorms and ranks ideas |
| `/idea-bank status` | Idea bank management | Inspect, dedup, and manage canonical candidates across runs |
| `/novelty-check "idea"` | Novelty verification | Checks against existing work |
| `/research-review "draft"` | External review | GPT-5.4 xhigh deep critique |
| `/experiment-audit` | Integrity check | Cross-model audit of eval code |
| `/result-to-claim` | Verdict judgment | Codex judges if claims are supported |
| `/paper-claim-audit "paper/"` | Numerical claim audit | Zero-context fresh reviewer cross-checks paper numbers vs raw evidence |
| `/citation-audit "paper/"` | Bibliography audit | Cross-family reviewer verifies existence + metadata + context for every \cite |
| `/overleaf-sync setup\|pull\|push\|status` | Overleaf bridge | Two-way sync via Overleaf Git bridge; token stays in OS keychain, never in chat |
| `/paper-plan "topic"` | Outline creation | Structured outline + claims matrix |
| `/paper-figure "plan"` | Figure generation | Plots from experiment data |
| `/paper-write "plan"` | LaTeX drafting | Section-by-section with citation check |
| `/paper-compile "paper/"` | PDF compilation | Multi-pass with auto-repair |
| `/research-wiki init` | Knowledge base | Persistent project memory |
| `/meta-optimize` | Self-improvement | Analyze usage, propose skill edits |
| `/analyze-results` | Result analysis | Statistics and comparison tables |
| `/ablation-planner` | Ablation design | Reviewer-perspective ablations |
| `/config-check` | Configuration check | ARIS .env, Codex, Feishu configuration check |
| `/model-usage-status` | Model usage | Recent Codex/LLM calls, fallbacks, failures |
| `/status` | Project status | Unified pipeline/session/experiment/reviewer status |
| `/paper-ingest "arxiv-id"` | Paper ingestion | Convert papers to structured Markdown sections |
| `/research-contract "idea"` | Research contract | Freeze hypothesis, signals, metrics before experiments |
| `/baseline-repro "repo"` | Baseline reproduction | Establish and verify baseline anchor |
| `/research-assurance` | Assurance check | Verify contract, baseline, audit, claims before paper |
| `/exec-review "file"` | One-shot review | Independent review of idea/contract/result |
| `/panel-review "topic"` | Panel review | Multi-round reviewer session for complex debates |
| `/session-orchestrator` | Session management | Multi-session research workflow with handoffs |
| `/session-handoff "task"` | Session handoff | Write structured handoff between sessions |

## Internal Tools

Some helper tools exist under `tools/` for scaffolding, ledger, status,
output validation, and contributor testing. Normal users should invoke
slash skills, not Python scripts. Only contributors/debuggers should
call these tools directly.

## Artifact Contracts

Skills communicate through plain-text files:

| Artifact | Created by | Consumed by |
|----------|-----------|-------------|
| `idea-stage/AGENTIC/FINAL_SELECTION/IDEA_SELECTION_REPORT.md` | idea-discovery | research-contract / experiment-bridge only after explicit user request |
| `EXPERIMENT_PLAN.md` | experiment-plan | experiment-bridge |
| `EXPERIMENT_LOG.md` | experiment-bridge | auto-review-loop, result-to-claim |
| `NARRATIVE_REPORT.md` | auto-review-loop | paper-writing |
| `paper/main.tex` | paper-write | paper-compile |
| `paper/main.pdf` | paper-compile | auto-paper-improvement-loop |
| `EXPERIMENT_AUDIT.md` | experiment-audit | result-to-claim |
| `EXPERIMENT_AUDIT.json` | experiment-audit | result-to-claim (machine-readable) |
| `PAPER_CLAIM_AUDIT.md/.json` | paper-claim-audit | paper-writing Phase 5.5 gate |
| `CITATION_AUDIT.md/.json` | citation-audit | paper-writing Phase 5.8 submission gate |
| `research-wiki/` | research-wiki | idea-creator, research-lit, result-to-claim |
| `.aris/meta/events.jsonl` | hooks (passive) | meta-optimize |
| `docs/research_contract.md` | research-contract | experiment-bridge, result-to-claim, research-assurance |
| `docs/research_contract.lock.json` | research-contract | experiment-bridge |
| `research/BASELINE.md` | baseline-repro | experiment-bridge, research-assurance |
| `research/BASELINE_REPRODUCTION_REPORT.md` | baseline-repro | experiment-bridge, research-assurance |
| `literature-md/<paper_id>/` | paper-ingest | novelty-check, baseline-repro, paper-writing |
| `.aris/sessions/SESSION_REGISTRY.json` | session-orchestrator | status |
| `.aris/sessions/ACTIVE_TASKS.json` | session-orchestrator | status |
| `.aris/sessions/HANDOFFS/` | session-handoff | session-orchestrator |
| `.aris/calls/llm_calls.jsonl` | llm_call_ledger | model-usage-status, status |
| `.aris/calls/current_call.json` | llm_call_ledger | model-usage-status, status |
| `research/CLAIM_EVIDENCE_TABLE.md` | research-assurance, result-to-claim | paper-writing |
| `research/ASSURANCE_REPORT.md` | research-assurance | paper-writing, submission |
| `idea-stage/AGENTIC/RUNS/<run_id>/` | research-lit / idea-discovery | idea-creator |
| `idea-stage/AGENTIC/IDEA_BANK.md` | idea-creator / idea-discovery | exec-review, novelty-check, idea-bank |
| `idea-stage/AGENTIC/IDEA_BANK.json` | idea-creator / idea-discovery | idea-bank (machine-readable) |
| `idea-stage/AGENTIC/CANONICAL_IDEAS/` | idea-creator / idea-discovery | exec-review, novelty-check |
| `idea-stage/AGENTIC/FINAL_SELECTION/IDEA_SELECTION_REPORT.md` | idea-discovery | research-contract, experiment-bridge (user-driven) |

## Cross-Model Protocol

- **Executor** (Claude/Codex): writes code, runs experiments, drafts papers
- **Reviewer** (GPT-5.4/Gemini/GLM): critiques, scores, demands revisions
- **Rule**: executor and reviewer must be different model families
- **Reviewer independence**: pass file paths only, never summaries or interpretations
- **Experiment integrity**: executor must NOT judge its own eval code — reviewer audits directly

## Shared References

Read these before invoking review-related skills:
- `skills/shared-references/reviewer-independence.md` — cross-model review protocol
- `skills/shared-references/experiment-integrity.md` — prohibited fraud patterns
- `skills/shared-references/effort-contract.md` — effort level specifications
- `skills/shared-references/citation-discipline.md` — citation rules
- `skills/shared-references/writing-principles.md` — writing standards
- `skills/shared-references/venue-checklists.md` — venue formatting
- `skills/shared-references/env-config-policy.md` — .env reading rules, variable conventions
- `skills/shared-references/model-routing.md` — role-based model routing definitions
- `skills/shared-references/transport-routing.md` — MCP/exec-review/panel-review suitability
- `skills/shared-references/research-contract.md` — contract protocol for skills
- `skills/shared-references/paper-ingest-protocol.md` — paper ingestion protocol and staged reading
- `skills/shared-references/session-protocol.md` — session management protocol

## Research Wiki (Optional)

If `research-wiki/` exists in the project:
- `/research-lit` auto-ingests discovered papers
- `/idea-creator` reads wiki before ideation, writes ideas back after
- `/result-to-claim` updates claim status
- Failed ideas become anti-repetition memory

Initialize with `/research-wiki init`.

## Effort Levels

| Level | Tokens | What changes |
|-------|:------:|-------------|
| `lite` | 0.4x | Fewer papers, ideas, rounds |
| `balanced` | 1x | Current default behavior |
| `max` | 2.5x | More papers, deeper review |
| `beast` | 5-8x | Every knob to maximum |

Codex reasoning is **always xhigh** regardless of effort.

## Source of Truth

- Each skill's behavior: read its `skills/<name>/SKILL.md`
- System-wide rules: read `skills/shared-references/*.md`
- This guide is a routing index, not the specification

## User Documentation

- `docs/RESEARCH_RELIABILITY_ENHANCEMENT_GUIDE_CN.md` — 中文完整使用与贡献指南（面向用户和贡献者，涵盖所有新增 skill/tool/artifact 的详细用法）

# ARIS Model Routing Overview

> All ARIS internal model routing is controlled through `.env` and resolved via
> `tools/model_route.py`. **Never edit a SKILL.md file to switch models.**
> External agents (Claude Code, Cursor, Trae, Codex CLI) are users/operators,
> not ARIS internal roles — they are NOT part of this routing table.

## Routing Architecture

```
User/Agent
  └─ slash command → skill → python tools/model_route.py <role> → JSON routing decision
                                    │
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
              codex_required                  deepseek_only
              codex_preferred                 / generation roles
                    ↓                               ↓
              mcp__codex__codex              mcp__llm-chat__chat
                    ↓
              (fallback to LLM if codex_preferred and Codex unavailable)
```

## Per-Role Routing

| Stage | Role | Purpose | Default Env Var | Current Default | Recommended Model | Cost | Critical Gate? | Codex Fallback? | Notes |
|-------|------|---------|----------------|-----------------|-------------------|------|----------------|-----------------|-------|
| Literature | literature_scout | Web/DB literature search | `LLM_LITERATURE_SCOUT_MODEL` | deepseek-v4-flash | deepseek-v4-flash | Low | No | N/A | Lightweight; flash is sufficient |
| Literature | paper_summarizer | Paper summary after ingest | `LLM_PAPER_SUMMARIZER_MODEL` | deepseek-v4-flash | deepseek-v4-flash | Low | No | N/A | Lightweight |
| Literature | gap_extractor | Extract research gaps | `LLM_GAP_EXTRACTOR_MODEL` | deepseek-v4-pro | deepseek-v4-pro | Medium | No | N/A | Needs synthesis |
| Literature | evidence_integrity_auditor | Audit lit survey integrity | `LLM_EVIDENCE_AUDITOR_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Codex preferred for cross-model independence |
| Idea | idea_generator | Brainstorm ideas from literature | `LLM_IDEA_GENERATOR_MODEL` | deepseek-v4-pro | deepseek-v4-pro | High | No | N/A | Heavy generation task |
| Idea | idea_deduplicator | Deduplicate idea bank | `LLM_IDEA_DEDUPLICATOR_MODEL` | deepseek-v4-pro | deepseek-v4-pro | Medium | No | N/A | Classification |
| Idea | idea_shortlist_auditor | Kill weak ideas before review | `LLM_IDEA_SHORTLIST_AUDITOR_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Codex preferred |
| Review | idea_reviewer | Executive review of candidate | `LLM_IDEA_REVIEWER_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Review | novelty_checker | Check prior art overlap | `LLM_NOVELTY_CHECKER_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Review | adversarial_reviewer | Adversarial stress-test | `LLM_ADVERSARIAL_REVIEWER_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Selection | final_selector | Final candidate selection | `LLM_FINAL_SELECTOR_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Contract | contract_reviewer | Contract completeness check | `LLM_CONTRACT_REVIEWER_PRIMARY` | codex | codex | Medium | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Experiment | experiment_implementer | Convert plan to runnable code | `LLM_EXPERIMENT_IMPLEMENTER_MODEL` | deepseek-v4-pro | deepseek-v4-pro | High | No | N/A | Complex ML implementation needs capable model |
| Experiment | experiment_code_reviewer | Review experiment code | `LLM_EXPERIMENT_CODE_REVIEWER_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Experiment | experiment_auditor | Audit experiment integrity | `LLM_EXPERIMENT_AUDITOR_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Result | result_judge | Judge claims vs evidence | `LLM_RESULT_JUDGE_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Paper | paper_writer | Draft paper sections | `LLM_PAPER_WRITER_MODEL` | deepseek-v4-pro | deepseek-v4-pro | High | No | N/A | Generation |
| Paper | claims_drafter | Draft claims from evidence | `LLM_CLAIMS_DRAFTER_MODEL` | deepseek-v4-pro | deepseek-v4-pro | Medium | No | N/A | Generation |
| Paper | paper_claim_auditor | Audit paper claims | `LLM_PAPER_CLAIM_AUDITOR_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Paper | final_paper_auditor | Final paper integrity check | `LLM_FINAL_AUDITOR_PRIMARY` | codex | codex | High | **Yes** | Yes (deepseek-v4-pro) | Cross-model independence required |
| Logs | log_summarizer | Summarize experiment logs | `LLM_LOG_SUMMARIZER_MODEL` | deepseek-v4-flash | deepseek-v4-flash | Low | No | N/A | Lightweight |
| Baseline | baseline_reviewer | Review baseline reproduction | `LLM_BASELINE_REVIEWER_MODEL` | deepseek-v4-pro | deepseek-v4-pro | Medium | No | N/A | Verification |

## Global Gate Routing

`ARIS_CODEX_GATE_MODE` controls ALL critical gates unless a per-role override exists:

| Mode | Behavior | When to Use |
|------|----------|------------|
| `codex_required` | Codex must be available; fail if not | Strict cross-model independence needed |
| `codex_preferred` | Try Codex first; fallback with warning | Balanced approach (default) |
| `deepseek_only` | Skip Codex; use LLM directly | No OpenAI API key available |

## Key Configuration

```bash
# Which Codex gate mode (global default)
ARIS_CODEX_GATE_MODE=codex_preferred

# Fallback model when Codex is unavailable
ARIS_CODEX_FALLBACK_MODEL=deepseek-v4-pro

# Per-role override (overrides global mode for specific role)
LLM_EXPERIMENT_CODE_REVIEWER_PRIMARY=codex

# Generation role model (always LLM, never Codex)
LLM_EXPERIMENT_IMPLEMENTER_MODEL=deepseek-v4-pro
LLM_PAPER_WRITER_MODEL=deepseek-v4-pro
```

## Switching Models

1. **Do NOT edit SKILL.md files** to change models.
2. Edit `.env` or set environment variables.
3. Run `python tools/model_route.py <role>` to verify.
4. The resolved route is recorded in artifact headers and the LLM call ledger.

## Fallback Rules

| Scenario | Behavior | Ledger Entry |
|----------|----------|-------------|
| Codex unavailable, mode=codex_required | FAIL — do NOT proceed | `status: failed` |
| Codex unavailable, mode=codex_preferred | Fallback to LLM, WARNING | `fallback_used: true, status: completed_with_fallback` |
| Codex unavailable, mode=deepseek_only | Use LLM directly (expected) | `codex_used: false, status: completed` |
| CODE_REVIEW=false | Skip code review, WARNING | N/A (no review call made) |

## File Locations

- **Env config**: `.env` (user-local, never committed) / `.env.example` (template, committed)
- **Route resolver**: `tools/model_route.py`
- **Call ledger**: `.aris/calls/llm_calls.jsonl` + `.aris/calls/current_call.json`
- **Skill files**: `skills/<name>/SKILL.md` (never hardcode models here)

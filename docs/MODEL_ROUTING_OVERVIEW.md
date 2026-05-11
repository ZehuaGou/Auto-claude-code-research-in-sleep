# ARIS Model Routing Overview

> All ARIS internal model routing is controlled through `.env` and resolved via
> `tools/model_route.py` and `tools/env_loader.py`. **Never edit a SKILL.md file to switch models.**

## Quick Start

1. Copy `.env.example` → `.env`
2. Fill in your API keys (DeepSeek, Kimi, MiniMax, OpenAI)
3. Assign models to roles via `ROLE_<ROLE>=<ALIAS>`
4. Done — slash commands (`/idea-discovery`, `/paper-writing`, etc.) work unchanged

## Architecture

```
User → slash command → skill → tools/model_route.py → routing decision
                                                    ↓
                         ┌─────────────────────────┴───────────────┐
                         ↓                                         ↓
               Codex MCP (backend_type=mcp)          API (backend_type=openai_compatible_api)
               · No API key needed                   · DeepSeek / Kimi / MiniMax / OpenAI
               · Auth via Claude Code app            · Requires <PROVIDER>_API_KEY
               · Set via CODEX_DEFAULT_MODEL        · Set via MODEL_<ALIAS>=<provider>:<model>
```

## Configuration Sections

### 1. Backend Configuration (API providers)

```bash
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com

KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1

MINIMAX_API_KEY=
MINIMAX_BASE_URL=https://api.minimax.io/v1

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
```

**Codex MCP** does NOT use an API key. Codex auth is handled by the Claude Code app.

### 2. Codex MCP Configuration

```bash
CODEX_ENABLED=true
CODEX_MCP_SERVER=codex
CODEX_DEFAULT_MODEL=auto   # Use Codex's default. Change to gpt-5.5 when available.
```

- `CODEX_DEFAULT_MODEL=auto` — uses whatever model Codex MCP resolves to by default
- When Codex supports GPT-5.5, change to `CODEX_DEFAULT_MODEL=gpt-5.5`
- **Do NOT confuse Codex with OpenAI API** — they are different backends

### 3. Model Aliases

```bash
MODEL_DS_FLASH=deepseek:deepseek-v4-flash
MODEL_DS_PRO_HIGH=deepseek:deepseek-v4-pro
MODEL_DS_PRO_MAX=deepseek:deepseek-v4-pro
MODEL_CODEX=codex:${CODEX_DEFAULT_MODEL}
MODEL_KIMI_LONG=kimi:moonshot-v1-32k
MODEL_MINIMAX=minimax:MiniMax-M2.7
```

Syntax: `MODEL_<ALIAS>=<provider>:<model>`

### 4. Model Parameters (per alias)

```bash
MODEL_DS_FLASH_THINKING=disabled
MODEL_DS_FLASH_EFFORT=low

MODEL_DS_PRO_HIGH_THINKING=enabled
MODEL_DS_PRO_HIGH_EFFORT=high

MODEL_DS_PRO_MAX_THINKING=enabled
MODEL_DS_PRO_MAX_EFFORT=max
```

- `_THINKING`: `enabled` | `disabled`
- `_EFFORT`: `low` | `medium` | `high` | `max`
- Codex effort is `xhigh` by default (use `MODEL_CODEX_EFFORT` to override)

### 5. Role Assignments

```bash
ROLE_IDEA_REVIEWER=CODEX
ROLE_NOVELTY_CHECKER=CODEX
ROLE_ADVERSARIAL_REVIEWER=CODEX
ROLE_FINAL_SELECTOR=CODEX
ROLE_EXPERIMENT_CODE_REVIEWER=CODEX
ROLE_EXPERIMENT_AUDITOR=CODEX
ROLE_RESULT_JUDGE=CODEX
ROLE_CONTRACT_REVIEWER=CODEX
ROLE_FINAL_AUDITOR=CODEX

ROLE_EXPERIMENT_IMPLEMENTER=DS_PRO_HIGH
ROLE_IDEA_GENERATOR=DS_PRO_HIGH
ROLE_GAP_EXTRACTOR=DS_PRO_HIGH
ROLE_PAPER_WRITER=DS_PRO_HIGH
ROLE_CLAIMS_DRAFTER=DS_PRO_HIGH

ROLE_LITERATURE_SCOUT=DS_FLASH
ROLE_PAPER_SUMMARIZER=DS_FLASH
ROLE_LOG_SUMMARIZER=DS_FLASH
ROLE_IDEA_DEDUPLICATOR=DS_PRO_HIGH
ROLE_BASELINE_REVIEWER=DS_PRO_HIGH
```

All available roles:
- `literature_scout`, `paper_summarizer`, `gap_extractor`
- `idea_generator`, `idea_deduplicator`
- `idea_reviewer`, `novelty_checker`, `adversarial_reviewer`
- `final_selector`, `contract_reviewer`
- `experiment_implementer`, `experiment_code_reviewer`, `experiment_auditor`
- `result_judge`
- `paper_writer`, `claims_drafter`, `final_auditor`
- `log_summarizer`, `baseline_reviewer`

### Role Assignment Table

| Stage | Role | Purpose | Default Backend |
|-------|------|---------|-----------------|
| Discovery | literature_scout | Find relevant papers | DS_FLASH |
| Discovery | paper_summarizer | Summarize paper content | DS_FLASH |
| Discovery | gap_extractor | Extract research gaps | DS_PRO_HIGH |
| Discovery | idea_generator | Generate research ideas | DS_PRO_HIGH |
| Discovery | idea_deduplicator | Deduplicate and canonicalize ideas | DS_PRO_HIGH |
| Discovery | idea_reviewer | Review idea quality and feasibility | CODEX |
| Discovery | novelty_checker | Check novelty of ideas | CODEX |
| Discovery | adversarial_reviewer | Adversarial critique of ideas | CODEX |
| Discovery | final_selector | Select final candidate | CODEX |
| Contract | contract_reviewer | Review research contract | CODEX |
| Baseline | baseline_reviewer | Verify baseline reproduction | DS_PRO_HIGH |
| Experiment | experiment_implementer | Implement experiments | DS_PRO_HIGH |
| Experiment | experiment_code_reviewer | Review experiment code | CODEX |
| Experiment | experiment_auditor | Audit experiment design | CODEX |
| Experiment | result_judge | Judge experimental results | CODEX |
| Writing | paper_writer | Write research paper | DS_PRO_HIGH |
| Writing | claims_drafter | Draft claims and contributions | DS_PRO_HIGH |
| Writing | final_paper_auditor | Final paper quality audit | CODEX |
| Writing | paper_claim_auditor | Audit paper claims | CODEX |
| Meta | evidence_integrity_auditor | Audit literature evidence integrity | CODEX |
| Meta | idea_shortlist_auditor | Audit idea shortlist quality | CODEX |
| Meta | log_summarizer | Summarize experimental logs | DS_FLASH |

## Switching Models Per-Role

To change a role's model, just update its `ROLE_<ROLE>` value:

```bash
# Switch novelty check from Codex to DeepSeek Max
ROLE_NOVELTY_CHECKER=DS_PRO_MAX
```

## Backend Types

| Backend | Type | Auth | Config |
|---------|------|------|--------|
| Codex | `mcp` | No API key needed | `CODEX_ENABLED`, `CODEX_MCP_SERVER`, `CODEX_DEFAULT_MODEL` |
| DeepSeek | `openai_compatible_api` | `DEEPSEEK_API_KEY` | `MODEL_DS_*` aliases |
| Kimi | `openai_compatible_api` | `KIMI_API_KEY` | `MODEL_KIMI_*` aliases |
| MiniMax | `openai_compatible_api` | `MINIMAX_API_KEY` | `MODEL_MINIMAX` alias |
| OpenAI | `openai_compatible_api` | `OPENAI_API_KEY` | `MODEL_OPENAI_*` aliases |

## Effort Levels

For **DeepSeek** models:
- `low` — fast, low cost
- `medium` — balanced
- `high` — strong reasoning (default for Pro High)
- `max` — maximum reasoning (default for Pro Max)

For **Codex MCP**:
- `xhigh` — highest reasoning effort (default)
- Set via `MODEL_CODEX_EFFORT=xhigh`

## Trusted Invocation — Declaration vs Actual Call

`model_route.py` is a **pure configuration resolver**. It only declares *which backend a role should use* — it does **not** make any real model calls.

**The actual model invocation must go through `tools/trusted_role_runner.py`** — the single trusted entry point for all ROLE_* tasks. This runner calls the backend via `tools/model_backends/`, records to the ledger, and produces verified artifacts with provenance headers.

This means `ROLE_*` changes in `.env` are enough to switch between Codex and
DeepSeek/API routes. Skill documents should keep calling
`trusted_role_runner.py`; they do not need to modify skill text when
`ROLE_* = CODEX` changes to `ROLE_* = DS_PRO_HIGH` or vice versa.

### Two Execution Sources

| Source | Meaning | Trust |
|--------|---------|-------|
| `routed_internal_model` | Code/output produced by a **real internal model call** recorded in the ledger | ✅ Verified |
| `external_agent_direct` | Code written directly by an external agent without any internal model invocation | ⚠️ Unverified |

### What `model_route.py` Cannot Do

- It cannot verify a model was actually called
- It cannot generate a `codex_thread_id` (only Codex MCP can)
- It cannot write to the ledger — that is the caller's responsibility
- It cannot invent a fallback backend when the runtime contract is ambiguous

### Ledger Entry Requirements

When a real model call is made, the ledger entry (`.aris/calls/llm_calls.jsonl`) must contain:

```json
{
  "implementation_source": "routed_internal_model",
  "routed_model_used": true,
  "actual_backend": "codex",
  "actual_model": "auto",
  "codex_thread_id": "thread_abc123",
  "verification_status": "verified_routed_call",
  "allowed_next_stage": true,
  "confidence_downgraded": false
}
```

Trusted role artifacts must also carry context isolation metadata:

```text
isolation_mode
task_id
context_manifest
allowed_input_files
forbidden_context
forbidden_context_checked
context_hash
prompt_file
response_file
source_boundary
contamination_scan_status
```

For Codex calls, `codex_thread_id` is **required** for verification. Without it, the entry is marked `codex_missing_thread_id`.
`codex_thread_id` must come from real Codex tool/session metadata, never from
commit hashes, plain terminal output, or human-written placeholders.

### No Masquerading

It is a violation to claim `implementation_source=routed_internal_model` when the code was produced by `external_agent_direct`. The ledger is the source of truth.

### No Silent Fallback

When a fallback occurs, it must always be recorded in the ledger with `fallback_used: true` and an explicit `fallback_reason`. A silent fallback — where the system falls back to a different backend without recording it — violates trust requirements.

`verified_with_fallback` does not automatically allow the next stage. The safe
default is `allowed_next_stage=false`, and the runner must exit non-zero unless
fallback next-stage use is explicitly enabled.

### Runtime Safety

`tools/trusted_role_runner.py` must fail closed when the runtime cannot execute
the declared backend:

- Codex MCP without an explicit Python adapter → `unsupported_runtime_backend`
- API backend missing key / `base_url` / model → `call_failed`
- Codex result without real `codex_thread_id` metadata → `codex_missing_thread_id`

These are verification failures, not soft warnings.

### External Codex MCP Handoff

The outer Agent environment can call `mcp__codex__codex` directly. A normal
Python script cannot directly call that outer-Agent MCP tool, so Codex routes
support a two-step bridge:

1. `--prepare-external-mcp`
2. outer Agent performs the real `mcp__codex__codex` call
3. `--complete-external-mcp`

Example:

```bash
python tools/trusted_role_runner.py \
  --role novelty_checker \
  --input review_context.md \
  --output review_output.md \
  --prepare-external-mcp \
  --require-codex-thread

python tools/trusted_role_runner.py \
  --complete-external-mcp \
  --call-id <call_id> \
  --codex-thread-id <real_codex_thread_id> \
  --response-file <saved_codex_response.md> \
  --output review_output.md
```

`prepare-external-mcp` creates a pending ledger entry and must keep
`allowed_next_stage=false`. Only `complete-external-mcp` with a real
`codex_thread_id` and non-empty response artifact may produce
`verified_routed_call`.

DeepSeek/OpenAI-compatible API roles do **not** use Codex handoff. They execute
directly via `tools/model_backends/openai_compatible.py` and do not require
`codex_thread_id`.

`prepare-external-mcp` is a successful handoff preparation state. It must return
`status=NEEDS_EXTERNAL_MCP_CALL`, `verification_status=pending_external_mcp`,
`allowed_next_stage=false`, and exit `0` so the outer Agent can continue into
the real MCP call before `complete-external-mcp`.

### Context Isolation Trust

The outer Agent may orchestrate files and prompts, but it must not inject
contaminating context into a trusted role prompt. Forbidden context includes:

- 当前聊天记录
- 旧结论
- 其他候选
- 用户偏好
- 历史 praise
- raw brainstorm trace
- 旧 review positive conclusion
- 未验证实验结果
- `external_agent_direct` output
- mock/dry-run artifact

Every `ROLE_*` stage must only see explicitly allowed inputs. `ROLE_*` switching
between Codex and DeepSeek/API still goes through `trusted_role_runner.py`; skill
documents do not need to modify skill text when the route changes.

Minimum stage rules:

- `novelty_checker`: allow current candidate, literature evidence, `LITERATURE_INDEX.md`, `GAP_MAP.md`; forbid other candidates, old novelty conclusions, generator trace, ad hoc results, `RUNS/IDEA_CARDS/`.
- `idea_reviewer` / `adversarial_reviewer`: allow current candidate, necessary background, explicit evidence; forbid generator trace, other candidates, old scores, user preference, historical praise.
- `final_selector`: allow canonical candidates, independent reviews, novelty reports, selection criteria; forbid raw brainstorm trace, user preference, old final selection, 外层 Agent 主观总结.
- `experiment_implementer`: allow experiment plan, final proposal, necessary code context, research contract; forbid old failure narratives, unverified results, outer-Agent implementation preference.
- `experiment_code_reviewer`: allow reviewed code, experiment plan, metric definition, split definition, expected behavior; forbid 实现者自我辩解, “已经没问题”, old positive review, unrelated experiment results.
- `result_judge`: allow experiment results, logs, metric definition, research contract; forbid optimistic outer-Agent summaries, unverified results, old conclusions, mock/dry-run artifacts.
- `paper_writer` / `final_paper_auditor`: allow verified results, research contract, approved claims, verified reviews; forbid unverified exploratory notes, `external_agent_direct` output, mock/dry-run artifacts, 未验证结果.

### Ledger Call ID

Each real model invocation should reference a `ledger_call_id` from `.aris/calls/llm_calls.jsonl` in its artifact provenance, enabling audit trail verification.

## Fallback Behavior

When Codex MCP is unavailable for a Codex-assigned role, the system falls back to the API backend configured in your `ROLE_<ROLE>` alias. Set a fallback alias explicitly:

```bash
ROLE_IDEA_REVIEWER=CODEX      # Primary: Codex MCP
# If Codex unavailable, caller should handle fallback per ARIS_CODEX_GATE_MODE
```

When a fallback occurs, the ledger entry must record:
- `fallback_used: true`
- `fallback_reason: "codex unavailable"` (or similar)
- `actual_backend` and `actual_model` of the fallback

## Legacy LLM_* Variables

Old `LLM_*` variables are still read as fallbacks if the new system is not fully configured:

```bash
# Only needed as fallback if MODEL_/ROLE_ system is incomplete
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-pro
LLM_FALLBACK_MODEL=deepseek-v4-flash
LLM_THINKING=enabled
LLM_REASONING_EFFORT=high
```

## Verifying Configuration

```bash
python tools/model_route.py idea_reviewer
python tools/config_check.py
```

## File Locations

- **Env template**: `.env.example` (committed, no secrets)
- **Env config**: `.env` (user-local, never committed)
- **Route resolver**: `tools/model_route.py`
- **Backend adapters**: `tools/model_backends/base.py`, `tools/model_backends/openai_compatible.py`, `tools/model_backends/codex_mcp.py`
- **Config checker**: `tools/config_check.py`
- **Env loader**: `tools/env_loader.py`
- **Call ledger**: `.aris/calls/llm_calls.jsonl`
- **Skill files**: `skills/<name>/SKILL.md` (never hardcode models here)

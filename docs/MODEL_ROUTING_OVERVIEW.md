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

## Fallback Behavior

When Codex MCP is unavailable for a Codex-assigned role, the system falls back to the API backend configured in your `ROLE_<ROLE>` alias. Set a fallback alias explicitly:

```bash
ROLE_IDEA_REVIEWER=CODEX      # Primary: Codex MCP
# If Codex unavailable, caller should handle fallback per ARIS_CODEX_GATE_MODE
```

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
- **Config checker**: `tools/config_check.py`
- **Env loader**: `tools/env_loader.py`
- **Call ledger**: `.aris/calls/llm_calls.jsonl`
- **Skill files**: `skills/<name>/SKILL.md` (never hardcode models here)
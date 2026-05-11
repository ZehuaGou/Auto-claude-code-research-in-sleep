---
name: idea-creator
description: Generate and canonicalize research ideas from a gap map or research direction. Divergent generation uses DeepSeek V4 Pro. Codex only used for shortlist audit gate. Use when user says "找idea", "generate ideas", "what can we work on".
argument-hint: [research-direction]
allowed-tools: Bash(*), Read, Write, Grep, Glob, WebSearch, WebFetch, Agent, mcp__codex__codex, mcp__codex__codex-reply
---

# Research Idea Creator

Generate research ideas for: $ARGUMENTS

## Prerequisites

`/idea-creator` reads from existing Phase 1 outputs. Before generating ideas, check:
1. `LITERATURE_INDEX.md` exists (from `/research-lit`)
2. `GAP_MAP.md` exists (from `/research-lit`)
3. `PHASE1_EVIDENCE_AUDIT.md` exists (from `/research-lit` Codex gate)

If these files do not exist, prompt the user to run `/research-lit "direction"` first.
`/idea-creator` does NOT perform its own full landscape survey.

## Overview

Given a verified GAP_MAP and LITERATURE_INDEX, generate 8–12 concrete research
ideas, write each as an independent card, deduplicate against the existing
idea bank, and produce canonical candidates.

**Model routing for idea-creator:**
- **idea_generator (divergent generation):** Uses DeepSeek V4 Pro (or configured `LLM_IDEA_GENERATOR_MODEL`). Does NOT use Codex for generation.
- **idea_deduplicator (mechanistic dedup):** Uses DeepSeek V4 Pro (or configured `LLM_IDEA_DEDUPLICATOR_MODEL`). Does NOT use Codex for dedup.
- **idea_shortlist_auditor (weak idea killer):** Routing controlled by `tools/model_route.py idea_shortlist_auditor`. Resolved at invocation time.

**What this skill does NOT do:**
- `/idea-creator` does NOT perform novelty checks. Use `/novelty-check` for that.
- `/idea-creator` does NOT do independent review. Use `/exec-review` for that.
- `/idea-creator` does NOT run pilot experiments. Use `/experiment-bridge` for that.
- `/idea-creator` does NOT make final kill decisions beyond shortlist audit.
- `/idea-creator` does NOT do adversarial review or final selection.
- `/idea-creator` does NOT write experiment plans.

## Outputs

- `IDEA_CARDS/idea_*.md` — raw generated idea cards
- `IDEA_BANK.md` / `IDEA_BANK.json` — deduplicated idea bank
- `CANONICAL_IDEAS/CAND_*.md` — canonical candidates
- `PHASE2_IDEA_SHORTLIST_AUDIT.md` — Codex shortlist gate output

## Constants

- **IDEA_GENERATOR_MODEL** — Set by `LLM_IDEA_GENERATOR_MODEL` env var (default: DeepSeek V4 Pro). Used for divergent idea generation.
- **IDEA_DEDUPLICATOR_MODEL** — Set by `LLM_IDEA_DEDUPLICATOR_MODEL` env var (default: DeepSeek V4 Pro). Used for mechanistic dedup.
- **SHORTLIST_AUDITOR_BACKEND = `codex`** — Codex MCP for the idea_shortlist_auditor gate. This is the ONLY Codex gate in idea-creator. Codex is NOT used for generation. All idea_shortlist_auditor calls must follow the global trusted role execution protocol (`shared-references/trusted-role-execution.md`).
- **OUTPUT_DIR = `idea-stage/`** — All idea-stage outputs. Create if absent.

## Workflow

### Phase 0: Load Research Wiki (if active)

**Skip this phase entirely if `research-wiki/` does not exist.**

If `research-wiki/` exists, resolve the canonical helper using the
shared resolution chain (see `../research-wiki/SKILL.md` for the
contract):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
ARIS_REPO="${ARIS_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .aris/installed-skills.txt 2>/dev/null)}"
WIKI_SCRIPT=".aris/tools/research_wiki.py"
[ -f "$WIKI_SCRIPT" ] || WIKI_SCRIPT="tools/research_wiki.py"
[ -f "$WIKI_SCRIPT" ] || { [ -n "${ARIS_REPO:-}" ] && WIKI_SCRIPT="$ARIS_REPO/tools/research_wiki.py"; }
[ -f "$WIKI_SCRIPT" ] || {
  echo "WARN: research_wiki.py not found." >&2
  echo "      Idea generation will still be produced." >&2
  echo "      Wiki integration will be skipped." >&2
  WIKI_SCRIPT=""
}
```

```
if research-wiki/query_pack.md exists AND is less than 7 days old:
    Read query_pack.md and use it as initial landscape context
else if research-wiki/ exists but query_pack.md is stale or missing:
    if [ -n "$WIKI_SCRIPT" ]: python3 "$WIKI_SCRIPT" rebuild_query_pack research-wiki/
    Then read query_pack.md as above
```

### Phase 1: Load Verified Inputs

**Do NOT run a new landscape survey.** Read from existing Phase 1 outputs:

1. Read `LITERATURE_INDEX.md` — verified paper index from `/research-lit`
2. Read `GAP_MAP.md` — verified research gap map from `/research-lit`
3. Read `PHASE1_EVIDENCE_AUDIT.md` — Codex evidence integrity gate output

If these files do not exist, stop and tell the user to run `/research-lit "direction"` first.

### Phase 2: Idea Generation

Use DeepSeek V4 Pro (env: `LLM_IDEA_GENERATOR_MODEL`) for divergent brainstorming. Do NOT use Codex for generation.

```
Prompt structure:
  You are a senior ML researcher. Using the following verified inputs:
  - LITERATURE_INDEX.md: [content]
  - GAP_MAP.md: [content]
  Generate 8-12 concrete research ideas. For each idea:
  1. One-sentence summary
  2. Core hypothesis
  3. Minimum viable experiment
  4. Novelty risk (which gap does it address?)
  5. Implementation risk: LOW / MEDIUM / HIGH
```

Do not reuse the generation thread for review or novelty check.

### Phase 3: Idea Card Output

Each generated idea is written as an independent file:

```
idea-stage/AGENTIC/RUNS/<run_id>/IDEA_CARDS/idea_001.md
idea-stage/AGENTIC/RUNS/<run_id>/IDEA_CARDS/idea_002.md
...
```

Each card includes:
- Hypothesis (one sentence)
- Motivation and gap addressed
- Method change (what is different from baselines)
- Novelty hypothesis (NOT confirmed_novel — the novelty checker decides this)
- Minimum viable experiment
- Expected signal
- Required data and compute
- Failure modes

### Generation Rules

1. Generate 8–12 ideas; if fewer than 3, mark `needs_review`.
2. Idea generator must NOT review its own ideas.
3. Generator must NOT claim `confirmed_novel` — only "novelty hypothesis".
4. Original idea cards are immutable; never modify or merge them after creation.

### Phase 4: Dedup & Canonicalization

After generation, run deduplication against the existing idea bank:

1. Read existing `IDEA_BANK.md` and `CANONICAL_IDEAS/` if they exist.
2. Compare new cards against existing candidates.
3. Dedup output:
   - `idea-stage/AGENTIC/IDEA_BANK.md` — updated index
   - `idea-stage/AGENTIC/IDEA_BANK.json` — machine-readable index
   - `idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md` — clean candidates

### Dedup Rules

1. Dedup only judges: duplicate / variant / complement / conflict.
2. Dedup does NOT do quality scoring.
3. Dedup does NOT do novelty checking.
4. If uncertain about a pair, keep both as separate candidates.
5. CANONICAL_IDEAS are the clean input for downstream reviewers/novelty checkers — no generator traces, no old scores, no user preferences.

### Phase 2 Codex Gate: Idea Shortlist Audit (idea_shortlist_auditor)

**This is an isolated judgment gate, not a generation continuation.**

**All idea_shortlist_auditor calls MUST use `tools/trusted_role_runner.py`.**

1. **Resolve routing** (via model_route.py, config-only):
   ```
   python tools/model_route.py idea_shortlist_auditor
   ```

2. **Execute via `tools/trusted_role_runner.py`**:
   ```
   python tools/trusted_role_runner.py \
       --role idea_shortlist_auditor \
       --input "<IDEA_BANK.md + CANONICAL_IDEAS/* context>" \
       --output "idea-stage/AGENTIC/SHORTLIST_AUDIT/PHASE2_SHORTLIST_AUDIT.md" \
       --require-codex-thread   # omit for deepseek_only mode
   ```

3. **Verify the execution**:
   ```
   python tools/validate_model_invocation.py --role idea_shortlist_auditor
   ```
   - If `verification_status` is NOT `verified_routed_call` or `verified_with_fallback`: **FAIL closed**
   - If `allowed_next_stage` is `false`: **FAIL closed**
   - If `codex_used=true` but no `codex_thread_id`: **FAIL closed**

4. **If trusted runner fails**: Do NOT substitute with external agent output. Report failure and stop.

5. **Output**: `idea-stage/AGENTIC/SHORTLIST_AUDIT/PHASE2_SHORTLIST_AUDIT.md`

The auditor must NOT read:
- Raw generation trace from `RUNS/<run_id>/IDEA_CARDS/`
- Generator prompts or intermediate outputs
- Old scores, previous reviews, or user preferences

4. **Gate decision**: Killed candidates are excluded from Phase 3 onward.

5. **Artifact header**: The output MUST begin with routing and isolation fields:
   ```
   routing_source: env
   global_codex_gate_mode: <value from ARIS_CODEX_GATE_MODE>
   isolation_mode: codex_thread|manual_subsession
   codex_thread_id: <id>|none
   primary_backend: codex|llm-chat
   actual_backend: codex|llm-chat
   actual_model: DEFAULT|<model>
   fallback_used: True|False
   fallback_reason: None|<reason>
   codex_used: true|false
   confidence_downgraded: true|false
   ```

6. **Fallback**: If Codex unavailable and route is `codex_preferred`, fallback to `LLM_IDEA_SHORTLIST_AUDITOR_FALLBACK_MODEL`. Mark with `REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK`. Isolation mode becomes `protocol_only` — verdict max is PASS_WITH_WARNINGS. If route is `codex_required` and Codex unavailable, fail. If route is `deepseek_only`, skip Codex and use fallback model directly.

### Phase 5: Write Ideas to Research Wiki (if active)

**Skip entirely if `research-wiki/` does not exist.**

```
if research-wiki/ exists:
    for each idea in all generated ideas:
        1. Create page: research-wiki/ideas/<idea_id>.md
           - node_id: idea:<id>, stage: proposed, outcome: unknown
           - Include: hypothesis, proposed method, expected outcome
        2. Add edges (only if $WIKI_SCRIPT resolved):
           python3 "$WIKI_SCRIPT" add_edge ... --type inspired_by ...
    Rebuild query pack (only if $WIKI_SCRIPT resolved)
```

## Output Protocols

> Follow these shared protocols for all output files:
> - **[Output Versioning Protocol](../shared-references/output-versioning.md)**
> - **[Output Manifest Protocol](../shared-references/output-manifest.md)**
> - **[Output Language Protocol](../shared-references/output-language.md)**

## Key Rules

- **Large file handling**: If the Write tool fails due to file size, immediately retry using Bash (`cat << 'EOF' > file`) to write in chunks. Do NOT ask the user for permission — just do it silently.
- The user provides a DIRECTION, not an idea. Your job is to generate the ideas.
- Quantity first, quality second: brainstorm broadly.
- Always estimate compute cost in each idea card.
- Record generated ideas, malformed/rejected idea drafts, and dedup/merge decisions. Do not make final kill decisions here.
- **If the user's direction is too broad (e.g., "NLP"), STOP and ask them to narrow it.**

## Composing with Other Skills

```
/idea-creator "direction"     → IDEA_CARDS + IDEA_BANK + CANONICAL_IDEAS
/novelty-check "CAND_001"    → novelty verdict (next step)
/exec-review "CAND_001.md"   → independent review (next step)
```

If the user explicitly asks to proceed to experiments after review:
```
/research-contract "CAND_XXX"     — user-driven, not automatic
/baseline-repro "baseline"         — user-driven, not automatic
/experiment-bridge "plan"          — user-driven, not automatic
```

## Internal Helpers

The tools `tools/agentic_idea_discovery.py` and `tools/isolated_job_runner.py`
may be called internally for job execution. Users should not call these directly.

## Review Tracing

After each `mcp__codex__codex` or `mcp__codex__codex-reply` reviewer call,
save the trace following `shared-references/review-tracing.md`.

## Resume / Interruption Recovery

This skill supports resumption from artifact file state after session interruption.

### Detection

Use `tools/resume_stage_state.py` to detect where Phase 2 left off:

```bash
python3 tools/resume_stage_state.py idea-creator
```

### Required Artifacts

- `IDEA_BANK.md` — deduplicated idea index (or `IDEA_BANK.json`)
- `CANONICAL_IDEAS/CAND_*.md` — canonical candidates (at least one active)
- `SHORTLIST_AUDIT/PHASE2_SHORTLIST_AUDIT.md` — Codex shortlist gate output

### Recovery Rules

- **No IDEA_BANK.md or no CANONICAL_IDEAS/**: Phase 2 not started. Verify Phase 1 artifacts exist first, then re-run `/idea-creator "direction"`.
- **IDEA_BANK.md + CAND_*.md exist, no PHASE2_SHORTLIST_AUDIT.md**: Idea generation and dedup done but Codex shortlist audit not completed. Run the shortlist audit gate: invoke `mcp__codex__codex` with the shortlist audit prompt (see Phase 2 Codex Gate above), or re-run `/idea-creator "direction" --run-gate`.
- **All 3 artifacts present**: Phase 2 is complete. Resume user intent continues to Phase 3 (exec-review). Do NOT regenerate ideas — proceed directly to `/exec-review CAND_XXX`.
- **Killed candidates exist**: Already excluded from pipeline; do NOT re-review them. Check `CANONICAL_IDEAS/` for file-level `**Status**: killed` markers, or read the shortlist audit kill list.

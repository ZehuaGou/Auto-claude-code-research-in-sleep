---
name: idea-bank
description: Inspect, deduplicate, manage canonical idea candidates, and perform final selection (Codex-gated).
---

# idea-bank

## Purpose

View the global idea bank, trigger re-dedup across runs, inspect a specific candidate's full review trail, or perform final selection.

**Critical gate**: `final-select` defaults to Codex. If Codex is unavailable, a marked fallback to DeepSeek V4 Pro is permitted (explicit `llm_fallback_gate` with downgraded confidence). Manual override is available as `manual-select` but produces `PASS_WITH_WARNINGS` max and is not a valid gate.

## When to Use

- Before starting a new run to check existing ideas
- After multiple `/research-lit` + `/idea-creator` runs to consolidate
- To review a candidate's full provenance
- To perform final selection after novelty-check is complete

## Workflow

### status (default)

1. Read `IDEA_BANK.md`
2. Show candidates grouped by status (active / killed / in_review)
3. Show summary counts per run

### dedup

1. Scan all `RUNS/<run_id>/IDEA_CARDS/` for unprocessed cards
2. Scan `CANONICAL_IDEAS/` for existing candidates
3. Run deduplication logic (via API backend or manual review)
4. Update `IDEA_BANK.md`, `IDEA_BANK.json`
5. Create new `CANONICAL_IDEAS/CAND_*.md` as needed

### <candidate-id>

1. Read the specified `CANONICAL_IDEAS/CAND_XXX.md`
2. Show provenance: which run(s) it came from, which idea cards
3. Show review verdicts: `REVIEWS/CAND_XXX_review.md`
4. Show novelty status: `NOVELTY/CAND_XXX_novelty.md`
5. Show adversarial findings: `ADVERSARIAL/CAND_XXX_adversarial.md`
6. Show `next_action`: what the user should do next

### final-select <candidate-id> — Codex Gate (Route via model_route.py)

Perform a final selection. Routing is determined by `tools/model_route.py final_selector` at invocation time.

**Prerequisites**: The candidate MUST have completed exec-review AND novelty-check before final-select can run.

```
/idea-bank "final-select CAND_001"
```

**Process**:

1. **Pre-flight checks**:
   - Verify exec-review is complete for the candidate (`REVIEWS/CAND_XXX_review.md` exists with valid header + verdict)
   - Verify novelty-check is complete (`NOVELTY/CAND_XXX_novelty.md` exists with mode=canonical_pipeline, valid header, verdict)
   - If either is incomplete, stop with error: "Pre-requisite review/novelty incomplete. Complete exec-review and novelty-check first."
   - If a provisional selection already exists, warn but continue

2. **Resolve routing**:
   ```
   python tools/model_route.py final_selector
   ```
   Parse the output JSON. The `effective_mode` field determines the path:
   - `codex_required` → Step 3 (Codex only; fail if unavailable)
   - `codex_preferred` → Step 3, with Step 4 fallback
   - `deepseek_only` → skip to Step 4 (DeepSeek V4 Pro directly)
   - `primary_backend`, `actual_model`, `selection_mode` are set from the route output

3. **Codex Gate** (when route says `codex_required` or `codex_preferred`):
   - Call Codex via `mcp__codex__codex` with role `final_selector`
   - Config: `{"model_reasoning_effort": "xhigh"}`
   - Allowed input files:
     - `IDEA_BANK.md`, `IDEA_BANK.json`
     - `CANONICAL_IDEAS/CAND_001.md` (and CAND_002.md for comparison)
     - `REVIEWS/CAND_001_review.md`, `REVIEWS/CAND_002_review.md`
     - `NOVELTY/CAND_001_novelty.md`, `NOVELTY/CAND_002_novelty.md`
     - `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` (only if marked provisional, i.e. no codex_thread_id)
     - `LITERATURE_INDEX.md`, `GAP_MAP.md`
   - Forbidden input files:
     - `RUNS/<run_id>/IDEA_CARDS/` (raw brainstorm)
     - Generator traces, user preference notes
     - Old scores, ad_hoc novelty files
   - Prompt must include:
     - Full candidate descriptions (CAND_001, CAND_002)
     - Review verdicts and key criticisms
     - Novelty verdicts
     - Comparison of complementary vs overlapping aspects
     - Ask: "Which candidate should proceed to experiments? Verdict must be one of: SELECT_CAND_001, SELECT_CAND_002, NO_STRONG_IDEA, NEEDS_REVISION"
   - **If Codex succeeds**:
     - Write `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` with artifact header that includes routing fields:
       ```
       mode: final_selection
       routing_source: env
       global_codex_gate_mode: <from route>
       selection_mode: codex_gate
       isolation_mode: codex_thread
       codex_thread_id: <actual thread id from Codex>
       primary_backend: codex
       actual_backend: codex
       actual_model: DEFAULT
       fallback_used: false
       fallback_reason: none
       codex_used: true
       confidence_downgraded: false
       forbidden_context_checked: true
       verdict: SELECT_CAND_001 / SELECT_CAND_002 / NO_STRONG_IDEA / NEEDS_REVISION
       ```
     - Write ledger: `role=final_selector`, status=`completed`
     - Only on verdict `SELECT_CAND_001` or `SELECT_CAND_002`:
       - Update `IDEA_BANK.md`: mark candidate as SELECTED
       - Update `IDEA_BANK.json`: move candidate from provisional/ready to "selected"
       - Update `CANONICAL_IDEAS/CAND_XXX.md`: status → SELECTED
     - On `NO_STRONG_IDEA`: leave status unchanged, report reason
     - On `NEEDS_REVISION`: leave status unchanged, report required changes
   - **If Codex is unavailable** AND route says `codex_required`:
     - **Fail**: stop with error "Codex required but unavailable. Set ARIS_CODEX_GATE_MODE=codex_preferred to allow fallback."
   - **If Codex is unavailable** AND route says `codex_preferred`:
     - Fallback to Step 4 with `fallback_used=true`, `fallback_reason` set to actual error

4. **LLM Fallback or DeepSeek Direct** (when route says `codex_preferred` + Codex unavailable, or `deepseek_only`):
   - Use `llm-chat` backend with model from route (default: `deepseek-v4-pro`)
   - **Do NOT pretend Codex was used**. Every field must honestly reflect the routing.
   - Write `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` with artifact header:
     ```
     mode: final_selection
     routing_source: env
     global_codex_gate_mode: <from route>
     selection_mode: llm_fallback_gate
     isolation_mode: protocol_only
     codex_thread_id: none
     primary_backend: <from route>
     actual_backend: llm-chat
     actual_model: <from route actual_model>
     fallback_used: <true if codex_preferred fallback, false if deepseek_only>
     fallback_reason: <error or "Codex disabled by ARIS_CODEX_GATE_MODE=deepseek_only">
     codex_used: false
     confidence_downgraded: true
     forbidden_context_checked: true
     verdict: SELECT_CAND_001_WITH_WARNINGS / SELECT_CAND_002_WITH_WARNINGS / NO_STRONG_IDEA / NEEDS_REVISION
     ```
   - Fallback verdicts allowed: `SELECT_CAND_001_WITH_WARNINGS`, `SELECT_CAND_002_WITH_WARNINGS`, `NO_STRONG_IDEA`, `NEEDS_REVISION`
   - On `SELECT_CAND_001_WITH_WARNINGS` or `SELECT_CAND_002_WITH_WARNINGS`:
     - Update `IDEA_BANK.md`: mark candidate as `SELECTED_WITH_FALLBACK` (not plain SELECTED)
     - Update `IDEA_BANK.json`: move candidate to "selected_with_fallback"
     - Update `CANONICAL_IDEAS/CAND_XXX.md`: status → `SELECTED_EMPIRICAL_WITH_LLM_FALLBACK`
     - Add prominent note in report: "This final selection did not use Codex. It used DeepSeek V4 Pro fallback."
   - On `NO_STRONG_IDEA` or `NEEDS_REVISION`: leave status unchanged, report reason
   - Write ledger: `role=final_selector`, status=`completed_with_warnings`, set `codex_used=false`, `confidence_downgraded=true`
7. **Next step after fallback selection**:
   - Proceed to `/research-contract` is permitted
   - `/research-contract` must record:
     - `final_selection_backend: deepseek-v4-pro`
     - `codex_used: false`
     - `rerun_codex_final_selector_recommended: true`

### manual-select <candidate-id> — Manual Override (PROTOCOL_ONLY, max PASS_WITH_WARNINGS)

**WARNING**: This bypasses the Codex gate. It does NOT count as a formal final selection.

```
/idea-bank "manual-select CAND_001"
```

**Process**:

1. Same pre-flight checks as final-select (review + novelty must be complete)
2. Write `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` with artifact header:
   ```
   mode: final_selection
   selection_mode: manual_override
   isolation_mode: protocol_only
   actual_backend: <used model>
   actual_model: DEFAULT
   fallback_used: false
   forbidden_context_checked: true
   verdict: PASS_WITH_WARNINGS
   ```
3. Update IDEA_BANK and CAND_XXX status to PROVISIONAL_SELECTED
4. Add note: "This is a manual override. Run /idea-bank 'final-select CAND_XXX' for a formal Codex verdict before proceeding to research-contract."
5. **Do NOT** record as `role=final_selector` in ledger. Use `role=manual_selector` instead.

## Inputs

- Command: `status`, `dedup`, `<candidate-id>`, `final-select <candidate-id>`, `manual-select <candidate-id>`

## Outputs

- Terminal output (status or candidate details)
- Updated `IDEA_BANK.md`, `IDEA_BANK.json` (dedup mode, final-select mode, manual-select mode)
- New canonical candidates (dedup mode)
- `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` (final-select and manual-select modes)

## Hard Rules

1. IDEA_BANK is an index only — never store full idea content in it.
2. Original run artifacts are immutable; never modify `RUNS/<run_id>/IDEA_CARDS/`.
3. CANONICAL_IDEAS are clean candidates; never include generator traces or raw run notes.
4. Never mix multiple runs into one giant report.
5. Never pass old scores or praise to a reviewer.
6. **/idea-bank can read `.meta/`** (provenance metadata). Reviewers, novelty checkers, and adversarial reviewers MUST NOT read `.meta/`.
7. **final-select routing via model_route.py**. Run `python tools/model_route.py final_selector` before each gate invocation. Follow the resolved mode (`codex_required`, `codex_preferred`, or `deepseek_only`). Silent fallback is forbidden — all downgrades must be explicitly recorded in the artifact header.
8. **manual-select** is protocol_only only. Never claim it as a formal Codex gate.
9. **No new top-level slash command** — final-selection is a sub-mode of `/idea-bank`, NOT `/final-selection`.
10. `final-select` without a valid Codex verdict must not change `selected` status in IDEA_BANK or CAND files.

## Integration

- Reads: `IDEA_BANK.md`, `IDEA_BANK.json`, `CANONICAL_IDEAS/`, `CANONICAL_IDEAS/.meta/`, `REVIEWS/`, `NOVELTY/`, `ADVERSARIAL/`, `FINAL_SELECTION/`
- Writes: `IDEA_BANK.md`, `IDEA_BANK.json`, `CANONICAL_IDEAS/` (dedup mode), `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` (final-select/manual-select)
- Complementary to: `/exec-review`, `/novelty-check`, `/idea-discovery`, `/status`

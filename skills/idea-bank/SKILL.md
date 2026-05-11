---
name: idea-bank
description: Inspect, deduplicate, manage canonical idea candidates, and perform final selection (Codex-gated).
---

# idea-bank

## Purpose

View the global idea bank, trigger re-dedup across runs, inspect a specific candidate's full review trail, or perform final selection.

**Critical gate**: `final-select` defaults to Codex. If Codex is unavailable, a marked fallback to DeepSeek V4 Pro is permitted (explicit `llm_fallback_gate` with downgraded confidence). Manual override is available as `manual-select` but produces `PASS_WITH_WARNINGS` max and is not a valid gate. All final_selector calls must follow the global trusted role execution protocol (`shared-references/trusted-role-execution.md`).

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
   - `codex_required` → Use `trusted_role_runner.py` with `--require-codex-thread`
   - `codex_preferred` → Use `trusted_role_runner.py` with `--require-codex-thread`; fallback handled by runner
   - `deepseek_only` → Use `trusted_role_runner.py` (no `--require-codex-thread`)

3. **Execute via `tools/trusted_role_runner.py`**:
   ```
   python tools/trusted_role_runner.py \
       --role final_selector \
       --input "<full context: candidates, reviews, novelty verdicts>" \
       --output "FINAL_SELECTION/IDEA_SELECTION_REPORT.md" \
       --require-codex-thread   # omit for deepseek_only mode
   ```
   - `trusted_role_runner.py` handles ledger start/finish automatically
   - Only `verified_routed_call` or `verified_with_fallback` with `allowed_next_stage=true` can proceed

4. **Verify the execution**:
   ```
   python tools/validate_model_invocation.py --role final_selector
   ```
   - If `verification_status` is NOT `verified_routed_call` or `verified_with_fallback`: **FAIL closed**
   - If `allowed_next_stage` is `false`: **FAIL closed**
   - If `codex_used=true` but no `codex_thread_id`: **FAIL closed**
   - If dry-run or mock: **FAIL closed**
   - `confidence_downgraded` and `routing_source` are recorded by `trusted_role_runner.py` in artifact provenance
   - `global_codex_gate_mode` reflects the current ARIS_CODEX_GATE_MODE setting at invocation time

5. **If trusted runner succeeds**:
   - Write `FINAL_SELECTION/IDEA_SELECTION_REPORT.md` with artifact header from runner
   - Only on verdict `SELECT_CAND_001` or `SELECT_CAND_002`:
     - Update `IDEA_BANK.md`: mark candidate as SELECTED
     - Update `IDEA_BANK.json`: move candidate from provisional/ready to "selected"
     - Update `CANONICAL_IDEAS/CAND_XXX.md`: status → SELECTED
   - On `NO_STRONG_IDEA`: leave status unchanged, report reason
   - On `NEEDS_REVISION`: leave status unchanged, report required changes

6. **If trusted runner fails**: Do NOT substitute with external agent output. Report failure and stop.

4. **LLM Fallback or DeepSeek Direct**: Now handled automatically by `trusted_role_runner.py` (Steps 3-6 above). When Codex is unavailable and route is `codex_preferred`, the runner falls back to the configured LLM and records `fallback_used=true`, `fallback_reason`. When route is `deepseek_only`, the runner uses the LLM directly. Status update logic below still applies.

5. **Post-selection status updates** (after trusted runner succeeds):
   - `SELECT_CAND_001` or `SELECT_CAND_002` (via Codex or verified fallback):
     - Update `IDEA_BANK.md`: mark candidate as `SELECTED`
     - Update `IDEA_BANK.json`: move candidate to "selected"
     - Update `CANONICAL_IDEAS/CAND_XXX.md`: status → `SELECTED`
   - `SELECT_CAND_001_WITH_WARNINGS` or `SELECT_CAND_002_WITH_WARNINGS` (fallback path):
     - Update `IDEA_BANK.md`: mark candidate as `SELECTED_WITH_FALLBACK`
     - Update `IDEA_BANK.json`: move candidate to "selected_with_fallback"
     - Update `CANONICAL_IDEAS/CAND_XXX.md`: status → `SELECTED_EMPIRICAL_WITH_LLM_FALLBACK`
     - Add note: "This final selection used DeepSeek V4 Pro fallback."
   - On `NO_STRONG_IDEA` or `NEEDS_REVISION`: leave status unchanged, report reason

6. **Next step after selection**:
   - Proceed to `/research-contract` (record `final_selection_backend`, `codex_used`, `rerun_codex_final_selector_recommended`)

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

---
name: idea-discovery-agentic
description: >-
  [INTERNAL REFERENCE] API-first isolated job architecture for research idea
  discovery. Users should invoke /idea-discovery, /research-lit, /idea-creator,
  /exec-review, /novelty-check, or /idea-bank.
argument-hint: [research-direction]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# Idea Discovery Agentic

This skill is an internal design reference for the agentic idea discovery architecture.
Normal users should use:
- /idea-discovery "direction"
- /research-lit "direction"
- /idea-creator latest
- /exec-review CAND_001
- /novelty-check CAND_001
- /idea-bank status

Do not use /idea-discovery-agentic as the primary workflow unless explicitly debugging or extending the architecture.

## Purpose

通过 isolated jobs 提高科研创新点发现质量，减少主会话上下文污染和自我确认偏差。

## When to Use

This skill is called internally by `/research-lit`, `/idea-creator`, `/novelty-check`, `/exec-review`, and `/idea-discovery`. Users should invoke those skills directly.

## Inputs

- research direction（主题描述）
- RESEARCH_BRIEF.md（如存在）
- docs/research_constraints.md（如存在）
- existing idea-stage/AGENTIC/IDEA_BANK.md（如存在）
- existing CANONICAL_IDEAS（如存在）

## Outputs

- idea-stage/AGENTIC/RUNS/<run_id>/
- idea-stage/AGENTIC/IDEA_BANK.md
- idea-stage/AGENTIC/IDEA_BANK.json
- idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md
- idea-stage/AGENTIC/REVIEWS/*.md
- idea-stage/AGENTIC/NOVELTY/*.md
- idea-stage/AGENTIC/ADVERSARIAL/*.md
- idea-stage/AGENTIC/FINAL_SELECTION/IDEA_SELECTION_REPORT.md

## Workflow

### Phase 0: Create Run

1. Create run_id: `YYYYMMDD_HHmmss_<slug>`
2. Create `idea-stage/AGENTIC/RUNS/<run_id>/` directories
3. Write `RUN_MANIFEST.md` (metadata, topic, parameters)
4. Write `INPUTS.md` (research direction, constraints)
5. Register run in `RUNS_INDEX.json`

### Phase 1: Literature Scout

- role: `literature_scout`
- backend: `claude_headless` (needs search/read tools)
- input_files: `[RESEARCH_BRIEF.md, docs/research_constraints.md]` if exist
- output_files: `[RUNS/<run_id>/LITERATURE_INDEX.md]`
- Run via `isolated_job_runner.py run --job-file <job.json>`
- If claude unavailable: write `needs_manual_literature_scout` handoff; stop or fallback to `/research-lit` only if user allows

### Phase 2: Gap Extractor

- role: `gap_extractor`
- backend: `api`
- model_env: `LLM_GAP_EXTRACTOR_MODEL`
- input_files: `[RUNS/<run_id>/LITERATURE_INDEX.md]`
- output_files: `[RUNS/<run_id>/GAP_MAP.md]`
- Must NOT generate idea — only extract gaps from literature

### Phase 3: Idea Generator

- role: `idea_generator`
- backend: `api`
- model_env: `LLM_IDEA_GENERATOR_MODEL`
- input_files: `[GAP_MAP.md, LITERATURE_INDEX.md]`
- output_files: `[IDEA_CARDS/idea_001.md … idea_NNN.md]`
- Generate 8–12 ideas
- Must NOT review own ideas
- Must NOT claim confirmed novelty
- Each idea card follows `templates/AGENTIC_IDEA_CARD_TEMPLATE.md`

### Phase 4: Dedup / Canonicalization

- role: `idea_deduplicator`
- backend: `api`
- model_env: `LLM_IDEA_DEDUPLICATOR_MODEL`
- input_files: `[new IDEA_CARDS, IDEA_BANK.md, CANONICAL_IDEAS/]` (existing)
- output_files: `[IDEA_BANK.md, IDEA_BANK.json, CANONICAL_IDEAS/CAND_*.md]`
- Identify: duplicates, variants, stronger versions, new directions
- Must NOT do novelty check
- Each canonical idea follows `templates/CANONICAL_IDEA_TEMPLATE.md`

### Phase 5: Independent Idea Review

- For each new/active canonical candidate with status `active`:
  - role: `idea_reviewer`
  - backend: `api` (default), `codex_optional` (if configured)
  - input_files: `[single CAND_*.md]` + relevant GAP_MAP excerpt
  - output_files: `[REVIEWS/CAND_XXX_review.md]`
- Reviewer must NOT read:
  - Other candidates
  - Generator trace
  - Previous scores
  - User preference
  - Old praise
- Verdict: `go / revise / kill`
- Each review follows `templates/IDEA_REVIEW_TEMPLATE.md`

### Phase 6: Novelty Check

- Only for `go` / `revise` candidates
- role: `novelty_checker`
- backend: `claude_headless` (may need search)
- input_files: `[single CAND_*.md, LITERATURE_INDEX.md, relevant paper sections]`
- output_files: `[NOVELTY/CAND_XXX_novelty.md]`
- Verdict:
  - `confirmed_novel` / `likely_incremental` / `already_done` / `insufficient_evidence`
- `insufficient_evidence` cannot become `confirmed_novel`

### Phase 7: Adversarial Review

- Only for candidates not killed
- role: `adversarial_reviewer`
- backend: `api` (default), `codex_optional` (if configured)
- model_env: `LLM_ADVERSARIAL_REVIEWER_FALLBACK_MODEL` (fallback)
- input_files: `[CAND_*.md, REVIEW, NOVELTY report]`
- output_files: `[ADVERSARIAL/CAND_XXX_adversarial.md]`
- Only finds weaknesses — no praise, no improvement suggestions

### Phase 8: Final Selection

- `main_architect` (current main Agent) reads only:
  - IDEA_BANK
  - CANONICAL_IDEAS
  - REVIEWS
  - NOVELTY reports
  - ADVERSARIAL reports
- Does NOT read generator traces or long task logs
- Output: `FINAL_SELECTION/IDEA_SELECTION_REPORT.md`
- Allowed conclusion: `no strong idea found`

## Hard Rules

1. Never merge raw run files directly into a giant IDEA_REPORT.
2. Every run is immutable.
3. Dedup creates canonical ideas; it does not rewrite original run ideas.
4. Reviewer sees one canonical idea at a time.
5. Novelty checker sees one canonical idea at a time.
6. No previous score/praise/user preference in reviewer prompt.
7. `no strong idea found` is acceptable.
8. This architecture stops at idea selection. If the user later chooses to proceed to experiments, downstream experiment skills should require research-contract and baseline-repro before implementation.
9. Do not submit runtime files to git.

## Failure Handling

- API unavailable: mark job failed, write handoff (status=failed).
- Claude unavailable: mark literature/novelty job `needs_manual`.
- Handoff missing: create fallback handoff (status=needs_review).
- Empty idea set: write `no strong idea found`.
- All ideas killed: write `no strong idea found`.
- Dedup uncertain: keep candidates separate.

## Integration

- `tools/agentic_idea_discovery.py` — orchestration (run creation, job generation)
- `tools/isolated_job_runner.py` — unified job execution engine
- `tools/env_loader.py` — .env reading
- `tools/llm_call_ledger.py` — call tracking
- `tools/session_registry.py` — session management
- `skills/shared-references/idea-bank-protocol.md` — idea storage protocol
- `skills/shared-references/model-routing.md` — role definitions
- `skills/shared-references/session-protocol.md` — session protocol
- `docs/AGENTIC_IDEA_DISCOVERY_DESIGN_CN.md` — design document

## Internal Tools for Skill Authors

Python helpers under `tools/` may be used internally by skills for scaffolding, ledger, job execution, and validation. Normal users should not call these directly. Contributors may inspect them for debugging and CI.

## Expected Artifacts

- `idea-stage/AGENTIC/RUNS/<run_id>/` — complete run artifacts
- `idea-stage/AGENTIC/IDEA_BANK.md` — candidate index
- `idea-stage/AGENTIC/IDEA_BANK.json` — machine-readable index
- `idea-stage/AGENTIC/CANONICAL_IDEAS/` — clean candidates
- `idea-stage/AGENTIC/FINAL_SELECTION/IDEA_SELECTION_REPORT.md` — final report

## Failure Example

If all ideas are killed:
- FINAL_SELECTION/IDEA_SELECTION_REPORT.md states `no strong idea found`
- Suggests alternative research directions
- Does not proceed to experiment planning

## Recovery Step

If a job fails mid-pipeline:
- Check `HANDOFFS/<role>.md` for error details
- Fix the issue and re-run the failed job with a new job file
- Resume from the failed phase, do not restart from scratch

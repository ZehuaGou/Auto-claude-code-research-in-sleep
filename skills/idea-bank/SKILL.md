---
name: idea-bank
description: Inspect, deduplicate, and manage canonical idea candidates across multiple agentic runs.
---

# idea-bank

## Purpose

View the global idea bank, trigger re-dedup across runs, or inspect a specific candidate's full review trail.

## When to Use

- Before starting a new run to check existing ideas
- After multiple `/research-lit` + `/idea-creator` runs to consolidate
- To review a candidate's full provenance

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

## Inputs

- Command: `status`, `dedup`, or a candidate ID like `CAND_001`

## Outputs

- Terminal output (status or candidate details)
- Updated `IDEA_BANK.md`, `IDEA_BANK.json` (dedup mode)
- New canonical candidates (dedup mode)

## Hard Rules

1. IDEA_BANK is an index only — never store full idea content in it.
2. Original run artifacts are immutable; never modify `RUNS/<run_id>/IDEA_CARDS/`.
3. CANONICAL_IDEAS are clean candidates; never include generator traces or raw run notes.
4. Never mix multiple runs into one giant report.
5. Never pass old scores or praise to a reviewer.
6. **/idea-bank can read `.meta/`** (provenance metadata). Reviewers, novelty checkers, and adversarial reviewers MUST NOT read `.meta/`.

## Integration

- Reads: `IDEA_BANK.md`, `IDEA_BANK.json`, `CANONICAL_IDEAS/`, `CANONICAL_IDEAS/.meta/`, `REVIEWS/`, `NOVELTY/`, `ADVERSARIAL/`
- Writes: `IDEA_BANK.md`, `IDEA_BANK.json`, `CANONICAL_IDEAS/` (dedup mode)
- Complementary to: `/exec-review`, `/novelty-check`, `/idea-discovery`

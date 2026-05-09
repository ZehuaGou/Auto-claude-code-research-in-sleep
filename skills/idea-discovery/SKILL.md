---
name: idea-discovery
description: "Workflow 1: Complete idea discovery pipeline. Orchestrates research-lit → idea-creator → exec-review → novelty-check → adversarial review → final selection. Use when user says \"找idea全流程\", \"idea discovery\", \"从零开始找方向\", or wants the complete idea exploration workflow."
argument-hint: [research-direction]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent, Skill, mcp__codex__codex, mcp__codex__codex-reply
---

# Workflow 1: Idea Discovery Pipeline

Orchestrate a complete idea discovery workflow for: **$ARGUMENTS**

## Overview

This skill chains sub-skills into a single automated pipeline:

```
/research-lit → /idea-creator → /exec-review → /novelty-check → adversarial → final selection
  (lit + gaps)   (ideas + dedup)   (review)      (novelty)       (critique)     (report)
```

Each phase builds on the previous one's output. The pipeline ends with
`FINAL_SELECTION/IDEA_SELECTION_REPORT.md` — a recommendation that may
conclude `no strong idea found`.

This pipeline does NOT default to pilot experiments, experiment plans,
or paper writing. Those are optional user-driven next steps.

## Constants

- **AUTO_PROCEED = true** — If user doesn't respond at a checkpoint, automatically proceed with the best option after presenting results. Set to `false` to always wait for explicit user confirmation.
- **REVIEWER_MODEL = `gpt-5.4`** — Model used via Codex MCP. Must be an OpenAI model (e.g., `gpt-5.4`, `o3`, `gpt-4o`). Passed to sub-skills.
- **OUTPUT_DIR = `idea-stage/`** — All idea-stage outputs go here. Create the directory if it doesn't exist.
- **COMPACT = false** — When `true`, generate compact summary files for short-context models and session recovery.

> 💡 Override by telling the skill, e.g., `/idea-discovery "topic" — compact: true`.

## Pipeline

### Phase 0: Load Research Brief (if available)

Before starting any other phase, check for a detailed research brief in the project:

1. Look for `RESEARCH_BRIEF.md` in the project root (or path passed as `$ARGUMENTS`)
2. If found, read it and extract:
   - Problem statement and context
   - Constraints (compute, data, timeline, venue)
   - What the user already tried / what didn't work
   - Domain knowledge and non-goals
   - Existing results (if any)
3. Use this as the primary context for all subsequent phases — it replaces the one-line prompt
4. If both `RESEARCH_BRIEF.md` and a one-line `$ARGUMENTS` exist, merge them (brief takes priority for details, argument sets the direction)

If no brief exists, proceed normally with `$ARGUMENTS` as the research direction.

### Phase 1: Literature Survey + Gap Extraction

Invoke `/research-lit` to map the research landscape and extract gaps:

```
/research-lit "$ARGUMENTS" — sources: all, gemini
```

**What this does:**
- Search arXiv, Google Scholar, Semantic Scholar for recent papers
- Build a landscape map: sub-directions, approaches, open problems
- If running in agentic mode: also output:
  - `idea-stage/AGENTIC/RUNS/<run_id>/LITERATURE_INDEX.md`
  - `idea-stage/AGENTIC/RUNS/<run_id>/GAP_MAP.md`
- Identify structural gaps and recurring limitations

**Codex Gate — Evidence Integrity Audit:** After literature survey, run
evidence_integrity_auditor via Codex (see `/research-lit` SKILL.md for
details). Only PASS or PASS_WITH_WARNINGS allows entry to Phase 2.
FAIL stops the pipeline. Audit output stored at
`idea-stage/AGENTIC/EVIDENCE_AUDIT/PHASE1_EVIDENCE_AUDIT.md`.

**Isolation requirement:** evidence_integrity_auditor must run as
`codex_thread` or `manual_subsession`. `protocol_only` is not acceptable
for this gate. Handoff must include `isolation_mode` and `codex_thread_id`
if applicable.

**🚦 Checkpoint:** Present the landscape summary to the user. Ask:

```
📚 Literature survey complete. Here's what I found:
- [key findings, gaps, open problems]

Does this match your understanding? Should I adjust the scope before generating ideas?
(If no response, I'll proceed with the top-ranked direction.)
```

- **User approves** (or no response + AUTO_PROCEED=true) → proceed to Phase 2.
- **User requests changes** → refine the search with updated queries, re-run `/research-lit` with adjusted scope.

### Phase 2: Idea Generation + Dedup

Invoke `/idea-creator` with the landscape context:

```
/idea-creator "$ARGUMENTS"
```

**What this does:**
- Generate 8-12 ideas from the literature landscape and gap map
- Each idea is an independent card: `IDEA_CARDS/idea_NNN.md`
- Run deduplication against existing IDEA_BANK
- Output:
  - `idea-stage/AGENTIC/RUNS/<run_id>/IDEA_CARDS/` — raw cards
  - `idea-stage/AGENTIC/IDEA_BANK.md` — updated index
  - `idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md` — clean candidates

**Quality gate:** If fewer than 3 ideas, mark `needs_review` and stop.

**Codex Gate — Idea Shortlist Audit:** After dedup and canonicalization, run
idea_shortlist_auditor via Codex (see `/idea-creator` SKILL.md for details).
Killed candidates are excluded from Phase 3 onward. Audit output stored at
`idea-stage/AGENTIC/SHORTLIST_AUDIT/PHASE2_SHORTLIST_AUDIT.md`.

**Isolation requirement:** idea_shortlist_auditor must run as
`codex_thread` or `manual_subsession`. `protocol_only` is not acceptable —
it can only yield PASS_WITH_WARNINGS, not full PASS. Handoff must include
Isolation Evidence.

**🚦 Checkpoint:** Present the generated ideas to the user:

```
💡 Generated X ideas, deduplicated to Y canonical candidates.

Top candidates:
1. CAND_001: [title] — [one-line hypothesis]
2. CAND_002: [title] — [one-line hypothesis]
...

Which should I review in depth? Or should I adjust direction?
(If no response, I'll review all active candidates.)
```

### Phase 3: Independent Review (Codex Gate)

For each active canonical candidate, invoke `/exec-review` via Codex:

```
/exec-review "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md"
/exec-review "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_002.md"
```

**Backend:** Codex MCP (via `LLM_IDEA_REVIEWER_PRIMARY=codex`). Fallback to deepseek-v4-pro if Codex unavailable. Default isolation_mode: `codex_thread`.

**Rules:**
- One candidate at a time — reviewer sees only one CAND_*.md
- No generator trace, no previous scores, no user preferences
- Output: `idea-stage/AGENTIC/REVIEWS/CAND_XXX_review.md` with verdict `go | revise | kill`

**Isolation requirement:** review MUST use `codex_thread` or `manual_subsession`. `protocol_only` is not acceptable — cannot yield full PASS. Review artifact header must include `isolation_mode` and `codex_thread_id` if applicable.

**This phase runs ONLY on canonical candidates (CAND_*.md), never on raw IDEA_CARDS.**

**Killed candidates** are excluded from further phases.

### Phase 4: Novelty Check (Codex Gate)

For each `go` or `revise` candidate, run `/novelty-check` via Codex:

```
/novelty-check "CAND_001"
/novelty-check "CAND_002"
```

**Backend:** Codex MCP (via `LLM_NOVELTY_CHECKER_PRIMARY=codex`). Fallback to deepseek-v4-pro if Codex unavailable. Default isolation_mode: `codex_thread`.

**Output:** `idea-stage/AGENTIC/NOVELTY/CAND_XXX_novelty.md`

**Isolation requirement:** novelty check MUST use `codex_thread` or `manual_subsession`. `protocol_only` is not acceptable. Novelty report artifact header must include `isolation_mode` and `codex_thread_id`.

**Verdict options:**
- `confirmed_novel` / `likely_incremental` / `already_done` / `insufficient_evidence`

**This phase runs ONLY on canonical candidates (CAND_*.md).**

Candidates with verdict `already_done` are excluded from further phases.
`insufficient_evidence` cannot enter the `top_idea_found` path.

### Phase 5: Adversarial Review (Codex Gate)

For each surviving candidate (not killed, not `already_done`), run an adversarial critique via Codex:

```
/exec-review "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md" — role: adversarial_reviewer
```

**Backend:** Codex MCP (via `LLM_ADVERSARIAL_REVIEWER_PRIMARY=codex`). Fallback to deepseek-v4-pro if Codex unavailable. Default isolation_mode: `codex_thread`.

**Output:** `idea-stage/AGENTIC/ADVERSARIAL/CAND_XXX_adversarial.md`

**Isolation requirement:** adversarial review MUST use `codex_thread` or `manual_subsession`. `protocol_only` is not acceptable.

The adversarial reviewer identifies only weaknesses — no praise, no improvement suggestions.

### Phase 6: Final Selection (Codex Gate)

The main architect (current Agent) reads only:
- `IDEA_BANK.md` — candidate status overview
- `CANONICAL_IDEAS/CAND_*.md` — candidate descriptions
- `REVIEWS/CAND_*_review.md` — review verdicts
- `NOVELTY/CAND_*_novelty.md` — novelty assessments
- `ADVERSARIAL/CAND_*_adversarial.md` — adversarial critiques

**Backend:** Codex MCP (via `LLM_FINAL_SELECTOR_PRIMARY=codex`). Fallback to deepseek-v4-pro if Codex unavailable. Default isolation_mode: `codex_thread`.

Does NOT read:
- Generator traces or raw run logs
- Job execution details
- Raw `RUNS/<run_id>/IDEA_CARDS/` content
- `CANONICAL_IDEAS/.meta/` (provenance metadata)

**Isolation requirement:** final_selector MUST use `codex_thread` or `manual_subsession`. `protocol_only` is not acceptable. Output must include `isolation_mode` and `codex_thread_id`.

**Output:** `FINAL_SELECTION/IDEA_SELECTION_REPORT.md`

**Allowed conclusions:**
- `top_idea_found: CAND_XXX` — recommended idea with rationale
- `multiple_candidates` — 2+ viable ideas, user decides
- `no strong idea found` — all ideas had fatal flaws or were not novel

If `no strong idea found`, output is a suggestion of alternative research directions, NOT a plan for experiments or papers.

If `insufficient_evidence` is the best novelty verdict, the final selector must NOT promote that candidate to `top_idea_found` — more evidence or literature search is needed first.

### Phase 7: Write Compact Files (when COMPACT = true)

**Skip entirely if `COMPACT` is `false`.**

Write `idea-stage/IDEA_CANDIDATES.md` — a lean summary of surviving ideas suitable for session recovery.

## Optional Follow-Up (User-Driven)

After the pipeline produces a recommendation, the user may choose:

```
# Only if user explicitly asks to proceed:
/research-contract "CAND_XXX"     — lock hypothesis and success criteria
/baseline-repro "baseline"        — establish baseline
/experiment-bridge "plan"         — implement experiments
```

The pipeline does NOT default to any of these. If the user wants to proceed, they must explicitly ask.

## Key Rules

- **Don't skip phases.** Each phase filters and validates — skipping leads to wasted effort.
- **No strong idea found is a legitimate output.** Do not force generation.
- **Kill ideas early.** It's better to kill 10 bad ideas in Phase 3 than to implement one and fail.
- **Reviewer isolation:** each candidate reviewed independently, no cross-contamination.
- If review, novelty, or adversarial phases produce insufficient evidence, allow `no strong idea found`.
- **Document everything.** Dead ends are just as valuable as successes for future reference.
- **Be honest.** Include negative results and failed ideas.
- **AUTO_PROCEED cannot cross the experiment boundary.** Even with AUTO_PROCEED=true, the pipeline never automatically invokes /research-contract, /baseline-repro, or /experiment-bridge. Those require explicit user command.
- **Feishu notifications are optional.** If `~/.claude/feishu.json` exists, send `checkpoint` at each phase transition and `pipeline_done` at final report. If absent/off, skip silently.

## Composing with Workflow 2

After this pipeline produces a validated top idea AND the user explicitly requests to proceed:

```
/idea-discovery "direction"     ← you are here (idea discovery only)
/research-contract "CAND_XXX"  ← only if user asks
/experiment-bridge "plan"      ← only if user asks
/auto-review-loop "scope"       ← Workflow 2
```

Or use `/research-pipeline` for the full end-to-end flow if the user explicitly requests it.

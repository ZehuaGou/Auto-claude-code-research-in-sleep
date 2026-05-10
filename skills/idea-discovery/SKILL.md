---
name: idea-discovery
description: "Workflow 1: Complete idea discovery pipeline. Orchestrates research-lit → idea-creator → exec-review → novelty-check → adversarial review → final selection. Use when user says \"找idea全流程\", \"idea discovery\", \"从零开始找方向\", or wants the complete idea exploration workflow."
argument-hint: [research-direction]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent, Skill, mcp__codex__codex, mcp__codex__codex-reply
---

# Workflow 1: Idea Discovery Pipeline (Recommended Entry Point)

`/idea-discovery` is the **recommended single-command entry point** for the ARIS research idea discovery pipeline. ARIS supports two usage modes:

**Mode A (Recommended):** `/idea-discovery "direction"` — auto-executes Phase 1–6 internally.
**Mode B (Supported):** Manual staged mode — users invoke `/research-lit`, `/idea-creator`, `/exec-review`, `/novelty-check` individually. Each sub-skill still auto-executes its own gate, isolation evidence, and ledger.

Both modes share the same reliability gates. Phase 1–6 are defined consistently regardless of invocation mode.

Orchestrate a complete idea discovery workflow for: **$ARGUMENTS**

## Phase Definitions

| Phase | Name | What happens | Codex Gate? |
|-------|------|-------------|-------------|
| Phase 1 | Literature + Gap Extraction | Research-lit survey → paper-ingest → GAP_MAP generation | Yes: evidence_integrity_auditor |
| Phase 2 | Idea Generation + Shortlist | Raw idea generation → dedup → canonicalization → IDEA_BANK | Yes: idea_shortlist_auditor |
| Phase 3 | Independent Review | Per-CAND review (one CAND at a time), verdict: go/revise/kill | Yes (idea_reviewer uses codex_thread) |
| Phase 4 | Novelty Check | Deep novelty search per active CAND | Yes (novelty_checker uses codex_thread) |
| Phase 5 | Adversarial Review | Weakness-only critique per surviving CAND | Yes (adversarial_reviewer uses codex_thread) |
| Phase 6 | Final Selection | Read all evidence → recommendation | Yes (final_selector uses codex_thread) |

**Gate rules**: FAIL stops the pipeline. PASS_WITH_WARNINGS continues but writes warnings into the next phase's input constraints.

**Codex routing**: All judgment gates resolve routing via `python tools/model_route.py <role>` at invocation time. Three modes (set via `ARIS_CODEX_GATE_MODE` in `.env`):
- `codex_required`: Codex only; fail if unavailable
- `codex_preferred`: Codex first; fallback to DeepSeek V4 Pro with warning
- `deepseek_only`: DeepSeek V4 Pro directly; mark codex_used=false

See `shared-references/model-routing.md` for details.

This pipeline does NOT default to pilot experiments, experiment plans, or paper writing. Those are optional user-driven next steps: `/experiment-bridge`, `/research-contract`, `/baseline-repro`, or `/research-pipeline`.

## Constants

- **AUTO_PROCEED = true** — Auto-proceed at checkpoints if user doesn't respond.
- **REVIEWER_BACKEND = `codex`** — Default for all judgment gates. Routing controlled by `tools/model_route.py`. See `shared-references/model-routing.md`.
- **OUTPUT_DIR = `idea-stage/`** — All idea-stage outputs. Create if absent.
- **COMPACT = false** — When true, generate compact summary files.

> `/idea-discovery` delegates to internal sub-skills but users should invoke only `/idea-discovery` for normal workflow.

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

## Resume / Interruption Recovery

When `/idea-discovery` is interrupted mid-pipeline and the user returns (e.g., "继续", "resume", "next step"), the system MUST recover from artifact file state, not chat context.

### Detection

Use the resume intent detector to confirm resume intent, then check each
phase's artifact state:

```bash
python tools/resume_stage_state.py detect-intent "<user message>"
python tools/resume_stage_state.py research-lit
python tools/resume_stage_state.py idea-creator
python tools/resume_stage_state.py exec-review [CAND]
python tools/resume_stage_state.py novelty-check [CAND]
```

### Recovery Logic

| Situation | Detect by | Resume at |
|-----------|-----------|-----------|
| Phase 1 not done | `python tools/resume_stage_state.py research-lit` shows status != complete | Start Phase 1 (research-lit) |
| Phase 1 done, Phase 2 not | Phase 1 artifacts exist, IDEA_BANK.md missing | Start Phase 2 (idea-creator) |
| Phase 2 partial (no gate) | IDEA_BANK + CAND_*.md exist, no SHORTLIST_AUDIT | Run shortlist audit gate only |
| Phase 2 done, Phase 3 not | All Phase 2 artifacts exist, REVIEWS/ empty | Start Phase 3 (exec-review per CAND) |
| Phase 3 partial | Some reviews exist, some missing | Continue with missing candidates only |
| Phase 3 done, Phase 4 not | All reviews exist, NOVELTY/ empty | Start Phase 4 (novelty-check per CAND) |
| Phase 4 partial | Some novelty reports exist, some missing | Continue with missing candidates only |
| All phases complete | All 4 stages report "complete" | Proceed to final selection or inform user "pipeline complete, choose next action" |

### Hard Rules

- **Do NOT repeat completed phases.** If Phase 1 artifacts exist (LITERATURE_INDEX.md + GAP_MAP.md + evidence audit with PASS verdict), do NOT re-run `/research-lit`.
- **Do NOT re-generate completed reviews.** If a candidate has a validated review file, do NOT re-review it unless the user explicitly asks for a new review.
- **Do NOT re-check novelty for completed candidates.** If a candidate has a canonical novelty report with confirmed verdict, the result stands.
- **Gate re-run is optional.** If IDEA_BANK exists but the shortlist audit was not completed, you may either run just the gate or re-run the full Phase 2. Prefer running just the gate to save time.
- **Source of truth is disk, not chat memory.** Always verify by checking artifact files with `python tools/resume_stage_state.py`. Never assume phase state from conversation context.

## Composing with Workflow 2

After this pipeline produces a validated top idea AND the user explicitly requests to proceed:

```
/idea-discovery "direction"     ← you are here (idea discovery only)
/research-contract "CAND_XXX"  ← only if user asks
/experiment-bridge "plan"      ← only if user asks
/auto-review-loop "scope"       ← Workflow 2
```

Or use `/research-pipeline` for the full end-to-end flow if the user explicitly requests it.

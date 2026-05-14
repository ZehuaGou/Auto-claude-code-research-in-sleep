# Architecture Complexity Audit

**Date:** 2026-05-14
**HEAD:** b60bae8

---

## 1. Purpose

This document evaluates whether the current ARIS-inspired system is overbuilt, which modules should stay, which should be deferred, and which need trimming. The goal is a lean, reliable one-command research automation system — not a bloated framework.

---

## 2. Module Inventory and Classification

### Legend

| Tag | Meaning |
|-----|---------|
| `core_mvp` | Must ship for v1. Directly blocks the one-command goal. |
| `near_term` | Useful within 1-2 phases. Not blocking MVP but high value soon. |
| `optional` | Nice to have. Adds value but not essential for core flow. |
| `deferred` | Should not be built now. Revisit after MVP ships. |
| `risk_of_overengineering` | Currently too heavy or speculative. Needs trimming or replacement with simpler approach. |

### Module Table

| # | Module | Files | Tag | Necessity for Target Doc | User Value | Token Cost | Runtime Complexity | Debuggability | Conflicts with Lightweight ARIS? | Should Build Now? |
|---|--------|-------|-----|--------------------------|------------|------------|-------------------|---------------|----------------------------------|-------------------|
| 1 | **Native Command (research_cli.py)** | `research_cli.py` | `core_mvp` | Critical — Section 5 requires one-command UX | High — eliminates manual command copying | Zero (no model calls in status/validate/continue) | Low — pure Python, no external deps | Easy — self-tests cover 44 cases | No — this IS the lightweight UX | Yes |
| 2 | **Workflow Config** | `configs/workflows/research_default.yaml` | `core_mvp` | Critical — source of truth for stage definitions | Medium — user doesn't touch it directly | Zero | Low — lightweight YAML parser, no PyYAML | Easy — parser is 100 lines | No — declarative config is lightweight | Yes |
| 3 | **Trusted Role Runner** | `tools/trusted_role_runner.py` | `core_mvp` | Critical — all model calls must go through trusted runner | High — trust boundary enforcement | Low (one model call per stage) | Medium — ledger recording, route resolution | Medium — ledger is append-only JSONL | No — original ARIS had trust boundaries | Yes |
| 4 | **Ledger (llm_calls.jsonl)** | `tools/llm_call_ledger.py` | `core_mvp` | Critical — traceability of all model calls | Low (internal) | Zero | Low — append-only file | Easy — JSONL is grep-friendly | No — lightweight append-only log | Yes |
| 5 | **Model Route** | `tools/model_route.py` | `core_mvp` | Critical — role-to-model routing | Low (internal) | Zero | Low — env var lookup | Easy | No | Yes |
| 6 | **Validate Model Invocation** | `tools/validate_model_invocation.py` | `core_mvp` | Critical — post-call verification | Low (internal) | Zero | Low — file checks | Easy | No | Yes |
| 7 | **Context Isolation Check** | `tools/context_isolation_check.py` | `core_mvp` | Critical — forbidden context enforcement | Low (internal) | Zero | Low — string matching | Easy | No | Yes |
| 8 | **Literature Evidence Pipeline** | `tools/literature_evidence_landing.py` | `core_mvp` | Critical — evidence acquisition for any idea | High — multi-source search + full-text | Medium (network I/O, no model calls) | High — 90 self-tests, multiple adapters, full-text store | Medium — large file (7800+ lines) | No — but file size is a concern | Yes, but consider splitting |
| 9 | **Research Status** | `tools/research_status.py` | `optional` | Supplementary — standalone status viewer | Low — research_cli.py status replaces it | Zero | Low | Easy | No — can be deprecated | No — deprecate in favor of CLI |
| 10 | **Research Workflow** | `tools/research_workflow.py` | `core_mvp` | Critical — plan/prepare mechanism for stages | Low (internal) | Zero | Medium — stage preparation logic | Medium | No | Yes |
| 11 | **Idea Pivot** | `configs/workflows/research_default.yaml` (idea_pivot stage) | `near_term` | Important — evidence-grounded pivot when current idea is blocked | High — unblocks blocked research cases | Low (one model call) | Low — follows existing stage pattern | Easy — contract-enforced | No | Yes |
| 12 | **Full-text Review** | `configs/workflows/research_default.yaml` (full_text_review stage) | `near_term` | Important — verifies closest prior work before experiment planning | High — prevents wasted experiments | Low (one model call) | Low — follows existing stage pattern | Easy | No | Yes |
| 13 | **Manual Local Ingestion** | `literature_evidence_landing.py` (ingest-manual-fulltext) | `near_term` | Important — user supplies local papers | Medium — for papers behind paywall | Zero | Low — file copy + metadata | Easy | No | Yes |
| 14 | **Broad Literature Scan** | Proposed, not implemented | `risk_of_overengineering` | Moderate — stronger evidence | High if working, but high risk of scope creep | High (multiple model calls for scan + review) | High — adaptive sizing, clustering, saturation detection | Hard — many tuning parameters | Yes — risks becoming a separate product | No — use adaptive sizing below |
| 15 | **Literature Memory** | Proposed, not implemented | `deferred` | Low for MVP — reading cards suffice | Medium — avoids re-reading same papers | Low (metadata only) | High if database, low if schema-only | Hard if database | Yes — risks becoming a knowledge graph project | No — reading card schema only |
| 16 | **Experiment Plan** | `configs/workflows/research_default.yaml` | `deferred` | Required for full automation, but blocked by current test case | High — but not reachable until evidence gaps closed | Low (one model call) | Low — follows stage pattern | Easy | No | No — blocked by test case |
| 17 | **Implementation Plan** | `configs/workflows/research_default.yaml` | `deferred` | Required for full automation | High — but blocked by experiment_plan | Low | Low | Easy | No | No |
| 18 | **Result Judge** | `configs/workflows/research_default.yaml` | `deferred` | Required for full automation | High — but blocked by implementation | Low | Low | Easy | No | No |
| 19 | **Paper Writing** | `configs/workflows/research_default.yaml` | `deferred` | Required for full automation | High — but blocked by result_judge | Medium (long output) | Low | Easy | No | No |
| 20 | **Alignment Guard** | `tools/alignment_guard.py` | `optional` | Supplementary — monitors alignment during execution | Low | Zero | Low | Easy | No | No — defer |
| 21 | **Exec Review** | `tools/exec_review.py` | `optional` | Supplementary — review execution quality | Low | Zero | Medium | Medium | No | No — defer |
| 22 | **Session Registry** | `tools/session_registry.py` | `optional` | Supplementary — tracks session state | Low | Zero | Low | Easy | No | No — defer |
| 23 | **Resume Stage State** | `tools/resume_stage_state.py` | `optional` | Supplementary — resume interrupted runs | Medium — useful for long runs | Zero | Low | Easy | No | No — defer until live start |
| 24 | **Slash Commands** | `tools/register_slash_commands.py` | `optional` | Nice-to-have — /status, /research-start | Medium — but research_cli.py covers it | Zero | Low | Easy | No | No — defer |
| 25 | **PDF Reader** | `tools/pdf_read.py` | `optional` | Useful for paper reading | Medium | Zero | Low | Easy | No | No — defer |
| 26 | **ArXiv/Crossref/Semantic Scholar Adapters** | `tools/arxiv_fetch.py`, `tools/openalex_fetch.py`, etc. | `core_mvp` (arxiv, openalex, crossref) / `deferred` (semantic_scholar) | Critical for multi-source evidence | High | Medium (network) | Low per adapter | Easy | No | Yes for implemented adapters |
| 27 | **Exa Search** | `tools/exa_search.py` | `deferred` | Optional — web search supplement | Low | Medium (API call) | Low | Easy | No | No |
| 28 | **DeepXiv** | `tools/deepxiv_fetch.py` | `deferred` | Optional — deep paper metadata | Low | Medium (API) | Low | Easy | No | No |
| 29 | **Config Check** | `tools/config_check.py` | `optional` | Supplementary — validates config | Low | Zero | Low | Easy | No | No — defer |
| 30 | **Figure Renderer** | `tools/figure_renderer.py` | `deferred` | Paper writing only | Low | Medium | Medium | Medium | No | No |
| 31 | **Paper Illustration** | `tools/paper_illustration_image2.py` | `deferred` | Paper writing only | Low | Medium | Medium | Medium | No | No |
| 32 | **Paper Ingest** | `tools/paper_ingest.py` | `optional` | Paper reading pipeline | Low | Low | Low | Easy | No | No |
| 33 | **Research Wiki** | `tools/research_wiki.py` | `deferred` | Knowledge base — too heavy for MVP | Low | Medium | High | Hard | Yes — wiki = heavy | No |
| 34 | **Isolated Job Runner** | `tools/isolated_job_runner.py` | `optional` | Sandboxed execution | Low | Low | Medium | Medium | No | No — defer |
| 35 | **Agentic Idea Discovery** | `tools/agentic_idea_discovery.py` | `deferred` | Replaced by idea_pivot stage | Low | Medium | Medium | Easy | No | No |
| 36 | **Generate Codex/Claude Review Overrides** | `tools/generate_codex_claude_review_overrides.py` | `deferred` | Model routing overrides | Low | Zero | Low | Easy | No | No |

---

## 3. Key Findings

### 3.1 What's Working Well

- **research_cli.py** is the right abstraction. One command, zero model calls, self-tested. This is the core product.
- **Workflow config as source of truth** — stages defined in YAML, not hardcoded. Clean separation.
- **Trusted role runner + ledger** — every model call is traceable. No silent model calls.
- **Literature evidence pipeline** — multi-source (arXiv + OpenAlex + Crossref), full-text acquisition, review. 90 self-tests.
- **Stage output contracts** — each trusted output has forbidden phrases, required fields, readiness gates.

### 3.2 What's Too Heavy

- **`literature_evidence_landing.py` is 7800+ lines.** This is the single biggest complexity risk. It contains: query planning, job management, normalization, candidate scoring, top-k selection, full-text acquisition, extraction, store validation, manifest management, review notes, and CLI. This should be split into 3-4 focused modules.

### 3.3 What Should Be Deferred

| Module | Reason |
|--------|--------|
| Broad Literature Scan | High risk of scope creep. Current 10-paper top_k is sufficient for MVP. |
| Literature Memory | Database/knowledge-graph risk. Reading card schema is enough now. |
| Experiment Plan / Implementation / Result Judge / Paper Writing | Blocked by current test case. Build when evidence is sufficient. |
| Research Wiki | Too heavy. Knowledge base is a separate product. |
| Figure Renderer / Paper Illustration | Paper-writing only. Not needed until experiments produce results. |
| Exa Search / DeepXiv / Semantic Scholar | Nice-to-have sources. Current 3 sources are sufficient. |
| Slash Commands | research_cli.py covers the UX. Slash commands add no value. |
| Alignment Guard / Exec Review / Session Registry | Supplementary tools. Not blocking anything. |

---

## 4. Broad Literature Scan: Balanced Approach

The current 10-paper top_k is sufficient for novelty risk assessment. A "broad scan" should be an optional deeper pass, not the default. Here's the balanced approach:

### 4.1 Adaptive Sizing

```yaml
broad_scan:
  sizing: adaptive
  min_papers: 15
  max_papers: 50
  target: "coverage of 80% of relevant work within 2 standard deviations of query relevance"
  stop_rules:
    - type: relevance_decay
      threshold: "3 consecutive papers below 0.3 relevance score"
    - type: cluster_saturation
      threshold: "no new cluster in last 10 papers"
    - type: diminishing_returns
      threshold: "5 papers with same closest_prior_work"
```

### 4.2 Two-Pass Strategy

1. **Pass 1 — Metadata scan** (no full text): Fetch 15-50 papers by title/abstract relevance. Score and cluster. Identify top 10-25 for deep review.
2. **Pass 2 — Deep review** (full text for top 10-25 only): Acquire full text, run trusted review. This is the existing Phase 21 flow.

### 4.3 Low-Yield Handling

If the scan finds fewer than 10 relevant papers:
- Record `low_literature_yield: true` in the evidence summary
- Do NOT fabricate additional papers
- Do NOT broaden the query artificially
- Recommend: "Low literature yield — consider narrowing the research question or checking if this is a genuinely new area"

### 4.4 Over-Supply Handling

If the scan finds more than 50 relevant papers:
- Apply cluster saturation stop rule
- Use relevance decay to trim the tail
- Record `high_literature_density: true` in the evidence summary
- Recommend: "High literature density — consider focusing on the most novel subset"

---

## 5. Literature Memory: Future Scaffold

### 5.1 What NOT to Build

- No SQLite/PostgreSQL/Neo4j database
- No citation graph
- No semantic similarity index
- No knowledge graph
- No entity extraction pipeline

### 5.2 What to Build (Eventually)

A simple **reading card schema** — one markdown file per paper, structured as:

```yaml
---
paper_id: ftq_006
title: "ICR Probe: ..."
authors: [...]
year: 2024
relevance_to_idea: 0.85
closeness_to_our_method: high
key_finding: "uses internal classifier representations for detection"
gap_we_address: "does not use trajectory analysis"
review_date: 2026-05-14
reviewer: full_text_reviewer
---
```

This is a flat file, not a database. It can live in `literature/reading_cards/` and be grep-friendly. No index needed beyond filename conventions.

### 5.3 Why This Is Enough

For an MVP research automation system:
- 10-50 papers per idea is the realistic scope
- A human can scan 50 reading cards in 10 minutes
- Grep across 50 `.md` files is instant
- No query language needed — just `grep "gap_we_address" literature/reading_cards/*.md`

---

## 6. Final Recommendations

### 6.1 Keep Now (core_mvp)

| Module | Action |
|--------|--------|
| research_cli.py | Keep. This is the product. |
| Workflow config | Keep. Source of truth for stages. |
| Trusted role runner + ledger | Keep. Trust boundary. |
| Model route + validator | Keep. Traceability. |
| Context isolation | Keep. Safety boundary. |
| Literature evidence pipeline | Keep, but plan to split `literature_evidence_landing.py` into 3-4 modules in a future refactoring phase. |
| Research workflow (plan/prepare) | Keep. Stage preparation mechanism. |
| arXiv/OpenAlex/Crossref adapters | Keep. Multi-source evidence. |

### 6.2 Build Soon (near_term)

| Module | Action |
|--------|--------|
| Idea pivot stage | Already scaffolded. Complete when current case is blocked. |
| Full-text review stage | Already implemented. Ready to use. |
| Manual local ingestion | Already implemented. Ready to use. |

### 6.3 Don't Build Now (deferred)

| Module | Why Deferred |
|--------|-------------|
| Broad literature scan | Use adaptive sizing approach above when needed. Not now. |
| Literature memory | Reading card schema only. No database. |
| Experiment plan / implementation / result judge / paper writing | Blocked by test case. Build when evidence is sufficient. |
| Research wiki | Too heavy. Separate product. |
| Figure renderer / paper illustration | Paper-writing only. |
| Exa / DeepXiv / Semantic Scholar | Current 3 sources sufficient. |
| Slash commands | CLI covers UX. |
| All supplementary tools | Not blocking anything. |

### 6.4 Minimum Viable Path Forward

1. **Fix `literature_evidence_landing.py` file size** — split into `literature_pipeline.py`, `fulltext_acquisition.py`, `fulltext_store.py`, `cli.py`. Not urgent but should happen before adding more features.

2. **Complete the evidence → idea_pivot → experiment_plan flow** for a different regression test case (one with sufficient literature evidence). The current hallucination trajectory case is blocked by paywall papers and high_risk_overlap — this is a test case limitation, not a system limitation.

3. **Ship one-command live start** — wire `research_cli.py start` to actually execute stages via `trusted_role_runner.py`. This is the single highest-UX-value feature remaining.

4. **Defer everything else** until (a) live start works and (b) a regression test case completes the full flow.

---

## 7. Complexity Budget

The system has **36 Python files** in `tools/`. For an MVP, this is high. The target should be:

| Category | Current | Target | Action |
|----------|---------|--------|--------|
| Core CLI + config | 2 | 2 | Keep |
| Trust boundary (runner, ledger, route, validator, isolation) | 5 | 5 | Keep |
| Literature pipeline | 1 (7800 lines) | 4 (split) | Refactor |
| Workflow engine | 1 | 1 | Keep |
| Adapters (arXiv, OpenAlex, Crossref) | 3 | 3 | Keep |
| Supplementary tools | 24 | 6-8 | Deprecate or archive |
| **Total active** | **36** | **~16** | **Trim 20 files** |

The 20 supplementary files should be archived to `tools/archive/` or deleted. They are not used by the core flow and add cognitive overhead.

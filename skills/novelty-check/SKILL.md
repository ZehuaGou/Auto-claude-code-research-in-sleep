---
name: novelty-check
description: Verify research idea novelty against recent literature. Canonical pipeline mode (CAND_XXX) or ad hoc mode (free-text). Use when user says "查新", "novelty check", or wants to verify a research idea is novel.
argument-hint: [CAND_XXX or free-text idea description]
allowed-tools: WebSearch, WebFetch, Grep, Read, Glob, mcp__codex__codex
---

# Novelty Check Skill

Check whether a proposed method/idea has already been done in the literature: **$ARGUMENTS**

## Two Modes

### Canonical Pipeline Mode (CAND_XXX input)
```
/novelty-check CAND_001
```
System auto-parses CAND_001 to `idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md`.
One CAND at a time. Uses codex_thread. Auto artifact header + ledger.
Output: `idea-stage/AGENTIC/NOVELTY/CAND_001_novelty.md`
Results feed into IDEA_BANK and final selection.

Artifact header must include:
```
mode: canonical_pipeline
isolation_mode: codex_thread|manual_subsession|protocol_only
codex_thread_id: <id>
```

### Ad Hoc Mode (free-text idea description)
```
/novelty-check "a method that uses hidden state transition residuals to detect hallucinations"
```
Allowed for informal exploration. Output must include `mode: ad_hoc` marker.
Output path: `idea-stage/AGENTIC/NOVELTY_ADHOC/<slug>.md` (NOT `NOVELTY/CAND_*.md`)
Results are **NOT** allowed to:
- Enter IDEA_BANK / IDEA_BANK.json
- Be referenced by FINAL_SELECTION
- Produce top_idea_found verdict
- Update canonical CAND status
Formal pipeline decisions must use canonical CAND_XXX mode.

Artifact header must include:
```
mode: ad_hoc
isolation_mode: codex_thread|manual_subsession|protocol_only
```

## Constants

- **REVIEWER_BACKEND = `codex`** — Default: Codex MCP for novelty judgments. See `shared-references/model-routing.md` for fallback model configuration.

## Evidence vs. Contamination

**"Isolation restricts contamination sources, not evidence sources."**

**Allowed neutral evidence:**
- Current CAND file (canonical mode) or user's free-text idea (ad hoc mode)
- LITERATURE_INDEX.md / GAP_MAP.md / PHASE1_EVIDENCE_AUDIT.md
- Relevant literature-md/<paper_id>/
- WebSearch / WebFetch new search results

**Forbidden contamination:**
- IDEA_CARDS raw brainstorming
- Generator trace / RUNS/
- Old praise / user preference / previous scores
- Old review praise / old novelty conclusions
- Other CAND materials

## Instructions

Given a method description, systematically verify its novelty:

### Phase A: Extract Key Claims
1. Read the user's method description
2. Identify 3-5 core technical claims that would need to be novel:
   - What is the method?
   - What problem does it solve?
   - What is the mechanism?
   - What makes it different from obvious baselines?

### Phase B: Multi-Source Literature Search
For EACH core claim, search using ALL available sources:

1. **Web Search** (via `WebSearch`):
   - Search arXiv, Google Scholar, Semantic Scholar
   - Use specific technical terms from the claim
   - Try at least 3 different query formulations per claim
   - Include year filters for 2024-2026

2. **Known paper databases**: Check against:
   - ICLR 2025/2026, NeurIPS 2025, ICML 2025/2026
   - Recent arXiv preprints (2025-2026)

3. **Read abstracts**: For each potentially overlapping paper, WebFetch its abstract and related work section

### Phase C: Cross-Model Verification
Before calling the reviewer, resolve routing via:
```
python tools/model_route.py novelty_checker
```
Parse the output JSON. Follow the resolved route:
- `codex_required`: Use Codex MCP only; fail if unavailable
- `codex_preferred`: Try Codex first; fallback to DeepSeek V4 Pro with warning
- `deepseek_only`: Use DeepSeek V4 Pro directly; mark codex_used=false

Then invoke the reviewer (Codex MCP or LLM chat per route):
```
config: {"model_reasoning_effort": "xhigh"}
```
Prompt should include:
- The proposed method description
- All papers found in Phase B
- Ask: "Is this method novel? What is the closest prior work? What is the delta?"

### Phase D: Novelty Report
Output a structured report:

```markdown
## Novelty Check Report

### Proposed Method
[1-2 sentence description]

### Core Claims
1. [Claim 1] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]
2. [Claim 2] — Novelty: HIGH/MEDIUM/LOW — Closest: [paper]
...

### Closest Prior Work
| Paper | Year | Venue | Overlap | Key Difference |
|-------|------|-------|---------|----------------|

### Overall Novelty Assessment
- Score: X/10
- Recommendation: PROCEED / PROCEED WITH CAUTION / ABANDON
- Key differentiator: [what makes this unique, if anything]
- Risk: [what a reviewer would cite as prior work]

### Suggested Positioning
[How to frame the contribution to maximize novelty perception]
```

### Important Rules
- Be BRUTALLY honest — false novelty claims waste months of research time
- "Applying X to Y" is NOT novel unless the application reveals surprising insights
- Check both the method AND the experimental setting for novelty
- If the method is not novel but the FINDING would be, say so explicitly
- Always check the most recent 6 months of arXiv — the field moves fast

### Canonical Idea Input

This skill supports structured canonical idea input:

**Input formats:**
- `CAND_001` — looks up `idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md`
- `CANONICAL_IDEAS/CAND_001.md` — explicit file path
- Free-text idea description (existing behavior)

**When the input is a CAND_*.md file:**
1. Read ONLY that candidate file + relevant literature sections.
2. Do NOT read:
   - Other candidates in CANONICAL_IDEAS/
   - Generator traces (RUNS/<run_id>/IDEA_CARDS/)
   - Previous novelty scores
   - User preferences or praise
3. Output written to: `idea-stage/AGENTIC/NOVELTY/CAND_XXX_novelty.md`

### Verdict Requirements

The output verdict MUST be one of:
- `confirmed_novel` — clearly novel based on evidence
- `likely_incremental` — incremental contribution, may still be publishable
- `already_done` — same or highly similar work exists
- `insufficient_evidence` — cannot determine from available literature

**Hard Rules:**
- `insufficient_evidence` must NOT be treated as `confirmed_novel`. If evidence is insufficient, state what additional search would be needed.
- `insufficient_evidence` cannot enter final selection's `top_idea_found` path.
- `already_done` must kill or exclude the candidate from further phases.
- `likely_incremental` can only be backup or revise — should not directly become `top_idea_found`, unless the final_selector explicitly explains why the incremental contribution is still worth pursuing.

## Reliability Additions

### Model Routing
novelty 生死判断通过 `tools/model_route.py novelty_checker` 解析路由。
在每次 gate 调用前运行 `python tools/model_route.py novelty_checker`，按照 resolved route 执行：
- `codex_required`: Codex only; fail if unavailable
- `codex_preferred`: Codex first; fallback to DeepSeek V4 Pro with warning
- `deepseek_only`: DeepSeek V4 Pro directly; mark codex_used=false
fallback 输出必须标记 `REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK`。

### Paper Ingest Sections
读取 paper-ingest 输出的 Markdown 章节进行查新，不要直接塞 PDF。
查新按 staged reading 规则读：
- abstract.md + introduction.md 确定背景和问题
- method.md 理解方法细节
- related_work.md 对比最接近工作

### Deep Ingest for Closest Prior Work
- 对 candidate 的 closest prior work，优先读取 `literature-md/<paper_id>/abstract.md`、`introduction.md`、`method.md`、`related_work.md`。
- 如果这些文件不存在或是占位内容（例如 `[Section not extracted]`），先调用 `/paper-ingest <paper_id> --deep`。
- novelty verdict 不得只基于标题/摘要，除非标记 `insufficient_evidence`。
- deep ingest 后使用 `section_index.json` 检查哪些章节有可用内容。

### Structured Verdict
输出必须区分四种 verdict：
- `confirmed_novel` — 确认新颖
- `likely_incremental` — 可能是增量工作
- `already_done` — 已有相同/高度相似工作
- `insufficient_evidence` — 证据不足

### Call Ledger
所有 Codex / LLM 调用写入 `.aris/calls/llm_calls.jsonl`。
不允许 silent fallback。

### Artifact Header
每个 novelty report 输出文件开头必须包含模型追踪 header + 隔离证据：

```
routing_source: env
global_codex_gate_mode: <value from ARIS_CODEX_GATE_MODE>
isolation_mode: manual_subsession|codex_thread|protocol_only
codex_thread_id: <id>|none
task_id: <session task id>|none
allowed_input_files: <exact file list>
forbidden_context_checked: true|false
primary_backend: codex|llm-chat
primary_model: <model name or "DEFAULT">
actual_backend: codex|llm-chat
actual_model: <model name or "DEFAULT">
fallback_used: True|False
fallback_reason: None|<reason>
codex_used: true|false
confidence_downgraded: true|false
```

**隔离要求：**
- 若 `actual_backend=codex`：必须记录 `codex_thread_id`
- 若无 `codex_thread_id` 也无 physical_new_session evidence：isolation_mode 为 `protocol_only`
- `protocol_only` 结果不能作为完全 PASS — 最高 PASS_WITH_WARNINGS
- 缺少 isolation_mode 或 codex_thread_id（当 codex 时）：标记 NEEDS_ISOLATION_EVIDENCE

如果从 Codex fallback 到 LLM，必须额外包含：
```
REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK: true
```

## Review Tracing

After each `mcp__codex__codex` or `mcp__codex__codex-reply` reviewer call, save the trace following `shared-references/review-tracing.md`. Use `tools/save_trace.sh` or write files directly to `.aris/traces/<skill>/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).

## Resume / Interruption Recovery

This skill supports resumption from artifact file state after session interruption.

### Detection

Use `tools/resume_stage_state.py` to detect where Phase 4 left off:

```bash
python3 tools/resume_stage_state.py novelty-check [CAND_XXX]
```

If no candidate is specified, checks all candidates that have completed Phase 3 reviews.

### Required Artifacts

- `NOVELTY/CAND_XXX_novelty.md` — one per candidate with verdict

### Recovery Rules

- **No NOVELTY/ directory or no novelty files found**: Phase 4 not started. Verify Phase 3 reviews exist first (at least one reviewed candidate), then run `/novelty-check CAND_XXX` for each reviewed candidate.
- **Some candidates checked, some missing**: Partial Phase 4. Do NOT re-run novelty-check on completed candidates. Use `tools/resume_stage_state.py novelty-check` to identify which are missing.
- **All candidates with reviews have novelty reports**: Phase 4 is complete. Resume user intent continues to Phase 5 (adversarial review) or Phase 6 (final selection). Do NOT re-run novelty checks.
- **Candidates with `already_done` verdict**: Excluded from further phases. Do NOT include them in adversarial review or final selection.
- **Candidates with `insufficient_evidence`**: Cannot enter `top_idea_found` path. If the user wants to proceed, more literature search is needed first.
- **Canonical vs ad_hoc distinction**: Only `mode: canonical_pipeline` novelty reports (in `NOVELTY/` directory) count toward pipeline progress. Ad hoc reports (in `NOVELTY_ADHOC/`) are informational and do NOT advance the pipeline state.

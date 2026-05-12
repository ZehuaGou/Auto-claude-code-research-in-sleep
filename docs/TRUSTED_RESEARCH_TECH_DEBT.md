# Trusted Research Automation Tech Debt

This file tracks issues deferred for MVP that must be addressed later. Any "fix later" item must be recorded here — not just left in chat history.

## Maintenance Rules

- Every time someone says "fix later", a corresponding entry must be added or updated in this file.
- Before entering a new workflow stage, check this file for blocking tech debt.
- When an item is resolved, do NOT delete it — mark it as Resolved and record the commit hash.
- "Fix later" items left only in chat are not valid — they must be in this file.

---

## P0/P1 Deferred Items

### TD-001 input_normalization output shape
- **Current**: Single file `research/current/input_normalization.md`.
- **Target**: `brief.md` + `candidate_idea.md` as separate outputs.
- **Deferred reason**: Fits current workflow single `output_file` mechanism.
- **Next steps**: Evaluate whether workflow supports multi-output, or keep structured sections in `input_normalization.md`.

### TD-002 Literature layer is still MVP
- **Current**: `literature_search` reads `literature_notes.md` + `literature/search_runs/current/top_k.md`. No query planning, multi-source search, dedup, full-text acquisition, or paper parsing.
- **Target**: Fully operational literature material store with real search, dedup, full-text retrieval, and parsing.
- **Next steps**: Implement search_runs pipeline incrementally — query planning → multi-source search → dedup → acquisition queue → paper parsing.

### TD-003 top_k.md template must not become evidence
- **Status**: MVP resolved; follow-up required.
- **Current**: `top_k.md` is checked by `tools/validate_literature_evidence.py`.
- **Resolved by**:
  - `87ce06b` — added literature evidence validator
  - `42811e9` — fixed block parsing, url/doi, evidence_strength rules
  - `f7c5152` — tightened evidence gap status logic
- **MVP coverage**:
  - `template_only` is blocked.
  - all-no-full-text evidence becomes `insufficient_evidence`.
  - invalid `evidence_strength` becomes `insufficient_evidence`.
  - partial full-text gaps become `valid_with_gaps`.
  - HTML comment templates are not parsed as real papers.
- **Remaining follow-up**:
  - skill-level gate added: `e279d40` — skill SKILL.md now requires validator before novelty_check
  - workflow prepare precheck added: `f4de796` — prepare novelty_check blocks on non-valid evidence
  - valid_with_gaps manual confirmation policy still pending

### TD-004 research_status.py header parsing is permissive
- **Status**: Resolved.
- **Resolved by**: `this commit` — `read_artifact_header()` now only accepts artifact headers when the file's first line is `---`.
- **Change**: Switched from `text.find("---")` to line-by-line parsing that requires the very first line to be `---`.
- **Effect**: Plain markdown section dividers in file body are no longer misidentified as trusted artifact headers.

### TD-005 Literature docs style cleanup
- **Status**: Resolved.
- **Resolved by**: `3d136a9 + this commit` — literature/README.md rewritten in unified English; remaining mixed-language text fixed.

### TD-006 Experiment execution bridge not fully trusted yet
- **Current**: Workflow has `experiment_plan` / `implementation_plan` / `result_judge`, but experiment-bridge, real experiment execution, code review, and result archiving are not yet integrated into the trusted workflow.
- **Target**: `experiment-bridge` strictly connected to the current workflow; no external agent bypass.
- **Next steps**: Design experiment-bridge integration with the trusted workflow; ensure result_judge reads only verified experiment outputs.

### TD-007 Paper audit chain not trusted yet
- **Current**: `paper_writing` stage exists, but `final_paper_auditor` / claim audit / citation audit / `auto-review-loop` are not yet trusted.
- **Target**: Full audit chain trusted before submission.
- **Next steps**: After `result_judge` and `paper_draft` stabilize, design `final_paper_auditor` integration.

### TD-008 WebSearch/WebFetch evidence landing
- **Status**: In progress.
- **Progress**:
  - `tools/literature_evidence_landing.py` added in this commit — provides `validate-raw` and `append-raw` for `raw_results.jsonl` schema.
  - `literature/README.md` updated with evidence landing documentation.
  - `skills/literature-search/SKILL.md` updated with landing tool usage instructions.
- **Remaining**:
  - `raw_results.jsonl` → `candidates.jsonl` pipeline not implemented.
  - `candidates.jsonl` → `top_k.md` pipeline not implemented.
  - Optional: WebFetch extraction helper to parse abstract/metadata from fetched HTML.
  - Dedup and ranking not implemented yet.
  - `manual_acquisition_queue.md` processing not automated.

### TD-009 Legacy AGENTIC status migration
- **Current**: `/status` switched to trusted workflow; `idea-stage/AGENTIC/` is no longer the default main path.
- **Target**: Legacy status available for old projects without mixing into current trusted workflow.
- **Next steps**: If legacy project viewing is still needed, design a `legacy` status mode separate from the current workflow.

---

## Resolved Items

_(No items resolved yet.)_

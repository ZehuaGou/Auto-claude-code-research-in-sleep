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
  - enforce `validate_literature_evidence.py` as a hard pre-check before `novelty_check` can output `confirmed_novel`.
  - decide whether `valid_with_gaps` can proceed to novelty_check or must require manual confirmation.

### TD-004 research_status.py header parsing is permissive
- **Current**: Artifact header parsing uses `text.find("---")`. Plain markdown dividers may be misidentified as trusted headers.
- **Target**: Only accept a trusted artifact header when the file's first line is `---`.
- **Next steps**: Change `read_artifact_header()` in `research_status.py` to require first-line `---`.

### TD-005 Literature docs style cleanup
- **Current**: `literature/README.md` mixes Chinese and English.
- **Target**: Unified documentation language and consistent formatting.
- **Next steps**: Rewrite `literature/README.md` in consistent language.

### TD-006 Experiment execution bridge not fully trusted yet
- **Current**: Workflow has `experiment_plan` / `implementation_plan` / `result_judge`, but experiment-bridge, real experiment execution, code review, and result archiving are not yet integrated into the trusted workflow.
- **Target**: `experiment-bridge` strictly connected to the current workflow; no external agent bypass.
- **Next steps**: Design experiment-bridge integration with the trusted workflow; ensure result_judge reads only verified experiment outputs.

### TD-007 Paper audit chain not trusted yet
- **Current**: `paper_writing` stage exists, but `final_paper_auditor` / claim audit / citation audit / `auto-review-loop` are not yet trusted.
- **Target**: Full audit chain trusted before submission.
- **Next steps**: After `result_judge` and `paper_draft` stabilize, design `final_paper_auditor` integration.

### TD-008 WebSearch/WebFetch evidence landing
- **Current**: WebSearch/WebFetch boundaries are defined in skill docs, but there is no standard evidence landing tool. Results may exist only in chat.
- **Target**: All WebSearch/WebFetch results saved to `raw_results.jsonl` / `candidates.jsonl` / `top_k.md` and pass through `validate_literature_evidence.py` before downstream use.
- **Next steps**: Implement evidence landing workflow; add tool to write WebFetch results to `raw_results.jsonl`.

### TD-009 Legacy AGENTIC status migration
- **Current**: `/status` switched to trusted workflow; `idea-stage/AGENTIC/` is no longer the default main path.
- **Target**: Legacy status available for old projects without mixing into current trusted workflow.
- **Next steps**: If legacy project viewing is still needed, design a `legacy` status mode separate from the current workflow.

---

## Resolved Items

_(No items resolved yet.)_

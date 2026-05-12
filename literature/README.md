# Literature Material Store

This directory holds structured literature evidence for the ARIS trusted research workflow.

## Structure

- `search_runs/` — evidence from each literature search run
  - `current/` — working directory for the current search
    - `search_plan.yaml` — search plan template
    - `raw_results.jsonl` — raw search results (unfiltered)
    - `candidates.jsonl` — candidate papers (pending evaluation)
    - `top_k.md` — structured top-k evidence (trusted workflow input)
- `papers/` — parsed paper materials
- `manual_pdf_drop/` — manual PDF drop location for user-supplied papers
- `manual_acquisition_queue.md` — queue for papers that cannot be auto-retrieved
- `cache/` — subsequent cache

## Current Status

This is a skeleton only. No real search has been conducted.
The files in `search_runs/current/` are templates, not evidence.

## Notes

- `top_k.md` with `status: template_only` is not valid novelty evidence.
- Run `python tools/validate_literature_evidence.py` to check evidence status before use.
- Literature evidence must flow through `literature_search` stage before reaching `novelty_check`.

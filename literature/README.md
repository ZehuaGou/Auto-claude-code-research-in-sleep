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

## Evidence Landing

WebSearch and WebFetch results must not stay only in chat. Paper metadata obtained externally must be saved as local JSONL.

Use `tools/literature_evidence_landing.py`:

```bash
# Append raw records from a local JSONL export to raw_results.jsonl
python tools/literature_evidence_landing.py append-raw \
  --input <local_evidence.jsonl> \
  --run-dir literature/search_runs/current

# Validate raw_results.jsonl
python tools/literature_evidence_landing.py validate-raw \
  --file literature/search_runs/current/raw_results.jsonl

# Build candidates.jsonl from raw_results.jsonl (normalize + dedup)
python tools/literature_evidence_landing.py build-candidates \
  --run-dir literature/search_runs/current

# Validate candidates.jsonl
python tools/literature_evidence_landing.py validate-candidates \
  --file literature/search_runs/current/candidates.jsonl
```

**Data flow**: `raw_results.jsonl` (raw evidence) → `candidates.jsonl` (normalized, deduped) → `top_k.md` (trusted workflow input). `raw_results.jsonl` and `candidates.jsonl` are not novelty verdicts.

## Top-K Evidence Builder

After `candidates.jsonl` is ready, build `top_k.md` with deterministic metadata scoring:

```bash
# Build top_k.md from candidates.jsonl
python tools/literature_evidence_landing.py build-top-k \
  --run-dir literature/search_runs/current \
  --k 10

# Validate the generated top_k.md before novelty_check
python tools/validate_literature_evidence.py \
  --file literature/search_runs/current/top_k.md
```

**What build-top-k does:**
- Selects top-k canonical candidates by metadata completeness score
- Scores: +2 stable_id, +2 abstract, +1 retrieved_at, +1 source=arxiv/openreview/openalex, +1 authors, +1 venue; -2 no abstract, -1 no stable_id
- Generates `top_k.md` with structured evidence blocks
- Does NOT verify full text, does NOT make novelty verdict
- Does NOT set evidence_strength=high automatically

**What build-top-k does NOT do:**
- Does NOT call model APIs or make novelty judgments
- Does NOT verify full_text_available=yes
- Does NOT set confirmed_novel / already_done / likely_incremental
- Does NOT auto-generate relevance_to_research_contract

`top_k.md` with `status: populated_by_tool` is a structured evidence summary, not a novelty verdict. It must pass `validate_literature_evidence.py` before reaching `novelty_check`.

## Notes

- `top_k.md` with `status: template_only` is not valid novelty evidence.
- Run `python tools/validate_literature_evidence.py` to check evidence status before use.
- Literature evidence must flow through `literature_search` stage before reaching `novelty_check`.

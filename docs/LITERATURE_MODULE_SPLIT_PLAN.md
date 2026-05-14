# Literature Module Split Plan

**Date:** 2026-05-14
**HEAD:** b37f933
**Goal:** Reduce `literature_evidence_landing.py` (8002 lines) by extracting safe, self-contained modules.

---

## 1. Current Responsibilities in literature_evidence_landing.py

| # | Responsibility | Lines (approx) | Functions |
|---|---------------|----------------|-----------|
| 1 | JSONL helpers | 88-180 | `_parse_jsonl`, `_write_jsonl`, `_validate_records` |
| 2 | Raw validation | 182-283 | `validate_raw`, `_print_validate_human`, `append_raw` |
| 3 | Title normalization / candidate ID | 285-353 | `_normalize_title`, `_is_title_match`, `_canonical_identity`, `_is_arxiv_doi`, `_candidate_id_from_identity`, `_build_stable_ids`, `_authors_to_list` |
| 4 | Candidate building + validation | 354-670 | `build_candidates`, `validate_candidates`, `_print_validate_candidates_human` |
| 5 | Scoring (relevance + ranking) | 671-821 | `_score_text_relevance`, `_compute_ranking_score`, `_score_candidate` |
| 6 | Top-k selection | 822-1051 | `build_top_k`, `_write_top_k_md` |
| 7 | Query variant generation | 1052-1110 | `_generate_query_variants` |
| 8 | Search plan | 1111-1284 | `build_search_plan`, `validate_search_plan_dict`, `validate_search_plan` |
| 9 | Search jobs | 1285-1528 | `build_search_jobs`, `validate_search_jobs_dict`, `validate_search_jobs`, `init_run_skeleton`, `validate_acquisition_status`, `build_manual_queue` |
| 10 | Run summarization | 1644-1785 | `summarize_run` |
| 11 | Job result validation + normalization | 1786-2116 | `_find_forbidden_verdict_fields`, `validate_job_results_dict`, `validate_job_results`, `normalize_job_results`, `summarize_job_results` |
| 12 | OpenAlex adapter | 2117-2569 | 7 functions |
| 13 | OpenAlex pipeline | 2570-2840 | `run_openalex_pipeline` |
| 14 | arXiv adapter | 2841-3210 | 4 functions |
| 15 | Crossref adapter | 3211-3568 | 4 functions |
| 16 | Multi-source pipeline | 3569-3805 | `_execute_jobs_by_source`, `run_multisource_pipeline` |
| 17 | **Full-text store constants** | 6033-6054 | `VALID_ACQUISITION_STATUSES`, etc. |
| 18 | **Full-text store validation** | 6617-6811 | `validate_fulltext_store` |
| 19 | **Full-text store summary** | 6812-6891 | `summarize_fulltext_store`, `recompute_fulltext_store_summary` |
| 20 | **PDF extraction** | 6958-7025 | `extract_pdf_text` |
| 21 | **extract-fulltext-store command** | 7027-7341 | `extract_fulltext_store` |
| 22 | **Manual local ingestion** | 7342-7500+ | `ingest_manual_fulltext` |
| 23 | Self-test | 3806-6032 | `_self_test` |
| 24 | CLI (argparse) | 7500-8002 | `main()` |

---

## 2. Recommended Module Split

### Target Structure

```
tools/
  literature/
    __init__.py          # Package marker (empty or minimal)
    store.py             # Store validation + summary helpers
    extraction.py        # PDF text extraction
    manual_ingest.py     # Manual local file ingestion
  literature_evidence_landing.py  # CLI facade (all old commands still work)
```

### Module Responsibilities

#### `tools/literature/store.py` (~300 lines)
- Constants: `VALID_ACQUISITION_STATUSES`, `VALID_ACQUISITION_METHODS`, `VALID_EXTRACTION_STATUSES`, `VALID_EXTRACTION_METHODS`, `OPENALEX_HOST_PATTERNS`, `DOI_HOST_PATTERNS`, `VALID_PRIORITIES`
- `validate_fulltext_store(store_path, json_output)`
- `summarize_fulltext_store(store_path, json_output)`
- `recompute_fulltext_store_summary(manifest)`

#### `tools/literature/extraction.py` (~70 lines)
- `extract_pdf_text(pdf_path)`

#### `tools/literature/manual_ingest.py` (~160 lines)
- `ingest_manual_fulltext(store_path, queue_id, local_file, json_output)`
- Depends on: `store.py` (for `recompute_fulltext_store_summary`)

#### `tools/literature_evidence_landing.py` (facade, ~7700 lines → ~7400 lines after extraction)
- All existing functions remain
- Import and re-export from new modules for backward compatibility
- CLI commands unchanged
- Self-test unchanged (tests still call functions in this file)

---

## 3. What Gets Extracted This Round

Only the safest, most self-contained functions:

| Function | Why Safe | Dependencies |
|----------|----------|-------------|
| `extract_pdf_text` | Pure function, no file I/O except reading PDF, no state | None (uses stdlib + optional imports) |
| `validate_fulltext_store` | Reads manifest.json, returns dict. No side effects. | Constants only |
| `summarize_fulltext_store` | Reads manifest.json, returns dict. No side effects. | None |
| `recompute_fulltext_store_summary` | Pure function, takes manifest dict, returns summary dict | None |
| `ingest_manual_fulltext` | Reads/writes manifest+queue. Well-scoped. | `recompute_fulltext_store_summary` |

**NOT extracted this round** (too coupled):
- Search plan / jobs / scoring / top-k (deeply intertwined)
- Source adapters (OpenAlex, arXiv, Crossref) — each is 300+ lines with shared helpers
- `extract_fulltext_store` — calls `extract_pdf_text` + writes to store, medium risk
- Self-test — references everything

---

## 4. Backward Compatibility

All old commands continue to work:

```bash
python tools/literature_evidence_landing.py validate-fulltext-store --store <dir>
python tools/literature_evidence_landing.py summarize-fulltext-store --store <dir>
python tools/literature_evidence_landing.py extract-fulltext-store --store <dir>
python tools/literature_evidence_landing.py ingest-manual-fulltext --store <dir> --queue-id <id> --local-file <path>
python tools/literature_evidence_landing.py --self-test
# ... all other commands unchanged
```

The facade (`literature_evidence_landing.py`) imports from the new modules and delegates. Old code that does `from tools.literature_evidence_landing import validate_fulltext_store` still works.

---

## 5. Schema / Output Invariants

- **manifest.json schema**: unchanged
- **full_text_queue.json schema**: unchanged
- **review_notes.md format**: unchanged
- **CLI output format**: unchanged
- **Self-test behavior**: unchanged (88 tests pass)

---

## 6. What Does NOT Change

- No new CLI commands
- No new stages
- No new model calls
- No changes to trusted_outputs
- No changes to workflow config
- No changes to research_cli.py

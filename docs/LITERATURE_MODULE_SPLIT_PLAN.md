# Literature Module Split Plan

**Date:** 2026-05-14
**HEAD:** dee8671 → pending commit (Round 2 complete)
**Goal:** Continue reducing `literature_evidence_landing.py` by extracting source adapters and scoring helpers.

---

## Round 1 (completed)

Extracted: `store.py`, `extraction.py`, `manual_ingest.py`. Backward-compatible delegation wrappers in place. 88+ self-tests pass.

## Round 2 (completed)

### What was extracted this round

| Module | Functions | Lines (approx) | Risk |
|--------|-----------|----------------|------|
| `tools/literature/adapters/__init__.py` | Package marker | 1 | None |
| `tools/literature/adapters/openalex.py` | 7 functions + constant | ~260 | Low — self-contained HTTP + JSON mapping |
| `tools/literature/adapters/arxiv.py` | 5 functions + 3 constants | ~370 | Low — self-contained HTTP + XML parsing |
| `tools/literature/adapters/crossref.py` | 5 functions + 1 constant | ~370 | Low — self-contained HTTP + JSON mapping |
| `tools/literature/scoring.py` | 10 functions + 6 constants | ~190 | Low — pure functions, no I/O |

**Total extracted:** ~1190 lines from `literature_evidence_landing.py`.

### What stays in literature_evidence_landing.py

| Responsibility | Why it stays |
|----------------|-------------|
| JSONL helpers (`_parse_jsonl`, `_write_jsonl`, `_validate_records`) | Used by 10+ functions across the file |
| Raw validation (`validate_raw`, `append_raw`) | CLI commands, tightly coupled to JSONL helpers |
| Candidate building (`build_candidates`, `validate_candidates`) | Uses scoring helpers but orchestrates JSONL I/O |
| Top-k building (`build_top_k`, `_write_top_k_md`) | Uses scoring helpers but orchestrates JSONL I/O |
| Search plan / jobs (`build_search_plan`, `build_search_jobs`) | CLI commands, medium coupling |
| Job result validation / normalization | CLI commands, uses JSONL helpers |
| `_execute_jobs_by_source` | Dispatcher — imports from adapter modules |
| `run_multisource_pipeline` | Orchestrator — calls all pipeline steps |
| `run_openalex_pipeline` | OpenAlex-specific pipeline orchestrator |
| Self-test | Tests reference all functions |
| CLI (argparse `main()`) | Entry point |
| Full-text acquisition (`acquire_open_fulltext`, `acquire_alternative_fulltext`) | Uses urllib, writes files, tightly coupled to store |
| DOI resolvers (`_resolve_doi_arxiv`, `_resolve_doi_acl_anthology`) | Small helpers, used by `acquire_alternative_fulltext` |
| LaTeX conversion (`_latex_to_markdown`) | Used by `_acquire_arxiv_source` |
| `_parse_top_k_md` | Used by `acquire_open_fulltext` |
| `_check_run_dir_safe` | Used by pipeline orchestrators |
| `_append_jsonl` | Small helper, used by adapters and pipeline |

### Delegation wrappers

Each extracted function gets a thin delegation wrapper in `literature_evidence_landing.py`:

```python
def _normalize_title(title: str) -> str:
    from tools.literature.scoring import _normalize_title as _impl
    return _impl(title)
```

Old code that calls `from tools.literature_evidence_landing import _normalize_title` still works.

### New module structure

```
tools/
  literature/
    __init__.py              # Package marker
    store.py                 # Store validation + summary (Round 1)
    extraction.py            # PDF text extraction (Round 1)
    manual_ingest.py         # Manual local file ingestion (Round 1)
    scoring.py               # Title normalization, dedup, relevance scoring (Round 2)
    adapters/
      __init__.py            # Package marker
      openalex.py            # OpenAlex API adapter (Round 2)
      arxiv.py               # arXiv API adapter (Round 2)
      crossref.py            # Crossref API adapter (Round 2)
  literature_evidence_landing.py  # CLI facade (all old commands still work)
```

### What does NOT change

- No new CLI commands
- No new stages
- No new model calls
- No changes to trusted_outputs
- No changes to workflow config
- No changes to research_cli.py
- No changes to manifest.json / full_text_queue.json schema
- No changes to CLI output format
- Self-test behavior unchanged

### Risk assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Adapter functions use `_append_jsonl` from main file | Low | Each adapter duplicates the 5-line helper or imports from main |
| Scoring functions use hardcoded keyword groups | Low | Groups are domain-specific but functional; generalization is a future task |
| `_execute_jobs_by_source` dispatches to adapter functions | Low | Stays in main file, imports from adapter modules |
| Self-test references extracted functions | Low | Delegation wrappers preserve the same function names |

---

## Future rounds (not now)

| Module | Functions | When |
|--------|-----------|------|
| `tools/literature/multisource.py` | `_execute_jobs_by_source`, `run_multisource_pipeline` | After adapters are stable |
| `tools/literature/acquisition.py` | `acquire_open_fulltext`, `acquire_alternative_fulltext`, DOI resolvers, LaTeX conversion | After full-text flow is tested |
| `tools/literature/validators.py` | `validate_raw`, `validate_candidates`, `validate_job_results`, etc. | After candidate/validator flow is tested |

---

## Backward Compatibility

All old commands continue to work:

```bash
python tools/literature_evidence_landing.py --self-test
python tools/literature_evidence_landing.py validate-fulltext-store --store <dir>
python tools/literature_evidence_landing.py build-search-plan --topic <t> ...
python tools/literature_evidence_landing.py run-openalex-pipeline --topic <t> ...
python tools/literature_evidence_landing.py run-multisource-pipeline --topic <t> ...
# ... all other commands unchanged
```

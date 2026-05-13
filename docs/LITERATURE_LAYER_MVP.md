# Literature Search & Acquisition Layer — MVP Skeleton

**Date:** 2026-05-13
**Target Doc:** `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md` Section 8

---

## What This Is

A schema-level MVP skeleton for the Literature Search & Acquisition Layer. It provides:

- Query planning with deterministic query variant generation (no network calls)
- Search plan validation (no network calls)
- Search job expansion: plan → explicit per-source jobs (no network calls)
- Search job validation (schema check)
- Run skeleton initialization with valid default plans and jobs
- Acquisition status schema validation
- Manual acquisition queue building
- Run summarization (no network calls)
- Self-tests (42 tests, tempfile-based, no network)

This is **not** a full implementation. It has no real search execution, no PDF download, no PDF parsing, no citation dedup/ranking. It only defines the data contracts and validates them.

---

## Pipeline

```
build-search-plan (generate plan + query variants)
  → validate-search-plan (schema check)
  → build-search-jobs (expand plan → per-source jobs)
  → validate-search-jobs (schema check)
  → init-run-skeleton (create run with valid plan + jobs)
  → [source adapters execute jobs → job_results.jsonl]
  → validate-job-results (schema check)
  → normalize-job-results (job_results → raw_results)
  → build-candidates (dedup/rank)
  → build-top-k (select top evidence)
  → validate-acquisition-status (schema check)
  → build-manual-queue (papers needing manual PDF)
  → summarize-run (status overview)
```

---

## Query Planning MVP

Query planning happens before any search execution. It does NOT search the internet, does NOT judge novelty, and does NOT call models.

The `build-search-plan` command generates a validated search plan with deterministic query variants. The output is JSON-formatted content written to `search_plan.yaml` (full YAML parsing is future work).

Query variants are generated deterministically from the topic and `must_include` terms. They are non-exhaustive — real model-generated query planning is future work and must go through `trusted_role_runner` if added.

`init-run-skeleton` now creates a valid default `search_plan.yaml` using the topic as the first `must_include` term and default sources (`arxiv`, `semantic_scholar`, `openalex`, `crossref`). The generated plan validates PASS by default.

`summarize_run` now reports `search_plan_valid` — if the plan exists but is invalid, status is WARN (not PASS).

`validate-search-plan` now rejects novelty verdict fields (`verdict`, `novelty_verdict`, `confirmed_novel`, `already_done`, `likely_incremental`) and checks `start_year <= end_year`.

---

## Search Job Expansion MVP

Search job expansion converts a validated `search_plan.yaml` into explicit per-source search jobs. It does NOT search the internet, does NOT call APIs, does NOT judge novelty, and does NOT call models.

The `build-search-jobs` command expands `query_variants × sources` into job records. Each job is `status: "planned"`, `execution_result: "not_started"`, `network_required: true`. The output `search_jobs.json` is an execution queue for future source adapters.

`init-run-skeleton` now creates `search_jobs.json` alongside `search_plan.yaml`. A fresh skeleton produces valid plan + valid jobs, but since no search has run, `summarize_run` reports WARN.

`summarize_run` now reports `search_jobs_present`, `search_jobs_valid`, `search_job_count`, `planned_job_count`, `executed_job_count`.

Real search execution is handled by source adapters (see Source Adapter Interface below).

---

## Source Adapter Interface MVP

Source adapters are future real-search executors that take jobs from `search_jobs.json` and write results to `job_results.jsonl`. This MVP defines the schema and provides no-network validation/normalization tools. No real search is implemented.

See `docs/LITERATURE_SOURCE_ADAPTERS.md` for full specification.

The `validate-job-results` command validates `job_results.jsonl` against the `source_job_result_v1` schema. Each record represents one executed search job with status (success/empty/failed/rate_limited/auth_failed/blocked), retrieved records, and error info.

The `normalize-job-results` command converts successful job result records into `raw_results.jsonl` format. It is fail-closed: validates input first, validates output second, only writes if both pass.

The `summarize-job-results` command reports status breakdown: per-status counts, total raw records, per-source details.

`init-run-skeleton` now creates an empty `job_results.jsonl` alongside other template files.

`summarize_run` now reports `job_results_present`, `job_results_valid`, `job_result_count`, `successful_job_result_count`, `failed_job_result_count`, `total_raw_records_from_job_results`.

Failed/rate-limited/blocked jobs are valid execution evidence — they are recorded, not hidden. 401/402/403/429/captcha/paywall must not be bypassed.

---

## Commands

### build-search-plan

Generates a search plan with deterministic query variants. No network, no model.

```bash
python tools/literature_evidence_landing.py build-search-plan \
  --topic "hidden state trajectory hallucination detection" \
  --intent novelty_check \
  --must-include "hallucination detection" \
  --must-include "hidden states" \
  --must-include "representation trajectory" \
  --source arxiv \
  --source openalex \
  --source semantic_scholar \
  --start-year 2020 \
  --end-year 2026 \
  --max-results-per-source 50 \
  --exclude "generic anomaly detection unrelated to LLMs" \
  --output search_plan.yaml
```

Output includes: `topic`, `search_intent`, `must_include`, `exclude`, `sources`, `time_range`, `max_results_per_source`, `query_variants`, `notes`.

Query variant rules:
- Deterministic only (no model, no external knowledge)
- Topic itself is the first variant
- Combinations of `must_include` terms
- Limited to 5-10 variants
- Non-exhaustive

### validate-search-plan

Validates a search plan JSON file. Checks required fields, enum values, structural constraints, and rejects novelty verdict fields.

```bash
python tools/literature_evidence_landing.py validate-search-plan --file search_plan.yaml
python tools/literature_evidence_landing.py validate-search-plan --file search_plan.yaml --json
```

Required fields: `topic`, `search_intent`, `must_include`, `sources`, `time_range`, `max_results_per_source`

Additional checks:
- `start_year <= end_year`
- `query_variants` optional, but if present must be a list
- Novelty verdict fields rejected: `verdict`, `novelty_verdict`, `confirmed_novel`, `already_done`, `likely_incremental`

Valid search intents: `idea_discovery`, `novelty_check`, `experiment_plan`, `related_work`

Valid sources: `arxiv`, `semantic_scholar`, `openalex`, `crossref`, `unpaywall`, `openreview`, `conference_site`, `author_homepage`, `github`, `manual`

Note: `search_plan.yaml` currently stores JSON-formatted content. Full YAML parsing is future work. Manual PDFs should go through `manual` source + `manual_acquisition_queue.md` + `literature/manual_pdf_drop/`, not a `local_pdf` source.

### build-search-jobs

Expands a validated search plan into explicit per-source search jobs. No network, no model.

```bash
python tools/literature_evidence_landing.py build-search-jobs \
  --plan search_plan.yaml \
  --output search_jobs.json
```

Each job includes: `job_id`, `source`, `query`, `time_range`, `max_results`, `status` ("planned"), `network_required` (true), `execution_result` ("not_started"), `raw_output_file`, `error`, `notes`.

Job count = `len(sources) × len(query_variants)`. Job IDs are deterministic (`job_<source>_<hash>`). Fail-closed: invalid plan → no output file.

### validate-search-jobs

Validates `search_jobs.json` schema. Checks required fields, source validity, job_id uniqueness, and fixed field values.

```bash
python tools/literature_evidence_landing.py validate-search-jobs --file search_jobs.json
```

### validate-job-results

Validates `job_results.jsonl` against `source_job_result_v1` schema. Checks schema_version, job_id, source, query, status, retrieved_at, raw_record_count consistency, status-specific rules, and rejects novelty verdict fields.

```bash
python tools/literature_evidence_landing.py validate-job-results --file job_results.jsonl
python tools/literature_evidence_landing.py validate-job-results --file job_results.jsonl --json
```

### normalize-job-results

Converts successful job result records into `raw_results.jsonl` format. Fail-closed: validates input, extracts success records, validates output, only writes if all pass.

```bash
python tools/literature_evidence_landing.py normalize-job-results \
  --input job_results.jsonl \
  --output raw_results.jsonl
```

### summarize-job-results

Summarizes `job_results.jsonl`. Reports per-status counts, total raw records, per-source breakdown. No novelty judgment.

```bash
python tools/literature_evidence_landing.py summarize-job-results --file job_results.jsonl --json
```

### init-run-skeleton

Creates a run directory with a valid default search plan and empty template files.

```bash
python tools/literature_evidence_landing.py init-run-skeleton \
  --run-dir tmp/my_run --topic "hallucination detection" --intent novelty_check
```

Creates: `search_plan.yaml` (valid), `search_jobs.json` (valid), `raw_results.jsonl`, `candidates.jsonl`, `top_k.md`, `acquisition_status.json`, `manual_acquisition_queue.md`

Default search plan uses: topic as first `must_include`, default sources (`arxiv`, `semantic_scholar`, `openalex`, `crossref`), deterministic `query_variants`. Jobs are auto-generated from the plan.

### validate-acquisition-status

Validates `acquisition_status.json` schema. Checks paper entries for required fields, enum values, and evidence_gap consistency.

```bash
python tools/literature_evidence_landing.py validate-acquisition-status --file acquisition_status.json
```

Valid full_text_status: `available`, `metadata_only`, `manual_required`, `failed`
Valid parse_status: `not_started`, `parsing`, `parsed`, `failed`, `not_applicable`
Valid parse_quality: `high`, `medium`, `low`, `unknown`

Rule: if `full_text_status` is not `available`, `evidence_gap` must be non-empty.

### build-manual-queue

Builds `manual_acquisition_queue.md` from acquisition status. Only includes papers with `manual_required` or `failed` status.

```bash
python tools/literature_evidence_landing.py build-manual-queue \
  --acquisition-status acquisition_status.json \
  --output manual_acquisition_queue.md
```

### summarize-run

Summarizes a run directory. Reports file presence, record counts, acquisition status breakdown, and overall PASS/WARN/FAIL status.

```bash
python tools/literature_evidence_landing.py summarize-run --run-dir tmp/my_run
python tools/literature_evidence_landing.py summarize-run --run-dir tmp/my_run --json
```

Status logic:
- FAIL: no search_plan
- WARN: search_plan invalid, or search_jobs missing/invalid, or no raw results, or no candidates, or top_k still template_only
- PASS: plan valid, jobs valid, and all downstream files populated

Reports: `search_plan_present`, `search_plan_valid`, `search_jobs_present`, `search_jobs_valid`, `search_job_count`, `planned_job_count`, `executed_job_count`, `job_results_present`, `job_results_valid`, `job_result_count`, `successful_job_result_count`, `failed_job_result_count`, `total_raw_records_from_job_results`, `raw_result_count`, `candidate_count`, `top_k_present`, `acquisition_status_present`, `manual_queue_present`, `manual_required_count`, `full_text_available_count`, `metadata_only_count`.

### --self-test

Runs 42 tempfile-based self-tests covering all commands including query planning, search job expansion, source adapter interface, and pipeline smoke command.

```bash
python tools/literature_evidence_landing.py --self-test
```

---

## Run Directory Structure

```
tmp/<run_name>/
  search_plan.yaml           # JSON search plan
  search_jobs.json           # per-source search job queue
  job_results.jsonl          # source adapter job results (JSONL)
  raw_results.jsonl          # raw search results (JSONL)
  candidates.jsonl           # deduplicated/ranked candidates (JSONL)
  top_k.md                   # top-K evidence summary
  acquisition_status.json    # per-paper acquisition tracking
  manual_acquisition_queue.md # papers needing manual PDF
```

---

## What This Does NOT Do

- No real search execution (arXiv API, Semantic Scholar, OpenAlex)
- No PDF download or parsing
- No citation dedup or ranking
- No model calls
- No network calls
- No trusted execution integration
- No evidence quality judgment

---

## Relationship to Trusted Execution

When real search is implemented, the flow will be:

1. `research_workflow.py prepare literature_search` generates search plan
2. Search agent executes plan, writes raw_results.jsonl
3. `literature_evidence_landing.py` validates and processes results
4. `trusted_role_runner.py` executes literature_scout with validated evidence
5. `validate_model_invocation.py` verifies ledger and call

The MVP skeleton only covers steps 1 and 3 (schema validation). Steps 2, 4, 5 are future work.

# Source Adapter Interface — MVP

**Date:** 2026-05-13

> For operational usage, see [LITERATURE_LAYER_OPERATOR_GUIDE.md](LITERATURE_LAYER_OPERATOR_GUIDE.md).

---

## What This Is

A schema-level interface definition for source adapters that execute search jobs against real APIs. OpenAlex, arXiv, and Crossref adapters are now implemented. Semantic Scholar adapter is planned. The interface provides no-network validation and normalization tools for all adapter output.

Source adapters provide **metadata only** (title, authors, abstract, DOI, etc.). Full-text acquisition is handled separately by the `acquire-open-fulltext` command, which downloads arXiv LaTeX source, arXiv PDF, or open HTML/PDF for papers in the top-k evidence.

---

## Source Adapters

Source adapters are executors that take a job from `search_jobs.json`, call a real API, and write results as a line in `job_results.jsonl`. Each adapter must:

1. Read one job from `search_jobs.json`
2. Call the corresponding API (with proper rate limiting, auth, error handling)
3. Write one `source_job_result_v1` record to `job_results.jsonl`
4. Not fabricate records
5. Not bypass 401/402/403/429/captcha/paywall errors

---

## Pipeline Position

```
search_plan.yaml
  → search_jobs.json
  → job_results.jsonl     ← source adapters write here
  → raw_results.jsonl     ← normalize-job-results converts here
  → candidates.jsonl
  → top_k.md
  → acquisition_status.json
  → manual_acquisition_queue.md
```

---

## Job Result Schema (source_job_result_v1)

Each line in `job_results.jsonl` represents one executed search job:

```json
{
  "schema_version": "source_job_result_v1",
  "job_id": "job_openalex_xxxxxxxx",
  "source": "openalex",
  "query": "LLM hallucination detection hidden states",
  "status": "success",
  "http_status": 200,
  "retrieved_at": "2026-05-13",
  "raw_record_count": 15,
  "records": [ ... ],
  "error": "",
  "notes": ""
}
```

### Valid status values

| status | meaning | constraints |
|--------|---------|-------------|
| `success` | API returned results | `raw_record_count > 0`, `error` empty, every record has source/title/year/url/evidence_origin |
| `empty` | API returned zero results | `raw_record_count == 0`, `records == []` |
| `failed` | Request failed | `raw_record_count == 0`, `records == []`, `error` non-empty |
| `rate_limited` | HTTP 429 or equivalent | `raw_record_count == 0`, `records == []`, `error` non-empty |
| `auth_failed` | HTTP 401/403 | `raw_record_count == 0`, `records == []`, `error` non-empty |
| `blocked` | Captcha, paywall, IP block | `raw_record_count == 0`, `records == []`, `error` non-empty |

### Record schema (inside "records")

Each record must be convertible to `raw_results.jsonl`:

```json
{
  "source": "openalex",
  "title": "...",
  "authors": ["..."],
  "year": 2024,
  "url": "https://openalex.org/W...",
  "doi": "",
  "arxiv_id": "",
  "semantic_scholar_id": "",
  "openalex_id": "W...",
  "abstract": "...",
  "venue": "",
  "retrieved_at": "2026-05-13",
  "evidence_origin": "api_export",
  "notes": "source_job_id=job_openalex_xxxxxxxx; query=..."
}
```

---

## Commands

### validate-job-results

Validates `job_results.jsonl` against `source_job_result_v1` schema.

```bash
python tools/literature_evidence_landing.py validate-job-results --file job_results.jsonl
python tools/literature_evidence_landing.py validate-job-results --file job_results.jsonl --json
```

Exits non-zero on FAIL. No network, no model.

### normalize-job-results

Converts successful job result records into `raw_results.jsonl` format.

```bash
python tools/literature_evidence_landing.py normalize-job-results \
  --input job_results.jsonl \
  --output raw_results.jsonl
```

Fail-closed:
1. Validates `job_results.jsonl` first
2. If validation FAILS → exit non-zero, no output file
3. Extracts only `status == success` records
4. Validates converted records against raw schema
5. If converted records invalid → exit non-zero, no output file
6. Writes `raw_results.jsonl` only if everything passes

Non-success job results (empty, failed, rate_limited, auth_failed, blocked) are valid execution evidence but are NOT converted into paper records.

### summarize-job-results

Summarizes `job_results.jsonl` status breakdown.

```bash
python tools/literature_evidence_landing.py summarize-job-results --file job_results.jsonl --json
```

Output includes: total_jobs, per-status counts, total_raw_records, per-source breakdown.

Status logic:
- FAIL if schema invalid
- WARN if no success jobs but failures/rate limits exist
- PASS if schema valid and at least one success or empty job

No novelty judgment.

---

## OpenAlex Adapter MVP

The OpenAlex adapter is the first implemented source adapter. It executes planned OpenAlex search jobs from `search_jobs.json` and writes `source_job_result_v1` records to `job_results.jsonl`.

### Commands

#### run-openalex-job

Execute a single OpenAlex job by job ID:

```bash
python tools/literature_evidence_landing.py run-openalex-job \
  --job-id job_openalex_xxxxxxxx \
  --search-jobs search_jobs.json \
  --output job_results.jsonl \
  --per-page 5 \
  --mailto user@example.com
```

- Reads `search_jobs.json`, finds job by `job_id`
- Requires `job.source == "openalex"` — rejects non-openalex jobs before any network call
- Executes exactly one job, appends one `source_job_result_v1` line to output
- Validates result before writing (fail-closed)
- No PDF download, no model, no .env

#### run-openalex-jobs

Execute multiple OpenAlex jobs:

```bash
python tools/literature_evidence_landing.py run-openalex-jobs \
  --search-jobs search_jobs.json \
  --output job_results.jsonl \
  --max-jobs 3 \
  --per-page 5 \
  --mailto user@example.com \
  --overwrite
```

- Executes only `source == openalex` jobs
- Respects `--max-jobs` limit
- Appends by default; use `--overwrite` to replace output
- Skips non-openalex jobs silently

### API Details

- **Endpoint:** `https://api.openalex.org/works`
- **Query:** `search=<query>` with `per-page` and `sort=relevance_score:desc`
- **Year filter:** `filter=publication_year:<start>-<end>` when time_range present
- **No API key required** for MVP
- **Optional `--mailto`:** for polite API pool (never from .env)
- **Timeout:** 15 seconds
- **User-Agent:** `literature-evidence-landing/1.0`

### Record Mapping

Each OpenAlex work is mapped to a raw record:

| raw field | OpenAlex source |
|-----------|----------------|
| `source` | `"openalex"` |
| `title` | `display_name` or `title` |
| `authors` | `authorships[].author.display_name` |
| `year` | `publication_year` |
| `url` | `https://openalex.org/<W...>` |
| `doi` | `doi` stripped of `https://doi.org/` prefix |
| `arxiv_id` | `ids.arxiv` if present |
| `openalex_id` | `W...` extracted from `id` URL |
| `abstract` | Reconstructed from `abstract_inverted_index` |
| `venue` | `primary_location.source.display_name` |
| `evidence_origin` | `"api_export"` |

Works with missing/empty `display_name` and `title` are skipped (not fabricated).

### HTTP Status Handling

| HTTP status | job result status |
|-------------|-------------------|
| 200 + results | `success` |
| 200 + empty | `empty` |
| 401 / 403 | `auth_failed` |
| 402 | `blocked` |
| 429 | `rate_limited` |
| other | `failed` |
| timeout / network error | `failed` |

### Normalization Path

```
search_jobs.json
  → run-openalex-job / run-openalex-jobs
  → job_results.jsonl (source_job_result_v1 records)
  → validate-job-results
  → normalize-job-results
  → raw_results.jsonl
  → validate-raw
```

#### run-openalex-pipeline

Run the full OpenAlex pipeline from topic to top-k:

```bash
python tools/literature_evidence_landing.py run-openalex-pipeline \
  --topic "LLM hallucination detection hidden states" \
  --intent novelty_check \
  --must-include "hallucination detection" \
  --must-include "hidden states" \
  --run-dir tmp/my_run \
  --start-year 2020 \
  --end-year 2026 \
  --max-results-per-source 10 \
  --max-jobs 3 \
  --per-page 5 \
  --top-k 5 \
  --json
```

Pipeline steps (fail-closed):
1. `build_search_plan` → search_plan.yaml
2. `build_search_jobs` → search_jobs.json
3. (dry-run stops here)
4. `run_openalex_jobs` → job_results.jsonl
5. `validate_job_results` → check job_results.jsonl
6. `normalize_job_results` → raw_results.jsonl
7. `validate_raw` → check raw_results.jsonl
8. `build_candidates` → candidates.jsonl
9. `validate_candidates` → check candidates.jsonl
10. `build_top_k` → top_k.md
11. `summarize_run` → final summary

Options:
- `--dry-run`: Stop after plan + jobs (no network)
- `--overwrite`: Overwrite job results instead of append
- `--mailto`: Optional email for OpenAlex polite pool
- `--exclude`: Exclusion terms for query planning

Any step failure stops the pipeline and returns JSON with `failed_step` and `errors`.

---

## arXiv Adapter MVP

The arXiv adapter executes planned arXiv search jobs from `search_jobs.json` and writes `source_job_result_v1` records to `job_results.jsonl`.

### Commands

#### run-arxiv-job

Execute a single arXiv job by job ID:

```bash
python tools/literature_evidence_landing.py run-arxiv-job \
  --job-id job_arxiv_xxxxxxxx \
  --search-jobs search_jobs.json \
  --output job_results.jsonl \
  --max-results 5
```

- Reads `search_jobs.json`, finds job by `job_id`
- Requires `job.source == "arxiv"` — rejects non-arxiv jobs before any network call
- Executes exactly one job, appends one `source_job_result_v1` line to output
- Validates result before writing (fail-closed)
- No PDF download, no model, no .env

#### run-arxiv-jobs

Execute multiple arXiv jobs:

```bash
python tools/literature_evidence_landing.py run-arxiv-jobs \
  --search-jobs search_jobs.json \
  --output job_results.jsonl \
  --max-jobs 3 \
  --max-results 5 \
  --overwrite
```

- Executes only `source == arxiv` jobs
- Respects `--max-jobs` limit
- Appends by default; use `--overwrite` to replace output

### API Details

- **Endpoint:** `http://export.arxiv.org/api/query`
- **Query:** `search_query=all:<query>` with `max_results` and `sortBy=relevance`
- **Response format:** Atom XML
- **No API key required**
- **Timeout:** 20 seconds
- **User-Agent:** `literature-evidence-landing/1.0`
- **Rate limit:** arXiv recommends 3 second delay between requests

### Record Mapping

Each arXiv entry is mapped to a raw record:

| raw field | arXiv source |
|-----------|-------------|
| `source` | `"arxiv"` |
| `title` | `<title>` |
| `authors` | `<author><name>` list |
| `year` | Extracted from `<published>` |
| `url` | `<id>` (abs page, not PDF) |
| `doi` | `<doi>` if present |
| `arxiv_id` | Extracted from `<id>` URL |
| `abstract` | `<summary>` |
| `venue` | `"arXiv"` |
| `evidence_origin` | `"api_export"` |

### HTTP Status Handling

| HTTP status | job result status |
|-------------|-------------------|
| 200 + results | `success` |
| 200 + empty | `empty` |
| 401 / 403 | `auth_failed` |
| 429 | `rate_limited` |
| other | `failed` |
| timeout / network error | `failed` |

---

## Crossref Adapter MVP

The Crossref adapter executes planned Crossref search jobs from `search_jobs.json` and writes `source_job_result_v1` records to `job_results.jsonl`.

### Commands

#### run-crossref-job

Execute a single Crossref job by job ID:

```bash
python tools/literature_evidence_landing.py run-crossref-job \
  --job-id job_crossref_xxxxxxxx \
  --search-jobs search_jobs.json \
  --output job_results.jsonl \
  --rows 5
```

- Reads `search_jobs.json`, finds job by `job_id`
- Requires `job.source == "crossref"` — rejects non-crossref jobs before any network call
- Executes exactly one job, appends one `source_job_result_v1` line to output
- Validates result before writing (fail-closed)
- No PDF download, no model, no .env

#### run-crossref-jobs

Execute multiple Crossref jobs:

```bash
python tools/literature_evidence_landing.py run-crossref-jobs \
  --search-jobs search_jobs.json \
  --output job_results.jsonl \
  --max-jobs 3 \
  --rows 5 \
  --overwrite
```

- Executes only `source == crossref` jobs
- Respects `--max-jobs` limit
- Appends by default; use `--overwrite` to replace output

### API Details

- **Endpoint:** `https://api.crossref.org/works`
- **Query:** `query=<query>` with `rows` and `sort=relevance`
- **Year filter:** `filter=from-pub-date:<start>,until-pub-date:<end>` when time_range present
- **No API key required** for MVP (polite pool optional)
- **Timeout:** 15 seconds
- **User-Agent:** `literature-evidence-landing/1.0 (mailto:research@example.com)`

### Record Mapping

Each Crossref work is mapped to a raw record:

| raw field | Crossref source |
|-----------|----------------|
| `source` | `"crossref"` |
| `title` | `title[0]` |
| `authors` | `author[].given + family` |
| `year` | Extracted from `published-print` or `published-online` date-parts |
| `url` | `URL` or constructed from DOI |
| `doi` | `DOI` |
| `abstract` | `abstract` (HTML tags stripped) |
| `venue` | `container-title[0]` |
| `evidence_origin` | `"api_export"` |

Works with missing/empty `title` are skipped (not fabricated).

### HTTP Status Handling

| HTTP status | job result status |
|-------------|-------------------|
| 200 + results | `success` |
| 200 + empty | `empty` |
| 401 / 403 | `auth_failed` |
| 429 | `rate_limited` |
| other | `failed` |
| timeout / network error | `failed` |

---

## Multi-source Pipeline

The multi-source pipeline runs all three adapters in a single command:

```bash
python tools/literature_evidence_landing.py run-multisource-pipeline \
  --topic "LLM hallucination detection hidden states" \
  --intent novelty_check \
  --must-include "hallucination detection" \
  --must-include "hidden states" \
  --run-dir tmp/my_run \
  --sources arxiv \
  --sources crossref \
  --sources openalex \
  --start-year 2020 \
  --end-year 2026 \
  --max-results-per-source 10 \
  --max-jobs 36 \
  --per-page 5 \
  --top-k 10 \
  --overwrite \
  --json
```

Pipeline steps:
1. `build_search_plan` → search_plan.yaml
2. `build_search_jobs` → search_jobs.json (generates jobs for all requested sources)
3. (dry-run stops here)
4. `execute_jobs_by_source` → dispatches jobs to appropriate adapter by source type
5. `validate_job_results` → check job_results.jsonl
6. `normalize_job_results` → raw_results.jsonl
7. `validate_raw` → check raw_results.jsonl
8. `build_candidates` → candidates.jsonl (cross-source dedup by DOI, arXiv ID, normalized title)
9. `validate_candidates` → check candidates.jsonl
10. `build_top_k` → top_k.md

Options:
- `--dry-run`: Stop after plan + jobs (no network)
- `--overwrite`: Overwrite job results instead of append
- `--sources`: Repeatable, default: arxiv crossref openalex
- `--max-jobs`: Total jobs across all sources (default: 9)
- `--exclude`: Exclusion terms for query planning

---

## Rules for Future Adapters

1. **No fabrication.** Every record in `records` must come from the API response.
2. **No bypass.** 401/402/403/429/captcha/paywall must be recorded as failures, not worked around.
3. **No API key leakage.** Do not embed credentials in job result artifacts.
4. **Record failures.** Failed/rate-limited/blocked jobs must be written to `job_results.jsonl` with non-empty `error`, not silently dropped.
5. **Manual access belongs elsewhere.** Papers needing manual PDF go through `manual` source + `manual_acquisition_queue.md` + `literature/manual_pdf_drop/`.
6. **Auditable.** Every adapter call must produce a traceable `job_results.jsonl` entry.

---

## Adapters

| adapter | source | API | status | notes |
|---------|--------|-----|--------|-------|
| OpenAlex adapter | `openalex` | OpenAlex Works API | **implemented** | free, no key required |
| arXiv adapter | `arxiv` | arXiv Atom XML API | **implemented** | free, rate-limited |
| Crossref adapter | `crossref` | Crossref REST API | **implemented** | free, polite pool optional |
| Semantic Scholar adapter | `semantic_scholar` | S2 API | planned | free, aggressive rate limits |

---

## What This Does NOT Do

- No PDF download or parsing
- No model calls
- No novelty judgment
- No citation dedup or ranking (those happen downstream in build-candidates)
- No Semantic Scholar adapter yet
- No API key requirement (OpenAlex is free, arXiv/Crossref free tier)

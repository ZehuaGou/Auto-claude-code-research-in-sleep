# Source Adapter Interface — MVP

**Date:** 2026-05-13

---

## What This Is

A schema-level interface definition for source adapters that execute search jobs against real APIs. The OpenAlex adapter is now implemented. arXiv, Crossref, and Semantic Scholar adapters are planned. The interface provides no-network validation and normalization tools for all adapter output.

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
| arXiv adapter | `arxiv` | arXiv API | planned | free, rate-limited |
| Crossref adapter | `crossref` | Crossref REST API | planned | free, polite pool with key |
| Semantic Scholar adapter | `semantic_scholar` | S2 API | planned | free, aggressive rate limits |

---

## What This Does NOT Do

- No PDF download or parsing
- No model calls
- No novelty judgment
- No citation dedup or ranking (those happen downstream in build-candidates)
- No arXiv/Crossref/Semantic Scholar adapters yet
- No API key requirement (OpenAlex is free)

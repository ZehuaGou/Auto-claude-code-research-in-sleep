# Source Adapter Interface — MVP

**Date:** 2026-05-13

---

## What This Is

A schema-level interface definition for future source adapters that will execute search jobs against real APIs (OpenAlex, arXiv, Crossref, Semantic Scholar). This MVP does NOT implement real search. It only defines the data contract and provides no-network validation and normalization tools.

---

## Source Adapters Are Future Components

Source adapters are executors that take a job from `search_jobs.json`, call a real API, and write results as a line in `job_results.jsonl`. No source adapter is implemented yet. When implemented, each adapter must:

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

## Rules for Future Adapters

1. **No fabrication.** Every record in `records` must come from the API response.
2. **No bypass.** 401/402/403/429/captcha/paywall must be recorded as failures, not worked around.
3. **No API key leakage.** Do not embed credentials in job result artifacts.
4. **Record failures.** Failed/rate-limited/blocked jobs must be written to `job_results.jsonl` with non-empty `error`, not silently dropped.
5. **Manual access belongs elsewhere.** Papers needing manual PDF go through `manual` source + `manual_acquisition_queue.md` + `literature/manual_pdf_drop/`.
6. **Auditable.** Every adapter call must produce a traceable `job_results.jsonl` entry.

---

## Planned Adapters

| adapter | source | API | notes |
|---------|--------|-----|-------|
| OpenAlex adapter | `openalex` | OpenAlex Works API | free, no key required |
| arXiv adapter | `arxiv` | arXiv API | free, rate-limited |
| Crossref adapter | `crossref` | Crossref REST API | free, polite pool with key |
| Semantic Scholar adapter | `semantic_scholar` | S2 API | free, aggressive rate limits |

---

## What This Does NOT Do

- No real search execution
- No API calls
- No PDF download or parsing
- No model calls
- No novelty judgment
- No citation dedup or ranking (those happen downstream in build-candidates)

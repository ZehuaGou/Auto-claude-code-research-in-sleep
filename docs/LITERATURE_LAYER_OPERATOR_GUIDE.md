# Literature Layer Operator Guide

**Date:** 2026-05-13
**Target Doc:** `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md` Section 8

---

## 1. Purpose

This guide documents how to operate the Literature Layer MVP.

**What this layer does:**
- Generates search plans with deterministic query variants
- Expands plans into per-source search jobs
- Executes search jobs via OpenAlex, arXiv, and Crossref adapters
- Validates and normalizes search results
- Builds deduplicated candidates and top-k evidence summaries
- Supports multi-source pipeline with cross-source dedup

**What this layer does NOT do:**
- It does not replace `trusted_role_runner`
- It does not produce novelty verdicts
- It does not produce research trusted outputs
- It does not call models
- It does not bypass paywalls
- It does not commit PDFs or full extracted text
- It only prepares auditable literature evidence

---

## 2. Current Pipeline

```
search_plan.yaml
  → search_jobs.json
  → job_results.jsonl
  → raw_results.jsonl
  → candidates.jsonl
  → top_k.md
  → acquisition_status.json
  → manual_acquisition_queue.md
```

| File | Description |
|------|-------------|
| `search_plan.yaml` | Search plan with topic, intent, must_include terms, sources, time range, query variants |
| `search_jobs.json` | Expanded per-source search jobs (source × query_variant) |
| `job_results.jsonl` | Source adapter execution results (one line per executed job) |
| `raw_results.jsonl` | Normalized paper records extracted from successful job results |
| `candidates.jsonl` | Deduplicated candidates with canonical IDs and duplicate tracking |
| `top_k.md` | Top-K evidence summary (deterministic metadata completeness score) |
| `acquisition_status.json` | Per-paper full-text acquisition tracking |
| `manual_acquisition_queue.md` | Papers requiring manual PDF acquisition |

---

## 3. Command Categories

### No-network / no-model commands

These commands run entirely locally. They validate schemas, generate plans, expand jobs, and process results. No API calls, no model calls, no network access.

| Command | Purpose |
|---------|---------|
| `build-search-plan` | Generate search plan with deterministic query variants |
| `validate-search-plan` | Validate search plan schema |
| `build-search-jobs` | Expand plan into per-source jobs |
| `validate-search-jobs` | Validate search jobs schema |
| `validate-job-results` | Validate job_results.jsonl schema |
| `normalize-job-results` | Convert successful job results to raw_results.jsonl |
| `validate-raw` | Validate raw_results.jsonl schema |
| `build-candidates` | Deduplicate and rank into candidates.jsonl |
| `validate-candidates` | Validate candidates.jsonl schema |
| `build-top-k` | Select top-K candidates into top_k.md |
| `validate-acquisition-status` | Validate acquisition_status.json schema |
| `build-manual-queue` | Build manual acquisition queue from acquisition status |
| `summarize-run` | Summarize run directory status |
| `summarize-job-results` | Summarize job_results.jsonl status breakdown |
| `init-run-skeleton` | Create empty run skeleton with valid defaults |
| `run-openalex-pipeline --dry-run` | Pipeline stopped after plan + jobs (no network) |
| `run-multisource-pipeline --dry-run` | Multi-source pipeline stopped after plan + jobs (no network) |

### Network commands

These commands call real APIs (OpenAlex, arXiv, Crossref). They do NOT call models. Full-text acquisition downloads legally accessible open-access content only.

| Command | Purpose |
|---------|---------|
| `run-openalex-job` | Execute one OpenAlex search job |
| `run-openalex-jobs` | Execute multiple OpenAlex search jobs |
| `run-openalex-pipeline` (without `--dry-run`) | Full pipeline including OpenAlex execution |
| `run-arxiv-job` | Execute one arXiv search job |
| `run-arxiv-jobs` | Execute multiple arXiv search jobs |
| `run-crossref-job` | Execute one Crossref search job |
| `run-crossref-jobs` | Execute multiple Crossref search jobs |
| `run-multisource-pipeline` (without `--dry-run`) | Full multi-source pipeline (arXiv+Crossref+OpenAlex) |
| `acquire-open-fulltext` | Acquire open-access full text (arXiv source/PDF, open HTML/PDF) |
| `validate-fulltext-store` | Validate full-text store manifest |
| `summarize-fulltext-store` | Summarize full-text store status |

---

## 4. Safe Dry Run

Use `--dry-run` to validate plan and job generation without network calls:

```bash
python tools/literature_evidence_landing.py run-multisource-pipeline \
  --topic "LLM hallucination detection hidden states" \
  --intent novelty_check \
  --must-include "hallucination detection" \
  --must-include "hidden states" \
  --run-dir tmp/multisource_dry_run \
  --sources arxiv \
  --sources crossref \
  --sources openalex \
  --start-year 2020 \
  --end-year 2026 \
  --max-results-per-source 5 \
  --max-jobs 9 \
  --per-page 2 \
  --top-k 5 \
  --dry-run \
  --overwrite \
  --json
```

**Expected files created:**
- `search_plan.yaml` — search plan with query variants
- `search_jobs.json` — expanded per-source jobs

**Files NOT created (no network):**
- `job_results.jsonl`
- `raw_results.jsonl`
- `candidates.jsonl`
- `top_k.md`

---

## 5. Live Multi-source Smoke Run

Run the full pipeline with real API calls (arXiv + Crossref + OpenAlex):

```bash
python tools/literature_evidence_landing.py run-multisource-pipeline \
  --topic "LLM hallucination detection hidden states" \
  --intent novelty_check \
  --must-include "hallucination detection" \
  --must-include "hidden states" \
  --run-dir tmp/multisource_pipeline_smoke \
  --sources arxiv \
  --sources crossref \
  --sources openalex \
  --start-year 2020 \
  --end-year 2026 \
  --max-results-per-source 5 \
  --max-jobs 9 \
  --per-page 2 \
  --top-k 5 \
  --overwrite \
  --json
```

**Validation after live run:**

```bash
python tools/literature_evidence_landing.py summarize-run \
  --run-dir tmp/multisource_pipeline_smoke --json

python tools/literature_evidence_landing.py validate-job-results \
  --file tmp/multisource_pipeline_smoke/job_results.jsonl

python tools/literature_evidence_landing.py validate-raw \
  --file tmp/multisource_pipeline_smoke/raw_results.jsonl

python tools/literature_evidence_landing.py validate-candidates \
  --file tmp/multisource_pipeline_smoke/candidates.jsonl
```

**Important:**
- Live run may fail due to network issues, HTTP 429 (rate limit), or HTTP 403 (blocked)
- Do not bypass rate limits or auth failures
- Record failures in job_results.jsonl (they are valid execution evidence)
- Delete tmp run after testing unless explicitly needed

---

## 6. Full-text Acquisition

### Open-access full-text acquisition

Acquire legally accessible full text for top-k papers:

```bash
python tools/literature_evidence_landing.py acquire-open-fulltext \
  --top-k literature/search_runs/current/top_k.md \
  --output-dir literature/full_text_store/current \
  --prefer-latex --allow-arxiv-pdf --allow-open-html --allow-open-pdf \
  --max-items 10 --overwrite --json
```

**Acquisition priority:**
1. arXiv LaTeX source (preferred — preserves structure, formulas, citations)
2. arXiv PDF fallback (if source not available)
3. Open HTML/PDF from direct URL (non-arXiv papers)
4. Manual queue (if no legal automatic access)

**Where files go:**
- Downloaded PDFs: `raw_pdfs/` (gitignored)
- Downloaded HTML: `raw_html/` (gitignored)
- Downloaded LaTeX sources: `raw_sources/` (gitignored)
- Extracted text: `extracted_text/` (gitignored)
- Extracted Markdown: `extracted_markdown/` (gitignored)

**Why gitignored:** Raw downloads and extracted full text are local evidence-support material. They must not be committed to git (copyright, reproducibility, repository size).

**How to manually add missing PDFs:** Place the PDF in `raw_pdfs/<queue_id>.pdf` or `manual_sources/<queue_id>.pdf`, then update `review_notes.md`.

### Validate and summarize store

```bash
python tools/literature_evidence_landing.py validate-fulltext-store \
  --store literature/full_text_store/current

python tools/literature_evidence_landing.py summarize-fulltext-store \
  --store literature/full_text_store/current --json
```

**Understanding full_text_status:**

| Status | Meaning | Can provide evidence after review? |
|--------|---------|-----------------------------------|
| `source_acquired_unreviewed` | arXiv LaTeX source downloaded, rough Markdown extraction done | Yes (after human review) |
| `likely_full_text` | PDF downloaded, likely contains full text | Yes (after extraction + review) |
| `metadata_page_only` | OpenAlex metadata page, NOT full text | No — need alternative source |
| `landing_page_only` | DOI/publisher landing page, NOT full text | No — need alternative source |
| `manual_required` | Could not be acquired automatically | No — need manual acquisition |

**Critical distinction:** `acquired` does NOT mean `full_text_available`. OpenAlex URLs are metadata pages, not full text. DOI landing pages are typically not full text. Only arXiv LaTeX source and arXiv PDF provide actual full text potential.

### Extract PDF text (Phase 21C)

Extract text from PDFs in the full-text store that have not been extracted:

```bash
python tools/literature_evidence_landing.py extract-fulltext-store \
  --store literature/full_text_store/current \
  --only-missing --json
```

**Requirements:** Install one of: pymupdf, pypdf, pdfminer.six

**Behavior:** If no PDF extraction library is installed, returns `tool_missing` status with install suggestions.

### Acquire alternative full text (Phase 21C)

Acquire alternative open-access full text for non-reviewable papers via DOI resolvers:

```bash
python tools/literature_evidence_landing.py acquire-alternative-fulltext \
  --store literature/full_text_store/current \
  --target-status metadata_page_only \
  --target-status landing_page_only \
  --allow-arxiv --allow-acl-anthology \
  --allow-open-pdf --allow-open-html --json
```

**Supported resolvers:**
- arXiv DOI: `10.48550/arxiv.xxxx` → arXiv source/PDF
- ACL Anthology DOI: `10.18653/v1/...` → ACL Anthology PDF

**Limitations:**
- arXiv downloads may timeout in China (use VPN/proxy)
- IEEE/ACM/publisher DOIs not auto-resolved (paywall protection)
- Papers with no safe open-access path marked as `no_resolver_matched`

---

## 6. Runtime File Policy

| Path | Policy |
|------|--------|
| `tmp/*` | Runtime. Never commit. |
| `literature/search_runs/current/*` | Runtime unless explicitly staged by an approved task. |
| `research/*` | Trusted workflow area. Literature layer commands must not write there. |
| `.aris/*` | Ledger/runtime. Never commit. |
| `.env` | Credentials. Never commit. |

**Rules:**
- Do not use `git add .`
- Always check `git status --short` before committing
- Only commit documentation and code changes from approved tasks
- Runtime evidence files (job_results.jsonl, raw_results.jsonl, etc.) belong in tmp/ or explicitly approved run directories

---

## 7. What These Artifacts Are Not

| Artifact | What it is NOT |
|----------|---------------|
| `top_k.md` | NOT a novelty_check verdict |
| `raw_results.jsonl` | NOT a conclusion |
| `candidates.jsonl` | NOT a literature review |
| `job_results.jsonl` | NOT a scientific judgment |
| `search_plan.yaml` | NOT a research plan |

**This layer cannot say:**
- "novel"
- "no prior work"
- "confirmed novel"
- "direct overlap none"
- "likely incremental"

**Novelty judgment belongs ONLY to the novelty_check stage**, which requires:
- Valid top_k.md evidence
- trusted_role_runner execution
- validate_model_invocation PASS
- Proper artifact headers and ledger entries

---

## 8. Handoff to Trusted Workflow

Literature evidence can later be promoted into the official run directory only under an explicit aligned task.

**Requirements for trusted literature_search stage:**
- `trusted_role_runner` execution
- `validate_model_invocation` PASS
- Proper artifact headers
- Ledger entries
- Model route configuration
- Context isolation check
- Validator PASS

**Evidence files alone do NOT grant:**
- `allowed_next_stage` permission
- Trusted output status
- Novelty verdict authority

---

## 9. Failure Handling

| HTTP Status | Job Result Status | Action |
|-------------|-------------------|--------|
| 401 / 403 | `auth_failed` | Record failure. Do not retry with different credentials. |
| 402 | `blocked` | Record failure. Do not bypass paywall. |
| 429 | `rate_limited` | Record failure. Respect rate limits. |
| timeout / network error | `failed` | Record failure. Do not retry endlessly. |

**Rules:**
- Do not bypass 401/402/403/429/captcha/paywall errors
- Do not use cookies or login workarounds
- Do not fabricate missing records
- Failed jobs remain valid execution evidence if recorded properly in job_results.jsonl

---

## 10. Operator Checklist

### Before run

- [ ] `git status --short` shows clean working tree
- [ ] Using `tmp/` as run-dir (never `research/` or `literature/`)
- [ ] Using `--dry-run` first to validate plan
- [ ] Not committing runtime files

### After run

- [ ] `validate-job-results` PASS
- [ ] `normalize-job-results` PASS (if converting to raw_results)
- [ ] `validate-raw` PASS
- [ ] `validate-candidates` PASS
- [ ] `summarize-run` PASS
- [ ] Delete tmp run unless intentionally preserving
- [ ] `git status` shows no runtime files

---

## 11. Current Limitations

- **Semantic Scholar adapter deferred** — aggressive rate limits
- **Full-text extraction quality is rough** — LaTeX-to-Markdown is conservative, not perfect
- **PDF text extraction requires library** — PyMuPDF, pypdf, or pdfminer.six for arXiv PDF fallback
- **No citation graph ranking** — deterministic metadata completeness score only
- **No trusted reading** — evidence files are raw material, not analyzed conclusions
- **No novelty verdict** — this layer cannot judge novelty; that belongs to novelty_check stage
- **experiment_plan remains blocked** — full-text review of closest prior work required before advancing

---

## Related Documentation

- `docs/LITERATURE_LAYER_MVP.md` — MVP skeleton and command reference
- `docs/LITERATURE_SOURCE_ADAPTERS.md` — Source adapter interface and OpenAlex adapter
- `docs/TRUSTED_WORKFLOW_VALIDATION_STATUS.md` — Trusted workflow validation status
- `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md` — Target architecture (Section 8)

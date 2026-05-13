# Full-text Store

This store holds open-access or user-provided full text for papers in the current top-k evidence.

## Rules

- Do not bypass paywalls. Do not use Sci-Hub, login scraping, or cookie-based access.
- Raw PDFs, LaTeX sources, HTML files, and extracted full text are local-only and must not be committed to git.
- Generated Markdown is local evidence-support material, not a paper claim.
- Trusted stages must be rerun after manual review notes are updated.

## Directory Structure

- `raw_pdfs/` — downloaded PDF files (gitignored)
- `raw_html/` — downloaded HTML files (gitignored)
- `raw_sources/` — downloaded arXiv LaTeX source archives (gitignored)
- `extracted_text/` — extracted plain text from PDFs/HTML (gitignored)
- `extracted_markdown/` — extracted/converted Markdown from LaTeX/PDF/HTML (gitignored)
- `manifest.json` — acquisition manifest (committed)
- `full_text_queue.json` — acquisition queue with statuses (committed)
- `full_text_queue.md` — human-readable queue summary (committed)
- `review_notes.md` — per-paper review template (committed, to be filled by human)

## Usage

```bash
# Acquire open-access full text for top-k papers
python tools/literature_evidence_landing.py acquire-open-fulltext \
  --top-k literature/search_runs/current/top_k.md \
  --output-dir literature/full_text_store/current \
  --prefer-latex --allow-arxiv-pdf --allow-open-html --allow-open-pdf \
  --max-items 10 --overwrite --json

# Validate store
python tools/literature_evidence_landing.py validate-fulltext-store \
  --store literature/full_text_store/current

# Summarize store
python tools/literature_evidence_landing.py summarize-fulltext-store \
  --store literature/full_text_store/current --json
```

## Manual Queue

Papers that cannot be acquired automatically are listed in `full_text_queue.json` with status `manual_required`. To resolve:

1. Place the PDF or text file in the appropriate `raw_pdfs/` or `manual_sources/` directory.
2. Update `review_notes.md` with your review.
3. Re-run trusted stages (literature_search, novelty_check, method_refinement) after review.

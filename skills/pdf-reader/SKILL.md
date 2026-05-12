---
name: pdf-reader
description: Read, extract, and search PDF content using pdftotext (primary) or PyPDF2 (fallback). Use when user says "read paper", "open PDF", "extract PDF", "show me this paper", "search in PDF", or needs to read downloaded academic papers. Prefer this over the generic Read tool for PDF files — it extracts text directly and avoids token waste from failed PDF parsing.
argument-hint: [path-or-command]
allowed-tools: Bash(python tools/pdf_read.py:*), Read, Grep, Glob
---

# PDF Reader

Read and extract content from PDF files: $ARGUMENTS

## Constants

- **DEFAULT_PAGES = "1-3"** — Default page range for `read` command
- **SEARCH_MAX_RESULTS = 20** — Maximum search results returned
- **FETCH_SCRIPT** — `tools/pdf_read.py` relative to the project root, or the same path relative to the ARIS install.

## When to Use This Skill

Use this skill whenever you need to read a PDF file. The platform's built-in Read tool may fail on arXiv-generated PDFs (incorrect "password-protected" error). This skill bypasses that limitation by using `pdftotext` (preferred) or `PyPDF2` (fallback) to extract text directly.

## Commands

### Read — Extract text from specific pages

```bash
python3 tools/pdf_read.py read "PATH" --pages RANGE
```

**Examples:**
```bash
python3 tools/pdf_read.py read "papers/2510.03904.pdf" --pages 1-3
python3 tools/pdf_read.py read "papers/2510.03904.pdf" --pages 5    # single page
```

### Meta — Show PDF metadata

```bash
python3 tools/pdf_read.py meta "PATH"
```

Returns: title, author, page count, file size.

### Search — Find keyword in PDF

```bash
python3 tools/pdf_read.py search "KEYWORD" "PATH"
```

Options:
- `--context N` — lines of context around each match (default: 1)

## Token Efficiency

| Method | Token cost | Control |
|--------|-----------|---------|
| Read tool (platform) | Whole PDF (10-50K) | Page range |
| **pdf_read.py** | Exact pages (2-20K) | Exact pages |
| WebFetch arxiv | Abstract only (~1K) | None |

**Prefer `pdf_read.py` for deep reading** — it extracts exactly what you need without token waste.

## Dependencies

- **pdftotext** (poppler-utils) — primary backend, installed via system package manager
- **PyPDF2** — fallback backend, `pip install PyPDF2`

At least one must be available. `pdftotext` is preferred for better text extraction quality.

## Integration with Research Workflow

When doing literature review:

```bash
# 1. Quick scan: read first 2 pages of multiple papers
python3 tools/pdf_read.py read "papers/llm-log-ad/2512.09627.pdf" --pages 1-2

# 2. Deep read: read methods section when paper is relevant
python3 tools/pdf_read.py read "papers/llm-log-ad/2512.09627.pdf" --pages 3-6

# 3. Search for specific terms
python3 tools/pdf_read.py search "distillation" "papers/llm-log-ad/2512.09627.pdf"
```

## Safety Rules

- Only process PDFs that the user has legally obtained or provided.
- Do not use this skill to bulk-extract text from papers the user does not have rights to process.
- Do not download PDFs.
- Do not bypass paywalls or access controls.
- Do not output large verbatim sections from copyrighted PDFs unless the user owns or has rights to the document.
- Prefer metadata, page-limited excerpts, and structured summaries over full-text dumps.
- This skill is a local extraction helper, not a novelty verdict or trusted research conclusion.

## Trusted Workflow Boundary

- This skill does not call model APIs.
- This skill does not produce trusted conclusions.
- Extracted text must still flow through literature acquisition / evidence validation before novelty_check.
- It is not automatically part of research_default.yaml.

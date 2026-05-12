# Untracked Workspace Triage

This document records untracked files in the current Git working tree that may have value. It is NOT a cleanup action — these files have not been validated, and committing any of them requires individual review. This list prevents accidental commits or deletion of potentially valuable work.

---

## maybe_docs

| File | Reason |
|------|--------|
| `AGENTS.md` | Possible Codex agent instruction file; review content before committing. |
| `CLEAN_BRANCH_REPORT.md` | Historical cleanup report; may contain sensitive references (e.g., API key exposure notes); manual review required before commit. |
| `docs/research_contract_review.md` | Possible TokenTR contract review document; verify relevance and whether it belongs in `docs/` or elsewhere. |

---

## maybe_source

| File/Directory | Reason |
|---------------|--------|
| `detection/` | Possible anomaly detection source code (PatchTST, contrastive models, training pipelines). Review scope, dependencies, and whether generated artifacts (`__pycache__/`, `.pt` files) are properly excluded before any commit. |
| `experiments/` | Possible experiment scripts. Do NOT commit `results/`, `data/`, or any runtime outputs — these are covered by `.gitignore`. |
| `mcp-servers/codex-shim/` | Possible Codex MCP server shim. Review security assumptions and whether it is actively used. |
| `paper/` | Possible LaTeX paper source tree. Generated PDFs (`main.pdf`) and build artifacts (`*.aux`, `*.log`, etc.) must never be committed. |
| `probes/*.py` | Model probing scripts (`layer_sweep.py`, `ollama_diagnostic.py`, etc.). Review each before adding to the trusted workflow. |
| `probes/trajectory/` | Possible source directory. Inspect contents before committing. |
| `skills/ollama-model-download/` | Possible skill for downloading models via Ollama. Review `allowed-tools` and safety boundaries before committing. |
| `skills/pdf-reader/` | Possible skill for reading PDF files. Review tool usage and copyright-safe behavior before committing. |
| `tools/pdf_read.py` | Possible PDF extraction utility script. Review dependencies and copyright-safe extraction approach before committing. |

---

## unclear

| File | Reason |
|------|--------|
| `start_cti.sh` | Shell startup script; contains hardcoded paths (`C:\\self\\Git\\...`). Review whether it is obsolete or still in use before committing. |

---

## Rules

- **Do not commit any untracked directory wholesale.**
- **Do not use `git add .`** — add files explicitly by name.
- Before committing any item, inspect its contents and remove runtime / data / build artifacts.
- Skills must be reviewed for `allowed-tools` and whether they bypass the trusted workflow.
- Experiment code must not bring `results/`, `data/`, or `checkpoints/` into Git.
- Paper files must not include generated PDFs or LaTeX build outputs.
- Any sensitive or credential-like content must be excluded.
- Files that exist only in `??` (untracked) status have not been reviewed — assume none are safe to commit without inspection.

---

## Next Review Order

Suggested order for future review sessions:

1. `AGENTS.md` / `CLEAN_BRANCH_REPORT.md` — identity and sensitive content check
2. `tools/pdf_read.py` + `skills/pdf-reader/` — tool safety and copyright review
3. `mcp-servers/codex-shim/` — security and usage status
4. `detection/` — scope and dependency review
5. `probes/` — script purpose and whether any belong in the trusted workflow
6. `experiments/` — code vs. data separation check
7. `paper/` — LaTeX source review, confirm generated artifacts are excluded

---

## Change Log

| Date | Action |
|------|--------|
| 2026-05-12 | Document created; records current untracked items from `git status --short`. |

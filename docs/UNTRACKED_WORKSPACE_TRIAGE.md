# Untracked Workspace Triage

This document records untracked files in the current Git working tree that may have value. It is NOT a cleanup action — these files have not been validated, and committing any of them requires individual review. This list prevents accidental commits or deletion of potentially valuable work.

---

## maybe_docs

| File | Reason |
|------|--------|
| `AGENTS.md` | **Moved to should_not_commit** — see that section. |
| `CLEAN_BRANCH_REPORT.md` | **Moved to should_not_commit** — see that section. |
| `docs/research_contract_review.md` | **Moved to should_not_commit** — see that section. |

---

## maybe_source

| File/Directory | Reason |
|---------------|--------|
| `detection/` | Possible anomaly detection source code (PatchTST, contrastive models, training pipelines). Review scope, dependencies, and whether generated artifacts (`__pycache__/`, `.pt` files) are properly excluded before any commit. |
| `experiments/` | Possible experiment scripts. Do NOT commit `results/`, `data/`, or any runtime outputs — these are covered by `.gitignore`. |
| `mcp-servers/codex-shim/` | **Moved to should_not_commit** — see that section. |
| `paper/` | Possible LaTeX paper source tree. Generated PDFs (`main.pdf`) and build artifacts (`*.aux`, `*.log`, etc.) must never be committed. |
| `probes/*.py` | Model probing scripts (`layer_sweep.py`, `ollama_diagnostic.py`, etc.). Review each before adding to the trusted workflow. |
| `probes/trajectory/` | Possible source directory. Inspect contents before committing. |
| `skills/ollama-model-download/` | **Moved to should_not_commit** — see that section. |
| `skills/pdf-reader/` | Reviewed: allowed-tools narrowed, copyright/trusted workflow boundaries added; **moved to reviewed_for_commit**. |
| `tools/pdf_read.py` | Reviewed: local-only PDF text extraction, no network/model/file-write; **moved to reviewed_for_commit**. |

---

## unclear

| File | Reason |
|------|--------|
| `start_cti.sh` | Shell startup script; contains hardcoded paths (`C:\\self\\Git\\...`). Review whether it is obsolete or still in use before committing. |

---

## should_not_commit

| File/Directory | Reason |
|----------------|--------|
| `mcp-servers/codex-shim/` | Reviewed 2026-05-12. This local MCP shim mimics Codex tools but bypasses `trusted_role_runner.py`, `validate_model_invocation.py`, ledger recording, and `verification_status`. It can create unverified model outputs that appear like Codex results, so it must not be committed or used in the trusted workflow. Also see `.gitignore: mcp-servers/codex-shim/`. |
| `AGENTS.md` | Reviewed 2026-05-12. Codex-specific instruction file overlaps/conflicts with the current project rules (`CLAUDE.md`) and contains local Windows/Ollama assumptions. Do not commit unless rewritten and reconciled with the main project guidance. |
| `CLEAN_BRANCH_REPORT.md` | Reviewed 2026-05-12. Historical cleanup/security incident report describing API key exposure context. Do not commit to the public repository; keep only in private/internal archive if needed. |
| `docs/research_contract_review.md` | Reviewed 2026-05-12. TokenTR legacy review artifact without trusted artifact header, ledger, or current workflow status. Do not mix into current trusted workflow docs. |
| `skills/ollama-model-download/` | Reviewed 2026-05-12. Current skill uses broad `Bash(*)`, can trigger large local model downloads, contains local Windows/Ollama assumptions, and encourages Ollama model calls outside `trusted_role_runner.py`, ledger, and `verification_status`. Do not commit unless rewritten as a strictly bounded local utility with explicit user confirmation and trusted workflow boundary. |

---

## Rules

- **Do not commit any untracked directory wholesale.**
- **Do not use `git add .`** — add files explicitly by name.
- Before committing any item, inspect its contents and remove runtime / data / build artifacts.
- Skills must be reviewed for `allowed-tools` and whether they bypass the trusted workflow.
- Local MCP shims that bypass `trusted_role_runner.py` or lack `verification_status` must not be committed.
- Local instruction files that conflict with current trusted workflow guidance must not be committed without rewrite.
- Security incident reports must not be committed to the public repository.
- Local model download / inference skills that use broad Bash permissions or bypass trusted model routing must not be committed.
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

## reviewed_for_commit

| File/Directory | Review Result |
|----------------|---------------|
| `tools/pdf_read.py` | Reviewed 2026-05-12. Local-only PDF text extraction (pdftotext/PyPDF2). No network, no model calls, no file write. Committed with copyright safety notice in docstring. |
| `skills/pdf-reader/` | Reviewed 2026-05-12. `allowed-tools` narrowed to `Bash(python tools/pdf_read.py:*), Read, Grep, Glob`. Safety Rules and Trusted Workflow Boundary sections added. |

---

## Change Log

| Date | Action |
|------|--------|
| 2026-05-12 | Document created; records current untracked items from `git status --short`. |
| 2026-05-12 | `AGENTS.md`, `CLEAN_BRANCH_REPORT.md`, and `docs/research_contract_review.md` reviewed and marked should_not_commit; ignored to prevent accidental commit. |
| 2026-05-12 | `skills/ollama-model-download/` reviewed and marked should_not_commit; ignored to prevent accidental commit. |
| 2026-05-12 | `mcp-servers/codex-shim/` reviewed and marked should_not_commit; ignored to prevent accidental commit. |
| 2026-05-12 | PDF reader reviewed and accepted for commit: `tools/pdf_read.py` and `skills/pdf-reader/` moved to reviewed_for_commit. |

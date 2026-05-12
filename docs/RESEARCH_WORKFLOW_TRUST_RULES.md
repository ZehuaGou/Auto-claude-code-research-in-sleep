# ARIS Research Workflow — Trust Rules

These rules ensure the ARIS research system produces trustworthy results by preventing
external agents from bypassing the controlled workflow.

## Core Principles

1. **External Agent is a dispatcher only** — It schedules stages but never produces
   trusted conclusions directly. It must not organize prompts, select models, or claim
   results on its own.

2. **All research flow must enter through `tools/research_workflow.py`** — This is the
   only entry point for new research. No ad-hoc calls to `llm-chat` or `codex` MCP
   outside of this controller.

3. **`research_workflow.py` is the Workflow Controller** — It selects the role, generates
   the context manifest, and generates the prompt file. External agents cannot override
   these decisions.

4. **Trusted execution via `tools/trusted_role_runner.py`** — All model calls must go
   through this script, which records every call in the ledger with full routing metadata.

5. **Validation gates each stage** — `tools/validate_model_invocation.py` must PASS before
   proceeding to the next stage. A `PASS` means: correct role, correct backend, no
   fallback used, context manifest applied, contamination scan done.

6. **`allowed_next_stage=false` means STOP** — If validation sets `allowed_next_stage=false`,
   the workflow must not proceed. External agents cannot override this.

## Model Routing Rules

7. **Codex roles (mcp backend) must have real threadId** — `codex_thread_id` in the ledger
   must be non-null and traceable. A missing threadId means the call was not completed
   through the proper handoff protocol.

8. **DeepSeek / MiniMax / OpenAI roles must have real `actual_backend` and `actual_model`**
   — These are recorded in the ledger. "unknown" or "fallback" are not allowed without a
   recorded reason.

9. **Fallback must have a reason** — If `fallback_used=true`, the ledger entry must contain
   a non-empty `fallback_reason`. Silent fallback is a trust violation.

10. **`fallback_used=false` is required to proceed** — The Workflow Controller checks this
    field before executing any stage. If true, it stops before making the call.

## Context Isolation Rules

11. **Context manifest defines allowed inputs** — Before each stage, the workflow generates
    a manifest listing exactly which files the model may read. Any file not listed is
    forbidden.

12. **`forbidden_context` must be checked** — The ledger entry must have
    `forbidden_context_checked=true`. This prevents old conclusions, unverified results,
    or external agent preferences from contaminating the model input.

13. **Contamination scan is required** — `contamination_scan_status` must be set to
    "checked" before the stage output is trusted. Current workflow first version only
    generates `manifest_only` status; content-level automatic contamination scanning
    requires `context_isolation_check.py` to be completed in a future phase.

## Dry-Run and Mock Rules

14. **Dry-run is not evidence** — `--dry-run` output from `research_workflow.py` shows
    what *would* happen, but produces no ledger entry and cannot be used as proof of
    research progress.

15. **Mock/dry-run artifacts cannot enter the workflow** — Files produced by dry-runs,
   演练, or simulated runs are explicitly listed in `forbidden_context` and must not be
    used as research evidence.

## Deprecated Entrypoints

16. **`isolated_job_runner.py` is not a valid entry point for new research** — Existing
    research that used it is grandfathered; new research must use `research_workflow.py`.

## Sequential Gate

17. **All four stages must be completed in order** — research_contract → novelty_check →
    experiment_plan → implementation_plan. Skipping or reordering stages is not permitted.
    Each stage requires validation PASS before the next begins.

18. **No experiment code may be written before implementation_plan is validated** — Code
    written before the contract, novelty check, and experiment plan are all verified is
    considered premature and must not be committed.

## Summary

| Rule | What it prevents |
|------|-------------------|
| 1-6 | Agent bypasses trusted workflow |
| 7-10 | Wrong model / silent fallback |
| 11-13 | Context contamination |
| 14-15 | Dry-run artifact inflation |
| 16-18 | Out-of-order execution, premature coding |

These rules are not style guidelines — they are structural requirements.
Violations must cause the workflow to stop before producing any trusted output.
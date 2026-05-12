# Trusted Workflow Validation Status

**Date:** 2026-05-12

**Conclusion:** Trusted workflow gatekeeping is validated at zero-cost prepare level. No real model execution has been performed in these checks.

---

## Verified Items

### 1. input_normalization prepare path

- input_normalizer role exists in tools/model_route.py
- .env.example includes `ROLE_INPUT_NORMALIZER=DS_FLASH`
- tools/env_loader.py supports legacy `LLM_INPUT_NORMALIZER_MODEL` fallback
- With temporary local .env route, `python tools/research_workflow.py prepare input_normalization` reaches prepare
- It writes only tmp manifest/input files
- It prints trusted_role_runner command but does not execute it
- No model call, no ledger, no trusted output generated during prepare

### 2. research_contract blocking

- Missing `research/current/input_normalization.md` blocks research_contract
- Error occurs before model call
- No manifest/input/trusted output is generated

### 3. downstream stage blocking

The following stages all block when required inputs are missing:

- `literature_search`
- `novelty_check`
- `experiment_plan`
- `implementation_plan`
- `result_judge`
- `paper_writing`

All exited non-zero as expected. No model calls. No manifest/input files. No ledger. No trusted outputs. Git status remained clean.

### 4. literature evidence chain smoke test

- `validate-raw` works on empty skeleton and reports empty
- `validate-candidates` works on empty skeleton and reports empty
- `top_k.md` template_only is blocked by `validate_literature_evidence.py`
- Temporary raw -> candidates -> top_k pipeline works in `tmp/`
- `validate_literature_evidence.py` returns insufficient_evidence for generated top_k when full text is unverified, which is expected

### 5. novelty_check evidence precheck

- `plan novelty_check` does not trigger evidence precheck
- `prepare novelty_check` blocks on missing inputs first
- If inputs exist, template_only / insufficient_evidence / valid_with_gaps evidence should block before model call by workflow precheck

---

## Current Trusted Chain

```
raw_user_input.md
  -> input_normalization prepare / trusted_role_runner execution
     -> input_normalization.md
        -> research_contract.md
           -> literature_search.md
              -> novelty_check.md
                 -> experiment_plan.md
                    -> implementation_plan.md
                       -> experiment_results.md
                          -> result_judge.md
                             -> paper_draft.md
```

- Only prepare/blocking has been verified so far.
- Real trusted output generation still requires actual model calls through trusted_role_runner.py.
- Local `.env` must include `ROLE_INPUT_NORMALIZER=DS_FLASH` before running input_normalization.

---

## Not Yet Verified

- Real trusted_role_runner.py execution for input_normalizer
- Actual ledger entry creation
- validate_model_invocation.py on a real output
- Full input_normalization -> research_contract handoff with verified artifact header
- Full literature_search with real evidence
- novelty_check with valid top_k.md
- result_judge and paper_writing real stages

---

## Safety Notes

- Do not treat prepare output as trusted research output.
- Do not manually create trusted output headers.
- Do not edit ledger fields by hand.
- Do not bypass missing input checks.
- Do not commit .env.
- Do not use dry-run/mock outputs as evidence.

---

## Alignment Guard (added 2026-05-13)

### Purpose
Pre-execution discipline tool that forces every task to map to the target document's five-layer architecture before execution begins.

### Files
- `tools/alignment_guard.py` — CLI tool (check-task, check-status, --self-test)
- `docs/ALIGNMENT_GUARD.md` — usage documentation
- `docs/TASK_ALIGNMENT_TEMPLATE.md` — required task brief template

### Scope
- Validates task brief structure (13 required sections)
- Validates target layer enum (8 valid values)
- Rejects vague task goals
- Validates git status against allowed/forbidden files
- Supports deviation documentation for target doc departures

### Target Document Reference
- `docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md` (v1.0)

### Deviation Mechanism
Deviations from the target document must be documented with: target_doc_section, reason, proposed_alternative, risk_of_deviation, risk_if_not_deviating, requires_user_approval.

### Not a Replacement For
- `context_isolation_check.py` (content contamination detection)
- `trusted_role_runner.py` (model call execution)
- `validate_model_invocation.py` (ledger and call verification)

### Verification
- Self-test: 10/10 passed
- check-task integration: PASS on valid brief
- check-status integration: PASS on clean repo
- Regression: context_isolation_check 6/6, trusted_role_runner all passed, validate_model_invocation all passed

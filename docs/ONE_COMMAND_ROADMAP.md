# One-Command Trusted Research Automation Roadmap

**Date:** 2026-05-13
**Phase 18A/B/C Status:** IMPLEMENTED — `tools/research_cli.py` provides `status`, `validate`, `repair-queue`, and `start --dry-run` commands. No model calls. No network calls. One-command `start --dry-run` plan shows 17 stages (including method_refinement), 6 validators, 13 planned outputs, 10 stop conditions. Phase 18D (live start) remains future work.

**Phase 19 Status:** IMPLEMENTED — generic method_refinement stage added to `research_default.yaml`. Trusted output generated via trusted_role_runner (deepseek-v4-pro, ledger call_74a3b9561c50). Validator PASS. Readiness gate: needs_more_literature_evidence. Next allowed: collect_more_literature. Dry-run plan updated to include method_refinement. experiment_plan blocked until more literature evidence collected.

---

## 1. Goal

A user should be able to run one command:

```
python tools/research_cli.py start \
  --idea "I want to study token-level hallucination detection using hidden state trajectories" \
  --mode novelty_risk
```

or eventually:

```
/research-start "..."
/novelty-check
/status
```

and the system should automatically:
- save raw input
- normalize input
- create research contract
- run literature evidence pipeline
- run literature_search
- run novelty_check
- produce status summary
- stop safely if any stage fails

---

## 2. Design Principles

| Principle | Meaning |
|-----------|---------|
| User gives simple idea | One string, not 10 commands |
| Workflow owns prompt assembly | External Agent does not拼prompt |
| Skill owns method | Research methodology stays in Skill layer |
| Trusted runner owns model call | No direct model calls from CLI or Agent |
| Validator owns stage transition | No stage advancement without PASS |
| Repair queue owns known issues | Issues tracked, not silently ignored |
| No trusted conclusion from external Agent | Agent orchestrates, model concludes |
| No stage reads unapproved context | allowed_input_files enforced |

---

## 3. MVP Command Set

### Phase 18 Commands

```bash
# Start a new research workflow
python tools/research_cli.py start --idea "..." --mode novelty_risk

# Check current status
python tools/research_cli.py status

# Continue to next stage
python tools/research_cli.py continue --stage method_refinement

# View repair queue
python tools/research_cli.py repair-queue

# Validate current state
python tools/research_cli.py validate
```

### Future Native Slash Commands

```
/idea-discovery "..."
/research-contract "..."
/literature-search
/novelty-check
/method-refinement
/experiment-plan
/status
```

---

## 4. One-Command `novelty_risk` Flow

Internal sequence when user runs `start --idea "..." --mode novelty_risk`:

```
 1. Assert clean git status (or explicit --allow-dirty)
 2. Save raw_user_input.md
 3. Run input_normalization (prepare + execute via trusted_role_runner)
 4. Validate input_normalizer (validate_model_invocation)
 5. Run research_contract (prepare + execute)
 6. Validate contract_reviewer
 7. Run evidence pipeline (literature_evidence_landing dry-run → fetch → normalize → candidates → top_k)
 8. Validate evidence (validate_literature_evidence)
 9. Create literature_notes.md
10. Run literature_search (prepare + execute via trusted_role_runner)
11. Validate literature_scout
12. Run novelty_check (prepare + execute via trusted_role_runner)
13. Validate novelty_checker
14. Write status summary
15. Print next allowed action
```

Each step:
- On validator FAIL → stop, show failed_stage, show repair suggestion
- On model call FAIL → stop, log error, do not fabricate output
- On context isolation FAIL → stop, show contamination details

---

## 5. Failure Policy

| Condition | Behavior |
|-----------|----------|
| Validator FAIL | Stop. Show `failed_stage`. Show repair suggestion. Do not continue. |
| Model call error | Stop. Log error. Do not fabricate outputs. |
| Context isolation FAIL | Stop. Show contamination details. |
| Missing input file | Stop. Show which file is missing. |
| Evidence insufficient | Allow with `insufficient_evidence` verdict if stage config permits. |
| Route fallback used | Stop. Show `fallback_used=true`. Require explicit config fix. |
| Dirty git status | Stop unless `--allow-dirty` flag. |

Rerun policy:
- `--rerun-stage <stage>` required for rerunning completed stages
- No automatic rerun on failure
- No `git add .` — only explicit file adds

---

## 6. Status Summary Output

Desired JSON output from `research_cli.py status`:

```json
{
  "current_stage": "novelty_check",
  "completed_stages": [
    "input_normalization",
    "research_contract",
    "literature_search",
    "novelty_check"
  ],
  "blocked": false,
  "next_allowed_stage": "method_refinement",
  "validators": {
    "input_normalizer": "PASS",
    "contract_reviewer": "PASS",
    "literature_scout": "PASS",
    "novelty_checker": "PASS"
  },
  "evidence_status": "insufficient_evidence",
  "repair_queue_open": ["LRQ-004", "LRQ-005", "LRQ-008"],
  "warnings": [
    "Only OpenAlex source used — consider multi-source for stronger novelty claims"
  ]
}
```

---

## 7. Method Refinement Command

Future command:

```
python tools/research_cli.py continue --stage method_refinement
```

Generic `method_refinement` must output:
- method object (inputs, outputs, assumptions)
- exact differentiator from prior work
- testable hypothesis
- minimum experiment boundary
- non-claims (what the method does NOT prove)
- whether `experiment_plan` is allowed to proceed

This stage must be **generic** — not hardcoded to hallucination trajectory.

---

## 8. Implementation Phases

### Phase 18A — Status Summary Command

Phase 18A is implemented. See Phase 18A/B below.

### Phase 18B — Research CLI Skeleton
- Read existing artifacts from `research/current/trusted_outputs/`
- Run validators (`validate_model_invocation` for each completed stage)
- Print current state as JSON
- No model calls
- Estimated: 1 day

### Phase 18B — Research CLI Skeleton
- `research_cli.py` with subcommands: `status`, `validate`, `repair-queue`
- No stage execution yet
- Just reads existing state
- Estimated: 1 day

### Phase 18C — One-command `novelty_risk` dry-run
- Sequence planning only — show what would run
- No model calls, no network calls, no file mutations
- Validates inputs exist, shows planned stages/validators/outputs/stop conditions
- dry-run is NOT live orchestration — execution does not occur
- Estimated: 1 day

### Phase 18D — One-command `novelty_risk` live
- Execute existing workflow stages via `research_workflow.py prepare` + `trusted_role_runner.py`
- Fail closed on any error
- Estimated: 2 days

### Phase 19 — Generic Method Refinement Stage
- Add `method_refinement` stage to `research_default.yaml`
- Output contract
- Trusted runner integration
- Validator
- Estimated: 2 days

### Phase 20 — Multi-source Literature Bundle
- arXiv adapter
- Crossref adapter
- Maybe Semantic Scholar with rate-limit handling
- Estimated: 3 days

### Phase 21 — Full-text / Manual Acquisition MVP
- Manual acquisition queue
- User PDF drop directory
- Basic parser (sections extraction)
- Estimated: 3 days

---

## 9. Non-Goals for Next Phase

Explicitly **NOT** doing in Phase 18-19:

- No experiment execution
- No paper writing
- No claim of novelty
- No full autonomous overnight research loop
- No web UI
- No complex dashboard
- No automatic code implementation
- No GPU cluster integration
- No publication-level optimization

---

## 10. Acceptance Criteria for Phase 18

| Criterion | How to verify |
|-----------|--------------|
| User can run one status command | `python tools/research_cli.py status` prints JSON |
| User can see next allowed stage | Status output includes `next_allowed_stage` |
| User no longer manually inspects validators | CLI runs validators automatically |
| CLI refuses dirty repo unless allowed | `start` without `--allow-dirty` fails on dirty repo |
| CLI does not call model unless explicit | `status` and `validate` make zero model calls |
| CLI does not bypass trusted_role_runner | All model calls go through `trusted_role_runner.py` |
| CLI does not write .env/.aris | `git status` shows no .env/.aris changes |
| CLI works on new idea without hardcoding | `start --idea "any topic"` works, not just hallucination trajectory |

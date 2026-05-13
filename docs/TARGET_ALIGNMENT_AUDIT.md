# Target Alignment Audit

**Date:** 2026-05-13
**Against:** docs/TRUSTED_RESEARCH_AUTOMATION_TARGET.md v1.0

---

## 1. Executive Summary

The current system is no longer just ARIS patching. It has a working trusted execution skeleton with context isolation, trusted model routing, ledger recording, and artifact boundary enforcement.

However, the real product goal is **one-command trusted research automation for arbitrary research ideas** — not just running a single hallucination trajectory experiment. The hallucination trajectory topic must be treated only as a regression test case, not the system product.

The system is useful but incomplete. The primary gap is user experience: there is no single command to start a research workflow. The secondary gap is missing pipeline stages (method_refinement). The tertiary gap is literature source coverage.

---

## 2. Current Completed Capabilities

### Native Command Layer

**Status: NOT IMPLEMENTED**

- No `research_cli.py` exists.
- No single entry point for `start`, `status`, `continue`, `validate`.
- User must manually copy `python tools/research_workflow.py prepare <stage>` commands.
- `/status` slash command exists via `register_slash_commands.py` + `skills/status/SKILL.md` but is not integrated into a unified CLI.
- The target document specifies `/idea-discovery`, `/novelty-check`, `/experiment-plan`, `/status` — none of these exist as stable user-facing commands.

### Skill Method Layer

**Status: PARTIAL**

- `stage_output_contract` exists in workflow config for `literature_search` and `novelty_check` — enforces role boundaries.
- No reusable skill specs exist for all stages.
- No `method_refinement` stage defined in workflow config.
- Skill methodology is embedded in prompt text within workflow configs, not modularized.
- The `idea-discovery` skill concept from ARIS is not implemented.

### Workflow Discipline Layer

**Status: MOSTLY COMPLETE**

Completed:
- `research_workflow.py` plan/prepare mechanism
- `allowed_input_files` per stage
- `forbidden_context` per stage
- `stage_output_contract` for role boundary enforcement
- Literature evidence precheck (`_run_stage_prechecks`)
- Context manifests with `context_hash` and `contamination_scan_status`
- Path normalization fix (LRQ-009) — `normalize_context_path()` with traversal rejection
- Input file existence checks before model calls
- Stage output file validation

Gaps:
- One-command orchestration missing
- Route drift / call age handling needs policy (currently `call_too_old` just blocks)
- Core workflow self-test coverage gaps (LRQ-010)
- No `method_refinement` stage in workflow config

### Trusted Execution Layer

**Status: MOSTLY COMPLETE**

Completed:
- `trusted_role_runner.py` — full model call execution with ledger recording
- `model_route.py` — role-to-model routing via environment variables
- DeepSeek Flash and Pro routing via `openai_compatible_api` backend
- `external_agent_direct` distinction in output headers
- Ledger call IDs (`llm_calls.jsonl`)
- `validate_model_invocation.py` — post-call verification

Gaps:
- Codex MCP adapter not fully configured (pre-existing self-test failures)
- No user-friendly route status command integrated into CLI
- `call_too_old` policy needs formal definition (currently just `max-age-hours`)

### Trusted Output Layer

**Status: MOSTLY COMPLETE**

Completed:
- Trusted output files with YAML frontmatter headers
- `allowed_next_stage` field in output headers
- Artifact boundary checks via context isolation
- `validate_model_invocation` checks backend, model, fallback, verification_status

Gaps:
- Trusted output repair policy needs formalization
- Manual wording repairs need procedure (currently ad-hoc)
- `call_too_old` policy needs clarification

### Literature Layer

**Status: MVP COMPLETE**

Completed:
- OpenAlex adapter (`openalex_fetch.py`)
- Query planning (`literature_evidence_landing.py` build-search-plan)
- Search jobs (`build-search-jobs`)
- Job results (`validate-job-results`, `normalize-job-results`)
- Raw results → candidates → top_k pipeline
- Relevance scoring with domain negatives
- Dedup by normalized title + year tolerance
- Repair queue (`LITERATURE_REPAIR_QUEUE.md`)
- Operator guide (`LITERATURE_LAYER_OPERATOR_GUIDE.md`)
- `validate_literature_evidence.py` precheck

Gaps:
- Only OpenAlex implemented (LRQ-004)
- No full-text acquisition (LRQ-005)
- No paper parsing
- No citation graph / ranking (LRQ-008)
- No manual PDF parsing loop
- Keyword scoring not semantic (LRQ-003)

### Status Tracking Layer

**Status: PARTIAL**

- `research_status.py` exists as CLI status viewer
- `/status` slash command registered
- No unified status showing current stage, validators, blockers, repair queue, next allowed stage

---

## 3. Stage-by-Stage Audit

| Stage | Current Status | Trusted? | Evidence Quality | Main Gaps | Next Action |
|-------|---------------|----------|-----------------|-----------|-------------|
| raw_user_input | Manual file creation | N/A | N/A | No auto-save from CLI | Implement in CLI |
| input_normalization | Workflow config exists, model executed | Yes | Good (DeepSeek Flash) | No trusted output in current run | Re-run if needed |
| research_contract | Workflow config exists, model executed, trusted output exists | Yes | Good (DeepSeek Pro) | Complete | Ready |
| literature evidence acquisition | OpenAlex pipeline complete, top_k exists | Yes | Insufficient (metadata only, no full text) | Single source, no full text | Multi-source (P20) |
| literature_search | Trusted output exists | Yes | Bounded by OpenAlex only | Single source | Ready for current scope |
| novelty_check | Trusted output exists, contract-enforced | Yes | Insufficient_evidence (OpenAlex only, no full text) | Needs broader search for strong claims | Ready for risk assessment |
| method_refinement | **MISSING** | N/A | N/A | Not in workflow config | **Implement before experiment_plan** |
| experiment_plan | Workflow config exists, no execution | N/A | N/A | Blocked by missing method_refinement | Wait for method_refinement |
| implementation_plan | Workflow config exists | N/A | N/A | Blocked by experiment_plan | Wait |
| experiment_bridge | Not in workflow config | N/A | N/A | Not designed yet | P1 |
| result_judge | Workflow config exists | N/A | N/A | Blocked by experiment_bridge | Wait |
| paper_writing | Workflow config exists | N/A | N/A | Blocked by result_judge | Wait |

---

## 4. Target Document Requirements Not Yet Met

| Requirement | Target Section | Current Status |
|------------|---------------|----------------|
| Native command layer | Section 5 | Not implemented |
| One-command user experience | Section 5 | Not implemented |
| Skill specs for all stages | Section 6 | Partial (contracts only) |
| Multi-source search | Section 8.3 | Only OpenAlex |
| Full-text acquisition | Section 8.8 | Not implemented |
| Paper parsing | Section 8.9 | Not implemented |
| Literature material store | Section 8.10 | Partial (search_runs only) |
| Manual acquisition workflow | Section 8.8 | Not implemented |
| Method refinement stage | Section 12 | Not in workflow config |
| Status tracking | Section 12.10 | Partial (research_status.py) |
| Core workflow tests | Section 9 | Limited (LRQ-010) |
| Codex MCP route | Section 10.7 | Not usable (self-test failures) |
| Call age / route drift policy | Section 10 | Needs formal definition |

---

## 5. MVP-Acceptable vs Blocking

| Gap | Classification | Blocking? | Reason | Proposed Fix |
|-----|---------------|-----------|--------|-------------|
| Native command missing | near_term_mvp | Yes for usability | User must copy commands manually | Phase 18: research_cli.py |
| method_refinement missing | fix_now | Yes before experiment_plan | No generic method refinement exists | Phase 19: add workflow stage |
| Status tracking incomplete | near_term_mvp | Yes for automation | No unified status view | Phase 18A: status command |
| OpenAlex only | repair_queue | No for risk assessment, yes for strong novelty | Single source limits coverage | Phase 20: multi-source bundle |
| No full text | repair_queue | Yes for strong novelty claims | Evidence is metadata-only | Phase 21: manual acquisition |
| No paper parsing | repair_queue | Yes for paper writing | Cannot read PDFs programmatically | Phase 21: parser MVP |
| self-test coverage gaps | repair_queue | No | Pre-existing, not blocking | LRQ-010 |
| Codex MCP adapter | repair_queue | No unless using Codex stages | Using DeepSeek routing | LRQ-010 |
| Call age policy | repair_queue | No | Currently just blocks | Formalize policy |
| route drift detection | repair_queue | No | Not implemented | Add to status command |

---

## 6. Current System Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Context pollution | Reduced | Context manifests + forbidden markers + path normalization |
| Evidence insufficiency | High | Single source (OpenAlex), no full text — `insufficient_evidence` verdict is honest |
| User burden | High | Manual command copying required for every stage |
| Agent overstepping | Reduced | `stage_output_contract` + role boundary enforcement |
| Route/config drift | Medium | `validate_model_invocation` checks backend/model, but no drift detection |
| Treating test case as product | Medium | Must explicitly scope hallucination trajectory as regression test only |

---

## 7. Recommended Next Phase

### Phase 18: One-Command Orchestrator MVP

Before: experiment_plan, implementation_plan, paper writing.

Why:
- User pain is command-copy burden.
- System target is simple native command.
- Current pipeline must be wrapped into stable command before adding more research stages.
- Status tracking must work before adding stages.

### Phase 19: Generic Method Refinement Stage

Why:
- Every idea should be automatically refined before experiment planning.
- Do not hardcode hallucination trajectory.
- Method refinement should be reusable for arbitrary research ideas.

### Phase 20: Multi-source Literature Bundle

Why:
- OpenAlex-only limits novelty claim strength.
- arXiv + Crossref adapters are straightforward.

### Phase 21: Full-text / Manual Acquisition MVP

Why:
- Required for strong novelty claims.
- Required for paper writing.

---

## 8. Explicit Decision

1. **Do not proceed directly to experiment_plan.** Method refinement must come first.
2. **Do not treat hallucination trajectory as system product.** Use it only as regression test case.
3. **Next implementation should target generic system capability** (one-command orchestrator), not a specific research topic.
4. **Phase 18 is the priority.** It unblocks all subsequent stages by reducing user burden and providing status visibility.

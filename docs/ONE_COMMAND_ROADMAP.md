# One-Command Trusted Research Automation Roadmap

**Date:** 2026-05-13
**Phase 18A/B/C Status:** IMPLEMENTED — `tools/research_cli.py` provides `status`, `validate`, `repair-queue`, and `start --dry-run` commands. No model calls. No network calls. One-command `start --dry-run` plan shows 17 stages (including method_refinement), 6 validators, 13 planned outputs, 10 stop conditions. Phase 18D (live start) remains future work.

**Phase 19 Status:** IMPLEMENTED — generic method_refinement stage added to `research_default.yaml`. Trusted output generated via trusted_role_runner (deepseek-v4-pro, ledger call_74a3b9561c50). Validator PASS. Readiness gate: needs_more_literature_evidence. Next allowed: collect_more_literature. Dry-run plan updated to include method_refinement. experiment_plan blocked until more literature evidence collected.

**Phase 20 Status:** IMPLEMENTED — arXiv and Crossref source adapters added to `literature_evidence_landing.py`. Multi-source pipeline (`run-multisource-pipeline`) executes all three sources (arXiv, Crossref, OpenAlex) with cross-source dedup. 70 self-tests pass. Live evidence: 155 records from 31 successful jobs (3 sources), 73 canonical candidates, 10 top-k selected. Evidence promoted to `literature/search_runs/current/`. Semantic Scholar deferred.

**Phase 20B Status:** IMPLEMENTED — forbidden-token `confirmed_novel` removed from top_k generator. Trusted stages refreshed via trusted_role_runner: literature_search (deepseek-v4-flash, call_1aa9746795ae), novelty_check (deepseek-v4-pro, call truncated but file written), method_refinement (deepseek-v4-pro, needs_more_literature_evidence). experiment_plan remains blocked. Full-text verification of closest prior work (ICR Probe, INSIDE, Unsupervised Real-Time Detection) required before readiness gate can advance.

**Phase 21A Status:** IMPLEMENTED — open-access full-text acquisition MVP. 10/10 top-k papers acquired (5 arxiv_source, 1 arxiv_pdf, 4 open_html). 4 extracted_markdown, 5 extracted_text, 1 tool_missing (no PDF extraction library). No paywall bypass. No committed PDFs/full text. Full-text store with manifest, queue, review notes. 80 self-tests pass. **Phase 21A fix:** full_text_status classification added (source_acquired_unreviewed: 4, likely_full_text: 1, metadata_page_only: 4, landing_page_only: 1). OpenAlex metadata pages correctly classified as metadata_page_only. Manifest/queue consistency validated. experiment_plan remains blocked until human review of closest prior work completes (Phase 21B).

**Phase 21B Status:** IMPLEMENTED — trusted full-text review MVP. full_text_review stage added to research_default.yaml. full_text_reviewer role (DS_PRO_HIGH, deepseek-v4-pro). Bounded review input from local extracted materials (22KB). Trusted role runner executed (call_e2a8e48a2d35). Validation PASS. Review found high_risk_overlap with ICR Probe (ftq_006). 4/10 papers reviewable, 5/10 not reviewable (metadata/landing page only), 1/10 PDF extraction pending. Readiness: needs_more_full_text_acquisition. Next: collect_more_full_text. experiment_plan remains blocked.

**Phase 21C Status:** PARTIAL — command support implemented, live PDF review blocked by missing library. extract-fulltext-store command added (PyMuPDF/pypdf/pdfminer.six with graceful tool_missing). acquire-alternative-fulltext command added (arXiv DOI resolver, ACL Anthology DOI resolver). 88 self-tests pass. ftq_002 acquired via ACL Anthology (open_pdf, extraction pending). ftq_004/010 arXiv DOIs resolved but downloads timeout in China. ftq_007/009 IEEE DOIs not auto-resolved (paywall). Store: 4 source_acquired_unreviewed, 2 likely_full_text, 3 metadata_page_only, 1 landing_page_only. Live PDF text extraction requires library installation (pymupdf, pypdf, or pdfminer.six). experiment_plan remains blocked.

**Phase 21D Status:** IMPLEMENTED — collect_more_full_text. ftq_004 (arXiv 2410.02707) and ftq_010 (arXiv 2403.06448) full text acquired and extracted via pypdf (extracted_text/ftq_004.txt: 1635 lines, extracted_text/ftq_010.txt: 1233 lines). Both now reviewable. ftq_007/ftq_009 (IEEE DOIs) confirmed paywall — no legal OA version found by current configured sources/search pass. Store: 4 likely_full_text, 4 source_acquired_unreviewed, 2 manual_required. 90 self-tests pass. experiment_plan remains blocked.

**Phase 21E Status:** IMPLEMENTED — close remaining full-text evidence gaps. ftq_007 (Detection of LLM Hallucinations Using Late Internal Representations, ICMLA 2025) and ftq_009 (MixHD, ICASSP 2025) confirmed fully paywall_blocked after exhaustive legal OA search (arXiv, OpenAlex, Crossref, Semantic Scholar, author pages). No open access version found by current configured sources/search pass. Queue and manifest notes cleaned of Sci-Hub references. LRQ-023 added. experiment_plan blocked for current test case due to high_risk_overlap with ICR Probe and two papers behind paywall. This is a regression test case limitation, not a system limitation — the generic system can proceed with any idea that has sufficient literature evidence.

**Phase 21F Status:** IMPLEMENTED — literature module split + documentation consolidation. `literature_evidence_landing.py` split into `tools/literature/{store.py, extraction.py, manual_ingest.py}` with backward-compatible delegation wrappers. 88+ self-tests pass. Documentation v1.1: TRUSTED_RESEARCH_AUTOMATION_TARGET.md updated with executive summary, lightweight-first principle, adaptive broad literature discovery strategy, reading card approach, insufficient source handling, non-test-case binding, and complexity budget. TARGET_ALIGNMENT_AUDIT.md and ARCHITECTURE_COMPLEXITY_AUDIT.md synced.

**Phase 21G Status:** IMPLEMENTED — extract source adapters and scoring to literature submodules. `tools/literature/adapters/{openalex.py, arxiv.py, crossref.py}` + `tools/literature/scoring.py` extracted with backward-compatible delegation wrappers. 88 self-tests pass. Documentation v1.1 updated.

**Phase 21H Status:** IMPLEMENTED — extract multisource pipeline orchestrator to `tools/literature/multisource.py`. Backward-compatible delegation wrappers. 88 self-tests pass.

**Phase 21I Status:** DOCUMENTED — slash-command-first UX, slash command payload, user-facing 6-stage workflow, feedback loops, primary/advanced command split, phase-to-stage mapping. Documentation v1.2: TRUSTED_RESEARCH_AUTOMATION_TARGET.md updated with Sections 4a-4e. TARGET_ALIGNMENT_AUDIT.md and ONE_COMMAND_ROADMAP.md synced. Regression test topic selected: Chain-of-Thought prompting for mathematical reasoning.

---

## 1. Goal

A user should be able to run one slash command:

```
/research-intake "Chain-of-Thought prompting for mathematical reasoning in large language models"
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

The user-facing workflow has 6 phases (see TRUSTED_RESEARCH_AUTOMATION_TARGET.md Section 4c):

1. `/research-intake` — 输入研究方向
2. `/literature-intake` — 文献调研与领域理解
3. `/idea-synthesis` — 创新点生成
4. `/idea-audit` — 创新点验证、查新与研究边界锁定
5. `/experiment` — 实验与结果分析
6. `/paper-writing` — 论文撰写

Python CLI (`tools/research_cli.py`) is the Agent-facing execution layer, not the primary user interface.

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

### Primary User Commands (v1.2)

```
/research-intake "输入研究方向和约束"
/literature-intake "文献调研与领域理解"
/idea-synthesis "创新点生成"
/idea-audit "创新点验证、查新与研究边界锁定"
/experiment "实验与结果分析"
/paper-writing "论文撰写"
/status
```

### Advanced/Internal Commands (v1.2)

```
/novelty-check
/method-refinement
/full-text-review
/experiment-plan
/implementation-plan
/result-judge
/repair-queue
/validate
```

### Agent-Facing Python CLI (not primary user interface)

```bash
# These are called by Agent, not by end users
python tools/research_cli.py start --idea "..." --mode novelty_risk
python tools/research_cli.py status
python tools/research_cli.py continue --stage method_refinement
python tools/research_cli.py repair-queue
python tools/research_cli.py validate
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
- arXiv adapter (implemented)
- Crossref adapter (implemented)
- Semantic Scholar deferred (aggressive rate limits)
- Estimated: 3 days — DONE

### Phase 21A — Open-access Full-text Acquisition + Markdown Extraction MVP
- arXiv LaTeX source download and extraction
- arXiv PDF fallback with text extraction
- Open HTML/PDF download for non-arXiv papers
- LaTeX-to-Markdown rough conversion
- Full-text store with manifest, queue, review notes
- Manual queue for papers without legal automatic access
- 80 self-tests pass
- Estimated: 3 days — DONE

### Phase 21B — Full-text Review + Trusted Stage Rerun
- DONE (Phase 21B implemented)
- Trusted full-text review via trusted_role_runner
- Review found high_risk_overlap with ICR Probe (ftq_006)

### Phase 21C — PDF Extraction + Alternative Acquisition
- DONE (command support implemented)

### Phase 21D — collect_more_full_text
- DONE — ftq_004/ftq_010 extracted, ftq_007/ftq_009 confirmed paywall

### Phase 21E — close remaining evidence gaps
- DONE — exhaustive OA search confirms no legal open access for ftq_007/ftq_009

### Phase 22 — experiment_plan Unblocked (future)
- Requires either: (a) resolving paywall papers via institutional access, or (b) choosing a different regression test case with sufficient evidence
- This is a test case limitation, not a system limitation
- Generic system can proceed with any idea that has sufficient literature evidence

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

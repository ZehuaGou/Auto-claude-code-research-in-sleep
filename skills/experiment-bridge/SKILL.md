---
name: experiment-bridge
description: "Workflow 1.5: Bridge between idea discovery and auto review. Reads EXPERIMENT_PLAN.md, implements experiment code, deploys to GPU, collects initial results. Use when user says \"实现实验\", \"implement experiments\", \"bridge\", \"从计划到跑实验\", \"deploy the plan\", or has an experiment plan ready to execute."
argument-hint: [experiment-plan-path-or-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, Skill, mcp__codex__codex, mcp__codex__codex-reply
---

# Workflow 1.5: Experiment Bridge

Implement and deploy experiments from plan: **$ARGUMENTS**

## Overview

This skill bridges Workflow 1 (idea discovery + method refinement) and Workflow 2 (auto review loop). It takes the experiment plan and turns it into running experiments with initial results.

```
Workflow 1 output:                    This skill:                                    Workflow 2 input:
refine-logs/EXPERIMENT_PLAN.md   →   implement → code review → deploy → collect → initial results ready
refine-logs/EXPERIMENT_TRACKER.md     (model_route.py)   /run-experiment     for /auto-review-loop
refine-logs/FINAL_PROPOSAL.md
```

## Constants

- **CODE_REVIEW = true** — Cross-model code review before deployment (routed via `model_route.py experiment_code_reviewer`). Set `false` to skip (NOT recommended — if you skip, a WARNING will be issued).
- **AUTO_DEPLOY = true** — Automatically deploy experiments after implementation + review. Set `false` to manually inspect code before deploying.
- **SANITY_FIRST = true** — Run the sanity-stage experiment first (smallest, fastest) before launching the rest. Catches setup bugs early.
- **MAX_PARALLEL_RUNS = 4** — Maximum number of experiments to deploy in parallel (limited by available GPUs).
- **BASE_REPO = false** — GitHub repo URL to use as base codebase. When set, clone the repo first and implement experiments on top of it. When `false` (default), write code from scratch or reuse existing project files.
- **COMPACT = false** — When `true`, (1) read `idea-stage/IDEA_CANDIDATES.md` instead of full `idea-stage/IDEA_REPORT.md` if available, (2) append experiment results to `EXPERIMENT_LOG.md` after collection.

> Override: `/experiment-bridge "EXPERIMENT_PLAN.md" — compact: true, base repo: https://github.com/org/project`

## Inputs

This skill expects one or more of:

1. **`refine-logs/EXPERIMENT_PLAN.md`** (best) — claim-driven experiment roadmap from `/experiment-plan`
2. **`refine-logs/EXPERIMENT_TRACKER.md`** — run-by-run execution table
3. **`refine-logs/FINAL_PROPOSAL.md`** — method description for implementation context
4. **`idea-stage/IDEA_CANDIDATES.md`** — compact idea summary (preferred when `COMPACT: true`) *(fall back to `./IDEA_CANDIDATES.md` if not found)*
5. **`idea-stage/IDEA_REPORT.md`** — full brainstorm output *(fall back to `./IDEA_REPORT.md` if not found)*

If none exist, ask the user what experiments to implement.

## Workflow

### Phase 1: Parse the Experiment Plan

Read `EXPERIMENT_PLAN.md` and extract:

1. **Run order and milestones** — which experiments run first (sanity → baseline → main → ablation → polish)
2. **For each experiment block:**
   - Dataset / split / task
   - Compared systems and variants
   - Metrics to compute
   - Setup details (backbone, hyperparameters, seeds)
   - Success criterion
   - Priority (MUST-RUN vs NICE-TO-HAVE)
3. **Compute budget** — total estimated GPU-hours
4. **Method details** from `FINAL_PROPOSAL.md` — what exactly to implement

Present a brief summary:

```
📋 Experiment plan loaded:
- Milestones: [N] (sanity → baseline → main → ablation)
- Must-run experiments: [N]
- Nice-to-have: [N]
- Estimated GPU-hours: [X]

Proceeding to implementation.
```

### Phase 2: Implement Experiment Code

**Routing**: Before starting implementation, resolve the experiment_implementer model:
```bash
python tools/model_route.py experiment_implementer
```
This outputs the model to use (default: `deepseek-v4-pro`). The implementer is a generation role — always LLM, never Codex. The resolved model is used throughout Phase 2.

**If `BASE_REPO` is set** — clone the repo first:
```bash
git clone <BASE_REPO> base_repo/
# Read the repo's README, understand its structure, find entry points
# Implement experiments by modifying/extending this codebase
```

For each milestone (in order), write the experiment scripts:

1. **Check existing code** — scan the project (or cloned `base_repo/`) for existing experiment scripts, model code, data loaders. Reuse as much as possible.

2. **Implement missing pieces:**
   - Training scripts with proper argparse (all hyperparameters configurable)
   - Evaluation scripts computing the specified metrics
   - Data loading / preprocessing if needed
   - Baseline implementations if not already present
   - Fixed random seeds for reproducibility
   - Results saved to JSON/CSV for later analysis
   - Proper logging (wandb if configured in CLAUDE.md)

3. **Follow the plan's run order** — implement sanity-stage experiments first, then baselines, then main method, then ablations.

4. **Self-review before deploying:**
   - Are all hyperparameters from EXPERIMENT_PLAN.md reflected in argparse?
   - Is the random seed fixed and controllable?
   - Are results saved in a parseable format (JSON/CSV)?
   - Does the code match FINAL_PROPOSAL.md's method description?

### Phase 2.5: Cross-Model Code Review (when CODE_REVIEW = true)

**Routing**: Before reviewing, resolve the experiment_code_reviewer model:
```bash
python tools/model_route.py experiment_code_reviewer
```

This role is a critical gate:
- `codex_required` → Codex only; fail if unavailable (do NOT skip silently)
- `codex_preferred` → try Codex first; fallback to LLM with WARNING logged
- `deepseek_only` → skip Codex explicitly; use fallback model directly

**Skip this step if `CODE_REVIEW` is `false`.** If skipping, print a WARNING: "Code review is DISABLED (CODE_REVIEW=false). Experiment code deployed WITHOUT cross-model review. This is NOT recommended."

Send the experiment code for review following the route resolved above:

```
# Example: Codex route
python tools/llm_call_ledger.py start experiment-bridge experiment_code_reviewer codex
mcp__codex__codex:
  config: {"model_reasoning_effort": "xhigh"}
  prompt: |
    Review the following experiment implementation for correctness.
    ...
    For each issue found, specify: CRITICAL / MAJOR / MINOR and the exact fix.
python tools/llm_call_ledger.py finish \
  --actual-backend codex --codex-thread-id <id> \
  --isolation-mode codex_thread

# Example: LLM fallback route
python tools/llm_call_ledger.py start experiment-bridge experiment_code_reviewer llm-chat <model>
mcp__llm-chat__chat:
  model: <model>
  ...
python tools/llm_call_ledger.py finish \
  --actual-backend llm-chat --actual-model <model>
```

**On review results:**
- **No CRITICAL issues** → proceed to Phase 3
- **CRITICAL issues found** → fix them, then re-submit for review (max 2 rounds)
- **Codex unavailable AND codex_required** → FAIL: do NOT proceed. Report: "Codex review required by ARIS_CODEX_GATE_MODE but Codex is unavailable."
- **Codex unavailable AND codex_preferred** → fallback to LLM with WARNING logged via `llm_call_ledger.py fallback`. Proceed only after fallback review passes.

### Phase 3: Sanity Check (if SANITY_FIRST = true)

Before deploying the full experiment suite, run the sanity-stage experiment:

```
/run-experiment [sanity experiment command]
```

Wait for completion. Verify:
- Training loop runs without errors
- Metrics are computed and saved correctly
- GPU memory usage is within bounds
- Output format matches expectations

If sanity fails → **auto-debug before giving up** (max 3 attempts):

1. **Read the error** — parse traceback, stderr, and log files
2. **Diagnose** — classify the failure:
   - OOM → reduce batch size or enable gradient checkpointing
   - ImportError → install missing package
   - FileNotFoundError → fix path or download data
   - CUDA error → check GPU availability, reduce model size
   - NaN/divergence → reduce learning rate, check data preprocessing
3. **Fix and re-run** — apply the fix, re-run sanity
4. **Attempt 2+ still failing? → Call in Codex rescue** (if Codex plugin installed):
   Before the next retry, invoke `/codex:rescue` to get a second opinion on the root cause. Codex independently reads the code and error logs — it may spot issues Claude missed (wrong tensor shapes, subtle import shadowing, config mismatches, etc.). Apply its suggested fix, then re-run.
   - If `/codex:rescue` is not available (plugin not installed), continue with Claude's own diagnosis
5. **Still failing after 3 attempts?** → stop, report the failure with all attempted fixes and error logs. Do not proceed with broken code.

> Never give up on the first failure. Most experiment crashes are fixable without human intervention.

### Phase 4: Deploy Full Experiments

Deploy experiments following the plan's milestone order. **Route by job count**:

**Small batch (≤5 jobs per milestone)** → use `/run-experiment` directly:
```
/run-experiment [experiment commands]
```

**Large batch (≥10 jobs, multi-seed sweeps, or phase dependencies)** → use `/experiment-queue` for proper orchestration:
```
/experiment-queue [grid spec or manifest]
```

Auto-routing rule: if any milestone in `EXPERIMENT_PLAN.md` declares ≥10 jobs (e.g., `seeds: [42, 200, 201, ...]` × `N: [64, 128, 256]` × `n: [50K, 150K, 500K, 652K]` = 36 jobs) or declares teacher→student phase dependencies, route that milestone to `/experiment-queue`. Otherwise use `/run-experiment`.

`/experiment-queue` adds: OOM-aware retry with backoff, stale-screen cleanup, wave-transition race prevention, phase dependency enforcement, crash-safe state persistence in `queue_state.json`. See `skills/experiment-queue/SKILL.md` for the manifest YAML format.

For each milestone:
1. Deploy experiments in parallel (up to MAX_PARALLEL_RUNS for `/run-experiment`, or `max_parallel` from manifest for `/experiment-queue`)
2. Use `/monitor-experiment` to track progress (reads from queue_state.json if `/experiment-queue` is active)
3. Collect results as experiments complete

**🚦 Checkpoint (if AUTO_DEPLOY = false):**

```
🔧 Code implementation complete. Ready to deploy:

Milestone 0 (sanity): [status — passed/pending]
Milestone 1 (baseline): [N experiments, ~X GPU-hours]
Milestone 2 (main method): [N experiments, ~X GPU-hours]
Milestone 3 (ablations): [N experiments, ~X GPU-hours]

Total estimated: ~X GPU-hours on [N] GPUs

Deploy now? Or review the code first?
```

### Phase 5: Collect Initial Results

As experiments complete:

1. **Parse output files** (JSON/CSV/logs) for key metrics
2. **Training quality check** — if W&B data is available (CLAUDE.md has `wandb: true` and `wandb_project`), invoke `/training-check` to detect NaN, loss divergence, plateaus, or overfitting. If W&B is not configured, skip silently.
3. **Update `refine-logs/EXPERIMENT_TRACKER.md`** — fill in Status and Notes columns
4. **Check success criteria** from EXPERIMENT_PLAN.md — did each experiment meet its bar?
4. **Write initial results summary:**

```markdown
# Initial Experiment Results

**Date**: [today]
**Plan**: refine-logs/EXPERIMENT_PLAN.md

## Results by Milestone

### M0: Sanity — PASSED
- [result]

### M1: Baselines
| Run | System | Key Metric | Status |
|-----|--------|-----------|--------|
| R001 | baseline_1 | X.XX | DONE |

### M2: Main Method
| Run | System | Key Metric | Status |
|-----|--------|-----------|--------|
| R003 | our_method | X.XX | DONE |

### M3: Ablations
...

## Summary
- [X/Y] must-run experiments completed
- Main result: [positive/negative/inconclusive]
- Ready for /auto-review-loop: [YES/NO]

## Next Step
→ /auto-review-loop "[topic]"
```

### Phase 5.5: Write Compact Log (when COMPACT = true)

**Skip entirely if `COMPACT` is `false`.**

Append each completed experiment to `EXPERIMENT_LOG.md`:

```markdown
## [Run ID] — [timestamp]
- **System**: [method name]
- **Config**: [key hyperparameters]
- **Result**: [primary metric = X.XX]
- **Verdict**: [positive / negative / inconclusive]
- **Reproduce**: `python train.py --config configs/run_id.yaml --seed 42`
```

This structured log survives session recovery — downstream skills read it instead of parsing screen output.

### Phase 5.6: Auto Ablation Planning

After main experiments (M2) complete with positive results, invoke `/ablation-planner` to design ablation studies:

- Read the main results and method description
- Generate a claim-driven ablation plan: which components to remove, what to compare, expected outcomes
- Append ablation blocks to `refine-logs/EXPERIMENT_PLAN.md` and `refine-logs/EXPERIMENT_TRACKER.md`
- If main results are negative or inconclusive, skip ablation planning and note in the summary

If `/ablation-planner` is not available, skip silently — the existing EXPERIMENT_PLAN.md ablation blocks (if any) remain unchanged.

### Phase 6: Handoff

Present final status:

```
🔬 Experiment bridge complete:
- Implemented: [N] experiment scripts
- Deployed: [N] experiments on [M] GPUs
- Completed: [X/Y] must-run, [A/B] nice-to-have
- Main result: [one sentence]

Results: refine-logs/EXPERIMENT_RESULTS.md
Tracker: refine-logs/EXPERIMENT_TRACKER.md

Ready for Workflow 2:
→ /auto-review-loop "[topic]"
```

## Output Protocols

> Follow these shared protocols for all output files:
> - **[Output Versioning Protocol](../shared-references/output-versioning.md)** — write timestamped file first, then copy to fixed name
> - **[Output Manifest Protocol](../shared-references/output-manifest.md)** — log every output to MANIFEST.md
> - **[Output Language Protocol](../shared-references/output-language.md)** — respect the project's language setting

## Key Rules

- **CRITICAL — Evaluation must use dataset ground truth.** When writing evaluation scripts, ALWAYS compare model predictions against the dataset's actual ground truth labels/targets — NEVER use another model's output as ground truth. Double-check: (1) ground truth comes from the dataset split, not from a baseline/backbone model, (2) evaluation metrics are computed against the same ground truth for all methods, (3) if the task has official eval scripts, use those.
- **Follow the plan.** Do not invent experiments not in EXPERIMENT_PLAN.md. If you think something is missing, note it but don't add it.
- **Sanity first.** Never deploy a full suite without verifying the sanity stage passes.
- **Reuse existing code.** Scan the project before writing new scripts. Extend, don't duplicate.
- **Save everything as JSON/CSV.** The auto-review-loop needs parseable results, not just terminal output.
- **Update the tracker.** `EXPERIMENT_TRACKER.md` should reflect real status after each run completes.
- **Don't wait forever.** If an experiment exceeds 2x its estimated time, flag it and move on to the next milestone.
- **Budget awareness.** Track GPU-hours against the plan's budget. Warn if approaching the limit.
- **Vast.ai lifecycle.** If using vast.ai instances, destroy them after all experiments complete and results are downloaded. Running instances cost money every second — don't leave them idle. Use `/vast-gpu destroy` or `/vast-gpu destroy-all` when done.
- **Modal lifecycle.** If using `gpu: modal`, no cleanup is needed — Modal auto-scales to zero after each run. But always show cost estimates before running and verify the spending limit is set at https://modal.com/settings (NEVER through CLI).

## Reliability Additions

### Research Contract Gate
在 Phase 4（部署 full experiment）前，检查 `docs/research_contract.md` 是否存在：
- 如果存在：验证 contract 中的 success/failure signals、metrics、data split 与实验计划一致。
- 如果不存在：提示先运行 `/research-contract`。
- pilot/sanity 阶段可软通过（标记 provisional）。

### Baseline Report Gate
在 Phase 4 前，检查 `research/BASELINE_REPRODUCTION_REPORT.md` 是否存在：
- 如果存在：验证 baseline 复现可信度。
- 如果不存在：提示先运行 `/baseline-repro`。
- soft gate：允许跳过但记录 warning。

### Experiment Code Review
在 Phase 2.5（cross-model code review）执行后，检查 review verdict：
- 如果 review 返回 CRITICAL 问题：必须修复后重新提交 review，最多 2 轮。
- 如果 Codex review 不可用且配置为 codex_required：停止，不可跳过。
- 如果 Codex review 不可用且配置为 codex_preferred：fallback 到 LLM，记录 WARNING。
- 如果 CODE_REVIEW=false：打印 WARNING 后继续。
- review 结果写入 artifact header（routing_source, global_codex_gate_mode, actual_backend, actual_model, fallback_used, codex_used）。

### Pre-Implementation Code Scan
实现代码前，优先扫描现有代码和 base repo（如果 `BASE_REPO` 设置了），标识可复用的部分。

### Session Handoff
每个 milestone 完成后记录 session handoff，输出到 `.aris/sessions/HANDOFFS/`。

## Composing with Other Skills

```
/idea-discovery "direction"          ← Workflow 1: find + refine + plan
/experiment-bridge                   ← you are here (Workflow 1.5: implement + deploy)
/auto-review-loop "topic"            ← Workflow 2: review + iterate
/paper-writing "NARRATIVE_REPORT.md" ← Workflow 3: write the paper

Or use /research-pipeline for the full end-to-end flow (includes this bridge).
```

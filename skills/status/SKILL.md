---
name: status
description: Show current ARIS idea discovery workflow status (AGENTIC scope by default)
argument-hint: [--all | legacy | experiments]
allowed-tools: Bash(*), Read, Grep, Glob
---

# Status

## Purpose

统一查看 ARIS 当前 **idea discovery workflow** 状态。默认只关注 `idea-stage/AGENTIC/`，不混入旧项目状态。

## When to Use

- 想知道当前 idea discovery pipeline 整体状态时。
- 怀疑 reviewer 卡住时。
- pipeline 运行后。
- 新 session 开始时。

## Scope

```
current_scope = idea-stage/AGENTIC
```

| Mode | Command | Scope |
|------|---------|-------|
| **Default** | `/status` | Only `idea-stage/AGENTIC/` + `.aris/calls/` (filtered) |
| Full | `/status --all` | Everything including old projects |
| Legacy | `/status legacy` | `review-stage/`, old experiments, paper writing |
| Experiments | `/status experiments` | `EXPERIMENT_LOG.md`, `refine-logs/`, `experiments/` |

## Inputs

### Default mode (AGENTIC scope)

- `idea-stage/AGENTIC/LITERATURE_INDEX.md`
- `idea-stage/AGENTIC/GAP_MAP.md`
- `idea-stage/AGENTIC/EVIDENCE_AUDIT/`
- `idea-stage/AGENTIC/IDEA_BANK.md`
- `idea-stage/AGENTIC/IDEA_BANK.json`
- `idea-stage/AGENTIC/CANONICAL_IDEAS/`
- `idea-stage/AGENTIC/REVIEWS/`
- `idea-stage/AGENTIC/NOVELTY/`
- `.aris/calls/llm_calls.jsonl` (filtered to current workflow)
- `.aris/calls/current_call.json`
- `.aris/sessions/SESSION_REGISTRY.json`
- `.aris/sessions/ACTIVE_TASKS.json`

### Extra inputs for --all / legacy / experiments modes

- `review-stage/REVIEW_STATE.json`
- `review-stage/AUTO_REVIEW.md`
- `experiment_queue/*/queue_state.json`
- `EXPERIMENT_LOG.md`
- `refine-logs/EXPERIMENT_TRACKER.md`
- `config/status.json`

## Outputs

- status summary in chat/terminal only

## Workflow

1. **Determine mode**: Check `$ARGUMENTS` for `--all`, `legacy`, or `experiments`. Default is AGENTIC-scoped.
2. **Read resume state**: Call `tools/resume_stage_state.py` for each phase to determine current stage.
3. **Read AGENTIC artifacts**: LITERATURE_INDEX.md, GAP_MAP.md, evidence audit, IDEA_BANK, canonical ideas, reviews, novelty reports.
4. **Read current call**: `current_call.json` — show any active model call.
5. **Filter llm_calls.jsonl**: Show only calls whose `output_files` reference `idea-stage/AGENTIC/` (or the last 3 completed calls).
6. **Read active sessions**: `SESSION_REGISTRY.json` and `ACTIVE_TASKS.json` — filter out TEST ONLY sessions by default.
7. **Show current Codex routing config**: Read `ARIS_CODEX_GATE_MODE` from `.env` (default: codex_preferred). Display:
   ```
   Codex gate mode: <mode>
   ```
   If `deepseek_only`: add warning "Codex disabled by .env; critical gates use DeepSeek V4 Pro with downgraded confidence."
   If `codex_preferred` and any fallback occurred: add warning "Codex unavailable; fallback used."
8. **Infer current pipeline phase** from resume_stage_state.py results:
   - no_stage / not_started → idea discovery not begun
   - research-lit incomplete → literature survey
   - idea-creator incomplete → idea generation
   - exec-review incomplete → review in progress
   - novelty-check incomplete → novelty check in progress
   - All phases complete → ready for final selection
8. **Output next step** based on resume_stage_state.py actions.

## Hard Rules

- status 只读，不修改项目。
- 不泄露 API Key。
- 不读取大型日志全文，只读摘要或 tail。
- 如果某状态文件不存在，应标记 not initialized，不报错。
- **Default 模式不得读取并给出建议：**
  - `review-stage/`（旧 review 状态）
  - `experiment_queue/`（旧实验队列）
  - `research/`（旧研究）
  - `EXPERIMENT_LOG.md`（旧实验日志）
  - `refine-logs/`（旧实验记录）
  - 非 AGENTIC 的旧实验/paper-writing stage
- **Default 模式隐藏 TEST ONLY sessions**：session/task 描述包含 "TEST ONLY"、"test handoff"、"Search papers for test" 时默认隐藏，仅 `--all` 显示。
- 默认基于 `tools/resume_stage_state.py` 计算 next step，而非手动推断。

## Session Filtering

Default 模式过滤 sessions:

| Session / Task Description | Default | --all |
|---------------------------|---------|-------|
| "TEST ONLY: ..." | Hidden | Shown |
| "test handoff state" | Hidden | Shown |
| "Search papers for test" | Hidden | Shown |
| Other tasks | Shown | Shown |

## Failed Calls Filtering

Default 模式只显示当前 workflow 相关失败。旧失败或 fallback DNS 错误标记为 archived warnings，不作为当前 blocker，除非 `output_files` 指向 `idea-stage/AGENTIC/`。

## Next Steps Rules

Default 模式必须基于 `resume_stage_state.py` 计算：

```bash
python3 tools/resume_stage_state.py research-lit
python3 tools/resume_stage_state.py idea-creator
python3 tools/resume_stage_state.py exec-review CAND_001
python3 tools/resume_stage_state.py exec-review CAND_002
python3 tools/resume_stage_state.py novelty-check CAND_001
python3 tools/resume_stage_state.py novelty-check CAND_002
```

合理 next step 例子：
- 如果 CAND_002 exec-review needs_resume → 运行 `/exec-review CAND_002`
- 如果 CAND_002 novelty-check needs_resume → 运行 `/novelty-check CAND_002`
- 如果 review/novelty 完成但 final-selection 是 not_started 或 needs_resume → 运行 `/idea-bank "final-select CAND_001"`
- 如果 final-selection 是 complete_with_warnings → 显示 "Final selection: complete_with_warnings via DeepSeek V4 Pro fallback"，加 warning "Codex was not used"，建议可选 rerun `/idea-bank "final-select CAND_001"` 当 Codex 可用时。
- **不得建议 paper writing / experiments**，除非 final selection 已完成（通过正式 Codex gate 或 llm_fallback_gate）且用户显式进入实验/写作阶段。
- **research-contract 可以在 llm_fallback_gate 后进入**，但必须注明 final_selection_backend: deepseek-v4-pro, codex_used: false, rerun_codex_final_selector_recommended: true。

## Failure Handling

- JSON 损坏则标记 corrupt。
- queue_state 不存在则说明没有 experiment queue（default 模式不读取）。
- current_call 卡住超过阈值则提示可能 stuck。
- resume_stage_state.py 调用失败则降级到人工推断。

## Integration

- `tools/resume_stage_state.py` — 阶段状态检查
- `tools/llm_call_ledger.py` — 调用记录
- `.aris/calls/llm_calls.jsonl` — 模型调用日志
- `.aris/sessions/SESSION_REGISTRY.json` — session 注册
- `.aris/sessions/ACTIVE_TASKS.json` — 活跃任务
- `tools/validate_model_invocation.py` — 模型调用可信验证

## Model Invocation Trust Status

**Required**: `/status` must show model invocation trust status.

Run:
```
python tools/validate_model_invocation.py --summary
```

Display a table of key roles with their invocation status:

| Role | Expected Backend | Actual Backend | Source | Verified | Allowed Next |
|------|-----------------|----------------|--------|----------|--------------|
| idea_reviewer | codex | codex | routed_internal_model | ✅ | YES |
| experiment_implementer | llm-chat | - | no_ledger | ❌ | NO |
| ... | ... | ... | ... | ... | ... |

**Trust status rules:**
- `implementation_source=external_agent_direct` → show "⚠️ external" badge
- `verification_status=verified_routed_call` → show "✅ verified"
- `verification_status=codex_missing_thread_id` → show "❌ codex thread missing"
- `verification_status=unverified_external_execution` → show "❌ unverified"
- `allowed_next_stage=false` → show "🚫 blocked"
- `confidence_downgraded=true` → show "⚠️ confidence_downgraded"

**If `validate_model_invocation.py` is missing or fails:**
Display:
```
⚠️  model invocation trust cannot be verified
```

## Example Invocation

```
/status                    # AGENTIC scope only (default)
/status --all              # full project scope
/status legacy             # include old review/experiment state
/status experiments        # include experiment logs
```

## Expected Output

- 当前 scope (AGENTIC / --all / legacy / experiments)
- 当前 pipeline phase (from resume_stage_state.py)
- 活跃任务（filtered, hidden test-only）
- 活跃模型调用
- AGENTIC 实验/artifact 状态
- 失败调用（只显示当前 workflow 相关的）
- 下一步建议（基于 resume_stage_state.py）

## Global Trusted Role Execution

All `/status` displays rely on the global ARIS trusted role execution protocol.
See `skills/shared-references/trusted-role-execution.md` for the binding rules that
govern all ROLE_* tasks — model_route.py is a declaration only, trusted execution
must go through `tools/trusted_role_runner.py`, and external agents cannot masquerade
as internal model execution.

## Failure Example

如果 `idea-stage/AGENTIC/` 不存在：
- 标记 AGENTIC 阶段为 not initialized
- 建议先运行相关 skill

## Recovery Step

如果 `current_call.json` 卡住：
- 提示手动检查 `.aris/calls/current_call.json`
- 如果状态为 started 且超过 30 分钟，提示可能 stuck

如果 `resume_stage_state.py` 调用失败：
- 降级到人工推断阶段
- 提示用户检查 tools/ 目录完整性

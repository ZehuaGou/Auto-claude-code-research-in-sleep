---
name: status
description: Show unified ARIS project status: pipeline, sessions, experiments, reviewer calls, model usage, config warnings, and next action.
argument-hint: [--full]
allowed-tools: Bash(*), Read, Grep, Glob
---

# Status

## Purpose

统一查看 ARIS 当前状态，不只是实验状态。解决 Calling codex...、实验卡住、reviewer 卡住、用户不知道系统在干什么的问题。

## When to Use

- 想知道当前项目整体状态时。
- 怀疑 reviewer 卡住时。
- pipeline 运行后。
- 新 session 开始时。

## Inputs

- `.aris/sessions/SESSION_REGISTRY.json`（如存在）
- `.aris/sessions/ACTIVE_TASKS.json`（如存在）
- `.aris/calls/current_call.json`
- `.aris/calls/llm_calls.jsonl`
- `review-stage/REVIEW_STATE.json`（如存在）
- `experiment_queue/*/queue_state.json`（如存在）
- `config/status.json`
- `review-stage/AUTO_REVIEW.md`（如存在）
- `EXPERIMENT_LOG.md`（如存在）
- `refine-logs/EXPERIMENT_TRACKER.md`（如存在）

## Outputs

- status summary in chat/terminal only

## Workflow

1. 读取 `config/status.json`，展示配置警告。
2. 读取 `current_call.json`，展示当前是否有模型调用。
3. 读取 `llm_calls.jsonl`，展示最近一次模型调用。
4. 读取 `SESSION_REGISTRY.json` 和 `ACTIVE_TASKS.json`，展示活跃 session。
5. 读取 `queue_state.json`，展示实验队列。
6. 读取 `REVIEW_STATE.json`，展示 review loop 状态。
7. 读取 `EXPERIMENT_TRACKER.md` / `EXPERIMENT_LOG.md`，展示实验状态。
8. 推断当前 pipeline 阶段：
   - no idea
   - idea discovery
   - novelty check
   - baseline reproduction
   - research contract
   - experiment implementation
   - experiment running
   - result-to-claim
   - paper writing
   - final audit
9. 输出下一步建议。

## Hard Rules

- status 只读，不修改项目。
- 不泄露 API Key。
- 不读取大型日志全文，只读摘要或 tail。
- 如果某状态文件不存在，应标记 not initialized，不报错。

## Failure Handling

- JSON 损坏则标记 corrupt。
- queue_state 不存在则说明没有 experiment queue。
- current_call 卡住超过阈值则提示可能 stuck。

## Integration

- `tools/llm_call_ledger.py` — 读取调用记录
- `tools/config_check.py` — 配置检查
- `tools/session_registry.py` — session 信息
- `skills/model-usage-status/SKILL.md` — 模型调用详情

## Example Invocation

```
/status
/status --full
```

## Expected Output

- 当前阶段
- 活跃任务
- 活跃模型调用
- 实验状态
- fallback 警告
- 下一步建议

## Failure Example

如果 `.aris/` 目录不存在：
- 标记各项为 not initialized
- 建议先运行相关 skill

## Recovery Step

如果 `current_call.json` 卡住：
- 提示手动检查 `.aris/calls/current_call.json`
- 如果状态为 started 且超过 30 分钟，提示可能 stuck

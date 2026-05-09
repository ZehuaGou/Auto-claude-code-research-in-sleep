---
name: panel-review
description: Manage multi-round reviewer sessions for complex ideas, paper risks, method debates, or experiment failures.
argument-hint: [topic-or-task-id]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply, mcp__llm-chat__chat
---

# Panel Review

## Purpose

用于需要多轮上下文的 reviewer session。

## When to Use

- 复杂 idea 打磨。
- 论文漏洞追问。
- 方法风险辩论。
- 实验异常定位。
- reviewer 需要记住上一轮怀疑点。

## Inputs

- `task_id`
- initial context files
- previous handoff，如有
- reviewer memory，如有

## Outputs

`review-stage/panel_reviews/<task_id>/`：
- `ROUND_001.md`
- `ROUND_002.md`
- `REVIEWER_MEMORY.md`
- `PANEL_SUMMARY.md`
- `.aris/sessions/HANDOFFS/<task_id>.md`

## Workflow

1. 创建 `review-stage/panel_reviews/<task_id>/` 目录。
2. 初始化 reviewer memory。
3. Round 1：给 reviewer 文件路径和任务。
4. 保存 raw response。
5. 主 session 可写 rebuttal。
6. Round 2+：继续追问或要求 reviewer ruling。
7. 每轮写 `ROUND_xxx.md`。
8. 最后写 `PANEL_SUMMARY.md`。
9. 写 session handoff。

## Hard Rules

- panel session 有自己的上下文。
- 每轮输出 handoff 或 round 文件。
- 不允许 reviewer 只在聊天里说完不落盘。
- 所有调用必须写 `llm_calls.jsonl`。
- fallback 必须显式标记。

## Integration

- `tools/llm_call_ledger.py` — 调用记录
- `skills/session-handoff/SKILL.md` — 最终 handoff
- `skills/shared-references/model-routing.md` — 模型路由
- `skills/exec-review/SKILL.md` — 一次性审查替代方案

## Example Invocation

```
/panel-review "Is the method theoretically sound?"
/panel-review task_001
```

## Expected Artifacts

- `review-stage/panel_reviews/<task_id>/ROUND_001.md`
- `review-stage/panel_reviews/<task_id>/PANEL_SUMMARY.md`
- `.aris/sessions/HANDOFFS/<task_id>.md`

## Failure Example

如果 Codex 在某轮超时：
- 记录该轮为 incomplete
- 可继续下一轮
- 标记 degraded

## Recovery Step

如果 reviewer 偏离主题：
- 在下一轮给出更具体的 prompt
- 不要重新开始

## Status / Ledger

每轮调用必须写入：
- `.aris/calls/current_call.json`
- `.aris/calls/llm_calls.jsonl`

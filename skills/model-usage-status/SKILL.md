---
name: model-usage-status
description: Show recent Codex / LLM Chat / DeepSeek calls, fallback events, failures, and current active call.
argument-hint: [--recent 20]
allowed-tools: Bash(*), Read, Grep, Glob
---

# Model Usage Status

## Purpose

让用户知道 ARIS 当前到底调用了 Codex、deepseek-v4-pro、deepseek-v4-flash，是否发生 fallback。

## When to Use

- 想知道最近模型调用情况。
- reviewer 卡住时。
- 怀疑有 silent fallback 时。
- 调试模型路由时。
- status skill 或 research-pipeline 阶段性显示。

## Inputs

- `.aris/calls/llm_calls.jsonl`
- `.aris/calls/current_call.json`
- `config/status.json`

## Outputs

- 终端/聊天中的模型调用状态表（仅终端输出，不写入文件）

## Workflow

1. 检查 `.aris/calls/` 是否存在，不存在则提示尚无调用记录。
2. 读取 `current_call.json`，判断是否有正在进行的调用。
3. 读取 `llm_calls.jsonl`。
4. 统计：
   - Codex 调用次数
   - LLM Chat 调用次数
   - deepseek-v4-pro 调用次数
   - deepseek-v4-flash 调用次数
   - fallback 次数
   - failed 次数
   - 各 skill 调用次数
5. 输出最近 20 次调用表格。
6. 标记所有 `completed_with_fallback`。
7. 不显示 API Key，不显示完整 prompt。

输出表格字段：

| Time | Skill | Role | Primary | Actual | Status | Fallback | Error |

## Hard Rules

- 不泄露 API Key。
- 不泄露完整 prompt。
- 不修改调用账本。
- 只读状态。

## Failure Handling

- `llm_calls.jsonl` 不存在：输出"暂无调用记录"。
- `current_call.json` 损坏：标记 corrupt 并提示检查。
- JSONL 某行损坏：跳过该行并报告 skipped count。

## Integration

- `tools/llm_call_ledger.py` — 读取调用记录
- `skills/status/SKILL.md` — 统一状态展示的一部分

## Example Invocation

```
/model-usage-status
/model-usage-status --recent 50
```

## Expected Artifacts

- 无输出文件（仅终端/聊天输出）

## Failure Example

如果 `llm_calls.jsonl` 不存在：
- 输出 "暂无调用记录，请先运行需要调用模型的 skill"
- 不报错

## Recovery Step

如果 `current_call.json` 卡住（status=started 超过 30 分钟）：
- 提示可能 stuck
- 建议手动清空或等待

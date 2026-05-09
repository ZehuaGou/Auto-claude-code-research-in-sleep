---
name: session-handoff
description: Write structured handoff files between ARIS sessions.
argument-hint: [task-id]
allowed-tools: Bash(*), Read, Write, Edit
---

# Session Handoff

## Purpose

规范 session 之间的交接文件，让主 session 不需要读大量过程日志也能判断下一步。

## When to Use

- 副 session 完成任务后。
- 需要把结果传递给主 session 时。
- 多个 session 之间交接时。

## Inputs

- `task_id`
- 副 session 产生的输出文件
- session notes
- 判断和证据

## Output

`.aris/sessions/HANDOFFS/<task_id>.md`

## Workflow

1. 读取当前 task 状态。
2. 收集输出文件和关键结果。
3. 生成 handoff 文件。

## Handoff 模板

每份 handoff 必须包含：

```
# Handoff: <task_id>

## Metadata
- task_id:
- role:
- session_id:
- created_at:
- status: done / blocked / failed / needs_review

## Input Files
- ...

## Output Files
- ...

## Decision
明确说明本 session 做出了什么判断。

## Evidence
列出支持判断的文件、指标、日志、论文段落。

## Failure Modes
列出可能错在哪里。

## Unresolved Questions
列出未解决问题。

## Next Action
明确建议主 session 下一步做什么。

## Do Not Assume
列出主 session 不能擅自假设的东西。
```

## Hard Rules

- 不允许只在聊天里交接。
- 不允许副 session 不落盘。
- handoff 必须足够让主 session 不读原始长日志也能判断下一步。
- 如果 evidence 不足，必须写 evidence insufficient。

## Tool Integration

可通过 `tools/session_registry.py handoff <task_id> [status]` 自动生成 handoff 模板文件。

```bash
python3 tools/session_registry.py handoff task_001 draft
```

**注意：**
- 自动生成的 handoff 只是**模板**，不包含实际判断内容
- 生成后必须由执行该任务的 Agent 填充 `Decision` / `Evidence` / `Failure Modes` / `Next Action` 等字段
- 如果 evidence 不足，必须写 `evidence insufficient`，不能留空或编造
- 自动生成模板不能替代最终判断

### Handoff Status 语义

| 状态 | 含义 | 主 session 应如何处理 |
|------|------|----------------------|
| `draft` | 刚生成模板，还未填写内容 | ⚠️ 不能作为最终判断 |
| `needs_review` | handoff 仍有 TODO 或 evidence 不足 | ⚠️ 不能作为最终判断 |
| `done` | Decision / Evidence / Next Action 已填写，且无 TODO | ✅ 可信任 |
| `failed` | 任务失败 | ❌ 需要重新规划 |
| `blocked` | 任务被阻塞 | ❌ 需要解决阻塞 |

只有 `done` 状态的 handoff 才会将 session 设为 idle 并清空 current_task。

## Integration

- `tools/session_registry.py` — 读取 session 和 task 信息
- `skills/session-orchestrator/SKILL.md` — 主调度
- `skills/shared-references/session-protocol.md` — session 协议

## Example Invocation

```
/session-handoff task_001
```

## Expected Artifacts

- `.aris/sessions/HANDOFFS/<task_id>.md`

## Failure Example

如果 task_id 不存在：
- 提示 task not found
- 列出当前活跃 tasks

## Recovery Step

如果 handoff 文件损坏：
- 重新收集输出
- 重新生成 handoff

## Status / Ledger

本 skill 不调用模型，不写入 ledger。

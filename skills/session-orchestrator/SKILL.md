---
name: session-orchestrator
description: Manage ARIS multi-session research workflow with role-specific sessions and file-based handoffs.
argument-hint: [init|start|list|close|assign]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Session Orchestrator

## Purpose

管理多 session，防止一个主 session 塞满所有上下文。主 session 只做调度和判断，副 session 做具体任务并通过文件 handoff。

## When to Use

- 需要分配长任务给副 session。
- 主 session 上下文快满时。
- 需要在多个角色之间分工时。

## Inputs

- 用户指定 role 和 task

## Outputs

- `.aris/sessions/SESSION_REGISTRY.json`
- `.aris/sessions/ACTIVE_TASKS.json`

## Workflow

1. `init`：创建 `.aris/sessions` 目录和两个 JSON。
2. `register`：注册一个新 session（指定 role）。
3. `assign`：创建 task 并指定 role。
4. `list`：展示当前 sessions。
5. `close`：关闭 session。

## Session Types

| Type | Prefix | Duties |
|------|--------|--------|
| main_architect | `arch_` | 读 handoff，判断下一步，更新状态。不跑长任务 |
| literature_scout | `lit_` | 搜索论文，调用 research-lit / arxiv / paper-ingest |
| idea_generator | `idea_` | 生成 idea cards。不评审自己的 idea |
| idea_reviewer | `irev_` | 独立审查单个 idea card |
| novelty_checker | `nov_` | 针对 selected idea 查新 |
| baseline_reproducer | `base_` | 选择 baseline，复现 baseline |
| experiment_implementer | `impl_` | 根据 research_contract 修改代码 |
| experiment_runner | `run_` | 跑实验。不判断论文 claim |
| result_judge | `judge_` | 根据 contract 和实验结果判断 claim |
| paper_writer | `write_` | 根据 evidence table 写论文 |
| adversarial_reviewer | `arev_` | 最终审查。找漏洞 |

## Hard Rules

- 主 session 不跑长任务。
- 副 session 只读指定 input_files。
- 副 session 必须写 handoff。
- 主 session 只读 handoff，不读大量过程日志。
- 不允许只在聊天里交接。

## Context Isolation Model

当前 session-orchestrator 是**文件级 session registry + handoff protocol**，不是自动多进程管理器。

### What This Tool Does
- 注册逻辑 session（registry）
- 分配和跟踪 task（active tasks）
- 生成 handoff 模板文件
- 维护 session 状态机（active / idle / closed / failed）

### What This Tool Does NOT Do
- **不会自动启动多个真实 Claude/Claude Code 进程**
- **不会自动隔离模型上下文** — 如果外层 Agent 不新开窗口，所有 session 共享同一上下文
- **不会自动创建 tmux panel 或子进程**
- **不会阻止主 session 读取副 session 日志** — 这是约定而非强制

### How Real Isolation Works

上下文隔离依赖**外层 Agent 的执行纪律**：

1. 用户或自动化脚本为每个角色**手动打开新的 Claude Code 会话**（新终端 / tmux panel）
2. 新会话只读取该角色所需的 `input_files`
3. 完成后通过 `/session-handoff` 写 handoff 文件
4. 主 session **只读 handoff**，不读副 session 的全量过程日志

```
┌─────────────────────┐     ┌──────────────────────┐
│  Main Session        │     │  Sub Session          │
│  (orchestrator)      │     │  (literature_scout)   │
│                      │     │                       │
│  read handoff only   │◄────│  write handoff        │
│  assign tasks        │     │  read input_files     │
│  make decisions      │     │  do the work          │
└─────────────────────┘     └──────────────────────┘
```

### Recommended Usage for Real Isolation

1. 主 session 运行 `/session-orchestrator init` + `register` + `assign`
2. 用户手动打开新的 Claude Code 终端（新 session）
3. 新 session 中只运行 `/session-handoff` 查看任务，读取指定 input_files
4. 完成工作后写 handoff 文件（先用 `tools/session_registry.py handoff <task_id> draft` 生成模板）
5. 填写 Decision / Evidence 等字段后，再执行 `handoff <task_id> done`（自动检查 TODO）
6. 主 session 读取 handoff，判断下一步

### Why Not Automatic Multi-Process

- 自动启动多个 Claude Code 进程需要平台级 API（tmux / OS process management）
- 多数用户环境（特别是 Windows）不支持可靠的子进程隔离
- 文件级 handoff 足够覆盖 90% 的上下文污染场景，无需复杂基础设施

## Failure Handling

- `SESSION_REGISTRY.json` 不存在则初始化。
- JSON 损坏则备份为 .bak 并重建空结构。
- session 超时则标记 stale。

## Integration

- `tools/session_registry.py` — session 注册管理
- `skills/session-handoff/SKILL.md` — 生成 handoff 文件
- `skills/shared-references/session-protocol.md` — session 协议

## Example Invocation

```
/session-orchestrator init
/session-orchestrator register literature_scout
/session-orchestrator assign sess_lit_001 "Search papers on anomaly detection"
/session-orchestrator list
/session-orchestrator close sess_lit_001
```

## Expected Artifacts

- `.aris/sessions/SESSION_REGISTRY.json`
- `.aris/sessions/ACTIVE_TASKS.json`

## Failure Example

如果 JSON 损坏：
- 备份为 `.bak`
- 重建空结构
- 提示用户检查备份

## Recovery Step

如果 session 超时：
- 标记 stale
- 建议关闭后重新注册

## Status / Ledger

本 skill 不直接调用模型，不写入 ledger。但 assign 的 task 可能由其他 skill 调用模型。

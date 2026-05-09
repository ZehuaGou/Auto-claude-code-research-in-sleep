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

session-orchestrator 是**文件级 session registry + handoff 协议**，不是自动多进程管理器。当前系统不声称已实现真实多进程隔离。

### What This Tool Does
- 注册逻辑 session（registry）
- 分配和跟踪 task（active tasks）
- 生成 handoff 模板文件（包含 Isolation Evidence）
- 维护 session 状态机（active / idle / closed / failed）
- 审计 task 完整性（`audit` / `audit --repair`）

### What This Tool Does NOT Do
- **不会自动启动多个真实 Claude/Claude Code 进程**
- **不会自动隔离模型上下文** — 如果外层 Agent 不新开窗口，所有 session 共享同一上下文
- **不会自动创建 tmux panel 或子进程**
- **不会阻止主 session 读取副 session 日志** — 这是约定而非强制

### Three Acceptable Isolation Modes

上下文的真实隔离有三种可接受模式：

| 模式 | 关键词 | 隔离程度 | 适用阶段 |
|------|--------|----------|----------|
| **manual_subsession** | 用户手动开新终端 / 新 Claude Code 会话 | 真实会话级隔离 | Phase 1/2/3/4/5/6 均可 |
| **codex_thread** | 使用独立 Codex MCP thread，prompt 不含主 session 上下文 | 模型级隔离 | 关键 judgment gate（Phase 3/4/5/final） |
| **protocol_only** | 仅文件级 registry + handoff，无真实进程/线程隔离 | 无隔离 | **仅** Phase 0（paper-ingest）/ 非关键任务 |

**protocol_only 限制：**
- 只能作为 fallback，不得用于 Phase 3（review）、Phase 4（novelty）、Phase 5（adversarial）、Phase 6（final selection）
- protocol_only 对关键审查只允许 PASS_WITH_WARNINGS，不允许完全 PASS
- 标记为 protocol_only 的 handoff 不得作为 gate 决策的唯一依据

### How Real Isolation Works

上下文隔离依赖**外层 Agent 的执行纪律**：

1. 用户或自动化脚本为每个角色**手动打开新的 Claude Code 会话**（新终端 / tmux panel）
2. 新会话只读取该角色所需的 `input_files`
3. 完成后通过 `/session-handoff` 写 handoff 文件
4. 主 session **只读 handoff**，不读副 session 的全量过程日志
5. 对于关键 judgment gate，优先使用 Codex MCP 独立 thread（codex_thread mode）

```
┌─────────────────────┐     ┌──────────────────────┐
│  Main Session        │     │  Sub Session          │
│  (orchestrator)      │     │  (literature_scout)   │
│                      │     │                       │
│  read handoff only   │◄────│  write handoff        │
│  assign tasks        │     │  read input_files     │
│  make decisions      │     │  do the work          │
└─────────────────────┘     └──────────────────────┘

┌─────────────────────┐     ┌──────────────────────┐
│  Main Session        │     │  Codex Thread         │
│  (orchestrator)      │     │  (critical gate)      │
│                      │     │                       │
│  read handoff only   │◄────│  write handoff        │
│  assign tasks        │     │  isolated prompt      │
│  make decisions      │     │  codex_thread_id      │
└─────────────────────┘     └──────────────────────┘
```

### Isolation Evidence Requirement

每个关键 gate 的 handoff 必须包含 Isolation Evidence 字段：

```
## Isolation Evidence
- isolation_mode: manual_subsession | codex_thread | protocol_only
- physical_new_session: yes | no
- codex_thread_id: <id> | none
- allowed_input_files: ...
- forbidden_context: generator_trace, raw IDEA_CARDS, old praise, ...
- actual_backend: codex | llm-chat | other
- actual_model: ...
```

**缺少 Isolation Evidence 的 handoff：**
- 不能作为关键 gate 的最终决策
- 必须标记 needs_review
- 主 session 读取时需明确标记 ISOLATION_EVIDENCE_MISSING

### Handoff Integrity: Done Must Not Contain TODO

- 如果 handoff 标记为 `done` 但仍包含 `TODO:` 字段 → **INVALID_DONE_WITH_TODO**
- 通过 `tools/session_registry.py audit` 可检测
- 通过 `tools/session_registry.py audit --repair` 自动降级为 `needs_review`
- 如果 `requested_status=done` 且 handoff 含 TODO → 工具自动 downgrade 为 `needs_review`
- 主 session 不应信任含 TODO 的 done 状态

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

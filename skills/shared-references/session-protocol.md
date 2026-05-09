# Session Protocol

## Purpose

定义 ARIS 多 session 管理的角色、交接、状态协议。

## Session Types

| Type | Prefix | Duties |
|------|--------|--------|
| main_architect | `arch_` | 读 handoff，判断下一步，更新状态。不跑长任务，不读大量原始日志，不直接执行大规模实验。 |
| literature_scout | `lit_` | 搜索论文，调用 research-lit / arxiv / paper-ingest。不做最终 novelty 判断。 |
| idea_generator | `idea_` | 生成 idea cards。不评审自己的 idea。 |
| idea_reviewer | `irev_` | 独立审查单个 idea card。不看其他 idea，不看生成过程。 |
| novelty_checker | `nov_` | 针对 selected idea 查新。 |
| baseline_reproducer | `base_` | 选择 baseline，复现 baseline。 |
| experiment_implementer | `impl_` | 根据 research_contract 修改代码。不改 data split / metric / baseline 标准。 |
| experiment_runner | `run_` | 跑实验。不判断论文 claim。 |
| result_judge | `judge_` | 根据 contract 和实验结果判断 claim。不写论文正文。 |
| paper_writer | `write_` | 根据 evidence table 写论文。不创造没有证据的 claim。 |
| adversarial_reviewer | `arev_` | 最终审查。找漏洞。检查过度 claim。 |

## Session State Machine

```
created → active → idle → active → ... → closed
                ↘ failed
```

## File-Based Handoff Rule

- 主 session 不跑长任务。
- 副 session 只读指定 input_files。
- 副 session 必须写 handoff。
- 主 session 只读 handoff，不读大量过程日志。
- 不允许只在聊天里交接。

## Context Isolation Semantics

### Session Is a Logical Role, Not Necessarily a Process

- 当前 session 机制是**文件级注册 + handoff 协议**
- session 角色记录在 registry 中，但不代表有独立的操作系统进程
- 如果外层 Agent（Claude Code）不新开会话，多个 session 实际上共享同一上下文

### Real Isolation Depends on Outer Agent

| 隔离级别 | 实现方式 | 当前支持 |
|----------|----------|----------|
| 文件级隔离 | 每个角色只读指定 input_files，写 handoff | ✅ 已实现 |
| 逻辑状态隔离 | session registry + state machine | ✅ 已实现 |
| 进程级隔离 | 自动启动多个 Claude Code 进程 | ❌ 不支持 |
| 上下文隔离 | 阻止主 session 读取副 session 日志 | ❌ 依赖约定 |

### Requirements for Effective Context Isolation

1. 每个角色只读自己 `input_files` 中的文件
2. 每个角色通过 handoff 输出，不依赖聊天记录
3. `main_architect` 只能读取 handoff 和必要摘要
4. 禁止 `main_architect` 直接读取大量副 session 过程日志
5. 如果外层 Agent 不按此约定执行，隔离无效

## Handoff Contract

每个 handoff 必须包含：
1. task_id 和 role
2. **Isolation Evidence**（必填）：
   - isolation_mode（manual_subsession | codex_thread | protocol_only）
   - physical_new_session（yes | no）
   - codex_thread_id（codex_thread 时必须填写）
   - allowed_input_files（精确文件列表）
   - forbidden_context（明确排除的内容）
   - actual_backend / actual_model
   - fallback_used / fallback_reason
3. 输入输出文件列表
4. 明确判断（decision）
5. 证据（evidence）
6. 失败模式（failure modes）
7. 未解决问题（unresolved questions）
8. 下一步建议（next action）
9. 不允许主 session 擅自假设的事项（do not assume）

### Isolation Evidence Rules

- 所有关键 gate（review / novelty / adversarial / final）handoff 必须包含 Isolation Evidence
- 缺少 Isolation Evidence 的 handoff 不能标记为 done
- **protocol_only** 对关键审查只允许 PASS_WITH_WARNINGS，不能完全 PASS：
  - Phase 3 (review): 不允许 protocol_only 完全 PASS
  - Phase 4 (novelty): 不允许 protocol_only 完全 PASS
  - Phase 5 (adversarial): 不允许 protocol_only 完全 PASS
  - Phase 6 (final): 不允许 protocol_only 完全 PASS
- **codex_thread** handoff 必须记录 codex_thread_id
- **manual_subsession** handoff 必须记录 physical_new_session=yes

### Handoff Status Rules

- `draft`：刚生成模板，不能作为最终判断
- `needs_review`：handoff 仍有 TODO、evidence 不足、或 Isolation Evidence 缺失
- `done`：Decision / Evidence / Next Action / Isolation Evidence 已填写且无 TODO，**必须**由 `tools/session_registry.py` 自动检查确认
- 如果 handoff 文件包含 `TODO:` 但请求标记为 `done`，工具自动降级为 `needs_review`
- 标记为 done 但 handoff 含 TODO 的 task > INVALID_DONE_WITH_TODO，通过 `tools/session_registry.py audit` 检测
- 只有 `done` 状态才会将 session 设为 idle 并清空 current_task
- 主 session 不应信任 `draft` / `needs_review` handoff 作为最终结论

## Registry Schema

```json
{
  "sessions": [
    {
      "session_id": "sess_lit_001",
      "role": "literature_scout",
      "created_at": "2026-05-08T10:00:00Z",
      "status": "active|idle|closed|failed",
      "input_files": [],
      "output_files": [],
      "owner": "outer-agent|manual|codex|llm-chat",
      "current_task": "task_001",
      "last_handoff": ".aris/sessions/HANDOFFS/task_001.md"
    }
  ]
}
```

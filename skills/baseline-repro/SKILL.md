---
name: baseline-repro
description: Establish and verify a baseline reproduction before claiming any improvement.
argument-hint: [baseline-paper-or-repo]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, mcp__llm-chat__chat
---

# Baseline Reproduction

## Purpose

建立 baseline 锚点，避免没有复现就宣称新方法有效。

## When to Use

- 用户指定 baseline repo。
- idea 依赖某篇 paper / repo。
- experiment-bridge 准备实现新方法前。
- result-to-claim 判断 improvement 前。

## Inputs

- `RESEARCH_BRIEF.md`
- `EXPERIMENT_PLAN.md`
- 用户指定 base repo
- baseline 论文 / paper-ingest 输出
- 当前代码仓库
- dataset path
- original paper metrics

## Outputs

- `research/BASELINE.md`
- `research/BASELINE_REPRODUCTION_REPORT.md`
- `research/BASELINE_REVIEW.md`，如执行审查

## Workflow

1. 识别 baseline paper 和 repo。
2. 读取 paper-ingest 的 method / experiments / appendix（通过 `literature-md/<paper_id>/`）。
3. 读取 repo README 和运行脚本。
4. 生成 `research/BASELINE.md`（用 `templates/BASELINE_TEMPLATE.md`）。
5. 尝试规划复现命令，不要盲跑长任务。
6. 如果已有结果，整理成 `research/BASELINE_REPRODUCTION_REPORT.md`。
7. 如果没有结果，写明 not-run，并给出具体运行命令。
8. 调用 baseline_reviewer 审查复现可信度（使用 `LLM_BASELINE_REVIEWER_MODEL`）。All baseline_reviewer calls must follow the global trusted role execution protocol (`shared-references/trusted-role-execution.md`).
9. 输出是否允许进入新方法实验。

## Hard Rules

- baseline 没复现，不允许 claim improvement。
- baseline 复现失败，只能写"未建立可靠锚点"。
- 有 base repo 必须优先复用。
- 不允许轻易从零重写实验框架。
- 不允许把 paper reported number 当成本地 reproduced number。

## Failure Handling

- repo 无法运行：记录原因和最小修复建议。
- dataset 缺失：记录 missing dataset，不伪造结果。
- metric 不一致：标记 partial / invalid。
- seed/split 不一致：标记 caveat。

## Integration

- `templates/BASELINE_TEMPLATE.md` — baseline 模板
- `templates/BASELINE_REPRODUCTION_REPORT_TEMPLATE.md` — 复现报告模板
- `skills/shared-references/model-routing.md` — baseline_reviewer 路由
- `skills/paper-ingest/SKILL.md` — 读取论文方法
- `skills/experiment-bridge/SKILL.md` — 检查 baseline 状态

## Example Invocation

```
/baseline-repro https://github.com/xxx/baseline-repo
/baseline-repro idea-stage/IDEA_CARDS/idea_001.md
```

## Expected Artifacts

- `research/BASELINE.md`
- `research/BASELINE_REPRODUCTION_REPORT.md`

## Failure Example

如果 baseline repo 不可运行：
- 记录原因和环境问题
- BASELINE_REPRODUCTION_REPORT.md 标记 verdict=failed
- 给出最小修复建议

## Recovery Step

如果复现成功但 metric 有差异：
- 标记 partial
- 分析原因
- 可以 proceed 但有 caveat

## Status / Ledger

本 skill 可能调用 baseline_reviewer（LLM Chat），写入：
- `.aris/calls/llm_calls.jsonl`

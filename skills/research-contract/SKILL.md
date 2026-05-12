---
name: research-contract
description: Freeze research hypothesis, success/failure signals, metrics, data split, baseline requirement, and claim boundary before full experiments.
argument-hint: [idea-card-or-experiment-plan]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, mcp__codex__codex, mcp__llm-chat__chat
---

## Workflow Relation

This skill routes through the ARIS workflow stack internally:

- `tools/research_workflow.py` — generates `context_manifest` and `prompt_file` for the `research_contract` stage
- `tools/context_isolation_check.py` — scans input for forbidden context before model call
- `tools/trusted_role_runner.py` — executes the `contract_reviewer` role (Codex MCP or API)
- `tools/validate_model_invocation.py` — verifies ledger entry; `allowed_next_stage=true` required to proceed

Users invoke via `/research-contract "..."`. The skill internally orchestrates the full workflow chain above. External agents must not bypass this chain or substitute its components.

# Research Contract

## Purpose

实验前冻结研究假设和成功/失败标准，防止结果出来后 AI 事后编故事。

## When to Use

- idea 已经筛选通过，准备实现正式实验前。
- baseline 已经选定或复现前后。
- experiment-bridge 准备跑 full experiment 前。
- result-to-claim 需要判断结果是否支持 claim 前。

## Inputs

- `RESEARCH_BRIEF.md`，如存在
- `idea-stage/IDEA_CARDS/*.md`
- `idea-stage/IDEA_REPORT.md`
- `EXPERIMENT_PLAN.md`
- `research/BASELINE.md`，如存在
- `research/BASELINE_REPRODUCTION_REPORT.md`，如存在
- `literature-md/<paper_id>/method.md`，如需要

## Outputs

- `docs/research_contract.md`
- `docs/research_contract.lock.json`
- `docs/research_contract_review.md`，如执行审查
- `.aris/DECISION_EVENTS.jsonl`，如 contract 变更

## Workflow

1. 收集输入文件。
2. 识别当前 idea / method / baseline / dataset / metrics。
3. 使用模板 `templates/RESEARCH_CONTRACT_TEMPLATE.md` 生成 `docs/research_contract.md`。
4. 检查是否包含所有必需字段：
   - Research Question
   - Hypothesis
   - Method Change
   - Baseline Requirement
   - Success Signals
   - Failure Signals
   - Metrics
   - Data Split
   - Claim Boundary
5. 调用 contract_reviewer（参见 `model-routing.md` and `shared-references/trusted-role-execution.md`）：
   - All contract_reviewer calls MUST use `tools/trusted_role_runner.py`:
     ```
     python tools/trusted_role_runner.py \
         --role contract_reviewer \
         --input "<contract context>" \
         --output "docs/research_contract.md" \
         --require-codex-thread   # omit for deepseek_only mode
     ```
   - `trusted_role_runner.py` handles ledger start/finish automatically
   - Verify with `python tools/validate_model_invocation.py --role contract_reviewer`
   - If verification fails or allowed_next_stage=false: **FAIL closed**
6. 如果 reviewer 要求 revise，则修改 contract。
7. 如果 Codex 不可用，标记 `REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK`。
8. 生成 `docs/research_contract.lock.json`。
9. 在输出里提醒：full experiment 必须遵守该 contract。

## Hard Rules

- 没有 research_contract，不允许进入 full experiment。
- contract 锁定后不能静默修改。
- 如果修改，只能生成 v2。
- 修改原因必须写入 `.aris/DECISION_EVENTS.jsonl`。
- 如果因为结果不好而修改，必须明确标记 `result-driven modification`。
- Success Signals 和 Failure Signals 必须都存在。
- Claim Boundary 必须写清楚能 claim 什么、不能 claim 什么。

## Failure Handling

- 缺 baseline：允许生成 provisional contract，但 Baseline Requirement 标记 unresolved。
- 缺 data split：contract 不得 lock，必须提示补充。
- Codex 不可用：fallback 到 `LLM_CONTRACT_REVIEWER_FALLBACK_MODEL`，并标记 degraded review。

## Integration

- `templates/RESEARCH_CONTRACT_TEMPLATE.md` — contract 模板
- `skills/shared-references/research-contract.md` — contract 协议
- `skills/shared-references/model-routing.md` — contract_reviewer 路由
- `tools/llm_call_ledger.py` — 记录 reviewer 调用
- `skills/experiment-bridge/SKILL.md` — 在 full experiment 前检查 contract

## Example Invocation

```
/research-contract idea-stage/IDEA_CARDS/idea_001.md
```

## Expected Artifacts

- `docs/research_contract.md`
- `docs/research_contract.lock.json`
- `docs/research_contract_review.md`

## Failure Example

如果缺少 data split：
- contract 可以生成草案
- lock.json 的 locked 设为 false
- 提示用户补充 data split 后重新锁定

## Recovery Step

如果 reviewer fallback 到 LLM：
- 检查 `docs/research_contract_review.md` 是否 degraded 标记
- 确认 reviewer 输出质量后可接受或被要求重新生成

## Status / Ledger

本 skill 调用 contract_reviewer（Codex 或 fallback LLM），必须写入：
- `.aris/calls/current_call.json`
- `.aris/calls/llm_calls.jsonl`

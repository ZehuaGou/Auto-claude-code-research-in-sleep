---
name: research-assurance
description: Verify contract, baseline, audit, result-to-claim, and paper claims before writing or submitting.
argument-hint: [project-or-paper-path]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# Research Assurance

## Purpose

在写论文前统一验证 contract、baseline、audit、result-to-claim、claim-evidence。它是编排 skill，不重复实现 experiment-audit 和 result-to-claim。

## When to Use

- experiment-bridge 完成并收集结果后。
- 准备运行 paper-writing 前。
- 投稿前做最终检查。
- 需要生成 CLAIM_EVIDENCE_TABLE.md 时。

## Inputs

- `docs/research_contract.md`
- `research/BASELINE_REPRODUCTION_REPORT.md`
- `EXPERIMENT_LOG.md`
- `EXPERIMENT_AUDIT.md`（如存在）
- `EXPERIMENT_AUDIT.json`（如存在）
- `CLAIMS_FROM_RESULTS.md`（如存在）
- paper draft，如存在
- `review-stage/AUTO_REVIEW.md`（如存在）

## Outputs

- `research/ASSURANCE_REPORT.md`
- `research/CLAIM_EVIDENCE_TABLE.md`

## Workflow

1. 检查 `docs/research_contract.md` 是否存在。
2. 检查 `research/BASELINE_REPRODUCTION_REPORT.md` 是否存在。
3. 调用或读取 experiment-audit（`skills/experiment-audit/SKILL.md`）。
4. 调用或读取 result-to-claim（`skills/result-to-claim/SKILL.md`）。
5. 生成 `research/CLAIM_EVIDENCE_TABLE.md`。
6. 检查 paper draft 里的 claims 是否有 evidence。
7. 输出 `research/ASSURANCE_REPORT.md`。

## CLAIM_EVIDENCE_TABLE.md 格式

每条 claim 必须包含：
| claim_id | claim_text | contract_signal | experiment_id | result_file | metric | baseline_comparison | audit_status | evidence_strength | allowed_in_paper | required_caveat |

## ASSURANCE_REPORT.md 必须包含

1. Contract status
2. Baseline status
3. Experiment audit status
4. Result-to-claim status
5. Claim evidence table summary
6. Unsupported claims
7. Overclaim risks
8. Degraded review warnings
9. Required next actions

## Hard Rules

- 没有实验支撑的 claim 不能写进论文。
- 没有 contract 对应的 claim 不能写进论文。
- partial 不能扩大成 yes。
- degraded review 必须标记。
- experiment audit fail 时，相关 claim allowed_in_paper 必须是 no 或 needs caveat。

## Integration

- `templates/CLAIM_EVIDENCE_TABLE_TEMPLATE.md` — 证据表模板
- `skills/experiment-audit/SKILL.md` — 实验完整性审计
- `skills/result-to-claim/SKILL.md` — 结果到 claim 判断
- `skills/paper-writing/SKILL.md` — 写作前检查

## Example Invocation

```
/research-assurance
/research-assurance paper/
```

## Expected Artifacts

- `research/ASSURANCE_REPORT.md`
- `research/CLAIM_EVIDENCE_TABLE.md`

## Failure Example

如果 contract 不存在：
- 标记 contract_status=missing
- 提示先运行 /research-contract
- 但仍允许继续（soft gate）

## Recovery Step

如果 audit 失败：
- 相关 claim 标记 allowed_in_paper=no
- 提示修复后再生成 paper

## Status / Ledger

本 skill 可能调用 experiment-audit 和 result-to-claim（都写入 ledger），自身不直接调用模型。

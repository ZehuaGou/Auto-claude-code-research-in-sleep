# Research Contract Protocol

## Purpose

实验前冻结研究假设和成功/失败标准，防止结果出来后 AI 事后编故事。

## Must Contain

1. **Research Question** — 研究的核心问题
2. **Hypothesis** — 可检验的假设
3. **Method Change** — 方法的具体变化
4. **Baseline Requirement** — 需要对比的 baseline
5. **Success Signals** — 明确什么算成功
6. **Failure Signals** — 明确什么算失败
7. **Metrics** — 主要和次要指标
8. **Data Split** — 数据划分方式
9. **Ablation Plan** — 消融实验计划
10. **Expected Outcomes** — 预期结果
11. **Stop Criteria** — 提前停止条件
12. **Claim Boundary** — 能 claim 什么、不能 claim 什么
13. **Freeze Rule** — 冻结后修改规则

## Lock Schema

```json
{
  "contract_path": "docs/research_contract.md",
  "version": "v1",
  "created_at": "2026-05-08T10:00:00Z",
  "locked": true,
  "source_files": ["idea-stage/IDEA_CARDS/idea_001.md", "EXPERIMENT_PLAN.md"],
  "hash": "sha256-of-contract-content",
  "allowed_to_modify": false
}
```

## Rules

- 没有 research_contract 不允许进入 full experiment。
- contract 锁定后不能静默修改。
- 如果修改，只能生成 v2。
- 修改原因必须写入 `.aris/DECISION_EVENTS.jsonl`。
- 如果因为结果不好而修改，必须明确标记 `result-driven modification`。
- Success Signals 和 Failure Signals 必须都存在。
- Claim Boundary 必须写清楚能 claim 什么、不能 claim 什么。

## Failure Handling

- 缺 baseline：允许生成 provisional contract，但 Baseline Requirement 标记 unresolved。
- 缺 data split：contract 不得 lock，必须提示补充。
- Codex 不可用：fallback 到 LLM_CONTRACT_REVIEWER_FALLBACK_MODEL，并标记 degraded review。

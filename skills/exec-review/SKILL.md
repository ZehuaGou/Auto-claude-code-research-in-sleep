---
name: exec-review
description: Run one-shot independent review on a specific file, such as one idea card, contract, result snapshot, or paper relevance note.
argument-hint: [file-to-review]
allowed-tools: Bash(*), Read, Write, Grep, Glob, mcp__codex__codex, mcp__llm-chat__chat
---

# Exec Review

## Purpose

做一次性、独立、无长期上下文的审查。

## When to Use

- 单个 idea card 审查。
- contract 审查。
- 实验结果判断。
- paper relevance 判断。
- 不需要多轮上下文的场景。

## Inputs

- 一个明确文件路径。
- 可选少量支持文件。
- 不接受长篇口头解释作为主要输入。

## Outputs

- `review-stage/exec_reviews/<id>.md`
- `review-stage/exec_reviews/<id>.json`

## Artifact Header

Every output markdown file MUST begin with a model tracking header including isolation evidence:

```
isolation_mode: manual_subsession|codex_thread|protocol_only
codex_thread_id: <id>|none
task_id: <session task id>|none
allowed_input_files: <exact file list>
forbidden_context_checked: true|false
primary_backend: codex|llm-chat
primary_model: <model name or "DEFAULT">
actual_backend: codex|llm-chat
actual_model: <model name or "DEFAULT">
fallback_used: True|False
fallback_reason: None|<reason>
```

**Isolation rules:**
- If `actual_backend=codex`: must record `codex_thread_id`
- If no `codex_thread_id` and no `physical_new_session`: isolation_mode is `protocol_only`
- `protocol_only` results cannot yield full PASS — max is PASS_WITH_WARNINGS
- Missing isolation_mode or codex_thread_id (when codex): mark as NEEDS_ISOLATION_EVIDENCE

If fallback from Codex to LLM occurred, also include:
```
REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK: true
```

## Workflow

1. 读取输入文件。
2. 确定 review role：
   - idea_reviewer
   - contract_reviewer
   - result_judge
   - paper_relevance_reviewer
3. 根据 model-routing（`skills/shared-references/model-routing.md`）决定 primary：
   - codex 或 llm-chat
4. **Agent 调用前**写 `current_call.json`（通过 llm_call_ledger start）。
5. **Agent 执行** Codex 或 LLM Chat 调用。
6. 如果 Codex 失败，Agent fallback 到对应 LLM fallback。
7. **Agent 调用后**写 `llm_calls.jsonl`（通过 llm_call_ledger finish / fallback）。
8. 输出 markdown 和 json。
9. markdown 必须保留 reviewer raw response。

**注意：** `tools/exec_review.py` 只负责 review 初始化（init）和完成记录（complete/status），**不直接调用 Codex/LLM**。实际模型调用由外层 Agent 按本 SKILL.md 执行。

## 调用账本示例

```bash
python3 tools/llm_call_ledger.py start exec-review idea_reviewer codex
# ... call Codex or LLM ...
python3 tools/llm_call_ledger.py finish
# or if fallback:
python3 tools/llm_call_ledger.py fallback deepseek-v4-pro "codex timeout"
```

## Hard Rules

- 每个 idea 独立审查。
- reviewer 不允许看到其他 idea。
- reviewer 不允许看到 idea 生成过程。
- 调用 Codex / LLM 时必须写 `llm_calls.jsonl`。
- 不允许 silent fallback。

### Canonical Idea Review Rules

When reviewing a canonical idea candidate (`idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md`):

1. **One candidate at a time** — the reviewer input must contain exactly one CAND_*.md file.
2. **No generator trace** — do NOT include the corresponding `IDEA_CARDS/` or any generator reasoning.
3. **No previous scores** — do NOT include past review scores or novelty results.
4. **No user preferences** — do NOT include user's stated preferences or praise.
5. **Output directory** — results go to `idea-stage/AGENTIC/REVIEWS/CAND_XXX_review.md`.

**Review output fields:**
- `verdict: go | revise | kill`
- `novelty_risk` — is the claimed novelty plausible?
- `feasibility_risk` — can this be implemented with available resources?
- `baseline_risk` — how strong are the baselines?
- `minimum_fix` — what must change for this to become viable?
- `reason_to_kill` — if verdict is kill, the single strongest reason

## JSON Output Schema

```json
{
  "review_id": "...",
  "role": "idea_reviewer",
  "input_file": "...",
  "verdict": "go|revise|kill|pass|fail|partial",
  "score": null,
  "major_issues": [],
  "minimum_fixes": [],
  "confidence": "high|medium|low",
  "reviewer_backend": "codex|llm-chat",
  "fallback_used": false
}
```

## Integration

- `tools/exec_review.py` — review 初始化和完成
- `tools/llm_call_ledger.py` — 调用记录
- `skills/shared-references/model-routing.md` — 模型路由
- `skills/panel-review/SKILL.md` — 多轮复杂审查

## Example Invocation

```
/exec-review "CAND_001"
/exec-review "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md"
/exec-review docs/research_contract.md
/exec-review EXPERIMENT_LOG.md
```

When the input is a CAND_*.md file:
- Output goes to `idea-stage/AGENTIC/REVIEWS/CAND_XXX_review.md`
- Output also goes to `review-stage/exec_reviews/<id>.md` (legacy, for non-CAND reviews)

## Expected Artifacts

- `review-stage/exec_reviews/<id>.md`
- `review-stage/exec_reviews/<id>.json`

## Failure Example

如果 Codex 不可用：
- fallback 到 `LLM_IDEA_REVIEWER_FALLBACK_MODEL`
- 输出标记 `REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK`

## Recovery Step

如果 LLM 也失败：
- 标记 review 为 failed
- 提示用户检查 API Key 和网络

## Status / Ledger

必须写入：
- `.aris/calls/current_call.json`
- `.aris/calls/llm_calls.jsonl`

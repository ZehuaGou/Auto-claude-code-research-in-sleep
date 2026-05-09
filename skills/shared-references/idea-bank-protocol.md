# Idea Bank Protocol

## Purpose

定义 AGENTIC idea discovery 的 idea 存储、去重、索引、审查隔离协议。

## Core Rules

### 1. 每次 Run 独立保存

- 每次 `/research-lit`（agentic 模式）创建独立 run_id。
- run_id 格式：`YYYYMMDD_HHmmss_slug`。
- 原始 IDEA_CARDS 不可修改、不可覆盖、不可合并。
- 上午和下午的多次 run 独立保存。

### 2. IDEA_BANK 只做索引

`IDEA_BANK.md` 和 `IDEA_BANK.json` 只存放索引和状态字段，不存放完整 idea 正文。

`IDEA_BANK.md` 表格字段：

| candidate_id | title | source_runs | status | latest_verdict | novelty_status | next_action |

`IDEA_BANK.json` 结构：

```json
{
  "candidates": [
    {
      "candidate_id": "CAND_001",
      "title": "...",
      "source_runs": [],
      "canonical_file": "idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_001.md",
      "status": "active|revise|killed|recommended|backup",
      "latest_review": "idea-stage/AGENTIC/REVIEWS/CAND_001_review.md",
      "novelty_status": "unknown|confirmed_novel|likely_incremental|already_done|insufficient_evidence",
      "next_action": "..."
    }
  ]
}
```

### 3. CANONICAL_IDEAS 是去重后的干净候选

- 每个 candidate 一个文件。
- 不包含：generator 推理过程、旧分数、旧 praise、用户偏好。
- candidate 文件（CAND_*.md）只保留 reviewer 可读的纯净内容（hypothesis、method、baseline、experiment、claim boundary）。
- reviewer / novelty checker / adversarial reviewer 只读单个 canonical idea。
- **.meta 目录：** CANONICAL_IDEAS/.meta/CAND_XXX_meta.json 存储 provenance 细节（source_runs、merged_from、origin ideas、merge rationale、timestamps）。
- **访问控制：** /idea-bank 可以读 .meta；/exec-review 和 /novelty-check 不允许读 .meta。

### 4. Reviewer 隔离规则

- Reviewer 一次只读一个 candidate。
- Reviewer prompt **禁止包含**：
  - 其他 candidate 的内容
  - Generator 的推理过程
  - 之前的分数
  - 之前的 praise
  - 用户偏好
- Reviewer 的输入明确限制为：单个 CAND_*.md + GAP_EXCERPTS/CAND_XXX_gap.md。
- Reviewer **不允许读** CANONICAL_IDEAS/.meta/ 目录。

### 5. Novelty Checker 隔离规则

- Novelty checker 一次只读一个 candidate。
- 输入：单个 CAND_*.md + LITERATURE_INDEX.md + 相关论文章节。
- Novelty checker 不读其他 candidate 的 review 结果。
- `insufficient_evidence` 不能变为 `confirmed_novel`。

### 6. Dedup 职责

- Dedup 只能判断：重复 / 变体 / 互补 / 冲突。
- Dedup **不做** novelty 判断。
- Dedup **不做** quality 评分。
- 如果 dedup 不确定，保持 candidate 独立。

### 7. No Strong Idea Found

以下情况输出 `no strong idea found`：

- 所有 idea 在 review 阶段被 kill。
- Dedup 发现所有 idea 都是已有工作的微小变体。
- Novelty checker 确认所有剩余 idea 都 `already_done`。
- Adversarial reviewer 发现所有剩余 idea 都有致命缺陷。

这不是失败 — 是合法输出。

### 8. 状态流转

```
                   ┌──────────┐
                   │  active  │
                   └────┬─────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
         go/revise    kill     no_review
              │
       ┌──────┴──────┐
       ▼             ▼
  novelty_check   skip_review
       │
    ┌──┴──┐
    ▼     ▼
  novel  already_done
       │
    ┌──┴──┐
    ▼     ▼
  recommended  backup/killed
```

### 9. 跨 Run 归并流程

1. Run N 生成原始 IDEA_CARDS。
2. Dedup 比对：新 cards × 已有 CANDIDATES。
3. 新方向 → 创建新 CAND_XXX。
4. 已有方向的变体 → 合并到对应 CAND，更新 source_runs。
5. 弱重复 → 丢弃，记录 source_runs。
6. IDEA_BANK 更新状态。

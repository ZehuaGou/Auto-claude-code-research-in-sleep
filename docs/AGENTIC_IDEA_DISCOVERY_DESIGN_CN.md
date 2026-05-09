# API-first Agentic Idea Discovery V1 — Design Document

## 0. Skill-First 设计哲学

### 0.1 ARIS 是 Slash-Skill 系统

ARIS 的核心理念是 **skill-first**：用户通过 `/skill-name` 短命令操作，不需要记住任何 Python 命令。

```
用户入口:     /research-lit "方向"   /idea-creator "方向"   /novelty-check "CAND_001"
              /exec-review "CAND_001"   /idea-discovery "方向"   /idea-bank status
内部执行器:   python tools/agentic_idea_discovery.py ...
              python tools/isolated_job_runner.py ...
```

### 0.2 入口归并原则

原 ARIS 已经有一套完整 skill 入口体系。本项目新增策略**不新建平行命令体系**，而是将 agentic 策略并入原命令：

| 原入口 | 增强内容 | 新增策略 |
|--------|----------|----------|
| `/research-lit` | LITERATURE_INDEX + GAP_MAP + gap 质量门 | isolated literature_scout + gap_extractor |
| `/idea-creator` | IDEA_CARDS 独立输出 + dedup → IDEA_BANK + CANONICAL_IDEAS | isolated idea_generator + idea_deduplicator |
| `/novelty-check` | CAND_*.md 输入 + 严格 verdict | novelty_checker 隔离规则 |
| `/exec-review` | canonical idea 审查 + review 隔离规则 | idea_reviewer + adversarial_reviewer |
| `/idea-discovery` | 新 pipeline：lit → ideas → review → novelty → adversarial → selection | 完整端到端流程，默认输出 IDEA_SELECTION_REPORT 或 no strong idea found；是否进入实验由用户后续显式决定 |

**唯一新增入口：** `/idea-bank` — 原 ARIS 没有对应的 IDEA_BANK 管理功能。

### 0.3 为什么保留 Python 工具

Python 工具不删除，但角色改变：

| 用途 | 用户入口 | 内部工具 |
|------|----------|----------|
| 日常 idea discovery | `/research-lit`, `/idea-creator`, `/exec-review` 等 | agentic_idea_discovery.py |
| 查看 idea bank | `/idea-bank status` | isolated_job_runner.py |
| 调试/排错 | 不需要 | 直接运行 Python 工具看详细输出 |
| 贡献者测试 CI | 不需要 | Python 工具可无 head 运行 |
| 重复操作 | Skill 封装 | Python 工具处理重复性 job 编排 |

Python 工具保留为 **内部执行器**（internal executor），负责：
- 重复性操作（创建目录、生成 job JSON、执行 job）
- LLM call ledger 记录
- Job 输出校验
- CI 和贡献者测试

### 0.4 什么时候直接使用 Python 工具

- **调试**：某个 job 失败，需要查看原始输出
- **贡献者测试**：修改了 isolated_job_runner.py 后需要单独测试
- **CI**：自动化测试无法通过 slash skill 执行

正常用户永远不需要直接调用 Python 工具。

## 1. 问题定义

ARIS 当前的 idea discovery 流程（旧 `/idea-discovery`）存在以下问题：

- 主 Agent 在一个长上下文中依次执行 literature survey → gap analysis → idea generation → review → novelty check。
- 每步的判断、摘要、偏差都会污染后续步骤。
- 主 Agent 亲自整理 literature 和 gap，再把整理后的内容传给外部模型 — 主 Agent 的先入之见会影响 idea 生成和审查。
- 多次 run 的 idea 直接混入一个大 `IDEA_REPORT`，无法追溯、无法独立审查。
- 没有 `no strong idea found` 作为合法输出。

## 2. API 调用、Skill、Agent Session 的区别

### API Call

- 短生命周期（秒到分钟）。
- 一次请求-响应，不保持状态。
- 适合纯思考/生成/分类/结构化输出任务。
- **污染风险**：如果 API 的 prompt 由主 Agent 编写且包含主 Agent 的摘要/判断，主 Agent 的偏差仍会传入 API。这就是为什么 API 调用并不是天然隔离的 — **输入隔离比调用方式更重要**。

### Skill

- Markdown 文件定义的工作流，可包含多步操作。
- Skill 本身不隔离上下文 — 它只是操作步骤的描述。
- 如果 Skill 由主 Agent 执行，主 Agent 的上下文仍会污染每一步。

### Agent Session

- 长生命周期（分钟到小时）。
- 有独立上下文窗口。
- 适合需要工具调用（搜索、读网页、执行代码）的任务。
- **真正隔离**的条件：新开进程/窗口 + 只读指定 input_files + 通过 handoff 输出。

## 3. 为什么 Idea Discovery 需要 Isolated Jobs

| 问题 | 说明 | Isolated Job 如何解决 |
|------|------|----------------------|
| 上下文污染 | 主 Agent 的旧判断影响后续步骤 | 每个 job 只读 input_files，不读主聊天历史 |
| 自我确认偏差 | Agent 倾向于维护自己的早期判断 | Generator/Reviewer 分离，reviewer 不看 generator 推理过程 |
| 旧分数污染 | 已打分的 idea 在新 review 中倾斜判断 | Reviewer prompt 禁止包含历史分数和 praise |
| 多 run 混淆 | 上午的 idea 和下午的 idea 混在一起 | 每次 run 独立保存，dedup 后归入 CANONICAL_IDEAS |
| 无失败输出 | 系统必须找到 idea 才能继续 | `no strong idea found` 合法 |

## 4. 为什么不是所有步骤都用子 Agent

核心原则：**工具和能力匹配**。

| 任务类型 | 特点 | 适合的 backend | 理由 |
|----------|------|---------------|------|
| 纯思考/生成 | 固定输入，结构化输出 | API | 不需要工具调用，API 更快、更便宜、更可控 |
| 搜索/读网页 | 需要调用外部工具 | Claude headless Agent | 需要 Read/WebSearch/WebFetch 等工具 |
| 分类/比对 | 结构化输入输出 | API | 固定格式，不需要探索 |
| 查新 | 需要搜索和比对 | Claude headless Agent | 可能需要搜索最新论文 |
| 关键审查 | 高价值判断 | API (optional Codex) | Codex 有强推理能力但资源消耗大 |

**APl-first 不是 API-only**：能 APl 完成的就不用 Agent，但需要工具的必须用 Agent。

## 5. Backend 分配总表

| 角色 | Backend | 理由 |
|------|---------|------|
| literature_scout | claude_headless | 需要搜索、读网页、调用工具 |
| gap_extractor | api | 固定输入的分析任务 |
| idea_generator | api | 纯生成任务 |
| idea_deduplicator | api | 结构化比对任务 |
| idea_reviewer | api / codex optional | 高价值判断，但输入固定 |
| novelty_checker | claude_headless | 可能需要搜索最新论文 |
| adversarial_reviewer | api / codex optional | 纯批判任务，输入固定 |
| main_architect | 当前主 Agent | 只读 artifacts 汇总 |

## 6. V1 做什么

1. 文献搜索、gap 提炼、idea 生成、idea 审查、查新、反方审查分离。
2. 主 Agent 不亲自想 idea，不亲自审 idea。
3. 每个 job 只读指定 input_files。
4. 每个 job 输出明确 artifact。
5. 每次 idea discovery 都创建独立 run，不覆盖旧结果。
6. 多次 run 通过 IDEA_BANK 和 CANONICAL_IDEAS 归并。
7. 允许 `no strong idea found`。

## 7. V1 不做什么

1. 不自动写论文。
2. 不自动跑长实验。
3. 不自动改核心实验代码。
4. 不自动投稿。
5. 不做 Web UI。
6. 不做 daemon。
7. 不做 tmux 长驻 session 管理。
8. 不新增平行的主入口；所有 agentic 策略并入原 ARIS 命令内增强默认 idea discovery 流程。
9. 不破坏原有 ARIS 工作流。
10. 不保证一定能找到强 idea。

## 8. Run 隔离设计

每次 `/research-lit`（agentic 模式）都创建独立 run：

```
idea-stage/AGENTIC/RUNS/20260508_153000_topic/
├── RUN_MANIFEST.md
├── INPUTS.md
├── LITERATURE_INDEX.md
├── GAP_MAP.md
├── IDEA_CARDS/
│   ├── idea_001.md
│   └── idea_002.md
└── HANDOFFS/
    ├── literature_scout.md
    ├── gap_extractor.md
    └── idea_generator.md
```

- run_id 格式：`YYYYMMDD_HHmmss_slug`
- 原始 run 文件不可变、不覆盖、不合并。
- 上午和下午的两次 run 独立保存，互不干扰。

## 9. IDEA_BANK 和 CANONICAL_IDEAS

### IDEA_BANK

- 全局索引，记录所有 candidate 的状态。
- 不存放完整 idea 内容。
- 字段：candidate_id, title, source_runs, status, latest_verdict, novelty_status, next_action。

### CANONICAL_IDEAS

- 去重后的干净候选。
- 每个 candidate 独立文件。
- reviewer / novelty checker / adversarial reviewer **只读单个 canonical idea**。
- 不包含：旧分数、旧 praise、用户偏好、generator 推理过程。

### 多次 run 的处理

- run 1 产出 IDEA_CARDS → dedup → CAND_001, CAND_002
- run 2 产出 IDEA_CARDS → dedup（与 CAND_001, CAND_002 比对）→ CAND_003, CAND_004
- reviewer 只审新增/状态为 active 的 candidate
- 已 killed 的 candidate 不再审查

## 10. 如何避免 Reviewer 被污染

Reviewer prompt 中 **禁止包含**：

- 其他 candidate 的内容
- Generator 的推理过程
- 之前的分数（`score: 8`）
- 之前的 praise（`"这个 idea 很有创新性"`）
- 用户偏好（`"用户倾向于 LLM-based 方法"`）

Reviewer 只读：

- 单个 CAND_*.md
- 必要的 GAP_MAP 摘要

## 11. No Strong Idea Found

以下情况输出 `no strong idea found`：

- 所有 idea 在 review 阶段被 kill。
- dedup 后发现所有 idea 都是已有工作的微小变体。
- novelty checker 确认所有剩余 idea 都 `already_done`。
- adversarial_reviewer 发现所有剩余 idea 都有致命缺陷。

这不是失败 — 是合法输出。系统建议用户探索不同方向。

## 12. V1 文件结构

```
idea-stage/AGENTIC/
├── TOPIC.md
├── RUNS/<run_id>/
├── IDEA_BANK.md
├── IDEA_BANK.json
├── CANONICAL_IDEAS/CAND_*.md
├── REVIEWS/CAND_*_review.md
├── NOVELTY/CAND_*_novelty.md
├── ADVERSARIAL/CAND_*_adversarial.md
├── FINAL_SELECTION/IDEA_SELECTION_REPORT.md
├── RUNS_INDEX.json
└── IDEA_BANK.json
```

所有 `idea-stage/` 目录下的文件均为 runtime 产物，**不提交到 git**。

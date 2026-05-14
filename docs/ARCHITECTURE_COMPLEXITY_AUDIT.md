# Architecture Complexity Audit

**Date:** 2026-05-14
**HEAD:** f178bee

---

## 一、当前系统是否已经偏重？

### 1.1 哪些地方变复杂了？

| 区域 | 复杂度表现 | 严重程度 |
|------|-----------|---------|
| `literature_evidence_landing.py` | 已拆分：`tools/literature/{store.py, extraction.py, manual_ingest.py}` + delegation wrappers。原文件仍 7500+ 行但核心逻辑已分离 | **中** — 拆分后 debug 路径缩短 |
| Stage 数量 | 12+ 个 stage（raw_user_input → paper_writing），每个有 allowed_input_files、forbidden_context、stage_output_contract | **中** — 每个 stage 本身简单，但组合后状态空间大 |
| Validator 数量 | input_normalizer、contract_reviewer、literature_scout、novelty_checker、method_refiner、idea_pivoter、full_text_reviewer — 每个 stage 后都有 validate_model_invocation | **中** — 必要但增加维护成本 |
| 状态文件 | trusted_outputs/ 下多个 .md、manifest.json、full_text_queue.json、review_notes.md、repair queue、evidence summary | **中** — 文件多但每个有明确用途 |
| Workflow config 与 CLI 一致性 | STAGE_ORDER 静态列表 vs workflow config stages 曾不一致（已修） | **低** — 已修复，但需警惕 |

### 1.2 哪些复杂是必要的？

| 复杂度 | 为什么必要 |
|--------|-----------|
| Trusted role runner + ledger | 没有信任边界，模型可以静默调用，无法审计。这是原版 ARIS 没有的关键安全机制。 |
| Stage output contract | 防止模型输出格式漂移、forbidden phrase 污染、readiness gate 不一致。 |
| Context isolation | 防止 stage 之间上下文泄漏，特别是 forbidden_context 防止未批准的输入进入模型。 |
| Validate model invocation | 每次模型调用后验证 backend、model、fallback、verification_status。没有这个，无法保证调用链完整。 |
| Multi-source literature | 单一 OpenAlex 不足以支撑 novelty claim。arXiv + Crossref + OpenAlex 是最低要求。 |
| Full-text acquisition | metadata-only 的 novelty claim 不够 strong。full text 是验证 closest prior work 的必要条件。 |

### 1.3 哪些复杂是过度设计？

| 复杂度 | 问题 |
|--------|------|
| 36 个 Python 文件 | 对 MVP 来说太多。核心流程只需要 ~16 个文件。其余 20 个是 supplementary tools，不被核心流程使用。 |
| `literature_evidence_landing.py` 单文件 7800+ 行 | 已拆分为 4 个模块（store, extraction, manual_ingest + delegation wrappers）。核心逻辑已分离。 |
| Repair queue 23 个条目 | 部分条目是历史遗留（如 LRQ-001 到 LRQ-010），部分是新发现的。维护成本高。 |
| 每个 stage 都有完整的 forbidden_context 列表 | 部分 stage 的 forbidden_context 重复度高，可以提取公共规则。 |

### 1.4 哪些复杂会导致后期 debug 困难？

| 问题 | 影响 |
|------|------|
| `literature_evidence_landing.py` 太大 | 定位一个 bug 需要读 7800 行。grep 搜索结果太多。 |
| Stage 之间的依赖链长 | 从 raw_user_input 到 paper_writing 有 12 个 stage，任何一个失败都可能影响后续。需要清晰的错误传播路径。 |
| Workflow config 解析器是手写的 | 没有用 PyYAML，手写解析器可能有 edge case。但它只有 100 行，风险可控。 |
| 状态分散在多个文件中 | 要理解当前状态需要读 5+ 个文件。research_cli.py status 解决了这个问题，但底层仍然是多文件。 |

---

## 二、模块分级

### Legend

| Tag | Meaning |
|-----|---------|
| `core_mvp` | 必须保留，否则系统不成立 |
| `near_term` | 近期需要，但不一定本轮实现 |
| `deferred` | 有价值，但现在不该做 |
| `optional` | 可以作为增强，不影响主系统 |
| `risk_of_overengineering` | 可能拖慢系统、增加 token 成本、增加 debug 难度 |

### Module Table

| # | Module | Files | Tag | 必要性 | 用户价值 | Token 成本 | 运行复杂度 | Debug 难度 | 与 lightweight ARIS 冲突？ | 现在该做吗？ |
|---|--------|-------|-----|--------|---------|-----------|-----------|-----------|--------------------------|------------|
| 1 | **Native Command (research_cli.py)** | `research_cli.py` | `core_mvp` | 关键 — 一键 UX 是核心目标 | 高 — 消除手动复制命令 | 零 | 低 | 易 — 44 个自测 | 否 — 这就是 lightweight UX | 是 |
| 2 | **Workflow Config** | `research_default.yaml` | `core_mvp` | 关键 — stage 定义的 source of truth | 中 — 用户不直接操作 | 零 | 低 | 易 — 解析器 100 行 | 否 | 是 |
| 3 | **Trusted Role Runner** | `trusted_role_runner.py` | `core_mvp` | 关键 — 所有模型调用必须经过 trusted runner | 高 — 信任边界 | 低 | 中 | 中 | 否 | 是 |
| 4 | **Ledger** | `llm_call_ledger.py` | `core_mvp` | 关键 — 模型调用可追溯 | 低 | 零 | 低 | 易 — JSONL 可 grep | 否 | 是 |
| 5 | **Model Route** | `model_route.py` | `core_mvp` | 关键 — role-to-model 路由 | 低 | 零 | 低 | 易 | 否 | 是 |
| 6 | **Validate Model Invocation** | `validate_model_invocation.py` | `core_mvp` | 关键 — 调用后验证 | 低 | 零 | 低 | 易 | 否 | 是 |
| 7 | **Context Isolation** | `context_isolation_check.py` | `core_mvp` | 关键 — forbidden context 执行 | 低 | 零 | 低 | 易 | 否 | 是 |
| 8 | **Literature Evidence Pipeline** | `literature_evidence_landing.py` + `tools/literature/{store,extraction,manual_ingest,scoring,multisource}.py` + `tools/literature/adapters/{openalex,arxiv,crossref}.py` | `core_mvp` | 关键 — 证据获取 | 高 | 中 | 中 — 已拆分为 8 个模块 | 易 — 每个模块 < 370 行 | 否 | 是 |
| 9 | **Research Workflow** | `research_workflow.py` | `core_mvp` | 关键 — stage preparation | 低 | 零 | 中 | 中 | 否 | 是 |
| 10 | **arXiv/OpenAlex/Crossref** | `arxiv_fetch.py` 等 | `core_mvp` | 关键 — 多源证据 | 高 | 中 | 低 | 易 | 否 | 是 |
| 11 | **Idea Pivot** | workflow config stage | `near_term` | 重要 — 证据驱动的 pivot | 高 — 解锁 blocked case | 低 | 低 | 易 | 否 | 是 |
| 12 | **Full-text Review** | workflow config stage | `near_term` | 重要 — 验证 closest prior work | 高 — 防止浪费实验 | 低 | 低 | 易 | 否 | 是 |
| 13 | **Manual Local Ingestion** | `ingest-manual-fulltext` | `near_term` | 重要 — 用户提供本地论文 | 中 | 零 | 低 | 易 | 否 | 是 |
| 14 | **Broad Literature Scan** | 未实现 | `risk_of_overengineering` | 中 — 更强证据 | 高（如果能用），但 scope creep 风险高 | 高 | 高 | 难 | 是 — 可能变成独立产品 | 否 |
| 15 | **Literature Memory** | 未实现 | `deferred` | 低 — reading card 够用 | 中 | 低 | 高（如果数据库） | 难 | 是 — 可能变成知识图谱 | 否 |
| 16 | **Experiment Plan** | workflow config stage | `deferred` | 需要，但被 test case 阻塞 | 高 | 低 | 低 | 易 | 否 | 否 |
| 17 | **Implementation Plan** | workflow config stage | `deferred` | 需要，但被 experiment_plan 阻塞 | 高 | 低 | 低 | 易 | 否 | 否 |
| 18 | **Experiment Bridge** | 未实现 | `deferred` | 需要，但被 implementation_plan 阻塞 | 高 | 中 | 中 | 中 | 否 | 否 |
| 19 | **Result Judge** | workflow config stage | `deferred` | 需要，但被 experiment_bridge 阻塞 | 高 | 低 | 低 | 易 | 否 | 否 |
| 20 | **Paper Writing** | workflow config stage | `deferred` | 需要，但被 result_judge 阻塞 | 高 | 中 | 低 | 易 | 否 | 否 |
| 21 | **Research Status** | `research_status.py` | `optional` | 补充 — standalone viewer | 低 — CLI 已覆盖 | 零 | 低 | 易 | 否 | 否 |
| 22 | **Alignment Guard** | `alignment_guard.py` | `optional` | 补充 | 低 | 零 | 低 | 易 | 否 | 否 |
| 23 | **Exec Review** | `exec_review.py` | `optional` | 补充 | 低 | 零 | 中 | 中 | 否 | 否 |
| 24 | **Session Registry** | `session_registry.py` | `optional` | 补充 | 低 | 零 | 低 | 易 | 否 | 否 |
| 25 | **Resume Stage State** | `resume_stage_state.py` | `optional` | 补充 — 恢复中断运行 | 中 | 零 | 低 | 易 | 否 | 否 |
| 26 | **Slash Commands** | `register_slash_commands.py` | `optional` | 补充 | 中 — 但 CLI 已覆盖 | 零 | 低 | 易 | 否 | 否 |
| 27 | **PDF Reader** | `pdf_read.py` | `optional` | 有用 | 中 | 零 | 低 | 易 | 否 | 否 |
| 28 | **Exa Search** | `exa_search.py` | `deferred` | 可选 | 低 | 中 | 低 | 易 | 否 | 否 |
| 29 | **DeepXiv** | `deepxiv_fetch.py` | `deferred` | 可选 | 低 | 中 | 低 | 易 | 否 | 否 |
| 30 | **Semantic Scholar** | `semantic_scholar_fetch.py` | `deferred` | 可选 — rate limit 严格 | 低 | 中 | 低 | 易 | 否 | 否 |
| 31 | **Config Check** | `config_check.py` | `optional` | 补充 | 低 | 零 | 低 | 易 | 否 | 否 |
| 32 | **Figure Renderer** | `figure_renderer.py` | `deferred` | 仅 paper writing | 低 | 中 | 中 | 中 | 否 | 否 |
| 33 | **Paper Illustration** | `paper_illustration_image2.py` | `deferred` | 仅 paper writing | 低 | 中 | 中 | 中 | 否 | 否 |
| 34 | **Paper Ingest** | `paper_ingest.py` | `optional` | 补充 | 低 | 低 | 低 | 易 | 否 | 否 |
| 35 | **Research Wiki** | `research_wiki.py` | `deferred` | 知识库 — MVP 太重 | 低 | 中 | 高 | 难 | 是 — wiki = 重 | 否 |
| 36 | **Isolated Job Runner** | `isolated_job_runner.py` | `optional` | 沙箱执行 | 低 | 低 | 中 | 中 | 否 | 否 |
| 37 | **Agentic Idea Discovery** | `agentic_idea_discovery.py` | `deferred` | 已被 idea_pivot 替代 | 低 | 中 | 中 | 易 | 否 | 否 |

---

## 三、对 Broad Literature Scan 的重新判断

### 3.1 它是否对 idea discovery 有价值？

**有价值，但不是必须。**

当前 10-paper top_k 已经足够做 novelty risk assessment。broad scan 的价值在于：
- 发现更多 closest prior work，降低 high_risk_overlap 意外
- 为 idea pivot 提供更多 evidence-grounded 方向
- 对于成熟领域（如 NLP），10 篇可能遗漏关键竞争工作

但 broad scan 的风险是：
- 每次搜 100-300 篇太慢、太烧 token
- 如果不做全文读，metadata 质量不够做 deep review
- 如果做全文读，成本爆炸

### 3.2 是否应该现在做？

**不应该。** 原因：
1. 当前 MVP 还没跑通一次完整流程（experiment_plan 被阻塞）
2. broad scan 是优化，不是基础能力
3. 先让核心流程跑通，再考虑扩大搜索范围

### 3.3 有没有更轻量替代方案？

**有。** 当前的 multi-source pipeline（arXiv + OpenAlex + Crossref）已经比单一 OpenAlex 好很多。更轻量的替代方案：

1. **增加 Semantic Scholar**（deferred，rate limit 严格，但元数据质量高）
2. **增加引用次数排序**（OpenAlex 已有引用数据，只需在 scoring 中加入）
3. **增加 author name 去重**（同一作者多篇论文合并）

这些都不需要 "broad scan" 的完整基础设施。

### 3.4 如果做，如何避免每次都很慢、很烧 token？

关键原则：**先 metadata，后全文；先广后深。**

- Pass 1 只读 metadata（title + abstract + year + venue + citation count），不读全文
- Pass 1 用 deterministic scoring（不需要模型调用），选出 top 10-25
- Pass 2 只对 top 10-25 做全文 acquisition + trusted review
- Pass 2 才调用模型（full_text_reviewer）

### 3.5 不同 topic 的 adaptive sizing

| Topic 类型 | 特征 | 建议搜索范围 | 理由 |
|-----------|------|-------------|------|
| 小众方向 | 新领域、交叉学科、few papers | 30-80 篇 | 超过 80 篇大概率是噪音 |
| 普通方向 | 有明确 baseline 和竞争工作 | 80-200 篇 | 覆盖主要会议 + workshop |
| 大方向 | 热门领域（如 LLM、diffusion） | 先聚类，不全读 | 200+ 篇不可能全读，必须 cluster → sample → deep review |

Adaptive sizing 的实现方式：
1. 首次搜索返回 N 篇（N 由 topic 特征决定）
2. 如果 N < 30：`low_literature_yield`，不硬凑
3. 如果 30 ≤ N ≤ 200：正常流程
4. 如果 N > 200：先 cluster（按 venue + year + keywords），每个 cluster 选 top 3-5，总 deep review 不超过 25 篇

### 3.6 Stop Rules

| Rule | 触发条件 | 动作 |
|------|---------|------|
| Relevance decay | 连续 3 篇 relevance score < 0.3 | 停止搜索 |
| Duplicate saturation | 连续 10 篇都是已见过的 closest prior work | 停止搜索 |
| Cluster saturation | 新 cluster 数量在最近 10 篇中为 0 | 停止搜索 |
| No new method family | 连续 5 篇属于同一个 method family | 停止搜索 |
| Time budget | 搜索时间超过 5 分钟 | 停止搜索，记录 partial results |

### 3.7 Broad scan 只读 metadata，不默认全文读

- Pass 1：metadata only（title, abstract, year, venue, citation_count, DOI）
- Scoring：deterministic（keyword match + recency + citation count + venue tier）
- 不调用模型
- 不做全文 acquisition
- 只选 top 10-25 进入 Pass 2

### 3.8 Deep review 只选 top 10-25

- 全文 acquisition（arXiv source > PDF > open HTML）
- Trusted review（full_text_reviewer）
- 这是现有的 Phase 21 flow，不需要新基础设施

---

## 四、对 Literature Memory 的重新判断

### 4.1 是否真的能省 token？

**MVP 阶段不能。** 原因：
- 10-50 篇 paper 的 metadata 很小（< 100KB）
- 每次重新读 metadata 的 token 成本可以忽略
- 真正烧 token 的是模型调用（trusted review），不是读 metadata
- 唯一能省 token 的场景是：同一个 topic 跨多次 session 重复搜索。但这在 MVP 中不常见。

### 4.2 MVP 是否只需要 reading card markdown？

**是。** 一个 reading card = 一个 .md 文件，包含：
- paper_id, title, authors, year
- relevance_to_idea (score)
- closeness_to_our_method (high/medium/low)
- key_finding (一句话)
- gap_we_address (一句话)
- review_date, reviewer

这些信息已经在 full_text_review 的输出中存在。不需要额外的存储系统。

### 4.3 是否需要数据库？

**不需要。** 50 篇 paper 的 reading card 可以用 grep 搜索。500 篇也可以。1000 篇以上才需要数据库，但 MVP 不会处理 1000 篇。

### 4.4 是否会让系统变成维护成本很高的知识库工程？

**如果做数据库/向量库/知识图谱，会。** 这些系统的维护成本：
- Schema migration
- Index maintenance
- Cache invalidation
- 数据一致性检查
- 备份和恢复

MVP 不需要这些。

### 4.5 最小可行方案

```
literature/
  reading_cards/
    ftq_001.md
    ftq_002.md
    ...
  evidence_maps/
    current_idea.md    # 当前 idea 的 evidence map（哪些 paper 支持、哪些反对）
```

- 每篇 paper 一个 reading card（.md）
- 每个 idea 一个 evidence map（.md）
- 只缓存摘要和结构化判断
- 不缓存 raw full text
- 不做复杂向量库
- 不做 citation graph
- 不做 entity extraction

### 4.6 什么时候才值得实现？

当以下条件同时满足时：
1. 系统已经跑通完整流程（experiment_plan → paper_writing）
2. 同一个 topic 需要跨 3+ 次 session 重复搜索
3. Paper 数量超过 100 篇，grep 开始变慢
4. 有明确的 "我上次读过这篇" 的需求

目前这些条件都不满足。

---

## 五、和原版 ARIS 的对比

### 5.1 原版 ARIS 优点

| 优点 | 说明 |
|------|------|
| **Lightweight** | 核心概念少：Skill、Agent、Stage、Model Route。没有复杂的 trust boundary。 |
| **Low dependency** | 不需要 PyYAML、不需要数据库、不需要外部 API（除了模型调用）。 |
| **Native command** | 一键启动：`/research-start "..."`。用户不需要知道内部流程。 |
| **Markdown Skill** | 方法论嵌在 Markdown 里，人可读、可编辑、可版本控制。 |
| **Idea discovery** | 内置 idea discovery skill，不需要用户自己找 research direction。 |
| **Novelty check** | 内置 novelty check，自动判断 idea 是否新颖。 |
| **Experiment bridge** | 从 experiment plan 到 code implementation 的桥接。 |
| **Paper writing** | 自动写论文，包含 narrative report。 |
| **Multi-role / multi-model** | 不同 stage 用不同角色和模型（flash vs pro），effort level 可调。 |

### 5.2 当前系统新增优点

| 优点 | 说明 |
|------|------|
| **Trusted runner** | 所有模型调用经过 `trusted_role_runner.py`，不能静默调用。 |
| **Ledger** | 每次调用记录到 `llm_calls.jsonl`，可追溯。 |
| **Validator** | 每次调用后验证 backend、model、fallback、verification_status。 |
| **Context isolation** | forbidden_context 防止未批准的输入进入模型。 |
| **Trusted outputs** | 每个输出有 YAML frontmatter（schema_version, allowed_next_stage, verification_status）。 |
| **Evidence tracking** | 多源文献获取、full-text acquisition、manifest/queue 管理。 |
| **Stage output contract** | 每个 stage 有明确的 required fields、forbidden phrases、readiness gates。 |

### 5.3 当前系统新增风险

| 风险 | 严重程度 | 说明 |
|------|---------|------|
| **过多 stage** | 中 | 12+ 个 stage，每个有独立的配置、输入、输出、validator。状态空间大。 |
| **过多状态文件** | 中 | trusted_outputs/ 下 10+ 个 .md，加上 manifest.json、queue.json、review_notes.md、repair queue。 |
| **过多 validator** | 低-中 | 每个 stage 后都有 validate_model_invocation。必要但增加维护成本。 |
| **workflow 和 CLI 可能不一致** | 低 | 已修（STAGE_ORDER vs config stages），但需警惕未来 drift。 |
| **Literature layer 变重** | 高 | `literature_evidence_landing.py` 7800+ 行。单文件过大。 |
| **Debug 路径变长** | 中 | 从 raw_user_input 到 paper_writing 有 12 个 stage，错误传播链长。 |
| **Token 成本变高** | 中 | 每个 stage 一次模型调用，12 个 stage = 12 次调用。比原版 ARIS 多。 |
| **用户操作复杂度变高** | 低 | research_cli.py status/validate/continue 已简化，但底层仍然复杂。 |

### 5.4 总结

当前系统在 trust boundary 和 evidence tracking 上比原版 ARIS 强，但在 lightweight 和 debuggability 上不如。核心权衡是：**安全性 vs 复杂度**。对于生产级系统，这个权衡是值得的。对于 MVP，需要精简。

---

## 六、MVP 路线

### 6.1 MVP 必须保留

| Module | 理由 |
|--------|------|
| raw_user_input / input_normalization | 用户输入处理 |
| research_contract | 研究契约 |
| literature_search metadata | 文献搜索（metadata only） |
| novelty_check | 新颖性检查 |
| method_refinement | 方法精炼 |
| idea_pivot | 证据驱动的 pivot |
| experiment_plan | 实验计划 |
| status / validate / continue dry-run | CLI 核心 UX |
| trusted runner / validator / ledger | 信任边界 |
| context isolation | 安全边界 |
| stage output contract | 输出格式保证 |
| arXiv / OpenAlex / Crossref adapters | 多源证据 |

### 6.2 MVP 暂缓

| Module | 理由 |
|--------|------|
| Full broad scan 自动化 | 先跑通核心流程，再扩大搜索 |
| Literature memory 复杂系统 | Reading card schema 够用 |
| Citation graph | OpenAlex 已有引用数据，不需要单独的图 |
| Vector database | 50 篇 paper 用 grep 搜索 |
| Full paper parsing by sections | 当前 full-text acquisition + review 够用 |
| Paper-writing 自动化 | 被 result_judge 阻塞 |
| Result_judge 深度自动化 | 被 experiment_bridge 阻塞 |
| Experiment_bridge 完整自动化 | 被 implementation_plan 阻塞 |
| Implementation_plan 深度自动化 | 被 experiment_plan 阻塞 |

---

## 七、下一阶段建议

### 路线 1：Lightweight MVP 路线

**目标：** 最小可行产品，最快跑通完整流程。

**做法：**
1. 不新增任何 stage
2. 不新增任何工具文件
3. 只修 bug 和优化现有功能
4. 选一个新的 regression test idea（文献充足的），跑通 raw_user_input → experiment_plan
5. 完成后直接进入 experiment_plan → implementation → experiment → result_judge → paper_writing

**优点：** 最快出结果。
**缺点：** 功能最少。literature layer 没有优化。

**适合：** 想尽快看到端到端结果。

### 路线 2：Balanced Route（推荐）

**目标：** 在 MVP 基础上做最小必要的优化。

**做法：**
1. 拆分 `literature_evidence_landing.py`（7800+ 行 → 3-4 个模块）
2. 实现 `literature_evidence_landing.py` 的 `--file` alias 完善
3. 选一个新的 regression test idea，跑通 raw_user_input → experiment_plan
4. 实现 one-command live start（`research_cli.py start` 不再需要 `--dry-run`）
5. 完成端到端流程

**优点：** 代码质量提升 + 功能完整。
**缺点：** 比路线 1 多 2-3 天。

**适合：** 想要质量和速度的平衡。

### 路线 3：Heavy Research Automation Route

**目标：** 完整的自动化研究系统。

**做法：**
1. 实现 broad literature scan（adaptive sizing）
2. 实现 literature memory（reading card schema）
3. 实现 citation graph
4. 实现 full paper parsing by sections
5. 实现 experiment_bridge
6. 实现 paper-writing 自动化
7. 实现 result_judge 深度自动化

**优点：** 功能最完整。
**缺点：** 开发周期长（2-4 周），debug 困难，可能过度工程化。

**适合：** 想做一个完整的产品，而不是 MVP。

### 推荐

**推荐路线 2（Balanced Route）。**

理由：
- 路线 1 太简陋，literature layer 的 7800+ 行文件是个定时炸弹
- 路线 3 太重，MVP 还没跑通就加功能，风险高
- 路线 2 在质量和速度之间取得平衡：先拆分大文件，再跑通核心流程

---

## 八、Complexity Budget

当前系统有 **36 个 Python 文件** 在 `tools/`。对 MVP 来说太多。目标：

| Category | Current | Target | Action |
|----------|---------|--------|--------|
| Core CLI + config | 2 | 2 | Keep |
| Trust boundary (runner, ledger, route, validator, isolation) | 5 | 5 | Keep |
| Literature pipeline | 8 (split from 1) | 8 | DONE — `literature_evidence_landing.py` split into `tools/literature/{store.py, extraction.py, manual_ingest.py, scoring.py, multisource.py}` + `tools/literature/adapters/{openalex.py, arxiv.py, crossref.py}` with backward-compatible delegation |
| Workflow engine | 1 | 1 | Keep |
| Adapters (arXiv, OpenAlex, Crossref) | 3 | 3 | Keep |
| Supplementary tools | 24 | 6-8 | Deprecate or archive |
| **Total active** | **36** | **~16** | **Trim 20 files** |

20 个 supplementary files 应该 archive 到 `tools/archive/` 或删除。它们不被核心流程使用，增加认知负担。

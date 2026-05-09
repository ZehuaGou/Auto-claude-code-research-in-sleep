# ARIS Research Reliability Enhancement 使用与贡献指南

> 本文档面向 ARIS 用户和贡献者，说明 Research Reliability Enhancement 层的目标、用法、架构和维护规范。
> 本文档不替代原 ARIS 文档，而是增量补充。

---

## 1. 这次增强解决了什么问题

ARIS 原有流程以 Markdown skill 驱动，灵活但缺乏可靠性约束。本次增强在**不改变原 ARIS 架构**的前提下，围绕以下问题补充工具、技能和约束：

| 问题 | 表现 | 解决方法 |
|------|------|----------|
| **上下文污染** | 同一个 session 中先后处理多篇论文，前一论文的细节混淆后一论文的判断 | session-orchestrator + session-handoff 实现 session 隔离和结构化交接 |
| **无 baseline 宣称提升** | "我们的方法优于 perplexity" 但从未复现 baseline | baseline-repro 强制记录 baseline 复现状态，not-run 不可宣称提升 |
| **事后修改成功标准** | 实验后发现 AUROC=0.55，于是把 success threshold 改成 0.5 | research-contract 锁定 hypothesis、success/failure signals、metrics，lock 后不可修改 |
| **直接塞 PDF 进上下文** | 把整篇 PDF 塞给 LLM，token 浪费、关键信息丢失 | paper-ingest 将论文转为结构化 Markdown 目录和章节占位，按需分阶段阅读 |
| **Codex/LLM 调用黑箱** | 不知道每次 reviewer 调用用了什么模型、是否 fallback、有无失败 | llm_call_ledger 自动记录每次调用，model-usage-status 提供可视化 |
| **Claim 无实验支撑** | 论文里宣称 "方法在多模型上有效" 但只测了一个模型 | research-assurance 跟踪 claim→experiment 映射，claim boundary 强制执行 |
| **多 session 协作混乱** | 不同 session 之间没有结构化交接，上下文丢失 | session-protocol + handoff 模板实现标准化 session 间通信 |
| **保持 ARIS 轻量架构** | 不能引入复杂框架、数据库、外部依赖 | 所有新增功能为 Python 工具 + Markdown skill + JSON 文件，零外部依赖 |

---

## 2. 新增功能总览

### 2.1 新增 Skills

| Skill | 作用 | 主要输入 | 主要输出 | 什么时候用 |
|-------|------|----------|----------|------------|
| `/config-check` | 检查 .env、Codex、Feishu 配置，检测缺失变量 | .env 文件 | config/CONFIG_CHECK.md, config/status.json | 首次配置后、每次切换模型后 |
| `/model-usage-status` | 查看所有 Codex/LLM 调用记录、fallback 统计 | .aris/calls/llm_calls.jsonl | 终端输出 | 怀疑调用异常、需要审计模型用量时 |
| `/status` | 统一查看项目状态（pipeline/session/experiment/reviewer） | 各 artifact 文件 | 终端输出 | 随时了解项目当前阶段 |
| `/research-contract` | 冻结实验假设、成功/失败信号、metrics 和 claim boundary | idea card | docs/research_contract.md + lock.json | 实验开始前，锁定实验设计 |
| `/baseline-repro` | 建立和验证 baseline 复现状态 | baseline repo/paper | research/BASELINE.md, BASELINE_REPRODUCTION_REPORT.md | 任何实验开始前 |
| `/paper-ingest` | 将论文转为结构化 Markdown 目录和章节占位 | arXiv ID 或 PDF 路径 | literature-md/\<paper_id\>/ 含 metadata + 章节占位 | 阅读任何论文时 |
| `/session-orchestrator` | 管理多 session 研究流程 | 各类 artifact | .aris/sessions/SESSION_REGISTRY.json, ACTIVE_TASKS.json | 需要跨 session 协作时 |
| `/session-handoff` | 标准化 session 间交接 | 当前 session 上下文 | .aris/sessions/HANDOFFS/\<handoff\>.json | session 切换时 |
| `/exec-review` | 单轮 reviewer 审查 | idea/contract/result 文件 | 终端输出 + ledger 记录 | 需要快速独立审查时 |
| `/panel-review` | 多轮多 reviewer 复杂评审 | 待评审材料 | 多轮评审记录 | 需要深度 debate 时 |
| `/research-assurance` | 论文提交前的完整可靠性检查 | contract, baseline, experiment log, claims | research/CLAIM_EVIDENCE_TABLE.md, ASSURANCE_REPORT.md | 提交论文前 |

### 2.2 新增 Tools

| Tool | 作用 | 是否修改 .env |
|------|------|---------------|
| `tools/env_loader.py` | 统一读取 .env，不泄漏完整 key | ❌ 只读 |
| `tools/config_check.py` | 执行完整配置检查 | ❌ 只读 |
| `tools/llm_call_ledger.py` | 跟踪所有模型调用 | ❌ 只写文件 |
| `tools/paper_ingest.py` | 从 arXiv/PDF 提取元数据并生成章节占位 | ❌ 不涉及 |
| `tools/exec_review.py` | 初始化 review session 并集成 ledger；**不直接调用 Codex/LLM**（由 Agent 按 SKILL.md 执行） | ❌ 只写文件 |
| `tools/session_registry.py` | session 注册和任务管理 | ❌ 只写文件 |

### 2.3 新增 Shared References

| 文件 | 用途 |
|------|------|
| `skills/shared-references/env-config-policy.md` | .env 读取规则和命名约定 |
| `skills/shared-references/model-routing.md` | 12 个角色的模型路由定义 |
| `skills/shared-references/transport-routing.md` | MCP/exec-review/panel-review 适用性矩阵 |
| `skills/shared-references/research-contract.md` | 合同协议（13 个必填字段、锁定模式） |
| `skills/shared-references/paper-ingest-protocol.md` | 论文摄入协议和分阶段阅读规则 |
| `skills/shared-references/session-protocol.md` | 11 种 session 类型、状态机、handoff 合约 |

---

## 3. 推荐完整工作流

以下为 ARIS + 可靠性增强的推荐完整工作流。**加粗**为必须步骤，其余可选。

```
Step  1: /config-check                         确认环境就绪
Step  2: /research-lit 或 /arxiv "topic"       文献调研（可选）
Step  3: /paper-ingest "arxiv:2401.12345"      论文结构化摄入
Step  4: /idea-discovery "direction"             完整 idea discovery 全流程
         /research-lit "方向" → /idea-creator "方向" → /exec-review → /novelty-check
                                                 分步执行（推荐）
Step  5: /exec-review "idea"                    独立审查 idea（可选）
Step  6: /novelty-check "idea"                  查新判断
Step  7: /baseline-repro "baseline"             建立 baseline
Step  8: /research-contract "idea"              锁定实验合同
Step  9: /experiment-bridge "plan"              实现实验
Step 10: /experiment-audit "code"               审查实验完整性
Step 11: /result-to-claim "results"             判断 claim 支持程度
Step 12: /research-assurance                    提交前可靠性检查
Step 13: /paper-writing "results"               撰写论文
随时:   /status, /model-usage-status            查看项目状态
```

### 必须步骤

| 步骤 | 原因 |
|------|------|
| `/config-check` | 首次使用必须确认配置正确 |
| `/research-contract` | **实验前必须锁定** — 否则事后修改 success criteria 无从约束 |
| `/baseline-repro` | **任何对比 claim 必须复现 baseline** — not-run 不可宣称提升 |
| `/research-assurance` | **提交前必须运行** — 否则 claim 可能无实验支撑 |

### 可选但推荐步骤

| 步骤 | 推荐场景 |
|------|----------|
| `/exec-review` | idea 或 contract 需要独立 second opinion |
| `/novelty-check` | 需要正式查新报告 |
| `/experiment-audit` | 实验代码由主作者自己写，需要独立审查 |
| `/session-orchestrator` | 多人跨 session 协作 |

---

## 4. 配置说明

### 4.1 .env 规则

```
┌─────────────────────────────────────────────┐
│  真实配置 → 项目根目录 .env（已 .gitignore）  │
│  示例模板 → .env.example（可提交）            │
│  禁止提交 → 任何真实 API Key                  │
│  禁止覆盖 → 任何操作不得修改用户 .env          │
└─────────────────────────────────────────────┘
```

### 4.2 变量命名

- 所有可靠性相关变量使用 `LLM_*` 前缀
- 不使用 `DEEPSEEK_*` 或 `ARIS_*` 前缀
- 角色变量格式：`LLM_<ROLE>_PRIMARY` / `LLM_<ROLE>_FALLBACK_MODEL`

### 4.3 关键变量说明

| 变量 | 用途 | 必填 |
|------|------|------|
| `LLM_API_KEY` | DeepSeek / OpenAI API Key | 是 |
| `LLM_BASE_URL` | API 端点 URL | 是 |
| `LLM_MODEL` | 主模型名 | 是 |
| `LLM_FALLBACK_MODEL` | 降级模型名 | 否 |
| `LLM_THINKING` | thinking 模式配置 | 否 |
| `LLM_REASONING_EFFORT` | 推理力度 | 否 |
| `LLM_MAX_TOKENS` | 最大 token 数 | 否 |
| `LLM_<ROLE>_PRIMARY` | 角色专用主模型 | 否 |
| `LLM_<ROLE>_FALLBACK_MODEL` | 角色专用降级模型 | 否 |

### 4.4 Codex 不走 .env

- Codex CLI / MCP 配置在 `.mcp.json` 或 Codex 自身配置中
- `.env` 只管理 LLM Chat (OpenAI-compatible) 配置
- 新增角色模型变量只影响 llm-chat 降级行为，不影响 Codex

---

## 5. 模型角色路由说明

ARIS Research Reliability Enhancement 定义了 12 个 reviewer 角色，每个角色有明确的职责范围。

### 角色定义

| 角色 | 职责 | Codex 优先 | Fallback |
|------|------|-----------|----------|
| **literature_scout** | 搜索文献元数据，判断论文相关性，输出结构化的文献列表 | ❌ | DeepSeek |
| **paper_summarizer** | 总结 paper-ingest 生成的 Markdown 章节，提取关键方法与结果 | ❌ | DeepSeek |
| **idea_generator** | 根据 research direction 生成 idea card，包含 hypothesis、实验设计和预期结果 | ❌ | DeepSeek |
| **idea_reviewer** | 独立审查单个 idea 的 novelty、可行性、风险和预期贡献 | ✅ | DeepSeek |
| **novelty_checker** | 查新判断 — 对比 idea 与现有文献，确认是否存在 prior art | ✅ | DeepSeek |
| **contract_reviewer** | 审查 research contract 的完整性 — 确认 success/failure signals、metrics、data split、claim boundary | ✅ | DeepSeek |
| **baseline_reviewer** | 审查 baseline 复现是否可信，确认 baseline 配置与原始论文一致 | ❌ | DeepSeek |
| **experiment_code_reviewer** | 审查实验代码是否符合 research contract，检查 data leakage、metric 实现 | ❌ | DeepSeek |
| **experiment_auditor** | 审查实验完整性 — 确认实验覆盖所有 contract 要求的测试 | ✅ | DeepSeek |
| **result_judge** | 判断实验结果支持哪些 claim，输出 claim→experiment 映射表 | ✅ | DeepSeek |
| **final_auditor** | 最终论文审查 — 整体一致性检查 | ✅ | DeepSeek |
| **log_summarizer** | 日志和状态总结，输出可读的状态报告 | ❌ | DeepSeek |

### 路由策略

```
角色是否需要高级推理能力（Codex 优先）？
├─ 是 → 尝试 Codex（gpt-5.4-codex）
│       ├─ 成功 → 记录 completed
│       └─ 失败/超时 → 降级到 LLM Chat（DeepSeek）
│                       ├─ 记录 completed_with_fallback
│                       └─ 日志打印 REQUIRED 降级标记
│
└─ 否 → 直接使用 LLM Chat（DeepSeek）
        └─ 记录 completed
```

### Fallback 标记

当 Codex 降级到 LLM Chat 时，llm_call_ledger 会自动在日志中输出以下标记，确保降级可追踪：

```
REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK
```

该标记出现在 `.aris/calls/llm_calls.jsonl` 的 `fallback_used: true` 记录中，同时出现在终端日志里。

---

## 6. 关键 Artifact 说明

### 6.1 配置类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `config/status.json` | 结构化配置状态（机器可读） | config-check | status, 外部工具 |
| `config/CONFIG_CHECK.md` | 配置检查报告（人类可读） | config-check | 用户 |

### 6.2 Call Ledger 类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `.aris/calls/current_call.json` | 当前进行中的调用 | llm_call_ledger start | model-usage-status |
| `.aris/calls/llm_calls.jsonl` | 所有调用历史 | llm_call_ledger (全部命令) | model-usage-status, status |

### 6.3 Session 类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `.aris/sessions/SESSION_REGISTRY.json` | 所有 session 注册表 | session-orchestrator | status, session-orchestrator |
| `.aris/sessions/ACTIVE_TASKS.json` | 当前活跃任务列表 | session-orchestrator | status |
| `.aris/sessions/HANDOFFS/` | session handoff 记录 | session-handoff | session-orchestrator |

### 6.4 Contract 类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `docs/research_contract.md` | 研究合同（人类可读） | research-contract | experiment-bridge, result-to-claim, research-assurance |
| `docs/research_contract.lock.json` | 合同锁定信息 | research-contract | experiment-bridge, research-assurance |

### 6.5 Baseline 类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `research/BASELINE.md` | baseline 文档 | baseline-repro | experiment-bridge, research-assurance |
| `research/BASELINE_REPRODUCTION_REPORT.md` | baseline 复现报告 | baseline-repro | experiment-bridge, research-assurance |

### 6.6 Paper 类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `literature-md/<paper_id>/` | 结构化论文章节 | paper-ingest | novelty-check, baseline-repro, paper-writing |

### 6.7 Assurance 类

| 路径 | 用途 | 谁生成 | 谁读取 |
|------|------|--------|--------|
| `research/CLAIM_EVIDENCE_TABLE.md` | claim→experiment 映射表 | research-assurance, result-to-claim | paper-writing |
| `research/ASSURANCE_REPORT.md` | 提交前可靠性检查报告 | research-assurance | paper-writing, 提交 |

---

## 7. 每个新增 Skill 的详细用法

### 7.1 /config-check

**作用：** 检查 .env、Codex CLI、LLM Chat、Feishu webhook 配置，检测缺失变量。

**什么时候用：** 首次配置 ARIS 后、切换模型后、遇到连接问题时。

**示例命令：**
```
/config-check
```

**输入：** 项目根目录 `.env` 文件（只读）

**输出：**
- `config/status.json` — 结构化配置状态
- `config/CONFIG_CHECK.md` — 人类可读报告

**常见失败：**

| 问题 | 表现 | 恢复 |
|------|------|------|
| `.env` 不存在 | config-check 报告 .env not found | 从 .env.example 复制并填充 |
| Codex CLI 不可用 | codex.cli_available: false | 安装 Codex CLI 或忽略（非必须） |
| Feishu 未配置 | feishu.webhook_present: false | 可选，不影响核心功能 |
| 角色变量缺失 | warnings 中列出缺失变量 | 按需添加，fallback 会用 LLM_FALLBACK_MODEL |

**注意：** config-check **不会自动修改 .env**。所有问题只报告，由用户决定是否修改。

---

### 7.2 /model-usage-status

**作用：** 查看所有 Codex/LLM 调用记录，包括每次调用的 model、status、fallback 情况。

**什么时候用：**
- 怀疑某次 review 调用降级了
- 需要审计某次实验的模型用量
- 检查是否有 failed 调用被忽略

**示例命令：**
```
/model-usage-status
```

**输入：** `.aris/calls/llm_calls.jsonl`, `.aris/calls/current_call.json`

**输出：** 终端输出，包含：
- 总调用数
- Fallback 次数和失败次数
- By backend 统计（codex vs llm-chat）
- By skill 统计
- By status 统计
- 最近 20 条调用记录

**常见失败：**

| 问题 | 恢复 |
|------|------|
| ledger 为空（还没有调用） | 正常运行一次需要 Codex/LLM 的 skill |
| 文件被手动修改导致 JSON 解析失败 | 删除或修复对应行 |

---

### 7.3 /status

**作用：** 统一查看项目状态 — pipeline 进展、session 活跃情况、experiment 状态、reviewer 调用状态。

**什么时候用：** 随时，特别是重新开始工作时。

**示例命令：**
```
/status
```

**输入：** 各类 artifact 文件（自动检测）

**输出：** 终端输出

**常见失败：** 无 — 即使没有 artifact 也会输出最小状态。

---

### 7.4 /research-contract

**作用：** 在实验开始前锁定研究合同。合同包含 hypothesis、success signals、failure signals、metrics、data split、claim boundary。一旦 lock 不允许修改。

**什么时候用：** 任何实验开始前**必须**运行。

**示例命令：**
```
/research-contract "idea-stage/IDEA_CARDS/test_idea.md"
```

**输入：** idea card（Markdown，包含 hypothesis 和实验设计）

**输出：**
- `docs/research_contract.md` — 完整合同
- `docs/research_contract.lock.json` — 锁定记录

**合同必填字段：**

| 字段 | 说明 |
|------|------|
| hypothesis | 一句话研究假设 |
| success_signals | 什么结果算成功（含数值阈值） |
| failure_signals | 什么结果算失败 |
| metrics | 评估指标 |
| data_split | 数据划分方式 |
| claim_boundary | 哪些 claim 可以做，哪些不能做 |

**常见失败：**

| 问题 | 恢复 |
|------|------|
| idea card 缺少必要字段 | 补全 idea card 后重试 |
| contract 已被 lock | 无法修改 — 创建新 contract 或解除 lock |
| contract_reviewer 调用超时 | 检查 Codex 连接或确认 fallback 是否触发 |

---

### 7.5 /baseline-repro

**作用：** 记录 baseline 复现状态。支持三种状态：completed（已复现）、not-run（未运行）、failed（复现失败）。not-run 状态下不可宣称 "优于 baseline"。

**什么时候用：** 任何对比实验开始前**必须**运行。

**示例命令：**
```
/baseline-repro "repo" — effort: lite
```

**输入：** baseline paper/repo 路径

**输出：**
- `research/BASELINE.md` — baseline 文档
- `research/BASELINE_REPRODUCTION_REPORT.md` — 复现报告

**Verdict 含义：**

| Verdict | 含义 | 允许宣称提升？ |
|---------|------|---------------|
| completed | 成功复现 | ✅ 是 |
| not-run | 未运行 | ❌ 否 — soft gate 警告 |
| failed | 尝试复现但失败 | ❌ 否 — 需记录原因 |

**常见失败：**

| 问题 | 恢复 |
|------|------|
| --effort lite 且 baseline 复杂 | 改为 --effort balanced 或 max |
| baseline 环境问题 | 手动复现后更新 report |
| mock 模式（无实际 baseline） | 设置 verdict=not-run，标记为警告 |

---

### 7.6 /paper-ingest

**作用：** 从 arXiv 获取论文元数据和摘要，生成结构化 Markdown 目录和章节占位。支持分阶段阅读。

**当前实现：**
- arXiv metadata 获取（标题、作者、摘要、年份、categories、DOI）
- abstract 写入
- `literature-md/<paper_id>/` 目录结构创建
- `metadata.json`、`section_index.json` 生成
- introduction/method/experiments/related_work/conclusion → **章节占位**（非完整正文）

**注意：** 当前 tool **不自动完成** LaTeX/HTML/PDF 深度解析。introduction/method/experiments 等章节写入的是占位文本（"[Section not yet ingested — run paper-ingest with --deep to extract full text]"），非完整内容。如需完整论文正文，应由 Agent 按照 paper-ingest-protocol 进一步读取 PDF 或使用外部转换工具。

**什么时候用：** 阅读任何论文时 — 替代直接将 PDF 塞入上下文。

**示例命令：**
```
/paper-ingest "arxiv:2401.12345"
```

**输入：** arXiv ID 或 PDF 路径

**输出：** `literature-md/<paper_id>/` 目录，包含：

| 文件 | 内容（⚠️ 章节文件为占位文本，非完整正文） |
|------|------|
| `metadata.json` | 论文元数据（标题、作者、摘要） |
| `abstract.md` | 摘要（来自 arXiv XML） |
| `introduction.md` | ⚠️ 占位文本 |
| `method.md` | ⚠️ 占位文本 |
| `experiments.md` | ⚠️ 占位文本 |
| `related_work.md` | ⚠️ 占位文本 |
| `conclusion.md` | ⚠️ 占位文本 |
| `section_index.json` | 章节索引 |

完整章节正文需由 Agent 按 paper-ingest-protocol 从源 PDF/LaTeX/HTML 进一步读取。

**常见失败：**

| 问题 | 恢复 |
|------|------|
| arXiv ID 不存在 | 检查 ID 是否正确 |
| PDF 格式过于复杂 | 部分章节可能为空 — 手动补充 |
| 网络连接失败 | 检查网络后重试 |

---

### 7.7 /session-orchestrator

**作用：** 管理多 session 研究流程。注册 session、分配任务、跟踪状态。

**什么时候用：** 需要跨多个 session 协作时（例如：一个 session 做实验，另一个 session 写论文）。

**当前实现级别：**

| 功能 | 状态 |
|------|------|
| session registry（注册/列表/关闭） | ✅ 已实现 |
| active tasks（分配/查看） | ✅ 已实现 |
| handoff 模板生成 | ✅ 已实现（tools/session_registry.py handoff） |
| 自动启动多个真实 Claude/Claude Code 子进程 | ❌ 不支持 |
| 自动创建 tmux panel | ❌ 不支持 |
| 强制上下文隔离（阻止读取其他 session 日志） | ❌ 不支持（依赖约定） |

**示例命令：**
```
/session-orchestrator init
/session-orchestrator register literature_scout
```

**输入：** 各类 artifact

**输出：**
- `.aris/sessions/SESSION_REGISTRY.json`
- `.aris/sessions/ACTIVE_TASKS.json`

**推荐实际使用方式（真实上下文隔离）：**

1. 主 session 运行 `init` + `register` + `assign`
2. 用户手动打开新的 Claude Code 终端（新 session）
3. 新 session 只读取指定 `input_files`
4. 先用 `tools/session_registry.py handoff <task_id> draft` 生成 handoff 模板
5. 填写 Decision / Evidence 等字段后，再执行 `handoff <task_id> done`（自动检查 TODO）
6. 主 session 只读 handoff，不读副 session 全量过程日志

**重要说明：**
- 当前 session 机制是**文件级 registry + handoff protocol**，不是自动多进程管理器
- session 是逻辑角色，不一定是操作系统进程
- 上下文隔离依赖外层 Agent 按角色的新开会话和只读 input_files
- session 机制降低上下文污染，但不能替代真实模型上下文隔离

**常见失败：**

| 问题 | 恢复 |
|------|------|
| 重复注册 | 使用 `close` 关闭旧 session |
| handoff 文件未找到 | 先运行 `/session-handoff` |

---

### 7.8 /session-handoff

**作用：** 在 session 切换时生成结构化 handoff 记录，确保下一个 session 能获取完整上下文。

**什么时候用：** 每次 session 切换时。

**示例命令：**
```bash
/session-handoff "task: 继续实验分析"

# 或通过命令行工具自动生成模板（默认 draft 状态）：
python3 tools/session_registry.py handoff <task_id> draft

# 填写 Decision/Evidence 后标记为完成（自动检查 TODO）：
python3 tools/session_registry.py handoff <task_id> done
```

**输入：** 当前 session 上下文

**输出：** `.aris/sessions/HANDOFFS/<task_id>.md`

**注意：**
- `tools/session_registry.py handoff <task_id>` 可自动生成 handoff **模板**文件
- 自动生成的模板不包含实际判断内容 — 必须由执行任务的 Agent 手动填充
- 必须填充的字段：Decision、Evidence、Failure Modes、Next Action
- 如果 evidence 不足，必须写 `evidence insufficient`，不能留空或编造
- 如果 handoff 文件中仍有 `TODO:`，工具会自动拒绝标记为 `done`，降级为 `needs_review`

### Handoff Status 语义

| 状态 | 含义 | 主 session 应如何处理 |
|------|------|----------------------|
| `draft` | 刚生成模板，还未填写内容 | ⚠️ 不能作为最终判断 |
| `needs_review` | handoff 仍有 TODO 或 evidence 不足 | ⚠️ 不能作为最终判断 |
| `done` | Decision / Evidence / Next Action 已填写，且无 TODO | ✅ 可信任 |
| `failed` | 任务失败 | ❌ 需要重新规划 |
| `blocked` | 任务被阻塞 | ❌ 需要解决阻塞 |

只有 `done` 状态的 handoff 才会将 session 设为 idle 并清空 current_task。主 session 不应信任 `draft` / `needs_review` handoff 作为最终结论。

**Handoff 模板字段：**
- task_id, role, session_id, created_at, status
- Input Files, Output Files
- Decision（明确判断）
- Evidence（支持判断的文件/指标/日志）
- Failure Modes（可能错在哪里）
- Unresolved Questions（未解决问题）
- Next Action（建议主 session 下一步）
- Do Not Assume（主 session 不能擅自假设的事项）

**常见失败：**

| 问题 | 恢复 |
|------|------|
| session 未注册 | 先运行 session-orchestrator 注册 |
| 缺少必要上下文 | 补全后重试 |

---

### 7.9 /exec-review

**作用：** 单轮独立 reviewer 审查。支持审查 idea、contract、result 等。

**什么时候用：** 需要快速 second opinion 时。

**示例命令：**
```
/exec-review "file: idea-stage/IDEA_CARDS/my_idea.md" — role: idea_reviewer
```

**输入：** 待审查文件

**输出：** 终端输出 + ledger 记录

**常见失败：**

| 问题 | 恢复 |
|------|------|
| Codex 调用超时 | 自动 fallback 到 DeepSeek |
| 审查结果为空 | 检查输入文件格式 |

---

### 7.10 /panel-review

**作用：** 多轮多 reviewer 复杂评审。适用于需要深度 debate 的场景。

**什么时候用：** 对重要决定需要多个 reviewer 交叉验证时。

**示例命令：**
```
/panel-review "topic: 方法的 novelty 是否足够"
```

**输入：** 待评审材料

**输出：** 多轮评审记录

**常见失败：**

| 问题 | 恢复 |
|------|------|
| 多轮对话超出上下文 | 使用 session-handoff 分轮次处理 |
| reviewer 意见分歧 | 增加 final_auditor 裁决轮 |

---

### 7.11 /research-assurance

**作用：** 论文提交前的完整可靠性检查。验证 contract 是否锁定、baseline 是否复现、experiment 是否 audit、claim 是否有实验支撑。

**什么时候用：** 提交论文前**必须**运行。

**示例命令：**
```
/research-assurance
```

**输入：**
- `docs/research_contract.md` + `research_contract.lock.json`
- `research/BASELINE_REPRODUCTION_REPORT.md`
- `EXPERIMENT_LOG.md`
- `EXPERIMENT_AUDIT.md`（可选）

**输出：**
- `research/CLAIM_EVIDENCE_TABLE.md` — claim→experiment 映射
- `research/ASSURANCE_REPORT.md` — 完整检查报告

**claim 状态说明：**

| 字段 | 含义 | 值示例 |
|------|------|--------|
| evidence_strength | 证据强度 | none / weak / moderate / strong |
| allowed_in_paper | 是否允许写入论文 | yes / no / needs-caveat |
| audit_status | 审计状态 | not_run / passed / failed |

**常见失败：**

| 问题 | 恢复 |
|------|------|
| contract 未 lock | 运行 research-contract 并 lock |
| baseline 为 not-run | 复现 baseline 或标记为警告 |
| claim 无 experiment 对应 | 补充实验或删除该 claim |
| claim 超出 contract 的 claim boundary | 不允许 — 必须删除该 claim |

---

## 8. 新增 Tools 说明

### 8.1 tools/env_loader.py

**作用：** 统一 .env 文件读取工具。提供 masking 功能确保不泄漏完整 API Key。

**是否修改 .env：** ❌ 只读

**常用命令：**
```bash
python tools/env_loader.py             # 读取并显示 .env（mask 敏感值）
python tools/env_loader.py --key LLM_MODEL  # 查询特定变量
```

**输出：** JSON，包含 `{env_path, exists, vars, masked}`

**安全保证：** 所有 API Key 输出时自动 mask（`sk-****abcd`）。

---

### 8.2 tools/config_check.py

**作用：** 执行完整配置检查。包括 .env 变量、Codex CLI、缺失角色变量。

**是否修改 .env：** ❌ 只读

**常用命令：**
```bash
python tools/config_check.py
```

**输出：** `config/status.json` + `config/CONFIG_CHECK.md`

---

### 8.3 tools/llm_call_ledger.py

**作用：** 跟踪所有 Codex/LLM 模型调用。支持 start/finish/fail/fallback 生命周期。

**是否修改 .env：** ❌ 不涉及

**常用命令：**
```bash
python tools/llm_call_ledger.py start --skill test --role reviewer --backend codex --model gpt-5.4
python tools/llm_call_ledger.py finish --call-id <id> --output-files paper.md
python tools/llm_call_ledger.py fallback --call-id <id> --reason "timeout"
python tools/llm_call_ledger.py summary
```

**输出：**
- `.aris/calls/current_call.json` — 当前调用
- `.aris/calls/llm_calls.jsonl` — 全部历史

**安全保证：** 不记录 API Key 或 prompt 内容。

---

### 8.4 tools/paper_ingest.py

**作用：** 从 arXiv API 获取论文元数据和摘要，生成结构化 Markdown 目录和章节占位。

**注意：** 当前 tool **不自动完成** LaTeX/HTML/PDF 深度转 Markdown。完整正文提取属于 protocol 定义的未来工作，需要 Agent 或外部转换工具协作。

**是否修改 .env：** ❌ 不涉及

**常用命令：**
```bash
python tools/paper_ingest.py ingest 2401.12345                        # 从 arXiv 获取元数据 + 章节占位
python tools/paper_ingest.py ingest path/to/paper.pdf                  # 从本地 PDF 获取（基础 metadata，不做 PDF 解析）
python tools/paper_ingest.py metadata 2401.12345                       # 只获取元数据
python tools/paper_ingest.py list                                      # 列出已摄入的论文
```

**输出：** `literature-md/<paper_id>/` 目录

---

### 8.5 tools/exec_review.py

**作用：** 初始化 review session 并集成 ledger 记录。

**注意：** 本 tool **不直接调用 Codex/LLM**。它只管理 review 的初始化和状态记录。实际的 Codex/LLM 审查由外层 Agent 按照 `skills/exec-review/SKILL.md` 的 workflow 执行。Ledger 集成（llm_call_ledger start/finish/fallback）也需要 Agent 或 wrapper 主动调用。

**是否修改 .env：** ❌ 只写文件

**常用命令：**
```bash
python tools/exec_review.py init idea.md                   # 初始化 review（定位到文件）
python tools/exec_review.py init idea.md idea_reviewer codex # 指定 role 和 primary
python tools/exec_review.py complete <review-id>            # 完成 review
python tools/exec_review.py status                          # 查看所有 review
```

---

### 8.6 tools/session_registry.py

**作用：** session 注册和任务管理。

**是否修改 .env：** ❌ 只写文件

**常用命令：**
```bash
python tools/session_registry.py init                                 # 初始化 registry 和 tasks
python tools/session_registry.py register literature_scout            # 注册新 session（指定 role）
python tools/session_registry.py list                                 # 列出所有 session
python tools/session_registry.py close <session_id>                   # 关闭 session
python tools/session_registry.py assign <session_id> "run experiments" # 分配任务
python tools/session_registry.py tasks                                # 列出所有任务
python tools/session_registry.py handoff <task_id> draft              # 生成 handoff 模板（默认 draft）
python tools/session_registry.py handoff <task_id> done               # 标记完成（自动检查 TODO）
```

---

### 8.7 所有 Tools 的安全规则

```
1. 不允许输出完整 API Key — 必须 mask（sk-****）
2. 不允许修改 .env — 只读操作
3. 不允许记录 prompt 内容到 ledger — 只记 metadata
4. 不允许发送 .env 内容到外部 API
```

---

## 9. 贡献者维护规范

新增或修改 skill 时，SKILL.md **必须**包含以下所有章节。不可只创建空 skill 或只写抽象概念。

### 9.1 SKILL.md 必填章节

| 章节 | 要求 |
|------|------|
| **Frontmatter** | name, description, type (必须为 skill), model 配置 |
| **Purpose** | 1-2 句话说明 skill 解决什么问题 |
| **When to Use** | 什么场景下调用此 skill |
| **Inputs** | 需要哪些输入文件或参数 |
| **Outputs** | 生成哪些输出文件 |
| **Workflow** | 逐步执行流程 |
| **Hard Rules** | 不可违反的约束（如：不得修改 .env） |
| **Failure Handling** | 常见失败场景和恢复步骤 |
| **Integration** | 与哪些其他 skill/tool 交互 |
| **Example Invocation** | 完整的命令示例 |
| **Expected Artifacts** | 所有预期生成的 artifact |
| **Recovery Step** | 如果执行中断如何恢复 |
| **Status / Ledger** | 如何记录调用状态 |

### 9.2 通用规则

- 涉及 Codex/LLM 调用的 skill **必须**写入 `llm_calls.jsonl`
- 涉及跨 session 的 skill **必须**写入 handoff
- Codex fallback **必须**记录 fallback_reason 和 REQUIRED 标记
- 所有 artifact 路径使用相对于项目根目录的路径
- 不引入外部依赖（Python 标准库 + 已有依赖足够）

### 9.3 禁止事项

```
❌ 不要创建只有 frontmatter 的空 skill
❌ 不要只写 "调用 LLM 审查" 而不指定 role 和 model
❌ 不要跳过 hard rules 章节
❌ 不要直接读取用户 .env 内容输出到终端（用 mask）
❌ 不要引入新的外部 Python 依赖（如需新增需论证）
```

---

## 10. PR 检查清单

提交 PR 前请逐项检查：

### 10.1 安全

- [ ] 没有修改用户真实 `.env`
- [ ] 没有提交任何真实 API Key 到代码库
- [ ] `.env.example` 只包含示例变量，不含真实值
- [ ] 所有 API Key 输出使用 mask 处理

### 10.2 Skill 完整性

- [ ] 新增 skill 有完整的 SKILL.md（13 个必填章节）
- [ ] 新增 skill 的 frontmatter 配置正确
- [ ] 涉及 Codex/LLM 调用的 skill 写入了 llm_calls.jsonl
- [ ] 涉及跨 session 的 skill 写入了 handoff

### 10.3 Tool 可运行性

- [ ] 新增 tool 可通过 `python tools/<name>.py --help` 或 `python tools/<name>.py <subcommand> --help` 查看帮助
- [ ] 新增 tool 不修改 .env
- [ ] 新增 tool 不泄漏完整 API Key

### 10.4 Smoke Test

- [ ] `/config-check` 可运行并输出正确报告
- [ ] `/status` 可运行
- [ ] `/model-usage-status` 可运行
- [ ] Codex fallback 可追踪（ledger 包含 fallback 记录）
- [ ] Claim evidence 可追踪（research-assurance 可生成映射表）
- [ ] Baseline 和 contract 逻辑没有被绕过（not-run 不可宣称提升，lock 后不可修改）

### 10.5 文档

- [ ] `docs/RESEARCH_RELIABILITY_ENHANCEMENT_GUIDE_CN.md` 已更新
- [ ] `AGENT_GUIDE.md` 中的文档索引已更新
- [ ] Shared references 和新增 skill 的接口文档一致

---

## 11. 最小验证流程

完成修改后，按以下步骤验证：

### 步骤 1: /config-check

```bash
/config-check
```

预期输出：
- `config/status.json` — 包含 env/codex/feishu/role_vars 四个区块
- `config/CONFIG_CHECK.md` — 包含 DeepSeek、Codex、Feishu 配置检查结果

### 步骤 2: /status

```bash
/status
```

预期输出：终端打印项目状态摘要，包含 pipeline/session/experiment/reviewer 信息。

### 步骤 3: /model-usage-status

```bash
/model-usage-status
```

预期输出：终端打印 call ledger 统计（总调用数、fallback、by backend 等）。

### 步骤 4: /paper-ingest

```bash
/paper-ingest "arxiv:2401.12345"
```

预期输出：
```
literature-md/
└── 2401.12345/
    ├── metadata.json
    ├── abstract.md
    ├── introduction.md
    ├── method.md
    ├── experiments.md
    ├── related_work.md
    ├── conclusion.md
    └── section_index.json
```

### 步骤 5: /research-contract

```bash
/research-contract "idea-stage/IDEA_CARDS/test_idea.md"
```

预期输出：
- `docs/research_contract.md` — 包含 hypothesis、success/failure signals、metrics、claim boundary
- `docs/research_contract.lock.json` — locked: true

### 步骤 6: /baseline-repro

```bash
/baseline-repro "repo" — effort: lite
```

预期输出：
- `research/BASELINE.md`
- `research/BASELINE_REPRODUCTION_REPORT.md` — verdict: not-run（mock）

### 步骤 7: /research-assurance

```bash
/research-assurance
```

预期输出：
- `research/CLAIM_EVIDENCE_TABLE.md` — 包含 claim→experiment 映射
- `research/ASSURANCE_REPORT.md` — 包含 contract/baseline/experiment/claims 四部分检查

---

## 12. 已知限制

### 12.1 Soft Gate vs 强制约束

很多约束仍然是 **skill-level soft gate**，不是编译级强制约束。

- baseline not-run 时 research-assurance 会告警，但**不会阻止**继续写论文
- contract lock 是约定，不是技术强制（lock.json 可被手动删除）
- claim boundary 写在 contract 中，依赖 human-in-the-loop 遵守

**建议：** 在团队内形成 code review 文化，互相检查是否绕过 soft gate。

### 12.2 Codex 可用性

- Codex 可用性依赖用户本地 Codex CLI / MCP 配置
- 如果 Codex 未配置，所有 Codex-priority 角色将自动 fallback 到 DeepSeek
- Fallback 不会丢失功能，但 reviewer 的推理能力会降级
- 当前环境 Codex MCP 状态为 "unknown" — 不影响基本使用

### 12.3 paper-ingest 限制

- 当前 **不自动完成** LaTeX/HTML/PDF 深度转 Markdown
- arXiv XML 元数据不包含全文 — 只获取标题、作者、摘要
- introduction/method/experiments/related_work/conclusion 当前写入**占位文本**，非完整正文
- 如需完整论文内容，由 Agent 按 paper-ingest-protocol 进一步读取 PDF/HTML，或使用外部转换工具
- 对 PDF 格式复杂的论文（多栏、嵌套表格、数学公式密集），可能只能 partial ingest
- 非英语论文支持有限

### 12.4 panel-review 依赖 Agent 执行纪律

- panel-review 的多轮对话依赖外层 Agent（Claude Code / Codex CLI）的执行纪律
- 如果 Agent 跳过轮次或忽略 reviewer 意见，panel-review 的效果会打折扣

### 12.5 不保证科研 Idea 有效

- 本增强**不保证**科研 idea 一定有效、一定有 novelty、一定能发表
- 只提高流程可靠性：确保 claim 有实验支撑、确保 experiment 有 baseline 对比、确保结果可复现
- 科研质量仍取决于研究者的判断

---

## 13. 和原 ARIS 的关系

### 13.1 不替换原 ARIS

本增强是 **ARIS 的增量补充层**，不替换原有任何组件。

```
原 ARIS:    skills/research-pipeline/SKILL.md  +  skills/idea-discovery/SKILL.md  +  ...
增强层:     tools/llm_call_ledger.py           +  skills/research-contract/SKILL.md  +  ...
           shared-references/model-routing.md  +  ...
```

### 13.2 不重构核心 Workflow

- 原有 workflow（research-pipeline → W1 → W2 → W3）**完全不变**
- 每个原有 skill 只追加了一个 "## Reliability Additions" 章节，原内容一字不改
- 不修改 `server.py` 以外的任何核心代码

### 13.3 增量接入

- 新功能可以**按需接入** — 不需要全部使用
- 如果不使用 reliability enhancement，ARIS 原有功能完全不受影响
- `/status` 会显示哪些可靠性组件已激活

### 13.4 新增文件隔离

所有新增文件放在独立路径下，不影响原 ARIS 文件结构：

```
原 ARIS:    skills/<name>/SKILL.md, tools/*.py, docs/*.md
增强新增:   tools/llm_call_ledger.py, .aris/calls/, .aris/sessions/
            skills/shared-references/env-config-policy.md, config/
```

### 13.5 兼容性

| 原 ARIS 功能 | 增强后兼容性 |
|-------------|-------------|
| `/research-pipeline` | ✅ 不受影响 |
| `/idea-discovery` | ✅ SKILL.md 追加章节，原内容不变 |
| `/research-lit` | ✅ Agentic gap extraction 已并入（GAP_MAP + LITERATURE_INDEX） |
| `/idea-creator` | ✅ Agentic dedup + canonicalization 已并入 |
| `/novelty-check` | ✅ Canonical idea 输入 + 严格 verdict 已并入 |
| `/exec-review` | ✅ Canonical idea review 规则已并入 |
| `/idea-discovery` | ✅ Agentic pipeline（lit → ideas → review → novelty → selection）已并入 |
| `/idea-bank` | ✅ 新增，Idea 银行管理 |
| `/auto-review-loop` | ✅ 同上 |
| `/novelty-check` | ✅ 同上 |
| `/experiment-audit` | ✅ 同上 |
| `/result-to-claim` | ✅ 同上 |
| `/paper-writing` | ✅ 同上 |
| `.env` 原有配置 | ✅ 不受影响 |
| `.mcp.json` | ✅ server.py 向后兼容 |
| 外部 API 调用 | ✅ 不受影响 |

---

## 14. API-first Agentic Idea Discovery

### 14.1 为什么要加这一套

旧 `/idea-discovery` 在一个长上下文中依次执行 literature survey → gap analysis → idea generation → review → novelty check。这导致：

- 主 Agent 的摘要偏差、旧判断、早期偏好持续污染后续步骤。
- 主 Agent 亲自整理 literature 和 gap，再把整理后的内容传给外部模型 — 主 Agent 的先入之见直接影响 idea 生成和审查。
- 多次 run 的 idea 直接混入一个大 `IDEA_REPORT`，无法追溯、无法独立审查。
- 没有 `no strong idea found` 作为合法输出。

### 14.2 API 调用、Skill、Agent Session 的区别

| 维度 | API Call | Skill | Agent Session |
|------|----------|-------|---------------|
| 生命周期 | 秒到分钟 | 分钟到小时 | 分钟到小时 |
| 状态 | 无状态 | 无隔离 | 独立上下文窗口 |
| 工具能力 | 无 | 由执行者决定 | 有 |
| 适合任务 | 纯思考/生成/分类 | 工作流编排 | 需要工具调用的任务 |
| 上下文污染风险 | 取决于 prompt 来源 | 取决于执行者 | 低（如果隔离） |

**核心洞察**：API 调用本身短生命周期，但如果 prompt 由主 Agent 编写且包含主 Agent 的摘要/判断，主 Agent 的偏差仍会传入 API。**输入隔离比调用方式更重要**。

### 14.3 为什么纯思考任务优先 API

- API 调用更快、更便宜、更可控。
- 不需要工具调用（搜索、读网页、执行代码）的任务，用 Agent 是过度设计。
- API 的输入输出可以严格结构化，便于审计和重放。

### 14.4 为什么 literature_scout / novelty_checker 需要 Agent

- literature_scout 需要搜索论文、判断相关性、调用 WebSearch/WebFetch 等工具。
- novelty_checker 可能需要搜索最新论文、对比已有工作。
- 这类任务无法仅通过 API 完成，需要 Agent 的工具调用能力。

### 14.5 Backend 分配

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

### 14.6 每次 Run 独立保存

每次 `/research-lit`（通过内部 agentic 模式）创建独立 run：

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

- run_id 格式：`YYYYMMDD_HHmmss_slug`。
- 原始 run 文件不覆盖、不合并。
- 上午和下午的两次 run 独立保存。

### 14.7 为什么不把多次 Run 的 Idea 直接合并

- 直接合并导致无法追溯原始 run。
- 直接合并让 reviewer 看到太多上下文，增加偏差。
- 正确的做法：dedup → canonicalization → 独立 review。

### 14.8 IDEA_BANK 和 CANONICAL_IDEAS 怎么用

**IDEA_BANK**：全局索引，只存状态，不存完整内容。字段包括 candidate_id、title、source_runs、status、latest_verdict、novelty_status、next_action。

**CANONICAL_IDEAS**：去重后的干净候选。每个 candidate 一个独立文件。reviewer / novelty checker / adversarial reviewer **只读单个 canonical idea**。

Reviewer prompt **禁止包含**：其他 candidate 的内容、generator 推理过程、旧分数、旧 praise、用户偏好。

### 14.9 No Strong Idea Found

以下情况输出 `no strong idea found`：

- 所有 idea 在 review 阶段被 kill。
- Dedup 发现所有 idea 都是已有工作的微小变体。
- Novelty checker 确认所有剩余 idea 都 `already_done`。
- Adversarial reviewer 发现所有剩余 idea 都有致命缺陷。

这不是失败 — 是合法输出。系统建议用户探索不同方向。

### 14.10 推荐用法

ARIS 是 slash-skill 系统。用户通过原 ARIS 命令操作。

**完整流程：**
```
/idea-discovery "方向"
```

**分步流程：**
```
/research-lit "方向"
/idea-creator latest
/exec-review CANONICAL_IDEAS/CAND_001.md
/novelty-check CAND_001
/idea-bank status
```

**管理 idea bank：**
```
/idea-bank status         # 查看所有 candidate 状态
/idea-bank dedup          # 重新去重
/idea-bank CAND_001       # 查看某个 candidate 的完整审查链
```

**重要说明：**
- 默认只做前期创新点发现，输出 IDEA_SELECTION_REPORT 或 `no strong idea found`。
- 默认不进入实验、不写论文、不自动跑 pilot experiment。
- 如果没有强 idea，输出 `no strong idea found`，停止。
- 只有用户明确决定继续时，才调用 `/research-contract`、`/baseline-repro`、`/experiment-bridge`。
- `/idea-bank` 是唯一新增用户入口。原 ARIS 命令不变。

### 14.11 技能速查

| 命令 | 作用 | 底层调用 |
|------|------|----------|
| `/research-lit "方向"` | 文献搜索 + gap 提取 | agentic_idea_discovery.py + isolated_job_runner.py |
| `/idea-creator "方向"` | Idea 生成 + 去重 canonical | isolated_job_runner.py |
| `/novelty-check "CAND_001"` | 对 canonical idea 查新 | isolated_job_runner.py |
| `/exec-review "CAND_001"` | 独立审查 canonical idea | isolated_job_runner.py |
| `/idea-discovery "方向"` | 全流程一键执行 | 依次调用以上 skill |
| `/idea-bank status` | 查看/管理 idea bank | 直接读取 artifact 文件 |

**内部工具（skill 作者/贡献者用，普通用户不需要）：**
Python 辅助工具（`tools/agentic_idea_discovery.py`、`tools/isolated_job_runner.py` 等）用于脚本化 job 编排、llm call ledger 记录、输出校验。正常用户应使用 slash skill，不直接调用 Python 工具。

### 14.12 输出校验规则

| 角色 | 校验要求 |
|------|----------|
| gap_extractor | 输出包含 `GAP_` 或 `Gap statement` + `Confidence:` |
| idea_generator | 至少 3 个 idea card；未分拆到多个文件则标记 needs_review |
| idea_reviewer | `verdict:` 必须是 go / revise / kill |
| novelty_checker | 必须是 confirmed_novel / likely_incremental / already_done / insufficient_evidence |
| adversarial_reviewer | 包含 weakness / fatal flaw / reviewer objection |

- API 成功但校验失败 → handoff status = `needs_review`，不能进入下一阶段。

比旧 `/idea-discovery` 更适合严肃找创新点的场景，因为它：

1. 分离各步骤，减少上下文污染。
2. 每次 run 独立保存，支持多轮探索。
3. 通过 IDEA_BANK 和 CANONICAL_IDEAS 归并，不混成大文件。
4. 允许 `no strong idea found`。
5. main_architect 只读 artifacts，不亲自想 idea。

旧 `/idea-discovery` 保留，如果用户需要快速探索或已习惯旧流程，可以继续使用。

# 可信科研自动化系统目标设计文档

> 版本：v1.1
> 定位：Agent 驱动的可信科研自动化系统目标蓝图
> 用途：作为后续系统设计、项目改造、功能裁剪、阶段验收的统一依据
> v1.1 变更：新增执行摘要、先轻量后丰富原则、自适应文献发现策略、reading card 方法、不足来源处理、非单测试用例绑定、复杂度预算

---

## 1. 系统定位

本系统是一个面向科研自动化的 Agent 工作流系统。

它不是传统 Web 系统，也不是普通聊天助手，更不是单纯代码生成器。

它的核心使用方式是：

```
用户
→ 外部 Agent
→ 调用科研命令 / Skill / 工具
→ 生成阶段产物
→ 验证通过
→ 进入下一阶段
```

系统目标是辅助完成从研究想法到实验计划、实验实现、结果判断、论文写作的科研流程。

完整理想流程包括：

```
用户输入研究方向
→ 保存用户原始输入
→ 整理研究 brief / candidate idea
→ 候选想法生成
→ 文献搜索与材料获取
→ 研究边界锁定
→ 新颖性检查
→ 实验计划设计
→ 实现计划设计
→ 代码实现与审查
→ 实验运行
→ 结果判断
→ 论文写作
→ 状态追踪与迭代
```

系统最终目标：

> «保留 ARIS 类系统的 Skill 研究能力、原生命令体验和多阶段科研流程，同时加入更严格的上下文隔离、可信模型调用、阶段验证、可信输出和状态追踪机制。»

**一句话：**

借鉴 ARIS 的研究智慧和命令体验；
重建更可靠、更可控、更可追踪的科研自动化内核。

### 1.1 执行摘要（v1.1 新增）

本系统是 **受 ARIS 启发的可信科研自动化系统**，核心产品目标是：**用户一条命令启动任意研究想法的自动化科研流程**。

当前系统状态（v1.1）：

| 能力 | 状态 |
|------|------|
| 一键启动 CLI（status/validate/repair-queue/start dry-run） | 已实现 |
| 多源文献搜索（arXiv + OpenAlex + Crossref） | 已实现 |
| 全文获取 MVP（open-access arXiv/PDF/HTML） | 已实现 |
| 全文可信审阅（full_text_review） | 已实现 |
| 可信模型调用 + ledger + validator | 已实现 |
| 上下文隔离 + forbidden context | 已实现 |
| Stage output contract + role boundary | 已实现 |
| 一键 live start（不需要 --dry-run） | 待实现 |
| 端到端完整流程（raw_user_input → experiment_plan） | 待实现（当前 test case 被 paywall 阻塞） |

**关键约束：**

1. **hallucination trajectory（幻觉轨迹检测）只是回归测试用例，不是产品。** 系统产品是通用可信科研自动化。
2. **先轻量后丰富。** MVP 只保留核心流程，不追求功能完整。
3. **自适应文献发现。** 先 metadata 后全文，先广后深，按 topic 类型调整搜索范围。
4. **Reading card 够用，不上数据库。** 50 篇 paper 的 reading card 用 grep 搜索即可。
5. **复杂度有预算。** 36 个 Python 文件目标裁剪到 ~16 个活跃文件。

---

## 2. 与 ARIS 的关系

本系统不是完全照抄 ARIS，也不是完全抛弃 ARIS。

正确定位是：

> ARIS-inspired trusted research automation system
> 受 ARIS 启发的可信科研自动化系统

### 2.1 应借鉴 ARIS 的内容

应借鉴：

1. 原生命令体验；
2. Markdown Skill 体系；
3. 研究流程阶段化；
4. idea-discovery 思路；
5. novelty-check 思路；
6. experiment-bridge 思路；
7. paper-writing 思路；
8. auto-review-loop 思路；
9. 多角色协作；
10. 多模型分工；
11. effort level，即按任务重要性调整思考深度；
12. Skill 可组合的工作流体验。

### 2.2 不应照搬的问题

不应照搬：

1. 外部 Agent 自己组织最终 prompt；
2. Skill 自由产出可信结论；
3. 模型调用缺少强证据；
4. 阶段之间没有强制验证；
5. 上下文容易混入旧结论、旧实验、用户偏好；
6. 搜索结果直接变成结论；
7. 文献没读完就强行判断新颖；
8. 旧流程越叠越臃肿；
9. 失败后靠 Agent 自己补结果；
10. 没有 trusted output 文件作为阶段交接。

---

## 3. 总设计原则

| 原则 | 说明 |
|------|------|
| 原生命令保持简单 | 用户通过 "/idea-discovery"、"/novelty-check" 等命令使用系统 |
| 系统由 Agent 驱动 | 不优先设计复杂 Web UI 或后台面板 |
| Skill 不退场 | Skill 保留研究方法、判断标准、创新策略 |
| Workflow 负责纪律 | Workflow 管阶段、输入、上下文和 prompt 组装 |
| 外部 Agent 只调度 | 外部 Agent 不能自己写可信结论，不能冒充模型 |
| 输入必须受控 | 每阶段只能读取 allowed input |
| 上下文必须隔离 | 旧结论、用户偏好、未验证结果不能随便进入当前任务 |
| 模型调用必须可信 | 配置哪个模型，就必须真实调用哪个模型 |
| 调用必须有记录 | 每次关键模型调用都要写 ledger |
| 结果必须可验证 | Validator 不通过不能进入下一阶段 |
| 每阶段必须有输出文件 | 不靠聊天记忆和口头总结交接 |
| 文献搜索必须可追踪 | 搜索结果、文献来源、获取时间、阅读内容都要保存 |
| 失败必须停止 | 不允许失败后伪装成功继续推进 |
| 关键节点允许人工确认 | 防止系统自动把错误越滚越大 |
| 支持完整目标和 MVP 裁剪 | 先有完整蓝图，再按阶段实现 |
| 先轻量后丰富（v1.1） | MVP 只保留核心流程；broad scan、literature memory、citation graph 等丰富功能在核心流程跑通后再加 |
| 不绑定单一测试用例（v1.1） | hallucination trajectory 是回归测试，不是产品；系统必须能处理任意研究想法 |
| 复杂度有预算（v1.1） | 活跃文件数目标 ~16；超过则先裁剪再加新功能 |

---

## 4. 系统总体架构

系统采用四层主架构，加一个可信输出层。

- 第一层：Native Command Layer（原生命令层）
- 第二层：Skill Method Layer（Skill 研究方法层）
- 第三层：Workflow Discipline Layer（Workflow 执行纪律层）
- 第四层：Trusted Execution Layer（可信执行层）
- 第五层：Trusted Output Layer（可信输出层）

整体流程：

```
用户原生命令
→ Skill 提供研究方法
→ Literature Layer 获取文献材料
→ Workflow 控制输入和上下文
→ Workflow 组装受控 prompt
→ Context Isolation Check 检查污染
→ Trusted Runner 调用配置模型
→ Ledger 记录调用证据
→ Validator 验证可信性
→ Trusted Output 保存阶段结果
→ 下一阶段读取 trusted output
```

---

## 5. 第一层：Native Command Layer（原生命令层）

### 5.1 定义

原生命令层是用户和系统交互的入口。

用户通过简单命令发起科研任务，而不是手动执行底层脚本。

推荐命令：

```
/idea-discovery "我想找一个大模型可靠性方向的研究题目"
/research-contract "把当前候选想法锁定成研究边界"
/novelty-check "检查这个想法有没有新意"
/experiment-plan "为这个想法设计实验"
/implementation-plan "为实验写代码前做实现规划"
/experiment-bridge "根据实验计划准备实现和运行"
/result-judge "判断实验结果是否支持研究 claim"
/paper-writing "根据可信结果写论文"
/status
```

### 5.2 第一层职责

| 职责 | 说明 |
|------|------|
| 接收用户命令 | 保留原生命令体验 |
| 识别任务阶段 | 判断用户要进入哪个研究阶段 |
| 保存用户原始输入 | 用户原文应作为一手材料保存 |
| 转交后续流程 | 把任务交给 Skill / Workflow |

### 5.3 第一层禁止事项

第一层不应：

1. 组织最终 prompt；
2. 选择模型；
3. 直接调用模型；
4. 直接写可信结论；
5. 读取大量旧聊天上下文；
6. 决定是否进入下一阶段。

### 5.4 第一层目标

用户体验简单；
底层复杂性隐藏；
命令入口稳定；
不让用户被迫输入底层脚本。

---

## 6. 第二层：Skill Method Layer（Skill 研究方法层）

### 6.1 定义

Skill 研究方法层负责"怎么思考"。

它保留 ARIS 最有价值的部分：

1. 研究方法；
2. 创新策略；
3. 判断标准；
4. 文献策略；
5. 联网搜索策略；
6. 输出标准；
7. 失败标准；
8. 论文 claim 边界。

Skill 是研究方法说明书，不是执行器。

### 6.2 Skill 应保留的能力

#### idea-discovery

应保留：

1. 研究方向拆解；
2. gap finding，即研究空白发现；
3. candidate idea generation，即候选想法生成；
4. cross-domain analogy，即跨领域类比；
5. adversarial review，即反方审查；
6. feasibility filter，即可行性筛选；
7. novelty pre-check，即初步新颖性预判；
8. final selection，即候选筛选；
9. 低价值套壳 idea 识别；
10. 不同 effort level 的探索深度。

#### research-contract

应保留：

1. research question；
2. hypothesis；
3. allowed data；
4. forbidden data；
5. metrics；
6. baselines；
7. success criteria；
8. failure criteria；
9. leakage risks；
10. claim boundary；
11. 不允许声称的内容；
12. 后续实验不得随意改变的约束。

#### novelty-check

应保留：

1. closest prior work；
2. method overlap；
3. task overlap；
4. benchmark overlap；
5. real delta；
6. novelty boundary；
7. evidence gap；
8. reviewer attack point；
9. verdict 类型：
   - confirmed_novel；
   - likely_incremental；
   - already_done；
   - insufficient_evidence。

#### experiment-plan

应保留：

1. dataset selection；
2. baseline selection；
3. metric selection；
4. train / validation / test split；
5. ablation plan；
6. leakage check；
7. resource estimate；
8. success criteria；
9. failure criteria；
10. result interpretation plan。

#### implementation-plan

应保留：

1. 文件结构规划；
2. 模块职责；
3. 配置方案；
4. 测试方案；
5. 回滚方案；
6. 代码审查标准；
7. 运行入口；
8. 日志和输出格式。

#### experiment-bridge

应保留：

1. 实现前 gate；
2. sanity check；
3. code review；
4. experiment queue；
5. result collection；
6. reproducibility log；
7. 错误处理；
8. 运行结果归档。

#### result-judge

应保留：

1. 是否达到 success criteria；
2. 是否触发 failure criteria；
3. 是否支持 claim；
4. 是否需要补实验；
5. 是否存在指标误读；
6. 是否存在泄漏；
7. 是否过拟合；
8. 是否需要降低论文 claim。

#### paper-writing

应保留：

1. paper outline；
2. contribution framing；
3. related work；
4. method；
5. experiments；
6. limitations；
7. claim boundary；
8. citation discipline；
9. 不夸大结果；
10. 不隐瞒失败。

#### status

应保留：

1. 当前阶段；
2. 阶段完成状态；
3. trusted output 状态；
4. ledger 状态；
5. validate 状态；
6. blocked 原因；
7. 下一步建议；
8. 是否需要用户介入。

### 6.3 Skill 禁止事项

Skill 不应该：

1. 自己拼最终 prompt；
2. 自己读取旧上下文；
3. 自己整理用户输入并加入判断；
4. 自己选择模型；
5. 自己调用模型；
6. 自己写可信结论；
7. 自己决定 allowed_next_stage；
8. 绕过 Workflow；
9. 绕过 Trusted Runner；
10. 绕过 Validator；
11. 直接把搜索结果当结论；
12. 直接把文献摘要当最终判断。

### 6.4 Skill 定位

Skill 做研究方法；
Workflow 做执行纪律；
模型做具体思考；
Validator 做可信验证。

**一句话：**

Skill 是研究方法老师，不是答题人、执行人或文件整理员。

---

## 7. 用户输入处理设计

### 7.1 基本原则

用户原始输入是第一手材料。

外部 Agent 不应自由改写、总结、评价用户输入。

### 7.2 推荐输入文件

```
research/current/raw_user_input.md
research/current/brief.md
research/current/candidate_idea.md
```

### 7.3 raw_user_input

`raw_user_input.md` 保存用户原文。

要求：

1. 尽量原样保存；
2. 不加入外部 Agent 判断；
3. 不加入旧上下文；
4. 不加入"这个方向很有潜力"等评价；
5. 不总结成新含义；
6. 可以保留时间戳和来源。

### 7.4 input_normalizer

如果需要把用户原文整理成 `brief.md` 和 `candidate_idea.md`，应由受控内部 role 完成。

建议 role：

```
input_normalizer
```

职责：

1. 从 raw_user_input 中提取研究问题；
2. 提取候选想法；
3. 提取用户明确给出的约束；
4. 把不明确内容标记为 unknown；
5. 不评价想法好坏；
6. 不判断新颖性；
7. 不补充外部知识；
8. 尽量标注来源原句。

输出：

```
research/current/brief.md
research/current/candidate_idea.md
```

要求：

1. 必须走 trusted runner；
2. 必须有 ledger；
3. 必须 validate PASS；
4. 结果才可进入后续阶段。

---

## 8. Literature Search & Acquisition Layer（文献搜索与全文获取层）

### 8.1 模块定位

文献搜索与全文获取系统是科研自动化系统的重要组成部分。

它解决五个问题：

| 问题 | 含义 |
|------|------|
| 搜得到 | 找到相关论文、相似工作、最新工作 |
| 拿得到 | 尽量获取 PDF、HTML、Markdown 或其他全文材料 |
| 看得懂 | 把文献转成模型可读的章节文本 |
| 可追踪 | 每篇论文有来源、URL、DOI、检索时间、获取方式 |
| 不污染 | 搜索结果不能直接变成可信结论 |

本模块不是简单联网搜索，也不是为了绕过付费墙。

它的目标是：

尽量找到关键论文；
尽量获取可读全文；
无法自动获取时进入人工补全文队列；
所有材料文件化、可追踪、可进入 Workflow。

### 8.2 搜索和全文获取的区别

必须区分：

| 概念 | 含义 |
|------|------|
| 搜到论文 | 找到标题、作者、摘要、DOI、引用、链接等元数据 |
| 拿到全文 | 获取 PDF、HTML、Markdown、LaTeX 或正文文本 |

系统不能假设"搜到论文"就等于"拿到全文"。

### 8.3 推荐信息源

系统应支持多源搜索，而不是只依赖一个网站。

推荐信息源包括：

1. arXiv；
2. Semantic Scholar；
3. OpenAlex；
4. Crossref；
5. Unpaywall；
6. OpenReview；
7. 会议官网；
8. 作者主页；
9. GitHub 项目页面；
10. 用户手动补充 PDF；
11. Google / Google Scholar 作为人工辅助搜索来源。

系统不应把 Google Scholar 自动抓取作为默认主链路。

### 8.4 文献搜索主流程

文献搜索与获取分为七步：

```
Query Planning
→ Multi-source Search
→ Dedup & Ranking
→ Full-text Acquisition
→ Paper Parsing
→ Literature Material Store
→ Trusted Reading / Novelty Judgement
```

### 8.5 Query Planning（检索规划）

不要直接拿用户一句话搜索。

系统应先生成检索规划。

示例：

```yaml
topic: "hidden state trajectory hallucination detection"
search_intent: novelty_check
must_include:
  - hallucination detection
  - hidden states
  - representation trajectory
  - token-level detection
exclude:
  - unrelated generic anomaly detection
sources:
  - arxiv
  - semantic_scholar
  - openalex
  - crossref
time_range:
  start_year: 2020
  end_year: 2026
max_results_per_source: 50
```

要求：

1. query plan 必须保存为文件；
2. query plan 只负责检索方向；
3. query plan 不负责新颖性判断；
4. 如果 query plan 由模型生成，必须走可信模型调用；
5. 外部 Agent 不能自由编写检索结论。

建议输出：

```
literature/search_runs/<run_id>/search_plan.yaml
```

### 8.6 Multi-source Search（多源搜索）

系统应从多个来源搜索论文。

每条原始结果保存到：

```
literature/search_runs/<run_id>/raw_results.jsonl
```

字段示例：

```json
{
  "source": "semantic_scholar",
  "title": "...",
  "authors": ["..."],
  "year": 2025,
  "abstract": "...",
  "url": "...",
  "doi": "...",
  "arxiv_id": "...",
  "semantic_scholar_id": "...",
  "openalex_id": "...",
  "pdf_url": "...",
  "venue": "...",
  "retrieved_at": "2026-05-12T00:00:00Z"
}
```

要求：

1. 所有搜索结果必须保存；
2. 搜索结果不能直接作为可信结论；
3. 搜索结果必须经过去重、排序、筛选；
4. 搜索过程必须可复现；
5. 搜索时要记录 query、source、time、result count。

### 8.7 Dedup & Ranking（去重与排序）

去重依据：

1. DOI；
2. arXiv ID；
3. Semantic Scholar paperId；
4. OpenAlex ID；
5. normalized title。

排序依据：

| 排序因素 | 说明 |
|----------|------|
| 主题相关性 | 标题、摘要、关键词是否匹配 |
| 新近程度 | 越新的论文越可能影响 novelty |
| 引用关系 | 是否引用关键论文或被关键论文引用 |
| 全文可用性 | 是否能获取 PDF / HTML |
| 相似度 | 是否可能是 closest prior work |
| venue 质量 | 是否来自重要会议/期刊 |
| 方法重叠 | 是否与候选想法方法类似 |
| 任务重叠 | 是否解决相同或相近任务 |

输出：

```
literature/search_runs/<run_id>/candidates.jsonl
literature/search_runs/<run_id>/top_k.md
```

### 8.8 Full-text Acquisition（全文获取）

全文获取按优先级执行：

1. arXiv PDF / arXiv HTML / ar5iv HTML
2. Semantic Scholar 提供的 PDF URL
3. OpenAlex open access location
4. Unpaywall OA PDF
5. OpenReview
6. 会议官网
7. 作者主页
8. GitHub 项目页面
9. 用户手动补 PDF

如果拿不到全文，不应硬爬付费墙。

应写入：

```
literature/manual_acquisition_queue.md
```

示例：

```markdown
# Manual Acquisition Queue

## Paper
- Title: ...
- DOI: ...
- Publisher: ACM
- URL: ...
- Why needed: likely closest prior work
- Suggested action:
  - check institutional access
  - search author homepage
  - search arXiv / OpenReview
  - manually place PDF under literature/manual_pdf_drop/
```

### 8.9 Paper Parsing（论文解析）

全文拿到后，应解析为模型可读的章节文本。

推荐目录：

```
literature/papers/<paper_id>/
  metadata.json
  source.pdf
  source.html
  abstract.md
  introduction.md
  related_work.md
  method.md
  experiments.md
  conclusion.md
  references.md
  full_text.md
```

要求：

1. 不直接让模型读未解析 PDF；
2. 优先给模型读取章节文本；
3. 章节提取失败时，至少保留 full_text.md；
4. 解析质量低时，标记 parse_quality=low；
5. 每篇论文必须保留 metadata；
6. 解析后的文本必须能进入 allowed_input_files。

### 8.10 Literature Material Store（文献材料库）

系统应维护本地文献材料库。

建议结构：

```
literature/
  search_runs/
    <run_id>/
      search_plan.yaml
      raw_results.jsonl
      candidates.jsonl
      top_k.md
  papers/
    <paper_id>/
      metadata.json
      abstract.md
      introduction.md
      related_work.md
      method.md
      experiments.md
      conclusion.md
      references.md
      full_text.md
  manual_pdf_drop/
  manual_acquisition_queue.md
  cache/
```

缓存要求：

1. 同一 query 不重复搜索；
2. 同一 DOI 不重复请求；
3. 同一 PDF 不重复下载；
4. 同一论文不重复解析；
5. 每条缓存记录保留 retrieved_at；
6. 允许手动 refresh。

### 8.11 Trusted Reading / Novelty Judgement（可信阅读与查新判断）

文献搜索结果不能直接成为可信结论。

正确流程：

```
搜索结果
→ 保存成文件
→ 进入 allowed_input_files
→ Workflow 组装 prompt
→ Trusted Runner 调用模型阅读判断
→ Validator 验证
→ 输出 trusted novelty_check
```

例如 novelty-check 阶段允许输入：

```yaml
allowed_input_files:
  - research/current/candidate_idea.md
  - research/current/trusted_outputs/research_contract.md
  - literature/search_runs/<run_id>/top_k.md
  - literature/papers/<paper_id>/method.md
  - literature/papers/<paper_id>/related_work.md
```

### 8.12 付费墙论文处理原则

对于 ACM / IEEE / Springer / Elsevier 等付费墙论文，系统应：

1. 先查开放版本；
2. 查预印本；
3. 查作者主页；
4. 查会议主页；
5. 查开放获取位置；
6. 若仍无法获取，进入 manual_acquisition_queue；
7. 用户通过合法渠道手动补充 PDF；
8. 系统解析后再进入后续流程。

系统不应默认自动绕过付费墙。

如果论文可能是 closest prior work，但无全文，novelty-check 不能直接给 confirmed_novel，应标记：

> insufficient_evidence

或要求补全文。

### 8.13 Google / Google Scholar 策略

Google 和 Google Scholar 可作为人工辅助搜索来源，但不作为默认自动化主链路。

原因：

1. 结果不稳定；
2. 容易验证码；
3. 可复现性差；
4. 自动抓取风险高；
5. 代理依赖强；
6. 不适合作为长期稳定系统核心。

系统可以输出人工搜索建议：

```
Suggested manual search queries:
- "hidden state trajectory hallucination detection"
- "LLM hallucination hidden representations token-level"
```

人工搜索得到的结果必须保存成文件，才能进入 Workflow。

### 8.14 登录 session 策略

不建议使用随机登录 session 或自动登录下载作为主方案。

原因：

1. 不稳定；
2. 难复现；
3. 账号权限不一致；
4. cookie 管理复杂；
5. 容易触发验证码；
6. 不适合科研自动化系统长期维护。

推荐替代方案：

```
无法获取全文
→ manual_acquisition_queue
→ 用户合法渠道下载
→ 放入 manual_pdf_drop
→ 系统解析
```

### 8.15 阶段搜索权限

| 阶段 | 是否搜索 | 搜索深度 | 全文要求 |
|------|----------|----------|----------|
| idea-discovery | 可以 | 广泛搜索 | 可只读标题/摘要 |
| research-contract | 少量 | 只补关键事实 | 通常不需要全文 |
| novelty-check | 必须 | 深度查新 | 关键 prior work 要读 method / related_work |
| experiment-plan | 有限 | 查 protocol / baseline / metric | 重点论文可读 experiments |
| implementation-plan | 技术搜索 | 查官方文档 / API | 不搜新论文 |
| experiment-bridge | 默认不搜新论文 | 查技术报错 | 不需要论文全文 |
| result-judge | 默认不搜 | 避免事后改标准 | 不新增论文 |
| paper-writing | 受控搜索 | 补引用和 related work | 只用已确认文献 |

### 8.16 查新阶段特殊要求

novelty-check 是最依赖文献搜索的阶段。

必须满足：

1. 必须进行多源搜索；
2. 必须找 closest prior work；
3. 不能只看标题判断；
4. 不能只看摘要就 confirmed_novel；
5. 关键 prior work 无全文时，应标记 evidence gap；
6. 无法排除已有工作时，应输出 insufficient_evidence；
7. 搜索过程和阅读材料必须保存；
8. 最终 novelty verdict 必须来自可信模型调用。

### 8.17 自适应文献发现策略（v1.1 新增）

文献搜索不应一刀切。不同 topic 的文献量差异巨大，搜索范围应自适应调整。

#### 核心原则：先 metadata，后全文；先广后深

| Pass | 内容 | 模型调用 | 目的 |
|------|------|---------|------|
| Pass 1 | metadata only（title + abstract + year + venue + citation_count + DOI） | 不调用 | 广泛覆盖，deterministic scoring |
| Pass 2 | top 10-25 的全文 acquisition + trusted review | 调用 full_text_reviewer | 深度验证 closest prior work |

#### Adaptive Sizing

| Topic 类型 | 特征 | 建议搜索范围 | 理由 |
|-----------|------|-------------|------|
| 小众方向 | 新领域、交叉学科、few papers | 30-80 篇 | 超过 80 篇大概率是噪音 |
| 普通方向 | 有明确 baseline 和竞争工作 | 80-200 篇 | 覆盖主要会议 + workshop |
| 大方向 | 热门领域（如 LLM、diffusion） | 先聚类，不全读 | 200+ 篇不可能全读，必须 cluster → sample → deep review |

Adaptive sizing 实现方式：
1. 首次搜索返回 N 篇（N 由 topic 特征决定）
2. 如果 N < 30：`low_literature_yield`，不硬凑
3. 如果 30 ≤ N ≤ 200：正常流程
4. 如果 N > 200：先 cluster（按 venue + year + keywords），每个 cluster 选 top 3-5，总 deep review 不超过 25 篇

#### Stop Rules

| Rule | 触发条件 | 动作 |
|------|---------|------|
| Relevance decay | 连续 3 篇 relevance score < 0.3 | 停止搜索 |
| Duplicate saturation | 连续 10 篇都是已见过的 closest prior work | 停止搜索 |
| Cluster saturation | 新 cluster 数量在最近 10 篇中为 0 | 停止搜索 |
| No new method family | 连续 5 篇属于同一个 method family | 停止搜索 |
| Time budget | 搜索时间超过 5 分钟 | 停止搜索，记录 partial results |

#### Broad scan 只读 metadata，不默认全文读

- Pass 1：metadata only（title, abstract, year, venue, citation_count, DOI）
- Scoring：deterministic（keyword match + recency + citation count + venue tier）
- 不调用模型
- 不做全文 acquisition
- 只选 top 10-25 进入 Pass 2

#### Deep review 只选 top 10-25

- 全文 acquisition（arXiv source > PDF > open HTML）
- Trusted review（full_text_reviewer）
- 这是现有的 Phase 21 flow，不需要新基础设施

#### MVP 阶段 broad scan 策略

**MVP 不实现自动化 broad scan。** 原因：
1. 当前 MVP 还没跑通一次完整流程
2. broad scan 是优化，不是基础能力
3. 先让核心流程跑通，再考虑扩大搜索范围

当前 multi-source pipeline（arXiv + OpenAlex + Crossref）已足够做 novelty risk assessment。broad scan 作为 Phase 22+ 的增强功能。

### 8.18 Reading Card 方法（v1.1 新增）

#### 问题：是否需要 literature memory？

对于 MVP，**不需要复杂的 literature memory 系统**（数据库、向量库、知识图谱）。

原因：
1. 10-50 篇 paper 的 metadata 很小（< 100KB），每次重新读的 token 成本可忽略
2. 真正烧 token 的是模型调用（trusted review），不是读 metadata
3. 50 篇 paper 的 reading card 用 grep 搜索即可
4. 数据库/向量库的维护成本（schema migration、index maintenance、cache invalidation）远超收益

#### Reading Card Schema

每篇 paper 一个 reading card（.md 文件）：

```markdown
---
paper_id: ftq_006
title: "ICR Probe: ..."
authors: ["Author A", "Author B"]
year: 2025
relevance_to_idea: 0.85
closeness_to_our_method: high
key_finding: "Uses internal classifier for hallucination detection"
gap_we_address: "No trajectory-based approach"
review_date: 2026-05-14
reviewer: full_text_reviewer
---

## Summary
One paragraph summary of the paper.

## Method
Brief method description.

## Overlap with Our Idea
What overlaps and what doesn't.

## Evidence for Novelty Check
Supports or contradicts novelty claim.
```

#### 目录结构

```
literature/
  reading_cards/
    ftq_001.md
    ftq_002.md
    ...
  evidence_maps/
    current_idea.md    # 当前 idea 的 evidence map
```

#### 什么时候才值得实现更复杂的系统？

当以下条件**同时**满足时：
1. 系统已经跑通完整流程（experiment_plan → paper_writing）
2. 同一个 topic 需要跨 3+ 次 session 重复搜索
3. Paper 数量超过 100 篇，grep 开始变慢
4. 有明确的 "我上次读过这篇" 的需求

目前这些条件都不满足。

### 8.19 来源不足处理（v1.1 新增）

当文献搜索结果不足以支撑 strong novelty claim 时，系统应：

#### 判断标准

| 情况 | 处理 |
|------|------|
| 搜索结果 < 30 篇 | `low_literature_yield`，建议用户补充搜索方向 |
| closest prior work 无全文 | 标记 `evidence_gap`，不给 `confirmed_novel` |
| 关键竞争工作在付费墙后 | 标记 `paywall_blocked`，建议用户通过合法渠道获取 |
| 搜索结果全是高相关 | 不硬凑 `confirmed_novel`，输出 `likely_incremental` 或 `insufficient_evidence` |

#### 系统不应做的事

1. 不应为了凑数而降低 relevance threshold
2. 不应把低相关论文强行纳入 closest prior work
3. 不应绕过付费墙获取全文
4. 不应在 evidence 不足时强行给出 novelty verdict

#### 系统应做的事

1. 如实报告搜索覆盖范围和不足
2. 建议用户补充搜索方向或手动获取关键论文
3. 将不足来源记录到 repair queue
4. 在 novelty check 中明确标注 evidence gap

---

## 9. 第三层：Workflow Discipline Layer（Workflow 执行纪律层）

### 9.1 定义

Workflow 层负责把研究任务变成受控执行流程。

它做的是：

```
阶段控制
输入控制
上下文控制
prompt 组装
污染检查
```

它不做创新判断。

### 9.2 核心职责

| 职责 | 说明 |
|------|------|
| stage control | 确定当前阶段 |
| input control | 确定 allowed input |
| context boundary | 确定 forbidden context |
| prompt compile | 组装最终 prompt |
| manifest | 生成 context manifest |
| scan | 执行 context isolation check |
| stop on failure | 检查失败则停止 |

### 9.3 context_manifest

每次调用模型前应生成 context manifest。

示例：

```yaml
stage: novelty_check
role: novelty_checker
allowed_input_files:
  - research/current/candidate_idea.md
  - research/current/trusted_outputs/research_contract.md
  - literature/search_runs/<run_id>/top_k.md
  - literature/papers/<paper_id>/method.md
  - literature/papers/<paper_id>/related_work.md
forbidden_context:
  - old conclusions
  - unverified experiment results
  - user preference
  - other candidates
  - external_agent_direct output
  - mock/dry-run artifact
context_hash: xxx
contamination_scan_status: checked
```

### 9.4 prompt_file

最终 prompt 由 Workflow 生成。

包含：

1. 当前任务；
2. Skill 方法规则；
3. allowed input 内容；
4. 输出格式；
5. 禁止事项。

不得包含：

1. 外部 Agent 主观判断；
2. 旧聊天结论；
3. 用户偏好暗示；
4. 未验证实验结果；
5. 其他候选想法；
6. mock / dry-run 产物。

### 9.5 context isolation check

上下文检查应至少包括：

1. manifest 是否存在；
2. prompt 是否存在；
3. allowed input 是否存在；
4. prompt 是否引用未允许文件；
5. prompt 是否包含 forbidden markers；
6. context hash 是否生成；
7. 检查结果是否为 PASS。

---

## 10. 第四层：Trusted Execution Layer（可信执行层）

### 10.1 定义

可信执行层负责真实调用配置好的模型，并证明这次调用可信。

它回答：

```
谁执行？
实际用了哪个模型？
有没有记录？
能不能进入下一阶段？
```

### 10.2 组成

| 组件 | 作用 |
|------|------|
| model route | 解析 role 应调用哪个模型 |
| trusted runner | 真实调用模型 |
| ledger | 记录调用证据 |
| validator | 验证可信性 |
| backend adapter | 对接 Codex / DeepSeek / MiniMax / OpenAI |

### 10.3 模型路由

每个 role 应配置模型。

示例：

| role | 推荐模型类型 |
|------|-------------|
| input_normalizer | DeepSeek Pro / Flash |
| idea_generator | DeepSeek Pro / Codex |
| idea_reviewer | Codex |
| novelty_checker | Codex |
| contract_reviewer | Codex |
| experiment_auditor | Codex / DeepSeek Pro |
| experiment_implementer | DeepSeek Pro |
| experiment_code_reviewer | Codex |
| result_judge | Codex |
| paper_writer | DeepSeek Pro |
| final_paper_auditor | Codex |
| log_summarizer | DeepSeek Flash / MiniMax |

### 10.4 ledger 必须记录

```
role
expected_backend
expected_model
actual_backend
actual_model
call_id
codex_thread_id
fallback_used
fallback_reason
implementation_source
context_hash
contamination_scan_status
verification_status
allowed_next_stage
```

### 10.5 Validator 必须检查

1. ledger 是否存在；
2. actual_backend 是否存在；
3. actual_model 是否存在；
4. 是否符合 role 配置；
5. Codex 是否有 threadId；
6. fallback 是否有 reason；
7. context 是否通过检查；
8. verification_status 是否可信；
9. allowed_next_stage 是否为 true。

### 10.6 API 模型

DeepSeek / MiniMax / OpenAI API 通常只能看到传入 prompt。

因此主要风险不是 API 自己读文件，而是 prompt 在调用前被污染。

所以必须确保：

```
prompt 由 Workflow 生成
prompt 通过 context isolation check
调用由 trusted runner 完成
结果由 validator 验证
```

### 10.7 Codex MCP

Codex MCP 必须有真实 threadId。

流程：

```
prepare
→ 外部 MCP 调用
→ 获取 codex_thread_id
→ complete
→ validate
```

没有 threadId，不得声称 Codex 完成任务。

---

## 11. Trusted Output Layer（可信输出层）

### 11.1 定义

每个阶段都应产生可信输出文件。

可信输出是下一阶段的正式输入。

不能依赖：

1. 聊天记忆；
2. 外部 Agent 口头总结；
3. 临时文本；
4. 未验证结果。

### 11.2 输出目录

建议：

```
research/current/trusted_outputs/
```

### 11.3 阶段输出

| 阶段 | 输出 |
|------|------|
| input_normalizer | brief.md / candidate_idea.md |
| idea-discovery | candidate_ideas.md |
| research-contract | research_contract.md |
| novelty-check | novelty_check.md |
| experiment-plan | experiment_plan.md |
| implementation-plan | implementation_plan.md |
| experiment-bridge | code_change_report.md / code_review.md |
| result-judge | result_judgement.md |
| paper-writing | paper_draft.md |
| status | status_report.md |

### 11.4 artifact header

每个 trusted output 应包含：

```yaml
---
stage: novelty_check
role: novelty_checker
implementation_source: routed_internal_model
actual_backend: codex
actual_model: auto
ledger_call_id: call_xxx
codex_thread_id: xxx
fallback_used: false
verification_status: verified_routed_call
allowed_next_stage: true
context_hash: xxx
contamination_scan_status: checked
---
```

### 11.5 阶段交接规则

下一阶段只能读取：

1. 用户原始输入；
2. 当前阶段 allowed input；
3. 上一阶段 validate PASS 的 trusted output；
4. 明确允许的文献或搜索材料。

下一阶段不能读取：

1. 未验证结果；
2. dry-run 产物；
3. mock 产物；
4. 外部 Agent 临时总结；
5. 旧聊天结论；
6. 用户偏好性暗示。

---

## 12. 阶段流程详细设计

### 12.1 input-normalization

**目标：** 把用户原始输入转成结构化研究输入。

**输入：**

```
raw_user_input.md
```

**输出：**

```
brief.md
candidate_idea.md
```

**成功条件：**

1. 不补充外部知识；
2. 不评价；
3. 不判断新颖性；
4. 字段可追溯到用户原文。

**失败条件：**

1. 加入用户没说的信息；
2. 加入外部 Agent 判断；
3. 直接评价"有潜力"或"很新颖"。

### 12.2 idea-discovery

**目标：** 生成候选研究想法。

**输入：**

1. brief.md；
2. 用户方向；
3. 允许的文献/搜索材料。

**输出：**

```
candidate_ideas.md
```

**要求：**

1. 输出多个候选；
2. 每个候选要有 rationale；
3. 每个候选要有 risk；
4. 不直接视为最终方向；
5. 必须进入 research-contract / novelty-check。

### 12.3 research-contract

**目标：** 锁定研究边界。

**输入：**

1. candidate_idea.md；
2. 必要背景材料；
3. 允许的 baseline 信息。

**输出：**

```
research_contract.md
```

**必须包含：**

1. research question；
2. hypothesis；
3. data boundary；
4. metrics；
5. baselines；
6. success criteria；
7. failure criteria；
8. leakage risks；
9. claim boundary。

### 12.4 novelty-check

**目标：** 判断想法是否已有类似工作。

**输入：**

1. candidate_idea.md；
2. research_contract.md；
3. literature notes；
4. search results；
5. selected paper sections。

**输出：**

```
novelty_check.md
```

**verdict：**

```
confirmed_novel
likely_incremental
already_done
insufficient_evidence
```

**规则：**

1. already_done 必须停止；
2. insufficient_evidence 不能当 confirmed_novel；
3. confirmed_novel 必须有证据；
4. 不能只凭没搜到就说新颖；
5. 关键 prior work 无全文时必须标记 evidence gap。

### 12.5 experiment-plan

**目标：** 设计实验。

**输入：**

1. research_contract.md；
2. novelty_check.md；
3. 数据集信息；
4. baseline 信息；
5. 必要文献。

**输出：**

```
experiment_plan.md
```

**必须包含：**

1. dataset；
2. baseline；
3. metric；
4. split；
5. ablation；
6. resource budget；
7. leakage prevention；
8. success/failure criteria。

### 12.6 implementation-plan

**目标：** 写代码前规划实现。

**输入：**

1. research_contract.md；
2. novelty_check.md；
3. experiment_plan.md；
4. 代码结构信息。

**输出：**

```
implementation_plan.md
```

**必须包含：**

1. 文件修改计划；
2. 模块职责；
3. 配置项；
4. 测试计划；
5. 回滚计划；
6. review checklist。

### 12.7 experiment-bridge

**目标：** 从计划进入实现和运行。

**前置条件：**

1. research_contract validate PASS；
2. novelty_check validate PASS；
3. experiment_plan validate PASS；
4. implementation_plan validate PASS。

**输出：**

1. code_change_report.md；
2. code_review.md；
3. sanity_result.md；
4. experiment_run_manifest.md。

**规则：**

1. 先 sanity check；
2. 再 full experiment；
3. 代码审查不过不跑实验；
4. 实验结果必须结构化保存。

### 12.8 result-judge

**目标：** 判断结果是否支持研究 claim。

**输入：**

1. research_contract.md；
2. experiment_plan.md；
3. 实验结果；
4. baseline 结果；
5. ablation 结果。

**输出：**

```
result_judgement.md
```

**必须判断：**

1. 是否达到成功标准；
2. 是否触发失败标准；
3. 是否支持 claim；
4. 是否需要补实验；
5. 是否存在泄漏或指标误读；
6. 是否需要降低论文 claim。

### 12.9 paper-writing

**目标：** 基于可信结果写论文材料。

**输入：**

1. research_contract.md；
2. novelty_check.md；
3. experiment_plan.md；
4. result_judgement.md；
5. 已确认文献。

**输出：**

1. paper_draft.md；
2. related_work.md；
3. contribution.md；
4. limitation.md。

**规则：**

1. 不得超出 result_judgement；
2. 不得临时加入未经验证文献改变叙事；
3. 必须如实写 limitation。

### 12.10 status

**目标：** 显示当前研究状态。

不需要复杂 Web 面板。
通过 Agent 调用 "/status" 输出即可。

**应展示：**

1. 当前阶段；
2. 每阶段 trusted output 是否存在；
3. ledger 是否存在；
4. validate 是否 PASS；
5. allowed_next_stage 是否 true；
6. blocked 原因；
7. 下一步建议；
8. 是否需要人工确认。

---

## 13. 权限边界表

| 动作 | 外部 Agent | Skill | Workflow | Literature Layer | Trusted Runner | Validator | 用户 |
|------|-----------|-------|----------|-------------------|----------------|-----------|------|
| 接收用户命令 | 可以 | 不负责 | 不负责 | 不负责 | 不负责 | 不负责 | 发起 |
| 保存用户原文 | 可以，但只能原样 | 不负责 | 可检查 | 不负责 | 不负责 | 不负责 | 提供 |
| 整理 brief | 不允许 | 提供规则 | 触发 | 不负责 | 内部模型执行 | 验证 | 可确认 |
| 组织最终 prompt | 不允许 | 提供方法规则 | 允许 | 提供材料 | 不负责 | 不负责 | 不负责 |
| 选择模型 | 不允许 | 不允许 | 不允许 | 不负责 | 按配置执行 | 检查 | 配置 |
| 调用模型 | 不允许直接可信调用 | 不允许 | 不直接调用 | 不负责 | 允许 | 不调用 | 不调用 |
| 搜索文献 | 可触发但不下结论 | 提供策略 | 控制权限 | 执行搜索/保存材料 | 不负责 | 检查结果使用 | 可要求 |
| 阅读文献 | 不直接得结论 | 提供策略 | 控制材料 | 提供章节文本 | 模型阅读判断 | 验证 | 可指定 |
| 判断放行 | 不允许 | 不允许 | 不允许 | 不负责 | 初步标记 | 最终验证 | 可人工暂停 |
| 写 trusted output | 不允许 | 不允许 | 不负责最终内容 | 不负责 | 允许 | 检查 | 读取 |

---

## 14. 人工确认节点

系统应自动化，但不能完全无人控制。

确认节点不需要复杂 UI。
Agent 执行完后，可以输出选项，由用户选择下一步。

**示例：**

novelty-check 完成：

```
verdict: likely_incremental

请选择：
1. 继续，但降低目标
2. 重新搜索文献
3. 人工补充关键论文
4. 放弃该 idea
```

**建议人工确认点：**

| 节点 | 是否建议确认 | 原因 |
|------|-------------|------|
| 候选 idea 最终选择 | 建议 | 防止系统选了用户不想做的方向 |
| research contract 接受 | 建议 | 锁定边界后不应随便改 |
| novelty verdict 为 likely_incremental | 建议 | 是否继续值得讨论 |
| novelty verdict 为 insufficient_evidence | 建议 | 是否人工补全文献 |
| experiment plan 投入资源前 | 建议 | 避免浪费 GPU / 时间 |
| result judgement 与预期冲突 | 建议 | 防止模型过度解释 |
| paper claim 最终确定 | 建议 | 防止夸大 |

---

## 15. MVP 裁剪方案

完整系统很大，不应一次性全做。

### 15.1 MVP 目标

MVP 只做：

```
用户输入研究方向
→ input normalization
→ literature search basic support
→ research-contract
→ novelty-check
→ experiment-plan
→ status
```

暂不做：

1. 自动代码实现；
2. 自动跑大规模实验；
3. 自动论文写作；
4. 自动投稿级优化；
5. 复杂 dashboard；
6. 完整 Web UI；
7. 复杂自动登录下载；
8. 大规模付费墙全文获取。

### 15.2 MVP 必须有

| 功能 | 是否必须 |
|------|----------|
| 原生命令入口 | 必须 |
| raw_user_input | 必须 |
| input_normalizer | 建议纳入 MVP |
| literature search basic | 必须 |
| research_contract | 必须 |
| novelty_check | 必须 |
| experiment_plan | 必须 |
| context isolation | 必须 |
| trusted runner | 必须 |
| validator | 必须 |
| trusted output | 必须 |
| status | 必须 |

### 15.3 复杂度预算（v1.1 新增）

MVP 的活跃文件数应控制在 ~16 个。超过则先裁剪再加新功能。

| Category | 当前数量 | 目标数量 | 操作 |
|----------|---------|---------|------|
| Core CLI + config | 2 | 2 | 保留 |
| Trust boundary（runner, ledger, route, validator, isolation） | 5 | 5 | 保留 |
| Literature pipeline（拆分后） | 4 | 4 | 保留（已拆分） |
| Workflow engine | 1 | 1 | 保留 |
| Adapters（arXiv, OpenAlex, Crossref） | 3 | 3 | 保留 |
| Supplementary tools | 24 | 6-8 | 归档或删除 |
| **Total active** | **36** | **~16** | **裁剪 ~20 个文件** |

20 个 supplementary files 应 archive 到 `tools/archive/` 或删除。它们不被核心流程使用，增加认知负担。

**原则：新功能必须先证明不超出复杂度预算，才能加入。** 如果加一个新功能需要加一个新文件，则必须先归档一个旧文件。

### 15.4 MVP 后扩展

**P1：**

1. implementation-plan；
2. experiment-bridge；
3. result-judge；
4. stronger context scan；
5. literature material manager；
6. manual acquisition queue；
7. paper parsing。

**P2：**

1. paper-writing；
2. auto-review-loop；
3. GitHub CI；
4. semantic contamination detection；
5. deeper literature graph analysis。

---

## 16. 成功标准

理想系统成功标准：

1. 用户能用简单命令启动流程；
2. Skill 保留研究方法能力；
3. Workflow 能控制输入和上下文；
4. prompt 不由外部 Agent 自由拼接；
5. 文献搜索结果可追踪；
6. 关键文献能进入 allowed input；
7. 模型调用真实可信；
8. 每次调用有 ledger；
9. 每阶段可 validate；
10. 每阶段有 trusted output；
11. 下一阶段只读可信输出；
12. 失败时自动停止；
13. 外部 Agent 不能冒充内部模型；
14. 付费墙论文不能被强行绕过；
15. 无全文时能进入人工补全文队列；
16. 系统不会因为严格而难用；
17. 系统不会因为自动化而失控；
18. 能逐步裁剪 MVP；
19. 能吸收 ARIS 优点，但不被旧架构绑死。

---

## 17. 不绑定单一测试用例（v1.1 新增）

hallucination trajectory（幻觉轨迹检测）是本系统的**回归测试用例**，不是产品。

### 17.1 为什么不能绑定单一测试用例

1. 单一测试用例的文献覆盖、paywall 情况、竞争工作分布是特定的，不能代表通用场景
2. 如果系统设计围绕单一测试用例优化，会过度拟合该用例的特殊需求
3. 系统产品是"任意研究想法的可信科研自动化"，不是"幻觉轨迹检测自动化"

### 17.2 当前 test case 的局限

当前 hallucination trajectory test case 的局限是**测试用例的局限，不是系统的局限**：

| 局限 | 原因 | 系统能否解决 |
|------|------|-------------|
| ftq_007/ftq_009 在付费墙后 | IEEE ICMLA/ICASSP 论文无开放版本 | 合法渠道获取，或选其他 test case |
| high_risk_overlap with ICR Probe | 该方向已有密集竞争工作 | 这是 novelty check 的正常输出 |
| experiment_plan 被阻塞 | 上述两个局限的组合结果 | 换一个文献充足的 test case 即可 |

### 17.3 系统验证策略

1. 用 hallucination trajectory 作为回归测试（验证系统行为正确）
2. 选一个文献充足的 topic 作为端到端测试（验证系统能跑通完整流程）
3. 最终用任意用户想法作为产品测试（验证系统通用性）

---

## 18. 最终目标句

本系统的理想形态是：

> «用户用原生命令发起科研任务；Skill 提供研究智慧；Literature Layer 获取和整理文献材料；Workflow 控制输入边界和上下文；Trusted Runner 调用真实模型；Validator 验证可信性；Trusted Output 完成阶段交接。系统既保留 ARIS 的创新能力和命令体验，又避免外部 Agent 失控、上下文污染、模型冒充、搜索结果污染和无证据推进。»

**最终要达到：**

使用简单；
研究能力强；
文献搜索可追踪；
上下文干净；
调用可信；
阶段清楚；
结果可追踪；
失败能停止；
系统可扩展；
实现可裁剪。

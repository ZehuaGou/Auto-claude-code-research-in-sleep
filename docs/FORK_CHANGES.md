# Fork Changes / 本 Fork 修改说明

本仓库基于原作者的 **ARIS / Auto-claude-code-research-in-sleep** 项目进行修改。

本文件只说明本 fork 相对于上游项目新增或强化的内容。原版 ARIS 的核心工作流、skill 体系、paper-writing、review loop、experiment bridge、cross-model review 等基础能力，应归功于原作者和上游项目。

## 1. 上游项目来源

- Upstream repository: `wanshuiyin/Auto-claude-code-research-in-sleep`
- This fork is not the official upstream ARIS repository.
- 本 fork 不是原项目官方版本，而是基于原项目的个人研究改造版本。

## 2. 原版 ARIS 提供的核心能力

以下能力主要来自原版 ARIS：

- skill-based research workflow
- literature search / idea discovery / novelty check
- auto review loop
- experiment bridge
- paper writing / paper improvement / rebuttal / slides / poster workflows
- cross-model review philosophy
- markdown-first, lightweight research automation design

本 fork 不把这些基础能力声明为个人原创。

## 3. 本 fork 主要新增和修改内容

### 3.1 更严格的研究阶段控制

本 fork 增强了 idea discovery、review、novelty check、final selection、research contract、experiment bridge 等阶段的边界控制。

新增或强化：

- interrupted run / incomplete artifact 检查
- provisional selection 检查
- final selection gate
- research contract lock
- resume / validate / verify 检查逻辑
- 防止未完成产物被误判为 complete

### 3.2 `.env` + `model_route.py` 统一模型路由

本 fork 将 ARIS 内部模型调用集中到：

- `.env`
- `.env.example`
- `tools/model_route.py`
- `docs/MODEL_ROUTING_OVERVIEW.md`

主要支持：

`ARIS_CODEX_GATE_MODE=codex_required | codex_preferred | deepseek_only`

覆盖的内部角色包括：

- `idea_reviewer`
- `novelty_checker`
- `final_selector`
- `contract_reviewer`
- `experiment_implementer`
- `experiment_code_reviewer`
- `experiment_auditor`
- `result_judge`
- `paper_writer`
- `final_paper_auditor`

所有 fallback 都要求显式记录：

- `codex_used`
- `fallback_used`
- `fallback_reason`
- `confidence_downgraded`
- `actual_backend`
- `actual_model`

目标是避免 silent fallback。

### 3.3 Slash command wrapper 全量覆盖

本 fork 增加了对 `skills/*/SKILL.md` 的 slash command wrapper 自动覆盖检查。

目标：

- 每个 skill 都应有对应的 `.claude/commands/<skill>.md`
- 避免用到某个命令时才发现没有注册
- 新增 skill 后可以通过脚本检查 wrapper 覆盖率

### 3.4 Final selection 与 Research contract 加固

本 fork 增强了 final selection 和 research contract 阶段：

- final selection 必须通过 gate，不能只是当前 agent 直接选择
- 支持 Codex gate / DeepSeek fallback gate 的显式标记
- research contract 锁定 hypothesis、metrics、baselines、failure gates 和 claim boundary
- contract 修改需要新版本和原因记录

### 3.5 TokenTR 实验脚手架

本 fork 当前包含一个研究方向：

**TokenTR — token-level internal hidden-state transition residuals for hallucination detection**

当前已加入的实验相关文件：

- `experiments/TokenTR/DATA_REQUIREMENTS.md`
- `experiments/TokenTR/DATASET_AUDIT.md`
- `experiments/TokenTR/m0_hidden_extraction.py`
- `experiments/TokenTR/m1_tokentr_pilot.py`
- `experiments/TokenTR/validate_tokentr_data.py`
- `experiments/TokenTR/fixtures/tokentr_sanity.jsonl`

实验安全机制包括：

- 禁止把 sample-level `is_hallucinated` 伪装成 token-level labels
- 支持 token / span / sentence / claim label mode 的边界检查
- 支持 RAGTruth_Xtended char-offset span annotation 映射
- 使用 sample-grouped split，避免 token random split 泄露
- 禁止用 test set 选择 F1 threshold
- baseline 未完整实现时阻止 formal M1
- synthetic fixture 只能用于 pipeline sanity，不能作为正式实验结论

## 4. 当前 TokenTR 状态

TokenTR 目前仍处于实验验证阶段。

当前状态：

- RAGTruth_Xtended 已被选为主要 formal 数据源候选
- RAGTruth adapter 已经过 Codex review 并修复关键映射问题
- Qwen2.5-0.5B-Instruct 仅作为 pipeline smoke model
- formal M1 仍需在真实 hidden-state extraction 和完整 baseline gate 通过后才能继续

本 fork 不声称 TokenTR 已经完成正式实验验证，也不声称当前结果可以直接作为论文结论。

## 5. 本 fork 不声明的内容

本 fork 不声明：

- 自己是 ARIS 官方版本
- 替代上游 ARIS 项目
- TokenTR 已经是成熟论文结果
- synthetic / weak-label smoke test 是正式 hallucination detection evidence
- 当前实验脚手架已经支持正式论文投稿结论

## 6. 推荐使用方式

如果你想使用原版通用 ARIS，请优先参考上游项目。

如果你想参考这个 fork，可以重点查看：

- `AGENT_GUIDE.md`
- `docs/MODEL_ROUTING_OVERVIEW.md`
- `docs/FORK_CHANGES.md`
- `docs/FORK_MAINTENANCE.md`
- `experiments/TokenTR/`
- `.env.example`
- `tools/model_route.py`

本 fork 更偏向"严格审计 + 模型路由治理 + TokenTR 实验验证"的个人研究版本。
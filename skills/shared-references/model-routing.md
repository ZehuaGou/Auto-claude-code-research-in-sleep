# Model Routing — Role-Based Definitions

## Principle

定义 ARIS 内部角色该干什么、默认读什么、输出什么、优先调用谁、fallback 到谁。命名按角色，不用 cheap/normal/strong/critical。

## Global Codex Gate Routing

All critical judgment gates resolve routing via `tools/model_route.py` instead of hardcoding Codex requirements:

```
python tools/model_route.py <role>
```

**Three modes** (set via `ARIS_CODEX_GATE_MODE` in `.env`):

| Mode | Behavior | codex_used | confidence_downgraded |
|------|----------|------------|----------------------|
| `codex_required` | Require Codex; fail if unavailable | true | false |
| `codex_preferred` | Try Codex first; fallback to DeepSeek V4 Pro with warning | depends | true on fallback |
| `deepseek_only` | Skip Codex; use DeepSeek V4 Pro directly | false | true |

**Per-role override**: Set `LLM_<ROLE>_PRIMARY=codex` or `LLM_<ROLE>_PRIMARY=deepseek` in `.env` to override the global mode for a specific role.

**All gate artifacts must record**:
```
routing_source: env
global_codex_gate_mode: <value>
primary_backend: <codex|llm-chat|api>
actual_backend: <codex|llm-chat|api>
actual_model: <model>
fallback_used: true/false
fallback_reason: <reason or none>
codex_used: true/false
confidence_downgraded: true/false
```

## 1. literature_scout

**职责**：搜索和整理文献元数据。主要处理标题、摘要、作者、年份、venue、arXiv ID、DOI、代码链接。不负责最终判断 idea 是否 novel，不负责写论文 claim，不负责实验结果解释。

**默认输入**：用户研究主题、RESEARCH_BRIEF.md、research-wiki/query_pack.md（如存在）、arXiv / Semantic Scholar / WebSearch / Zotero / Obsidian 结果、literature-md/<paper_id>/metadata.json（如存在）

**默认输出**：LITERATURE_INDEX.md、research-wiki/papers/*.md（如 research-wiki 存在）、literature-md/<paper_id>/metadata.json

**模型变量**：LLM_LITERATURE_SCOUT_MODEL、LLM_LITERATURE_SCOUT_THINKING、LLM_LITERATURE_SCOUT_REASONING_EFFORT

**Codex 优先**：否

**调用账本**：如果调用 LLM Chat，必须写 llm_calls.jsonl。

## 2. paper_summarizer

**职责**：对 paper-ingest 后的 Markdown 章节做摘要。按阶段摘要，不把整篇论文塞进上下文。不做查新最终判断。

**默认输入**：literature-md/<paper_id>/abstract.md、introduction.md、method.md、experiments.md、related_work.md、conclusion.md、section_index.json

**默认输出**：literature-md/<paper_id>/summary.md、literature-md/<paper_id>/stage_summaries/*.md

**模型变量**：LLM_PAPER_SUMMARIZER_MODEL、LLM_PAPER_SUMMARIZER_THINKING、LLM_PAPER_SUMMARIZER_REASONING_EFFORT

**Codex 优先**：否

## 3. idea_generator

**职责**：基于 research brief、文献摘要、wiki query pack、failed ideas 生成候选 idea。输出多个独立 idea card。不评审自己的 idea，不判断最终 novelty。

**默认输入**：RESEARCH_BRIEF.md、LITERATURE_INDEX.md、research-wiki/query_pack.md、prior failed ideas、user constraints

**默认输出**：idea-stage/AGENTIC/RUNS/<run_id>/IDEA_CARDS/idea_*.md、idea-stage/AGENTIC/IDEA_BANK.md、idea-stage/AGENTIC/IDEA_BANK.json、idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md

**每个 idea card 必须包含**：title、one-line hypothesis、motivation、baseline dependency、method change、expected signal、required data、required compute、novelty risk、implementation risk、expected experiments、failure modes

**模型变量**：LLM_IDEA_GENERATOR_MODEL、LLM_IDEA_GENERATOR_THINKING、LLM_IDEA_GENERATOR_REASONING_EFFORT

**Codex 优先**：否

## 4. idea_reviewer

**职责**：对单个 idea card 做独立审查。只看一个 idea，不看其他 idea。不看 idea 生成过程。判断 idea 是否值得继续、是否太弱、是否已有明显重复。输出 go / revise / kill。

**默认输入**：exactly one idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md，可选必要的 LITERATURE_INDEX.md 摘要或 paper-ingest section。
**不允许的输入：** IDEA_CARDS/*、RUNS/*/IDEA_CARDS/*、其他 CAND_*.md、旧 review、旧 novelty、用户偏好、旧 praise。不允许输入其他 idea cards。

**默认输出**：idea-stage/AGENTIC/REVIEWS/CAND_XXX_review.md、idea-stage/AGENTIC/REVIEWS/CAND_XXX_review.json

**输出必须包含**：score、verdict (go/revise/kill)、novelty risk、feasibility risk、baseline risk、minimum fix、required evidence、reviewer confidence

**模型变量**：primary: LLM_IDEA_REVIEWER_PRIMARY、fallback: LLM_IDEA_REVIEWER_FALLBACK_MODEL、fallback thinking: LLM_IDEA_REVIEWER_FALLBACK_THINKING、fallback effort: LLM_IDEA_REVIEWER_FALLBACK_REASONING_EFFORT

**Codex 优先**：是，默认 primary=codex

**fallback**：Codex 不可用时 fallback 到 LLM_IDEA_REVIEWER_FALLBACK_MODEL。必须记录 llm_calls.jsonl。必须标记 REVIEWER_DOWNGRADED_FROM_CODEX_TO_LLM_FALLBACK。

## 5. novelty_checker

**职责**：对已经筛选后的 idea 做查新审查。判断是否已有相同/高度相似工作。明确区分 true novelty、incremental、already done、insufficient evidence。不负责生成 idea。

**默认输入**：exactly one idea-stage/AGENTIC/CANONICAL_IDEAS/CAND_*.md + literature-md/<paper_id>/abstract.md、introduction.md、method.md、related_work.md、LITERATURE_INDEX.md、research-wiki/query_pack.md
**不允许的输入：** 其他 CAND_*.md、IDEA_CARDS/*、RUNS/*/IDEA_CARDS/*、REVIEWS/*、旧 NOVELTY/*、generator trace、旧 novelty scores

**默认输出**：idea-stage/AGENTIC/NOVELTY/CAND_XXX_novelty.md、idea-stage/AGENTIC/NOVELTY/CAND_XXX_novelty.json

**输出必须包含**：closest prior work、overlap table、difference table、novelty verdict、confidence、must-cite papers、kill/revise/go recommendation

**模型变量**：primary: LLM_NOVELTY_CHECKER_PRIMARY、fallback: LLM_NOVELTY_CHECKER_FALLBACK_MODEL

**Codex 优先**：是

## 6. contract_reviewer

**职责**：审查 docs/research_contract.md 是否完整、是否可执行、是否存在事后解释空间。重点检查 success/failure signals 是否明确。不负责改实验结果。

**默认输入**：docs/research_contract.md、idea card、EXPERIMENT_PLAN.md、BASELINE.md

**默认输出**：docs/research_contract_review.md、docs/research_contract.lock.json

**输出必须包含**：missing fields、ambiguous success signals、ambiguous failure signals、data split concerns、metric concerns、claim boundary concerns、approve / revise

**模型变量**：primary: LLM_CONTRACT_REVIEWER_PRIMARY、fallback: LLM_CONTRACT_REVIEWER_FALLBACK_MODEL

**Codex 优先**：是

## 7. baseline_reviewer

**职责**：判断 baseline 是否选择合理、复现是否可信。不负责宣称新方法有效。检查 baseline repo、数据集、指标、seed、split 是否匹配。

**默认输入**：research/BASELINE.md、research/BASELINE_REPRODUCTION_REPORT.md、baseline logs、original paper metrics

**默认输出**：research/BASELINE_REVIEW.md

**输出必须包含**：reproduction verdict、metric gap、likely causes of mismatch、whether allowed to proceed、caveats

**模型变量**：LLM_BASELINE_REVIEWER_MODEL

**Codex 优先**：否，默认 LLM Pro 即可。

## 8. experiment_code_reviewer

**职责**：审查实验代码是否符合 research contract。检查有没有偷偷改 data split、metric、baseline、label、评估函数。检查是否从零重写了不该重写的框架。不负责最终 claim 判断。

**默认输入**：docs/research_contract.md、changed code files、EXPERIMENT_PLAN.md、baseline repo diff

**默认输出**：review-stage/experiment_code_review.md

**输出必须包含**：contract compliance、metric correctness、data split correctness、baseline compatibility、suspicious changes、required fixes

**模型变量**：LLM_EXPERIMENT_CODE_REVIEWER_MODEL

**Codex 优先**：否，默认 DeepSeek Pro / LLM_MODEL 即可。

## 9. experiment_auditor

**职责**：审查实验完整性。检查 fake ground truth、score normalization fraud、phantom results、dead code、scope overclaim。复用现有 experiment-audit skill，不重复造轮子。

**默认输入**：eval scripts、result files、EXPERIMENT_LOG.md、EXPERIMENT_AUDIT.json（如存在）、paper claims / narrative

**默认输出**：EXPERIMENT_AUDIT.md、EXPERIMENT_AUDIT.json

**模型变量**：primary: LLM_EXPERIMENT_AUDITOR_PRIMARY、fallback: LLM_EXPERIMENT_AUDITOR_FALLBACK_MODEL

**Codex 优先**：是

## 10. result_judge

**职责**：判断实验结果到底支持什么 claim。防止 partial 被写成 yes。防止单数据集结果被写成普遍结论。复用 result-to-claim skill。

**默认输入**：docs/research_contract.md、EXPERIMENT_LOG.md、EXPERIMENT_AUDIT.json、CLAIMS_FROM_RESULTS.md（如存在）、result files

**默认输出**：CLAIMS_FROM_RESULTS.md、research/CLAIM_EVIDENCE_TABLE.md

**输出必须包含**：claim_supported (yes / partial / no)、what_results_support、what_results_do_not_support、missing_evidence、suggested_claim_revision、confidence

**模型变量**：primary: LLM_RESULT_JUDGE_PRIMARY、fallback: LLM_RESULT_JUDGE_FALLBACK_MODEL

**Codex 优先**：是

## 11. final_auditor

**职责**：最终论文/报告审查。检查 claim 是否过度、citation 是否可靠、实验是否足够、是否值得投稿/继续。这是关键节点，可以用 Codex。

**默认输入**：paper draft、research/CLAIM_EVIDENCE_TABLE.md、EXPERIMENT_AUDIT.md、docs/research_contract.md、BASELINE_REPRODUCTION_REPORT.md

**默认输出**：review-stage/FINAL_AUDIT.md

**输出必须包含**：top risks、unsupported claims、missing baselines、missing ablations、citation risks、recommendation (submit / revise / hold / kill)

**模型变量**：primary: LLM_FINAL_AUDITOR_PRIMARY、fallback: LLM_FINAL_AUDITOR_FALLBACK_MODEL

**Codex 优先**：是

## 12. log_summarizer

**职责**：总结日志、状态、进度。不做科研结论判断，不做 claim 判断，不做 novelty 判断。

**默认输入**：logs、queue_state.json、EXPERIMENT_TRACKER.md、llm_calls.jsonl

**默认输出**：status summaries、model usage summaries、experiment progress summaries

**模型变量**：LLM_LOG_SUMMARIZER_MODEL

**Codex 优先**：否

---

## 13. gap_extractor

**职责**：从文献中提取研究 gap，不生成 idea。

**默认输入**：LITERATURE_INDEX.md

**默认输出**：GAP_MAP.md

**模型变量**：LLM_GAP_EXTRACTOR_MODEL、LLM_GAP_EXTRACTOR_THINKING、LLM_GAP_EXTRACTOR_REASONING_EFFORT

**Codex 优先**：否

**调用账本**：必须写 llm_calls.jsonl。

## 14. idea_deduplicator

**职责**：比较多个 run 的 idea，识别重复/变体/新方向。不做 novelty 判断，不做 quality 评分。

**默认输入**：IDEA_CARDS、IDEA_BANK、CANONICAL_IDEAS

**默认输出**：IDEA_BANK.md、IDEA_BANK.json、CANONICAL_IDEAS/CAND_*.md

**模型变量**：LLM_IDEA_DEDUPLICATOR_MODEL、LLM_IDEA_DEDUPLICATOR_THINKING、LLM_IDEA_DEDUPLICATOR_REASONING_EFFORT

**Codex 优先**：否

## 15. adversarial_reviewer

**职责**：只找漏洞，不美化。纯批判任务，输入固定。

**默认输入**：exactly one CAND_*.md + 对应 CAND 的 REVIEW + 对应 CAND 的 NOVELTY report
**不允许的输入：** 其他 candidate、IDEA_CARDS、generator trace

**默认输出**：idea-stage/AGENTIC/ADVERSARIAL/CAND_*_adversarial.md

**模型变量**：fallback: LLM_ADVERSARIAL_REVIEWER_FALLBACK_MODEL、LLM_ADVERSARIAL_REVIEWER_FALLBACK_THINKING、LLM_ADVERSARIAL_REVIEWER_FALLBACK_REASONING_EFFORT

**Codex 优先**：是（可选），默认 API

## 16. evidence_integrity_auditor

**职责**：对 Phase 1 文献调研结果做独立完整性审查。检查 LITERATURE_INDEX.md 和 GAP_MAP.md 中的证据是否充分、gap 是否真实、搜索是否全面。不生成 idea，不做 novelty 判断。

**默认输入**：LITERATURE_INDEX.md、GAP_MAP.md
**不允许的输入：** RUNS/<run_id>/ 下的原始搜索结果，未加工的外部 API 输出

**默认输出**：idea-stage/AGENTIC/EVIDENCE_AUDIT/PHASE1_EVIDENCE_AUDIT.md

**输出必须包含**：搜索覆盖度评分、gap 真实性评估、关键遗漏风险、PASS / PASS_WITH_WARNINGS / FAIL 结论

**模型变量**：primary: LLM_EVIDENCE_AUDITOR_PRIMARY、fallback: LLM_EVIDENCE_AUDITOR_FALLBACK_MODEL

**Codex 优先**：是

## 17. idea_shortlist_auditor

**职责**：对 Phase 2 生成的 canonical candidates 做独立短名单审查。检查 idea 是否在前人工作中改名重述、method delta 是否足够、最小实验是否明确、claim 是否越界、是否有 fatal flaw。只负责砍掉 weak ideas，不负责提升 idea 质量。

**默认输入**：IDEA_BANK.md、CANONICAL_IDEAS/ 目录下的所有 CAND_*.md
**不允许的输入：** RUNS/<run_id>/IDEA_CARDS/ 原始卡片、generator trace、review 历史

**默认输出**：idea-stage/AGENTIC/SHORTLIST_AUDIT/PHASE2_SHORTLIST_AUDIT.md

**输出必须包含**：每个 candidate 的 verdict (keep / kill)、kill 理由、prior work rename 检测、method delta 评分、minimum experiment 检查

**模型变量**：primary: LLM_IDEA_SHORTLIST_AUDITOR_PRIMARY、fallback: LLM_IDEA_SHORTLIST_AUDITOR_FALLBACK_MODEL

**Codex 优先**：是

## 18. final_selector

**职责**：在 Phase 6 做最终选择。读取所有评审材料，判断是否有值得推进的 idea。可以输出 top_idea_found、multiple_candidates 或 no strong idea found。不生成新 idea，不做额外查新。

**默认输入**：IDEA_BANK.md、CANONICAL_IDEAS/ 下所有 CAND_*.md、REVIEWS/ 下所有 review、NOVELTY/ 下所有 novelty report、ADVERSARIAL/ 下所有 adversarial review
**不允许的输入：** RUNS/<run_id>/ 原始运行日志、generator trace、raw API 输出

**默认输出**：idea-stage/AGENTIC/FINAL_SELECTION/IDEA_SELECTION_REPORT.md

**输出必须包含**：结论 (top_idea_found / multiple_candidates / no strong idea found)、每个活跃 candidate 的推荐、理由、风险

**模型变量**：primary: LLM_FINAL_SELECTOR_PRIMARY、fallback: LLM_FINAL_SELECTOR_FALLBACK_MODEL

**Codex 优先**：是

---

## Phase-by-Phase Codex Routing Summary

| Phase | Skill | Role | Codex? | Reason |
|-------|-------|------|--------|--------|
| 0 | paper-ingest | — | No | PDF/HTML→Markdown，纯机械转换，无需判断 |
| 1 | research-lit | literature_scout | No | 元数据搜索整理，无需判断 |
| 1 | research-lit | evidence_integrity_auditor | **Yes** | 证据完整性生死判断，Codex 独立审查 |
| 1 | research-lit | gap_extractor | No | 从文献提取 gap，非判断任务 |
| 2 | idea-creator | idea_generator | No | 发散生成，不需要 Codex 判断 |
| 2 | idea-creator | idea_deduplicator | No | 机械去重，非判断任务 |
| 2 | idea-creator | idea_shortlist_auditor | **Yes** | 短名单砍掉 weak ideas，生死判断 |
| 3 | exec-review | idea_reviewer | **Yes** | 独立审查，Codex 优先 |
| 3 | exec-review | contract_reviewer | **Yes** | 合同审查，Codex 优先 |
| 4 | novelty-check | novelty_checker | **Yes** | 查新生死判断，Codex 优先 |
| 5 | adversarial | adversarial_reviewer | **Yes** | 纯批判找漏洞，Codex 优先 |
| 6 | idea-discovery | final_selector | **Yes** | 最终选择，Codex 优先 |
| 7 | experiment-audit | experiment_auditor | **Yes** | 实验结果审查，Codex 优先 |
| 8 | paper-audit | result_judge | **Yes** | 结果 claim 判断，Codex 优先 |
| 8 | paper-audit | final_auditor | **Yes** | 最终论文审查，Codex 优先 |
| — | — | baseline_reviewer | No | baseline 复现审查，deepseek-v4-pro 即可 |
| — | — | experiment_code_reviewer | No | 实验代码审查，deepseek-v4-pro 即可 |
| — | — | log_summarizer | No | 轻量日志总结，deepseek-v4-flash |
| — | — | paper_summarizer | No | 论文摘要，deepseek-v4-flash |

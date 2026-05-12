# Literature Material Store

This directory holds structured literature evidence for the ARIS trusted research workflow.

## Structure

- `search_runs/` —保存每次文献搜索证据
  - `current/` —本次搜索的临时工作目录
    - `search_plan.yaml` —搜索计划模板
    - `raw_results.jsonl` —原始搜索结果（未筛选）
    - `candidates.jsonl` —候选论文（待评估）
    - `top_k.md` —结构化 top-k evidence（trusted workflow 输入）
- `papers/` —已解析的论文材料
- `manual_pdf_drop/` —用户手动补充 PDF 的入口
- `manual_acquisition_queue.md` —无法自动获取全文的论文队列
- `cache/` —后续缓存

## Current Status

This is a skeleton only. No real search has been conducted.
The files in `search_runs/current/` are templates, not evidence.


# Paper Ingest Protocol

## Purpose

定义 paper-ingest 的输入、输出、章节切分规则，供 paper-ingest skill、research-lit、novelty-check、baseline-repro 复用。

## Input Types

| Type | Detection | Priority |
|------|-----------|----------|
| arXiv ID | `^\d{4}\.\d{4,5}(v\d+)?$` | 1 |
| arXiv URL | `arxiv.org/abs/\d{4}\.\d{4,5}` | 1 |
| HTML / ar5iv | `arxiv.org/html/` | 2 |
| PDF path | `.pdf` extension | 3 |
| Existing Markdown | `.md` with paper metadata | 4 |
| LaTeX source | `.tex` with `\documentclass` | 5 |

## Output Directory Structure

```
literature-md/<paper_id>/
├── metadata.json
├── abstract.md
├── introduction.md
├── method.md
├── experiments.md
├── related_work.md
├── conclusion.md
├── appendix.md
├── full.md
└── section_index.json
```

## metadata.json Schema

```json
{
  "paper_id": "2401.12345",
  "title": "Paper Title",
  "authors": ["Author A", "Author B"],
  "year": "2024",
  "venue": "NeurIPS 2024",
  "arxiv_id": "2401.12345",
  "doi": "10.xxxx/xxxxx",
  "source_type": "arxiv|pdf|html|markdown|latex",
  "source_path": "/path/to/source",
  "ingested_at": "2026-05-08T10:00:00Z",
  "sections": ["abstract", "introduction", "method", "experiments", "related_work", "conclusion"]
}
```

## section_index.json Schema

```json
{
  "paper_id": "2401.12345",
  "sections": [
    {"name": "abstract", "file": "abstract.md", "purpose": "quick relevance and search"},
    {"name": "introduction", "file": "introduction.md", "purpose": "motivation and context"},
    {"name": "method", "file": "method.md", "purpose": "technical detail"},
    {"name": "experiments", "file": "experiments.md", "purpose": "results and comparisons"},
    {"name": "related_work", "file": "related_work.md", "purpose": "positioning"},
    {"name": "conclusion", "file": "conclusion.md", "purpose": "summary and limitations"},
    {"name": "appendix", "file": "appendix.md", "purpose": "additional details"}
  ],
  "recommended_reads": {
    "literature_review": ["abstract.md", "introduction.md"],
    "novelty_check": ["abstract.md", "introduction.md", "method.md", "related_work.md"],
    "baseline_repro": ["method.md", "experiments.md", "appendix.md"],
    "result_comparison": ["experiments.md"],
    "related_work_writing": ["related_work.md", "conclusion.md"]
  }
}
```

## Staged Reading Rules

- 文献调研只读 abstract + introduction。
- 查新读 abstract + introduction + method + related_work。
- baseline 复现读 method + experiments + appendix。
- 结果对比读 experiments + tables。
- 写 related work 读 related_work + conclusion。
- final audit 按 section_index 按需读取。

## Implementation Status

`tools/paper_ingest.py` 当前实现：
- arXiv metadata 获取（通过 arXiv Export API）
- abstract 写入（来自 arXiv XML）
- 目录结构创建 + 章节占位
- 无 LaTeX/HTML/PDF 深度解析

完整 LaTeX/HTML/PDF → Markdown 转换属于 **protocol 定义的理想流程**，当前 tool 不自动完成。如需完整正文，应由 Agent 读取原始 PDF/HTML 或使用外部转换工具。

## Fallback Chain（未来协议定义，当前 tool 仅实现 1）

1. 已有 Markdown → 直接复用（✓ 已实现）
2. arXiv source LaTeX → 转 Markdown（❌ 协议定义，未实现）
3. HTML / ar5iv → 结构化网页提取（❌ 协议定义，未实现）
4. PDF → 转 Markdown（❌ 协议定义，未实现）
5. PDF 前几页 → 部分提取（Agent 自行读取，标记 partial_ingest）

**当前 tool 实际能力**：仅通过 arXiv Export API 获取元数据和摘要，创建目录结构和章节占位。如需完整正文，应由 Agent 读取原始 PDF/HTML 或使用外部转换工具。

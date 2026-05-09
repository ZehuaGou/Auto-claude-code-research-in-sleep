---
name: paper-ingest
description: Convert arXiv/PDF/HTML/local papers into structured Markdown sections for staged reading.
argument-hint: [arxiv-id-url-or-pdf-path]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebFetch
---

# Paper Ingest

## Purpose

从 arXiv 获取论文元数据和摘要，生成结构化 Markdown 目录和章节占位，方便 staged reading。

## When to Use

- research-lit 找到重要论文后。
- arxiv 下载论文后。
- novelty-check 需要读方法和 related work 前。
- baseline-repro 需要读方法、实验、appendix 前。
- paper-writing 需要 related work 前。

## Inputs

- arXiv ID
- PDF path
- URL
- local paper path
- existing markdown path

## Outputs

`literature-md/<paper_id>/`：
- `metadata.json`
- `abstract.md`
- `introduction.md`
- `method.md`
- `experiments.md`
- `related_work.md`
- `conclusion.md`
- `appendix.md`
- `full.md`
- `section_index.json`

## Workflow

1. 判断输入类型（arXiv ID、PDF 路径、URL、已有 Markdown）。
2. 生成稳定 paper_id。
3. 创建 `literature-md/<paper_id>/`。
4. 获取 metadata（arXiv API 或 PDF 元数据）。
5. 获取 abstract（通过 arXiv API）。
6. 生成章节占位文件（introduction/method/experiments/related_work/conclusion/appendix/full），供 Agent 后续填充。
7. 写入各章节 md。
8. 生成 `section_index.json`。
9. 如果 `research-wiki/` 存在，调用 `research_wiki.py ingest_paper` 或更新对应 paper page。
10. 输出下一步建议：research-lit / novelty-check / baseline-repro 应该读哪些章节。

## Current Capabilities

`tools/paper_ingest.py` 当前已实现：
- arXiv metadata 获取（标题、作者、摘要、年份、categories、DOI）
- arXiv PDF 下载（`--download-pdf` / `--deep`）
- `--deep` 深度提取：HTML 正文提取（arXiv HTML / ar5iv）
- `--deep` 深度提取：PDF 文本提取 fallback（pymupdf → pypdf）
- 章节自动切分（abstract/introduction/related_work/method/experiments/conclusion/appendix）
- section_index.json（含 extraction_method、source_pdf、source_html、sections_detected、missing_sections）
- extraction_report.json（含 pdf_downloaded、html_success、warnings、errors）
- 表格/图片/OCR 暂不保证

## 使用方式

```bash
# Metadata + placeholder only
python tools/paper_ingest.py ingest 2401.12345

# Deep ingest: download PDF + extract full text + split sections
python tools/paper_ingest.py ingest 2401.12345 --deep

# Download PDF only
python tools/paper_ingest.py ingest 2401.12345 --download-pdf

# Force re-download
python tools/paper_ingest.py ingest 2401.12345 --deep --force
```

## 读取优先级（tool 当前支持 1–4）

1. 已有 Markdown → 直接复用
2. arXiv HTML / ar5iv → HTML to Markdown 提取（`--deep`）
3. PDF 文本提取 → pymupdf → pypdf fallback（`--deep`）
4. 直接读 PDF 前几页（Agent 自行读取）

## Deep Ingest 策略

- `--deep` 隐含 `--download-pdf`（自动下载 PDF）
- 优先使用 arXiv HTML（https://arxiv.org/html/<paper_id>），因为结构化更好
- HTML 不可用时，fallback 到 PDF 文本提取
- PDF 提取优先 pymupdf，没有则 fallback 到 pypdf
- 如果无 PDF 库可用，写 extraction_report.json 标记 missing_dependency，不崩溃
- 不将大量论文 default deep ingest
- research-lit 可对 top-k 关键论文调用 /paper-ingest --deep
- novelty-check 对 closest prior work 必须 deep ingest 或至少读取 abstract/introduction/method/related_work

## Staged Reading（遵循 paper-ingest-protocol）

- 文献调研只读 abstract + introduction。
- 查新读 abstract + introduction + method + related_work。
- baseline 复现读 method + experiments + appendix。
- 结果对比读 experiments + tables。
- 写 related work 读 related_work + conclusion。

## Hard Rules

- 不默认下载大量 PDF。
- 不默认把整篇 PDF 塞进上下文。
- 按 staged reading 规则分阶段读取。

## Failure Handling

- arXiv API 不可用：跳过 metadata 获取，使用用户提供的 ID 作为 paper_id。
- 无法生成章节目录：写 full.md，并在 section_index 标记 sections_unknown。
- 注意：本 tool 已支持 HTML/PDF 文本级 deep ingest，但不保证复杂表格、公式、图片、OCR 的完整还原。若 extraction_report.json 显示 low confidence、missing sections 或 extraction error，应由 Agent 补充读取原 PDF/HTML。

## Integration

- `tools/paper_ingest.py` — 核心提取和目录管理
- `skills/shared-references/paper-ingest-protocol.md` — 详细协议
- `skills/research-lit/SKILL.md` — 在调研后调用
- `skills/novelty-check/SKILL.md` — 读取结构化章节
- `skills/baseline-repro/SKILL.md` — 读取方法和实验

## Example Invocation

```
/paper-ingest 2401.12345
/paper-ingest papers/2401.12345.pdf
/paper-ingest https://arxiv.org/abs/2401.12345
```

## Expected Artifacts

- `literature-md/<paper_id>/metadata.json`
- `literature-md/<paper_id>/section_index.json`
- `literature-md/<paper_id>/*.md`

## Failure Example

如果 arXiv API 不可用：
- 跳过 metadata 获取
- 创建基础目录结构
- 标记 metadata_unavailable

## Recovery Step

如果目录创建失败：
- 检查 `literature-md/` 目录权限
- 手动创建 paper 目录后重试

## Status / Ledger

本 skill 不调用模型（只做文件转换），不写入 ledger。

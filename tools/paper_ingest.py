#!/usr/bin/env python3
"""
ARIS Paper Ingest Tool — Convert papers to structured Markdown sections.

Input: arXiv ID, arXiv URL, PDF path, or existing Markdown
Output: literature-md/<paper_id>/ with metadata.json, section_index.json,
        extraction_report.json, and section .md files

Commands:
  ingest <source> [--deep] [--download-pdf] [--force]
  metadata <paper-id>
  list
"""
from __future__ import annotations

import html.parser
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(TOOLS_DIR))

from env_loader import find_project_root

ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_API = "https://export.arxiv.org/api/query"
_ARXIV_HTML_BASE = "https://arxiv.org/html"
_ARXIV_PDF_BASE = "https://arxiv.org/pdf"

_ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
_ARXIV_ABS_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})")
_ARXIV_PDF_RE = re.compile(r"arxiv\.org/pdf/(\d{4}\.\d{4,5})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def paper_id_from_arxiv(arxiv_id: str) -> str:
    m = _ARXIV_ID_RE.match(arxiv_id)
    if m:
        return m.group(1)
    # Fallback: normalize slashes
    return arxiv_id.replace("/", "_")


def _resolve_arxiv_id(source: str) -> Optional[str]:
    """Extract arXiv ID from various input formats."""
    m = _ARXIV_ID_RE.match(source)
    if m:
        return m.group(1)
    m = _ARXIV_ABS_RE.search(source)
    if m:
        return m.group(1)
    m = _ARXIV_PDF_RE.search(source)
    if m:
        return m.group(1)
    return None


def get_literature_dir() -> Path:
    root = find_project_root()
    lit_dir = root / "literature-md"
    lit_dir.mkdir(parents=True, exist_ok=True)
    return lit_dir


def get_papers_dir() -> Path:
    root = find_project_root()
    pdir = root / "papers"
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


# ---------------------------------------------------------------------------
# arXiv metadata
# ---------------------------------------------------------------------------

def fetch_arxiv_metadata(arxiv_id: str) -> Optional[Dict[str, Any]]:
    """Fetch paper metadata from arXiv API."""
    pid = paper_id_from_arxiv(arxiv_id)
    url = f"{_ARXIV_API}?id_list={pid}&max_results=1"
    req = urllib.request.Request(url, headers={"User-Agent": "aris-paper-ingest/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"arXiv API error: {e}", file=sys.stderr)
        return None

    entry = root.find(f"{{{ATOM_NS}}}entry")
    if entry is None:
        return None

    title = (entry.findtext(f"{{{ATOM_NS}}}title", "") or "").strip().replace("\n", " ")
    summary = (entry.findtext(f"{{{ATOM_NS}}}summary", "") or "").strip().replace("\n", " ")
    authors = [a.findtext(f"{{{ATOM_NS}}}name", "") for a in entry.findall(f"{{{ATOM_NS}}}author")]
    published = (entry.findtext(f"{{{ATOM_NS}}}published", "") or "")[:10]
    updated = (entry.findtext(f"{{{ATOM_NS}}}updated", "") or "")[:10]
    categories = [c.get("term", "") for c in entry.findall(f"{{{ATOM_NS}}}category")]
    doi = ""
    for link in entry.findall(f"{{{ATOM_NS}}}link"):
        if link.get("title") == "doi":
            doi = link.get("href", "")
            break

    return {
        "paper_id": pid,
        "title": title,
        "authors": authors,
        "year": published[:4],
        "published": published,
        "updated": updated,
        "categories": categories,
        "doi": doi,
        "arxiv_id": pid,
        "abstract": summary,
    }


# ---------------------------------------------------------------------------
# PDF download
# ---------------------------------------------------------------------------

def download_arxiv_pdf(paper_id: str, dest: Path) -> bool:
    """Download PDF from arXiv. Returns True on success."""
    url = f"{_ARXIV_PDF_BASE}/{paper_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "aris-paper-ingest/1.0"})
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if len(data) < 5000:
            print(f"PDF too small ({len(data)} bytes), possibly a redirect page", file=sys.stderr)
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"PDF download error: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# HTML extraction (arXiv HTML / ar5iv)
# ---------------------------------------------------------------------------

class _TextExtractor(html.parser.HTMLParser):
    """Simple HTML-to-text extractor that preserves headings and paragraphs."""

    def __init__(self):
        super().__init__()
        self._text: List[str] = []
        self._skip = False  # skip script/style content

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in ("script", "style"):
            self._skip = True
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = t[1]
            self._text.append(f"\n{'#' * int(level)} ")
        elif t in ("p", "div", "br", "li", "tr"):
            self._text.append("\n")

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("script", "style"):
            self._skip = False
        elif t in ("p", "div", "li", "th", "td"):
            self._text.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self) -> str:
        raw = "".join(self._text)
        # Collapse excessive blank lines
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def fetch_arxiv_html(paper_id: str) -> Optional[str]:
    """Fetch the ar5iv/arXiv HTML version. Returns raw HTML or None."""
    url = f"{_ARXIV_HTML_BASE}/{paper_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "aris-paper-ingest/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            html_bytes = r.read()
        # arXiv HTML is UTF-8
        return html_bytes.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("arXiv HTML not available (404)", file=sys.stderr)
        else:
            print(f"arXiv HTML error {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"arXiv HTML fetch error: {e}", file=sys.stderr)
        return None


def html_to_text(html_content: str) -> str:
    """Convert HTML to plain text with basic heading/preservation."""
    # Strip mathjax/annotation-xml etc.
    html_content = re.sub(
        r'<annotation[^>]*>.*?</annotation>', '', html_content, flags=re.DOTALL
    )
    extractor = _TextExtractor()
    try:
        extractor.feed(html_content)
        return extractor.get_text()
    except Exception as e:
        print(f"HTML text extraction error: {e}", file=sys.stderr)
        return re.sub(r"<[^>]+>", "", html_content).strip()


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> Optional[str]:
    """Extract text from PDF using pymupdf(fitz) or pypdf fallback."""
    # Try pymupdf first
    try:
        import fitz  # type: ignore

        doc = fitz.open(str(pdf_path))
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            pages.append(f"\n\n[Page {i + 1}]\n\n{text}")
        doc.close()
        return "".join(pages).strip()
    except ImportError:
        pass
    except Exception as e:
        print(f"pymupdf error: {e}", file=sys.stderr)
        # Fall through to pypdf

    # Try pypdf
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(pdf_path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(f"\n\n[Page {i + 1}]\n\n{text}")
        return "".join(pages).strip()
    except ImportError:
        return None  # No PDF library available
    except Exception as e:
        print(f"pypdf error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

SECTION_PATTERNS = {
    "abstract": r"^\s*(?:abstract|Abstract|ABSTRACT)\s*$",
    "introduction": r"^\s*(?:1[\.\s]|I[\.\s])?\s*(?:introduction|Introduction|INTRODUCTION)\s*$",
    "related_work": r"^\s*(?:\d[\.\s])?\s*(?:related\s*work|background|Background|Related\s*Work|RELATED\s*WORK|Related\s*Works?)\s*$",
    "method": r"^\s*(?:\d[\.\s])?\s*(?:method|Method|METHOD|methodology|Methodology|approach|Approach|model|Model|proposed|Proposed|system|System|framework|Framework)\s*$",
    "experiments": r"^\s*(?:\d[\.\s])?\s*(?:experiment|Experiment|experiments|Experiments|EXPERIMENTS|evaluation|Evaluation|EVALUATION|results|Results|RESULTS|empirical|Empirical)\s*$",
    "conclusion": r"^\s*(?:\d[\.\s])?\s*(?:conclusion|Conclusion|CONCLUSION|discussion|Discussion|DISCUSSION|concluding|Concluding|summary|Summary)\s*$",
    "appendix": r"^\s*(?:appendix|Appendix|APPENDIX|supplementary|Supplementary|SUPPLEMENTARY|appendix\s*[a-z]?)\s*$",
}

# Order matters: we scan in priority order
SECTION_ORDER = [
    "abstract", "introduction", "related_work", "method",
    "experiments", "conclusion", "appendix",
]


def _normalize_heading(line: str) -> str:
    """Strip markdown heading markers and common numbering."""
    s = line.lstrip("#").strip()
    s = re.sub(r"^\d+[\.\)]\s*", "", s)  # remove "1.", "2)"
    s = re.sub(r"^[IVXLCDM]+[\.\)]\s*", "", s)  # remove "I.", "II."
    return s.strip()


def split_sections(full_text: str) -> Dict[str, str]:
    """Split full text into named sections by heading heuristics.

    Returns dict mapping section_name -> content (empty string if not found).
    """
    sections: Dict[str, str] = {s: "" for s in SECTION_ORDER}
    lines = full_text.splitlines()

    # Build list of (line_idx, section_name) for detected headings
    detected: List[tuple[int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Must be a heading-like line (starts with # or is short and prominent)
        is_heading = stripped.startswith("#")
        for sec_name, pattern in SECTION_PATTERNS.items():
            test = _normalize_heading(
                stripped.lstrip("#").strip()
            ) if is_heading else _normalize_heading(stripped)
            if re.match(pattern, test, re.IGNORECASE):
                detected.append((i, sec_name))
                break

    # Deduplicate: keep first occurrence of each section
    seen: set[str] = set()
    unique_detected: List[tuple[int, str]] = []
    for idx, name in detected:
        if name not in seen:
            seen.add(name)
            unique_detected.append((idx, name))

    if not unique_detected:
        return sections

    # Extract content between detected headings
    for k, (idx, name) in enumerate(unique_detected):
        start = idx + 1
        end = unique_detected[k + 1][0] if k + 1 < len(unique_detected) else len(lines)
        content_lines = []
        for j in range(start, end):
            content_lines.append(lines[j])
        sections[name] = "\n".join(content_lines).strip()

    return sections


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def write_section(paper_dir: Path, name: str, content: str):
    section_file = paper_dir / f"{name}.md"
    section_file.write_text(content.strip() + "\n" if content else "", encoding="utf-8")


def write_metadata(paper_dir: Path, metadata: Dict[str, Any]):
    metadata["ingested_at"] = datetime.now(timezone.utc).isoformat()
    (paper_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_section_index(
    paper_dir: Path,
    paper_id: str,
    sections_found: Dict[str, str],
    extraction_method: str,
    source_pdf: str,
    source_html: str,
):
    """Write section_index.json with extraction metadata."""
    section_map = {
        "abstract": "quick relevance and search",
        "introduction": "motivation and context",
        "method": "technical detail",
        "experiments": "results and comparisons",
        "related_work": "positioning",
        "conclusion": "summary and limitations",
        "appendix": "additional details",
    }
    section_list = []
    sections_detected = []
    missing_sections = []
    for name in SECTION_ORDER:
        content = sections_found.get(name, "")
        has_content = len(content) > 50  # meaningful content threshold
        if has_content:
            sections_detected.append(name)
        else:
            missing_sections.append(name)
        section_list.append({
            "name": name,
            "file": f"{name}.md",
            "purpose": section_map.get(name, "general"),
            "has_content": has_content,
            "char_count": len(content),
        })

    index = {
        "paper_id": paper_id,
        "extraction_method": extraction_method,
        "source_pdf": source_pdf,
        "source_html": source_html,
        "has_full_text": bool(sections_found.get("__full__", "")),
        "sections": section_list,
        "sections_detected": sections_detected,
        "missing_sections": missing_sections,
        "confidence": "high" if len(sections_detected) >= 4 else "medium" if sections_detected else "low",
        "recommended_reads": {
            "literature_review": ["abstract.md", "introduction.md"],
            "novelty_check": ["abstract.md", "introduction.md", "method.md", "related_work.md"],
            "baseline_repro": ["method.md", "experiments.md", "appendix.md"],
            "result_comparison": ["experiments.md"],
            "related_work_writing": ["related_work.md", "conclusion.md"],
        },
    }
    (paper_dir / "section_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_extraction_report(paper_dir: Path, report: Dict[str, Any]):
    report["reported_at"] = datetime.now(timezone.utc).isoformat()
    (paper_dir / "extraction_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# cmd_ingest
# ---------------------------------------------------------------------------

def cmd_ingest(args: List[str]):
    """Ingest a paper with optional deep extraction.

    Usage: paper_ingest.py ingest <source> [--deep] [--download-pdf] [--force]
    """
    if not args:
        print("Usage: paper_ingest.py ingest <arxiv-id|url|pdf-path> [--deep] [--download-pdf] [--force]", file=sys.stderr)
        sys.exit(1)

    source = args[0]
    deep = "--deep" in args or "-d" in args
    download_pdf = "--download-pdf" in args or deep  # deep implies download-pdf
    force = "--force" in args or "-f" in args

    # --- Resolve paper ID and source type ---
    arxiv_id = _resolve_arxiv_id(source)
    pdf_path_candidate = Path(source)

    if arxiv_id:
        paper_id = paper_id_from_arxiv(arxiv_id)
        source_type = "arxiv"
        metadata = fetch_arxiv_metadata(arxiv_id)
        if metadata is None:
            print(f"arXiv API error for {arxiv_id}, creating minimal metadata", file=sys.stderr)
            metadata = {
                "paper_id": paper_id,
                "title": f"arXiv:{arxiv_id}",
                "authors": [],
                "year": "",
                "published": "",
                "updated": "",
                "categories": [],
                "doi": "",
                "arxiv_id": arxiv_id,
                "abstract": "[Abstract not available — arXiv API error]",
            }
    elif pdf_path_candidate.exists() and pdf_path_candidate.suffix.lower() == ".pdf":
        paper_id = pdf_path_candidate.stem.replace(" ", "_").lower()
        source_type = "pdf"
        metadata = {
            "paper_id": paper_id,
            "title": pdf_path_candidate.stem,
            "authors": [],
            "year": "",
            "venue": "",
            "arxiv_id": "",
            "doi": "",
            "source_type": source_type,
            "source_path": str(pdf_path_candidate),
            "abstract": "[Abstract not available — PDF source]",
        }
    else:
        print(f"Unknown source or file not found: {source}", file=sys.stderr)
        sys.exit(1)

    # --- Setup output dirs ---
    lit_dir = get_literature_dir()
    papers_dir = get_papers_dir()
    paper_dir = lit_dir / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    metadata["source_type"] = source_type
    metadata["sections"] = list(SECTION_ORDER)
    write_metadata(paper_dir, metadata)

    # --- PDF download ---
    pdf_downloaded = False
    pdf_dest = papers_dir / f"{paper_id}.pdf"
    if download_pdf and arxiv_id:
        if pdf_dest.exists() and not force:
            print(f"PDF already exists: {pdf_dest} (use --force to re-download)", file=sys.stderr)
            pdf_downloaded = True
        else:
            print(f"Downloading PDF: {_ARXIV_PDF_BASE}/{arxiv_id}", file=sys.stderr)
            pdf_downloaded = download_arxiv_pdf(arxiv_id, pdf_dest)
    elif pdf_path_candidate.exists() and pdf_path_candidate.suffix.lower() == ".pdf":
        pdf_downloaded = True
        pdf_dest = pdf_path_candidate  # use the original PDF path

    pdf_path_str = str(pdf_dest) if pdf_downloaded else ""

    # --- Extraction report (initial) ---
    extraction_method = "placeholder"
    html_attempted = False
    html_success = False
    pdf_extraction_attempted = False
    pdf_extraction_success = False
    warnings: List[str] = []
    errors: List[str] = []
    full_text = ""

    # --- Deep extraction ---
    if deep:
        # Strategy A: Already have markdown source? (detect .md input)
        if source.endswith(".md") and Path(source).exists():
            full_text = Path(source).read_text(encoding="utf-8", errors="replace")
            extraction_method = "markdown_source"
            print("Using existing markdown as full text", file=sys.stderr)

        # Strategy B: arXiv HTML extraction
        if not full_text and arxiv_id:
            html_attempted = True
            print(f"Fetching arXiv HTML: {_ARXIV_HTML_BASE}/{arxiv_id}", file=sys.stderr)
            html_raw = fetch_arxiv_html(arxiv_id)
            if html_raw:
                full_text = html_to_text(html_raw)
                if len(full_text) > 500:
                    html_success = True
                    extraction_method = "arxiv_html"
                    print(f"HTML extraction successful ({len(full_text)} chars)", file=sys.stderr)
                else:
                    warnings.append("HTML fetched but extracted text too short")
                    full_text = ""
            else:
                warnings.append("arXiv HTML unavailable")

        # Strategy C: PDF text extraction
        if not full_text and pdf_downloaded:
            pdf_extraction_attempted = True
            pdf_path = pdf_dest if pdf_dest.exists() else None
            if pdf_path and pdf_path.exists():
                print(f"Extracting text from PDF: {pdf_path}", file=sys.stderr)
                try:
                    extracted = extract_pdf_text(pdf_path)
                    if extracted and len(extracted) > 200:
                        full_text = extracted
                        pdf_extraction_success = True
                        extraction_method = "pdf_text"
                        print(f"PDF extraction successful ({len(full_text)} chars)", file=sys.stderr)
                    elif extracted:
                        warnings.append(f"PDF text too short ({len(extracted)} chars)")
                    else:
                        errors.append("PDF extraction returned empty text")
                except ImportError:
                    msg = (
                        "PDF extraction libraries not available. "
                        "Install: pip install pymupdf or pip install pypdf"
                    )
                    warnings.append(msg)
                    extraction_method = "pdf_text_missing_dependency"
                except Exception as e:
                    errors.append(f"PDF extraction error: {e}")

        if not full_text:
            warnings.append("No full text extracted; writing placeholder sections")

    # --- Write full.md ---
    if full_text:
        write_section(paper_dir, "full", full_text)
    else:
        placeholder = (
            f"# {metadata.get('title', paper_id)}\n\n"
            f"[Full text not extracted — see extraction_report.json for details]\n"
        )
        write_section(paper_dir, "full", placeholder)

    sections_found: Dict[str, str] = {"__full__": full_text if full_text else ""}

    if full_text:
        # Split sections from full text
        sections_found.update(split_sections(full_text))
        # Count sections with meaningful content (exclude __full__ flag)
        content_counts = sum(
            1 for k, v in sections_found.items()
            if k != "__full__" and isinstance(v, str) and len(v) > 50
        )
        extraction_confidence = "high" if content_counts >= 4 else "medium"
    else:
        sections_found.update({s: "" for s in SECTION_ORDER})

    # Write section files
    write_section(paper_dir, "abstract", sections_found.get("abstract", "") or metadata.get("abstract", ""))
    for section in ["introduction", "method", "experiments", "related_work", "conclusion", "appendix"]:
        content = sections_found.get(section, "")
        heading = section.replace("_", " ").title()
        if content:
            write_section(paper_dir, section, f"# {heading}\n\n{content}")
        else:
            write_section(paper_dir, section, f"# {heading}\n\n[Section not extracted — see extraction_report.json]")

    # --- Write section_index.json ---
    write_section_index(
        paper_dir, paper_id,
        sections_found,
        extraction_method=extraction_method,
        source_pdf=pdf_path_str,
        source_html=f"{_ARXIV_HTML_BASE}/{arxiv_id}" if arxiv_id else "",
    )

    # --- Write extraction_report.json ---
    report = {
        "paper_id": paper_id,
        "input": source,
        "source_type": source_type,
        "pdf_downloaded": pdf_downloaded,
        "pdf_path": pdf_path_str,
        "html_attempted": html_attempted,
        "html_success": html_success,
        "pdf_extraction_attempted": pdf_extraction_attempted,
        "pdf_extraction_success": pdf_extraction_success,
        "extraction_method": extraction_method,
        "warnings": warnings,
        "errors": errors,
    }
    write_extraction_report(paper_dir, report)

    # --- Output summary ---
    result = {
        "paper_id": paper_id,
        "path": str(paper_dir),
        "source_type": source_type,
        "title": metadata.get("title", ""),
        "extraction_method": extraction_method,
        "pdf_downloaded": pdf_downloaded,
        "sections_written": [s for s in SECTION_ORDER if sections_found.get(s, "")],
        "extraction_report": str(paper_dir / "extraction_report.json"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# cmd_metadata, cmd_list
# ---------------------------------------------------------------------------

def cmd_metadata(args: List[str]):
    if not args:
        print("Usage: paper_ingest.py metadata <paper-id>", file=sys.stderr)
        sys.exit(1)
    lit_dir = get_literature_dir()
    paper_dir = lit_dir / args[0]
    meta_file = paper_dir / "metadata.json"
    if not meta_file.exists():
        print(f"Paper not found: {args[0]}", file=sys.stderr)
        sys.exit(1)
    print(meta_file.read_text(encoding="utf-8"))


def cmd_list():
    lit_dir = get_literature_dir()
    papers = []
    for d in sorted(lit_dir.iterdir()):
        if d.is_dir():
            meta_file = d / "metadata.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    papers.append({
                        "paper_id": meta.get("paper_id", d.name),
                        "title": meta.get("title", d.name),
                        "year": meta.get("year", ""),
                        "venue": meta.get("venue", ""),
                    })
                except Exception:
                    papers.append({"paper_id": d.name, "title": d.name, "year": "", "venue": ""})
    print(json.dumps(papers, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: paper_ingest.py <ingest|metadata|list> [args...]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    cmd_args = sys.argv[2:]

    if cmd == "ingest":
        cmd_ingest(cmd_args)
    elif cmd == "metadata":
        cmd_metadata(cmd_args)
    elif cmd == "list":
        cmd_list()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    main()

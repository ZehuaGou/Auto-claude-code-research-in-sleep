#!/usr/bin/env python3
"""CLI helper for reading and extracting text from PDF files.

Used by the ``pdf-reader`` skill (skills/pdf-reader/SKILL.md).

Commands
--------
read      Extract text from specific pages of a PDF.
meta      Show PDF metadata (pages, size, title if available).
search    Search for a keyword in a PDF and show matching pages.

Examples
--------
python3 tools/pdf_read.py read papers/llm-das.pdf --pages 1-3
python3 tools/pdf_read.py meta papers/llm-das.pdf
python3 tools/pdf_read.py search "GRPO" papers/llm-das.pdf

Safety: Only use this tool on PDFs the user has legally obtained or has the
right to process. This tool does not download PDFs, bypass paywalls, call
models, or access the network. Avoid dumping entire copyrighted papers into
downstream prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _find_pdftotext() -> str | None:
    """Locate pdftotext binary. Returns path or None."""
    for candidate in ("pdftotext", "/usr/bin/pdftotext", "/mingw64/bin/pdftotext"):
        try:
            subprocess.run(
                [candidate, "-v"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return candidate
        except Exception:
            continue
    return None


def _extract_pdftotext(path: str, first: int = 1, last: int | None = None) -> str:
    """Extract text using pdftotext. Returns empty string on failure."""
    pdftotext = _find_pdftotext()
    if not pdftotext:
        return ""
    args = [pdftotext, "-layout", "-f", str(first)]
    if last is not None:
        args.extend(["-l", str(last)])
    args.extend([path, "-"])
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        return result.stdout
    except Exception:
        return ""


def _extract_pypdf2(path: str, first: int = 1, last: int | None = None) -> str:
    """Extract text using PyPDF2. Returns empty string on failure."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        try:
            import PyPDF2
            PdfReader = PyPDF2.PdfReader
        except ImportError:
            return ""

    try:
        reader = PdfReader(path)
        total = len(reader.pages)
        if last is None:
            last = total
        last = min(last, total)
        lines = []
        for i in range(first - 1, last):
            text = reader.pages[i].extract_text()
            if text:
                lines.append(text)
        return "\n\n".join(lines)
    except Exception:
        return ""


def read_pdf(path: str, first: int = 1, last: int | None = None) -> dict:
    """Extract text from a PDF. Tries pdftotext first, falls back to PyPDF2."""
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}", "path": str(p)}
    if not p.suffix.lower() == ".pdf":
        return {"error": f"Not a PDF: {path}", "path": str(p)}

    text = _extract_pdftotext(path, first=first, last=last)
    backend = "pdftotext"
    if not text:
        text = _extract_pypdf2(path, first=first, last=last)
        backend = "pypdf2"

    return {
        "path": str(p),
        "pages": f"{first}-{last or 'end'}",
        "text": text,
        "char_count": len(text),
        "backend": backend,
    }


def meta_pdf(path: str) -> dict:
    """Return PDF metadata."""
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}", "path": str(p)}

    result = {
        "path": str(p),
        "size_kb": p.stat().st_size // 1024,
        "pages": 0,
    }

    pdftotext = _find_pdftotext()
    if pdftotext:
        try:
            r = subprocess.run(
                [pdftotext, path, "-", "-l", "1", "-f", "1"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
        except Exception:
            r = None
    else:
        r = None

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        result["pages"] = len(reader.pages)
        info = reader.metadata
        if info:
            result["title"] = getattr(info, "title", None) or None
            result["author"] = getattr(info, "author", None) or None
    except ImportError:
        # Try to get page count from pdftotext if we ran it
        pass

    # Extract title from first page text as fallback
    if not result.get("title") and r and r.stdout:
        lines = [l.strip() for l in r.stdout.split("\n") if l.strip()]
        if lines:
            result["first_line"] = lines[0][:200]

    return result


def search_pdf(path: str, keyword: str, context: int = 1) -> dict:
    """Search for keyword in PDF, return matching pages with context lines."""
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}", "path": str(p)}

    text = _extract_pdftotext(path)
    if not text:
        text = _extract_pypdf2(path)
    if not text:
        return {"error": "Could not extract text", "path": str(p)}

    lines = text.split("\n")
    matches = []
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    for i, line in enumerate(lines):
        if pattern.search(line):
            start = max(0, i - context)
            end = min(len(lines), i + context + 1)
            matches.append({
                "line": i + 1,
                "text": "\n".join(lines[start:end]).strip(),
            })

    return {
        "path": str(p),
        "keyword": keyword,
        "matches": len(matches),
        "results": matches[:20],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read and extract text from PDF files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    read_parser = subparsers.add_parser("read", help="Extract text from specific pages")
    read_parser.add_argument("path", help="Path to PDF file")
    read_parser.add_argument(
        "--pages",
        default="1-3",
        metavar="RANGE",
        help="Page range, e.g. 1-3 or 5 (default: 1-3)",
    )

    meta_parser = subparsers.add_parser("meta", help="Show PDF metadata")
    meta_parser.add_argument("path", help="Path to PDF file")

    search_parser = subparsers.add_parser("search", help="Search keyword in PDF")
    search_parser.add_argument("keyword", help="Keyword to search for")
    search_parser.add_argument("path", help="Path to PDF file")
    search_parser.add_argument(
        "--context",
        type=int,
        default=1,
        help="Lines of context around matches (default: 1)",
    )

    return parser


def _parse_pages(pages_str: str) -> tuple[int, int | None]:
    """Parse '1-3' or '5' into (first, last)."""
    m = re.match(r"(\d+)(?:-(\d+))?", pages_str.strip())
    if not m:
        return 1, None
    first = int(m.group(1))
    last = int(m.group(2)) if m.group(2) else first
    return first, last


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.command == "read":
        first, last = _parse_pages(args.pages)
        result = read_pdf(args.path, first=first, last=last)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if "error" not in result else 1

    if args.command == "meta":
        result = meta_pdf(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if "error" not in result else 1

    if args.command == "search":
        result = search_pdf(args.path, args.keyword, context=args.context)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if "error" not in result else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())

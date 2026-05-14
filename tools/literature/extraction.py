"""PDF text extraction helpers — extracted from literature_evidence_landing.py."""

from pathlib import Path


def extract_pdf_text(pdf_path: Path) -> dict:
    """Extract text from a PDF file using available libraries.

    Tries in order: PyMuPDF (fitz), pypdf, pdfminer.six.
    Returns dict with status, method, text content, error.
    """
    # Try PyMuPDF
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        text = "\n".join(text_parts)
        return {
            "status": "extracted_text",
            "method": "pymupdf",
            "text": text,
            "error": "",
        }
    except ImportError:
        pass
    except Exception as e:
        return {"status": "failed", "method": "pymupdf", "text": "", "error": str(e)}

    # Try pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts)
        return {
            "status": "extracted_text",
            "method": "pypdf",
            "text": text,
            "error": "",
        }
    except ImportError:
        pass
    except Exception as e:
        return {"status": "failed", "method": "pypdf", "text": "", "error": str(e)}

    # Try pdfminer.six
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(str(pdf_path))
        return {
            "status": "extracted_text",
            "method": "pdfminer",
            "text": text,
            "error": "",
        }
    except ImportError:
        pass
    except Exception as e:
        return {"status": "failed", "method": "pdfminer", "text": "", "error": str(e)}

    # No library available
    return {
        "status": "tool_missing",
        "method": "none",
        "text": "",
        "error": "No PDF extraction library installed. Install one of: pymupdf, pypdf, pdfminer.six",
    }

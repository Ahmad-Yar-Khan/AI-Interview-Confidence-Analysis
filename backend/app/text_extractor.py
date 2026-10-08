"""
text_extractor.py
-----------------
Extracts raw text from PDF, DOCX, or TXT resume files.
No structure parsing — just clean plain text for the LLM context.
"""

import io
import logging

logger = logging.getLogger(__name__)


def extract_text(contents: bytes, filename: str) -> str:
    ext = (filename or "").rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        return _from_pdf(contents)
    elif ext == "docx":
        return _from_docx(contents)
    elif ext == "txt":
        return contents.decode("utf-8", errors="ignore").strip()
    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def _from_pdf(contents: bytes) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t.strip())
    return "\n".join(text_parts)


def _from_docx(contents: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(contents))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

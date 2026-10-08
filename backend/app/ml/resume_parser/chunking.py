"""
chunking.py (resume_parser)
-----------------------------
Splits a resume's raw text into (label, text) chunks by detecting section
headers. Feeds the RAG retrieval layer (question_service._extract_projects_section,
get_debug_chunks) — a distinct job from "extract a single structured field",
which is why it's its own module.
"""

import re

from app.ml.resume_parser.models import ResumeProfile

SECTIONS = [
    (r"skills?|technical\s+skills?|core\s+competencies|technologies|tech\s+stack", "skills"),
    (r"(work\s+)?experience|employment|professional\s+background",                  "experience"),
    (r"projects?|personal\s+projects?|key\s+projects?",                             "projects"),
    (r"education|academic\s+background|qualifications",                             "education"),
    (r"certifications?|courses?|training",                                          "certifications"),
    (r"leadership|activities|extracurricular|volunteer|involvement",                "leadership"),
    (r"achievements?|awards?|honors?|accomplishments?",                             "achievements"),
    (r"summary|objective|profile|about",                                            "summary"),
]


def get_chunks(profile: ResumeProfile) -> list[tuple[str, str]]:
    """
    Split raw resume text into (label, text) chunks by detecting section headers.
    Uses raw_text directly instead of re-joining parsed fields, which avoids
    compounding extraction errors from badly-formatted or multi-column PDFs.
    """
    raw = profile.raw_text
    if not raw:
        return []

    # Find every section header (a line that is ONLY the header text, nothing else)
    hits: list[tuple[int, int, str]] = []
    for pattern, label in SECTIONS:
        for m in re.finditer(
            r"^[ \t]*(?:" + pattern + r")[ \t]*[:\-]?[ \t]*$",
            raw,
            re.IGNORECASE | re.MULTILINE,
        ):
            hits.append((m.start(), m.end(), label))

    if not hits:
        # No headers found — return the whole text as a single chunk
        return [("resume", raw.strip())]

    hits.sort(key=lambda x: x[0])

    # Remove overlapping matches (keep the first one at each position)
    deduped: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, label in hits:
        if start >= last_end:
            deduped.append((start, end, label))
            last_end = end

    # Slice the text that falls between consecutive headers
    chunks: list[tuple[str, str]] = []
    for i, (_, end, label) in enumerate(deduped):
        next_start = deduped[i + 1][0] if i + 1 < len(deduped) else len(raw)
        text = raw[end:next_start].strip()
        if len(text) > 30:
            chunks.append((label, text))

    return chunks

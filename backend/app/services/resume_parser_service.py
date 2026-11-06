"""
resume_parser_service.py
------------------------
Splits the plain resume text produced by app/text_extractor.py into labelled
sections and exposes the skills and projects blocks that downstream LLM/agent
context will use instead of resending the whole resume.

This runs at upload time (see api/routes/resume.py) and covers both common
layouts:
  - a header on its own line:        "SKILLS" / "Projects"
  - a header with inline content:    "Skills: Python, SQL, Docker"

Only section text is extracted here. Keyword/entity extraction stays in
app/ml/resume_parser/extractors.py.
"""

import re

# Canonical label -> header spellings. A header may end at the end of the line
# (standalone) or be followed by ':' / '-' and content on the same line.
_SECTION_HEADERS: dict[str, tuple[str, ...]] = {
    "summary": (
        r"(?:professional\s+)?summary",
        r"career\s+objective",
        r"objective",
        r"professional\s+profile",
        r"profile",
        r"about(?:\s+me)?",
    ),
    "skills": (
        r"technical\s+skills?(?:\s*&\s*tools)?",
        r"core\s+(?:competenc(?:y|ies)|skills?)",
        r"key\s+skills?",
        r"professional\s+skills?",
        r"skills?(?:\s*&\s*(?:abilities|competencies))?",
        r"technologies(?:\s+used)?",
        r"tech\s+stack",
        r"areas?\s+of\s+expertise",
        r"proficienc(?:y|ies)",
        r"expertise",
    ),
    "experience": (
        r"(?:work|professional|employment|relevant)\s+(?:experience|history)",
        r"experience",
        r"employment",
        r"career\s+history",
        r"work\s+history",
    ),
    "projects": (
        r"(?:personal|key|academic|selected|major|technical|relevant|side)\s+projects?",
        r"projects?\s+(?:experience|work)",
        r"projects?",
        r"portfolio",
    ),
    "education": (
        r"education(?:al)?\s+background",
        r"education",
        r"academic\s+background",
        r"qualifications",
    ),
    "certifications": (
        r"certifications?",
        r"certificates?",
        r"licenses?",
        r"courses?",
        r"training",
    ),
    "achievements": (
        r"achievements?",
        r"awards?",
        r"honors?",
        r"accomplishments?",
    ),
    "leadership": (
        r"leadership",
        r"activities",
        r"extracurricular(?:\s+activities)?",
        r"volunteer(?:\s+(?:experience|work))?",
        r"involvement",
        r"community\s+service",
    ),
}

_HEADER_PREFIX = r"^(?:#+\s*)?"

_STANDALONE = [
    (label, re.compile(rf"{_HEADER_PREFIX}(?:{pattern})\s*[:\-\u2013\u2014]?\s*$", re.IGNORECASE))
    for label, patterns in _SECTION_HEADERS.items()
    for pattern in patterns
]
_INLINE = [
    (label, re.compile(rf"{_HEADER_PREFIX}(?:{pattern})\s*[:\-\u2013\u2014]\s*(.+)$", re.IGNORECASE))
    for label, patterns in _SECTION_HEADERS.items()
    for pattern in patterns
]

_EXTRACTED_LABELS = ("skills", "projects")


def _match_header(line: str) -> tuple[str, str | None] | None:
    """Return (section label, inline text or None) when `line` is a section header."""
    for label, rx in _STANDALONE:
        if rx.match(line):
            return label, None
    for label, rx in _INLINE:
        m = rx.match(line)
        if m:
            return label, m.group(1).strip()
    return None


def parse_resume_sections(text: str) -> dict[str, str]:
    """
    Split resume text into sections keyed by canonical label. Unknown text
    before the first recognised header is ignored; repeated headers append to
    the same section.
    """
    if not text:
        return {}

    collected: dict[str, list[str]] = {}
    current: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        match = _match_header(line) if line else None
        if match is not None:
            current, inline = match
            collected.setdefault(current, [])
            if inline:
                collected[current].append(inline)
            continue
        if current is not None and line:
            collected[current].append(line)

    return {label: "\n".join(lines).strip() for label, lines in collected.items() if lines}


def extract_skills_and_projects(text: str) -> dict[str, str]:
    """
    Return {"skills": ..., "projects": ...} for the resume. A section that is
    absent comes back as an empty string, so callers can rely on both keys.
    """
    sections = parse_resume_sections(text)
    return {label: sections.get(label, "") for label in _EXTRACTED_LABELS}

"""
resume_service.py
------------------
Resume-upload business logic, pulled out of main.py's upload_resume route.

Note: the original main.py also defined `_build_profile()` and
`_build_category_contexts()` — both are dead code (only called by each other,
never by any route; confirmed by grep during the restructure) and have been
dropped rather than relocated, consistent with deleting scorer.py and
question_selector.py elsewhere in this cleanup.
"""

import re

_RESUME_SECTIONS = {
    "experience": {
        "work experience", "professional experience", "employment history",
        "work history", "experience", "employment",
    },
    "education": {
        "education", "degree", "bachelor", "master", "gpa",
        "university", "college", "b.sc", "m.sc", "b.tech", "m.tech", "graduated",
    },
    "skills": {
        "technical skills", "core skills", "key skills", "skills",
        "competencies", "proficiencies", "technologies",
    },
    "identity": {
        "curriculum vitae", "linkedin", "github.com", "career objective",
        "professional summary",
    },
    "extras": {
        "certifications", "internship", "publications", "volunteer",
        "achievements", "awards",
    },
}


def looks_like_resume(text: str) -> bool:
    """
    Requires three independent signals that only co-occur in resumes:
      1. Contact info  — email address or phone number
      2. Date patterns — year ranges from work/education history
      3. Section depth — keywords from at least 2 distinct resume sections
    Falls back to accepting the file if it has 4+ distinct sections (covers
    rare resumes that omit contact details in the extracted text).
    """
    lower = text.lower()

    has_email = bool(re.search(r'\b[\w.+-]+@[\w-]+\.\w{2,}\b', text))
    has_phone = bool(re.search(r'(\+?\d[\d\s\-().]{7,14}\d)', text))
    has_years = bool(re.search(r'\b(19|20)\d{2}\b', text))

    sections_hit = sum(
        1 for kws in _RESUME_SECTIONS.values()
        if any(kw in lower for kw in kws)
    )

    strong_match = (has_email or has_phone) and has_years and sections_hit >= 2
    fallback     = sections_hit >= 4
    return strong_match or fallback


def guess_name(text: str) -> str:
    """Best-effort: first non-empty line is usually the candidate's name."""
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 5 and not any(c in line for c in "@:/"):
            return line
    return "Candidate"

"""
extractors.py (resume_parser)
--------------------------------
Field extractors: name, title, skills, experience, education, projects.
Regex/keyword-based, with a single spaCy NER fallback inside extract_name()
for the one case regex handles least reliably (names that don't sit cleanly
on their own line in "Title Case Title Case" form).

Text extraction itself (PDF/DOCX/TXT -> raw text) lives in app/text_extractor.py,
not here — the versions that used to be duplicated in this file were dead code
(never imported by main.py) and have been deleted as part of this restructure.
"""

import re
import logging

import spacy

from app.ml.resume_parser.models import ExperienceEntry
from app.ml.resume_parser.skill_taxonomy import KNOWN_SKILLS

logger = logging.getLogger(__name__)

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None


def extract_email(text: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
    return m.group(0) if m else ""


def extract_phone(text: str) -> str:
    m = re.search(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}", text)
    return m.group(0).strip() if m else ""


def extract_name(text: str) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:8]:
        if re.search(r"[@|/\\<>]", line):
            continue
        if len(line.split()) <= 4 and re.match(r"^[A-Z][a-z]+([ \-][A-Z][a-z]+)+$", line):
            return line
    if nlp:
        doc = nlp(text[:500])
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                return ent.text
    return lines[0] if lines else "Candidate"


def extract_title(text: str, name: str) -> str:
    TITLE_KW = [
        "engineer", "developer", "architect", "scientist", "analyst",
        "manager", "lead", "director", "consultant", "specialist",
        "designer", "researcher", "intern", "officer", "head",
        "full stack", "backend", "frontend", "devops", "ml", "ai",
        "data", "software", "cloud", "security", "qa", "product",
    ]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:20]:
        if line == name:
            continue
        if any(kw in line.lower() for kw in TITLE_KW) and len(line.split()) <= 8:
            return line
    return ""


def extract_skills(text: str) -> list[str]:
    found = set()
    lower_text = text.lower()

    # Strategy 1: Skills section block
    skills_section = re.search(
        r"(skills?|technical skills?|core competencies|technologies)[:\s\n]+(.*?)(\n\n|\Z)",
        lower_text,
        re.IGNORECASE | re.DOTALL,
    )
    if skills_section:
        block = skills_section.group(2)
        tokens = re.split(r"[,|\n•·▪▸\-\t]+", block)
        for tok in tokens:
            tok = tok.strip()
            if 2 <= len(tok) <= 40 and not tok.isdigit():
                found.add(tok.title())

    # Strategy 2: Keyword scan
    for kw in KNOWN_SKILLS:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower_text, re.IGNORECASE):
            found.add(kw.title())

    noise = {"And", "Or", "The", "With", "For", "A", "An", "In", "Of"}
    found = {s for s in found if s not in noise and len(s) > 1}
    return sorted(found)


def extract_experience(text: str) -> list[ExperienceEntry]:
    entries = []
    exp_match = re.search(
        r"(work\s+)?experience[:\s\n]+(.*?)(?=\n(education|projects?|skills?|certif|awards?|publications?)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    block = exp_match.group(2) if exp_match else text
    job_splits = re.split(r"\n(?=[A-Z][^\n]{5,60}\n)", block)

    date_pattern = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})"

    for chunk in job_splits:
        lines = [l.strip() for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        role = lines[0]
        company = ""
        duration = ""

        for line in lines[1:4]:
            if re.search(date_pattern, line, re.IGNORECASE):
                duration = line
                continue
            if not line.startswith(("•", "-", "·", "▪")) and len(line.split()) <= 6:
                company = line

        highlights = []
        for line in lines:
            if re.match(r"^[•\-·▪▸]\s*", line):
                clean = re.sub(r"^[•\-·▪▸]\s*", "", line).strip()
                if len(clean) > 20:
                    highlights.append(clean)

        if role and len(role) > 3 and not role.startswith(("•", "-")):
            entries.append(ExperienceEntry(
                role=role,
                company=company,
                duration=duration,
                highlights=highlights[:6],
            ))

    return entries[:6]


def extract_education(text: str) -> list[str]:
    edu_match = re.search(
        r"education[:\s\n]+(.*?)(?=\n(experience|projects?|skills?|certif|awards?)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not edu_match:
        return []
    block = edu_match.group(1)
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    degree_kw = ["bachelor", "master", "phd", "b.s", "m.s", "b.e", "m.e", "mba", "bsc", "msc"]
    return [
        line for line in lines
        if any(kw in line.lower() for kw in degree_kw) or re.search(r"\d{4}", line)
    ][:4]


def extract_projects(text: str) -> list[str]:
    proj_match = re.search(
        r"projects?[:\s\n]+(.*?)(?=\n(experience|education|skills?|certif|awards?)\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not proj_match:
        return []
    block = proj_match.group(1)
    return [
        l.strip() for l in block.split("\n")
        if l.strip() and len(l.strip()) > 10
    ][:8]

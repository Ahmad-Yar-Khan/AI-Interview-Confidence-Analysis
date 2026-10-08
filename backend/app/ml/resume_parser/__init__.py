"""
resume_parser package
----------------------
Re-exports the public API so existing call sites can do:
    from app.ml.resume_parser import ResumeProfile, extract_name, get_chunks, ...
without needing to know the internal module split.
"""

from app.ml.resume_parser.models import ResumeProfile, ExperienceEntry
from app.ml.resume_parser.skill_taxonomy import SKILL_CATEGORY_MAP, KNOWN_SKILLS
from app.ml.resume_parser.extractors import (
    extract_email,
    extract_phone,
    extract_name,
    extract_title,
    extract_skills,
    extract_experience,
    extract_education,
    extract_projects,
)
from app.ml.resume_parser.chunking import get_chunks
from app.ml.resume_parser.weights import compute_category_weights

__all__ = [
    "ResumeProfile",
    "ExperienceEntry",
    "SKILL_CATEGORY_MAP",
    "KNOWN_SKILLS",
    "extract_email",
    "extract_phone",
    "extract_name",
    "extract_title",
    "extract_skills",
    "extract_experience",
    "extract_education",
    "extract_projects",
    "get_chunks",
    "compute_category_weights",
]

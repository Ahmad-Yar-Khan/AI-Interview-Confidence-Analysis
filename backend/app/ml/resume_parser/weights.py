"""
weights.py (resume_parser)
-----------------------------
Computes per-category relevance weights for a parsed resume, used to bias
question selection toward the categories the candidate's resume actually
evidences.
"""

import re

from app.ml.resume_parser.models import ResumeProfile
from app.ml.resume_parser.skill_taxonomy import SKILL_CATEGORY_MAP


def compute_category_weights(profile: ResumeProfile) -> dict:
    full_text = (
        " ".join(profile.skills)
        + " " + " ".join(
            e.role + " " + e.company + " " + " ".join(e.highlights)
            for e in profile.experience
        )
        + " " + " ".join(profile.projects)
        + " " + " ".join(profile.education)
        + " " + profile.title
    ).lower()

    weights = {}
    for category, keywords in SKILL_CATEGORY_MAP.items():
        if category == "HR & Behavioral":
            weights[category] = 0.50   # universal
            continue
        if not keywords:
            weights[category] = 0.10
            continue
        matches = sum(
            1 for kw in keywords
            if re.search(r"\b" + re.escape(kw) + r"\b", full_text)
        )
        weight = min(1.0, 0.10 + (matches / max(len(keywords) * 0.3, 1)) * 0.90)
        weights[category] = round(weight, 3)

    return weights

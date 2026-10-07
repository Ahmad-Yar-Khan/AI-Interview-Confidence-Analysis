"""
question_selector.py
--------------------
Selects tailored interview questions for any parsed resume.

Uses global SBERT FAISS search + post-retrieval diversity constraints.
No keyword pre-filtering — SBERT handles semantic relevance directly.
HR & Behavioral questions are always sampled separately.
"""

import random
import logging

from resume_parser import ResumeProfile
from embedding_engine import EmbeddingEngine
from data_loader import QuestionBank, Question, NULL_ANSWER_CATEGORIES, CATEGORIES

logger = logging.getLogger(__name__)

DEFAULT_TOTAL_QUESTIONS = int(__import__("os").getenv("MAX_QUESTIONS", 12))

HR_RESERVED  = 2
MAX_PER_CAT  = 3   # cap per technical category to ensure breadth


def build_resume_text(profile: ResumeProfile) -> str:
    """Compose resume text for embedding. Title and skills lead for relevance."""
    parts = []
    if profile.title:
        parts.append(profile.title)
    parts += profile.skills
    for exp in profile.experience:
        parts.append(exp.role)
        parts.append(exp.company)
        parts += exp.highlights
    parts += profile.projects
    parts += profile.education
    return " ".join(parts)


def select_questions(
    profile: ResumeProfile,
    bank: QuestionBank,
    engine: EmbeddingEngine,
    total: int = DEFAULT_TOTAL_QUESTIONS,
) -> list[dict]:
    """
    Global FAISS retrieval → post-filter for category diversity + difficulty spread.
    HR questions sampled separately. No keyword pre-filtering.
    """
    tech_slots = total - HR_RESERVED

    resume_vec = engine.embed(build_resume_text(profile))

    # Generous search buffer — diversity constraints will filter it down
    search_k = min(len(bank.questions), tech_slots * 8)
    _, indices = engine.search(resume_vec, top_k=search_k)

    # Soft difficulty caps to avoid all-Easy or all-Hard sets
    max_easy = max(1, round(tech_slots * 0.25))
    max_hard = max(1, round(tech_slots * 0.35))

    cat_counts:  dict[str, int] = {}
    diff_counts: dict[str, int] = {"Easy": 0, "Medium": 0, "Hard": 0}
    tech_selected: list[Question] = []
    seen: set[str] = set()

    for idx in indices:
        if len(tech_selected) >= tech_slots:
            break
        q = bank.questions[idx]
        if q.category in NULL_ANSWER_CATEGORIES:
            continue
        if q.question in seen:
            continue
        if cat_counts.get(q.category, 0) >= MAX_PER_CAT:
            continue
        diff = q.difficulty
        if diff == "Easy" and diff_counts["Easy"] >= max_easy:
            continue
        if diff == "Hard" and diff_counts["Hard"] >= max_hard:
            continue

        tech_selected.append(q)
        seen.add(q.question)
        cat_counts[q.category] = cat_counts.get(q.category, 0) + 1
        diff_counts[diff] = diff_counts.get(diff, 0) + 1

    # Backfill: relax per-category cap if still short
    if len(tech_selected) < tech_slots:
        for idx in indices:
            if len(tech_selected) >= tech_slots:
                break
            q = bank.questions[idx]
            if q.category in NULL_ANSWER_CATEGORIES or q.question in seen:
                continue
            tech_selected.append(q)
            seen.add(q.question)

    # HR: random sample, no embedding needed
    hr_pool = bank.get_by_category("HR & Behavioral")
    hr_selected = random.sample(hr_pool, min(HR_RESERVED, len(hr_pool)))

    all_selected = tech_selected + hr_selected

    logger.info(
        f"Selected {len(all_selected)} questions for '{profile.name}': "
        + ", ".join(
            f"{cat}={sum(1 for q in tech_selected if q.category == cat)}"
            for cat in CATEGORIES
            if any(q.category == cat for q in tech_selected)
        )
    )

    return [
        {**q.to_dict(), "why": _explain_why(q, profile)}
        for q in all_selected
    ]


def _explain_why(q: Question, profile: ResumeProfile) -> str:
    """Short human-readable reason why this question was selected."""
    if q.category in NULL_ANSWER_CATEGORIES:
        return "Universal behavioral question — asked in every interview"

    for skill in profile.skills:
        if skill.lower() in q.combined_text.lower():
            return f"Matched your skill: {skill}"

    for exp in profile.experience:
        for h in exp.highlights:
            words = [w.lower() for w in h.split() if len(w) > 4]
            if any(w in q.combined_text.lower() for w in words):
                return f"Relevant to your role: {exp.role} at {exp.company}"

    return f"Relevant to {q.category}"

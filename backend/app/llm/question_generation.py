"""
question_generation.py
-----------------------
All question-generation functions: category inference, full-resume generation,
dataset-question personalization, and project-question generation (standalone
and combined variants).

Note on what's actually wired into the live app: only generate_questions() and
generate_dataset_and_project_questions() are called from question_service.py
today. infer_categories(), personalize_dataset_questions(), and
generate_project_questions() are complete, working, but currently unwired —
kept here as available capabilities (same category as compute_category_weights
in resume_parser), not deleted, since they aren't broken or duplicated, just
not currently called by any route.
"""

import json
import logging

from app.llm.groq_client import chat, parse_json
from app.llm.prompts import (
    CATEGORY_PROMPT,
    QUESTION_PROMPT,
    QUESTION_PROMPT_FALLBACK,
    PERSONALIZE_PROMPT,
    COMBINED_QUESTION_PROMPT,
    PROJECT_QUESTION_PROMPT,
)

logger = logging.getLogger(__name__)


# ── Category Inference ───────────────────────────────────────

def infer_categories(resume_text: str) -> list[str]:
    prompt = CATEGORY_PROMPT.format(resume_text=resume_text)
    cats   = parse_json(chat(prompt))
    if not isinstance(cats, list):
        raise ValueError("Expected a JSON array of category strings")
    cats = [str(c).strip() for c in cats if str(c).strip()]
    logger.info(f"Groq inferred categories: {cats}")
    return cats[:5]


# ── Question Generation ───────────────────────────────────────

def generate_questions(
    resume_text: str,
    total: int = 12,
    job_context: str = "",
    category_contexts: dict | None = None,
) -> list[dict]:
    job_section = f"TARGET ROLE CONTEXT:\n{job_context.strip()}\n\n" if job_context.strip() else ""

    if category_contexts:
        categories_str = "\n".join(f"  - {cat}" for cat in category_contexts)
        context_blocks = []
        for cat, chunks in category_contexts.items():
            block = f"[{cat}]\n" + "\n".join(f"  • {chunk}" for chunk in chunks)
            context_blocks.append(block)
        category_context_str = "\n\n".join(context_blocks)

        prompt = QUESTION_PROMPT.format(
            total=total,
            tech_total=total - 2,
            job_section=job_section,
            categories_str=categories_str,
            category_context_str=category_context_str,
        )
    else:
        prompt = QUESTION_PROMPT_FALLBACK.format(
            total=total,
            job_section=job_section,
            resume_text=resume_text,
        )

    questions = parse_json(chat(prompt))

    for i, q in enumerate(questions):
        q.setdefault("id", f"q{i+1}")
        q.setdefault("has_answer", q.get("model_answer") is not None)
        q["question_id"] = q["id"]

    logger.info(f"Groq generated {len(questions)} questions")
    return questions


# ── Dataset Question Personalization ─────────────────────────

def personalize_dataset_questions(questions: list[dict], resume_text: str) -> list[dict]:
    if not questions:
        return questions

    questions_json = json.dumps(
        [{"id": q["id"], "question": q["question"], "category": q["category"],
          "difficulty": q["difficulty"], "model_answer": q.get("model_answer")}
         for q in questions],
        indent=2,
    )

    prompt    = PERSONALIZE_PROMPT.format(
        count=len(questions),
        questions_json=questions_json,
        resume_text=resume_text[:3000],
    )
    rewritten = parse_json(chat(prompt))

    id_map = {q["id"]: q for q in questions}
    result = []
    for rq in rewritten:
        original = id_map.get(rq.get("id"), {})
        rq.setdefault("has_answer", True)
        rq["question_id"] = rq.get("id", original.get("id", ""))
        result.append(rq)

    logger.info(f"Personalized {len(result)} dataset questions")
    return result


# ── Combined: Personalize dataset questions + generate project questions ──────

def generate_dataset_and_project_questions(
    dataset_qs: list[dict],
    projects_text: str,
    resume_text: str,
    project_count: int = 4,
) -> tuple[list[dict], list[dict]]:
    questions_json = json.dumps(
        [{"id": q["id"], "question": q["question"], "category": q["category"],
          "difficulty": q["difficulty"], "model_answer": q.get("model_answer")}
         for q in dataset_qs],
        indent=2,
    )

    prompt = COMBINED_QUESTION_PROMPT.format(
        dataset_count=len(dataset_qs),
        project_count=project_count,
        questions_json=questions_json,
        resume_text=resume_text[:3000],
        projects_text=projects_text,
    )
    result = parse_json(chat(prompt))

    out_dataset = result.get("dataset", [])
    out_project = result.get("project", [])

    for i, q in enumerate(out_dataset):
        q.setdefault("has_answer", True)
        fallback_id = dataset_qs[i]["id"] if i < len(dataset_qs) else f"ds{i+1}"
        q.setdefault("id", fallback_id)
        q["question_id"] = q["id"]

    for i, q in enumerate(out_project):
        q.setdefault("id", f"p{i+1}")
        q.setdefault("has_answer", True)
        q.setdefault("model_answer", None)
        q["question_id"] = q["id"]

    logger.info(
        f"Combined generation: {len(out_dataset)} personalized dataset "
        f"+ {len(out_project)} project questions"
    )
    return out_dataset, out_project


# ── Project Question Generation ───────────────────────────────

def generate_project_questions(
    projects_text: str,
    count: int = 4,
    already_covered: list[str] | None = None,
) -> list[dict]:
    if already_covered:
        covered_lines = "\n".join(f"  - {q}" for q in already_covered)
        avoid_section = (
            f"ALREADY COVERED — do NOT ask about these topics or overlap with these questions:\n"
            f"{covered_lines}\n\n"
        )
    else:
        avoid_section = ""

    prompt    = PROJECT_QUESTION_PROMPT.format(
        count=count,
        projects_text=projects_text,
        avoid_section=avoid_section,
    )
    questions = parse_json(chat(prompt))

    for i, q in enumerate(questions):
        q.setdefault("id", f"p{i+1}")
        q.setdefault("has_answer", True)
        q.setdefault("model_answer", None)
        q["question_id"] = q["id"]

    logger.info(f"Groq generated {len(questions)} project questions")
    return questions

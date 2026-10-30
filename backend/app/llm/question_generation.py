"""
question_generation.py
-----------------------
All question-generation functions: category inference, full-resume generation,
dataset-question personalization, and project-question generation (standalone
and combined variants).

Note on what's actually wired into the live app: generate_interview_questions()
and generate_questions() (fallback) are called from question_service.py, and
generate_followup() from followup_service.py. infer_categories(),
personalize_dataset_questions(), and generate_project_questions() are
complete, working, but currently unwired —
kept here as available capabilities (same category as compute_category_weights
in resume_parser), not deleted, since they aren't broken or duplicated, just
not currently called by any route.
"""

import json
import logging
import re

from app.llm.groq_client import chat, parse_json
from app.llm.validation import (
    CLAIMS_ABOUT_CANDIDATE, FollowupRejected, neutralize, output_problem, unsupported_details,
)
from app.llm.prompts import (
    INTERVIEWER_SYSTEM_PROMPT,
    CATEGORY_PROMPT,
    QUESTION_PROMPT,
    QUESTION_PROMPT_FALLBACK,
    PERSONALIZE_PROMPT,
    BASE_QUESTION_PROMPT,
    FOLLOWUP_PROMPT,
    PROJECT_QUESTION_PROMPT,
)

logger = logging.getLogger(__name__)


# ── Category Inference ───────────────────────────────────────

async def infer_categories(resume_text: str) -> list[str]:
    prompt = CATEGORY_PROMPT.format(resume_text=resume_text)
    cats   = parse_json(await chat(prompt))
    if not isinstance(cats, list):
        raise ValueError("Expected a JSON array of category strings")
    cats = [str(c).strip() for c in cats if str(c).strip()]
    logger.info(f"Groq inferred categories: {cats}")
    return cats[:5]


# ── Question Generation ───────────────────────────────────────

async def generate_questions(
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

    questions = parse_json(await chat(prompt, system=INTERVIEWER_SYSTEM_PROMPT, temperature=0.3))

    for i, q in enumerate(questions):
        q.setdefault("id", f"q{i+1}")
        q.setdefault("has_answer", q.get("model_answer") is not None)
        q["question_id"] = q["id"]

    logger.info(f"Groq generated {len(questions)} questions")
    return questions


# ── Dataset Question Personalization ─────────────────────────

async def personalize_dataset_questions(questions: list[dict], resume_text: str) -> list[dict]:
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
    rewritten = parse_json(await chat(prompt))

    id_map = {q["id"]: q for q in questions}
    result = []
    for rq in rewritten:
        original = id_map.get(rq.get("id"), {})
        rq.setdefault("has_answer", True)
        rq["question_id"] = rq.get("id", original.get("id", ""))
        result.append(rq)

    logger.info(f"Personalized {len(result)} dataset questions")
    return result


# ── Interview questions (the live path) ──────────────────────

_VALID_DIFFICULTY = {"Easy", "Medium", "Hard"}
MAX_FOLLOWUP_WORDS = 45   # the prompt asks for 40; a little slack before rejecting

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", text.lower()).strip()


def _evidence_supported(evidence, source_norm: str) -> bool:
    """The quoted evidence must really appear in the material the model was given."""
    if not isinstance(evidence, str):
        return False
    e = _norm(evidence)
    return len(e) >= 8 and e in source_norm


def _mix_rules(count: int, has_role: bool) -> str:
    """Prompt text describing the question mix. Without a job title there are no general 'role' questions."""
    if not has_role:
        return (
            f'- All {count} questions are about the candidate\'s own work: projects, work experience, or skills '
            f'they list (kind "resume"). You may test the fundamentals of a skill they list, quoting that part '
            f'of the resume as evidence.'
        )
    n_role = 2 if count >= 4 else 1
    return (
        f'- {count - n_role} questions about the candidate\'s own work: projects, work experience, or skills they '
        f'list (kind "resume").\n'
        f'- {n_role} question(s) on core fundamentals of the target role, pitched at the candidate\'s experience '
        f'level (kind "role"). You may draw topics from the role brief.'
    )


async def generate_interview_questions(
    resume_text: str,
    role_context: str,
    has_role: bool,
    count: int = 5,
) -> list[dict]:
    """
    Ask Groq for the opening questions, working from the WHOLE resume (not just
    the projects section) plus the role context (job title, years of
    experience, research brief).

    Anti-hallucination is enforced in code, not just in the prompt:
      - "resume" questions must carry an `evidence` quote found in the resume,
        and every name / technology / acronym / number in the question must
        itself appear in the resume (validation.unsupported_details);
      - "role" questions are only accepted when a job title was chosen, and are
        dropped if they claim anything about the candidate;
      - all questions are screened for URLs, code fences and injection phrasing.
    Returns at most `count` verified questions (possibly fewer — the caller retries).
    """
    resume = neutralize(resume_text.strip()[:7000], "resume")
    source_norm = _norm(resume)
    mix = _mix_rules(count, has_role)

    prompt = BASE_QUESTION_PROMPT.format(
        role_context=role_context,
        count=count,
        mix_rules=mix,
        candidate_material=f"<resume>\n{resume}\n</resume>",
    )
    raw = parse_json(await chat(prompt, system=INTERVIEWER_SYSTEM_PROMPT, temperature=0.3))
    if not isinstance(raw, list):
        raise ValueError("Expected a JSON array of questions")

    out: list[dict] = []
    for q in raw:
        if not isinstance(q, dict) or not isinstance(q.get("question"), str) or not q["question"].strip():
            continue
        text = " ".join(q["question"].split())
        model_answer = q.get("model_answer") if isinstance(q.get("model_answer"), str) else None
        kind = q.get("kind", "resume")

        problem = output_problem(text, model_answer)
        if not problem and kind == "role":
            if not has_role:
                problem = "general role question but no job title was chosen"
            elif CLAIMS_ABOUT_CANDIDATE.search(text):
                problem = "general role question makes a claim about the candidate"
        elif not problem:
            if not _evidence_supported(q.get("evidence"), source_norm):
                problem = "evidence quote not found in the resume"
            else:
                invented = unsupported_details(text, resume)
                if invented:
                    problem = f"mentions details not in the resume: {invented}"
        if problem:
            logger.info(f"Dropped question ({problem}): {text[:80]!r}")
            continue

        out.append({
            "question":     text,
            "category":     (q.get("category") or "General").strip()[:40],
            "difficulty":   q["difficulty"] if q.get("difficulty") in _VALID_DIFFICULTY else "Medium",
            "model_answer": model_answer[:800] if model_answer else None,
            "has_answer":   True,
            "is_followup":  False,
        })
        if len(out) >= count:
            break

    logger.info(f"Groq generated {len(raw)} questions, {len(out)} passed grounding checks")
    return out


# ── Follow-up generation ─────────────────────────────────────

async def generate_followup(
    question: str,
    answer: str,
    score: int,
    feedback: str,
    years: int | None = None,
) -> dict:
    """One follow-up for a weak answer, based only on the question and what was said."""
    experience_line = (
        f"The candidate has {years} year{'s' if years != 1 else ''} of experience.\n\n"
        if years is not None else ""
    )
    prompt = FOLLOWUP_PROMPT.format(
        experience_line=experience_line,
        score=score,
        question=neutralize(question, "question", "answer", "scorer_feedback"),
        answer=neutralize(answer.strip()[:3000], "question", "answer", "scorer_feedback"),
        feedback=neutralize((feedback or "none").strip()[:500], "question", "answer", "scorer_feedback"),
    )
    result = parse_json(await chat(prompt, system=INTERVIEWER_SYSTEM_PROMPT, temperature=0.4))
    if not isinstance(result, dict) or not isinstance(result.get("question"), str) or not result["question"].strip():
        raise FollowupRejected("no question returned")

    text = " ".join(result["question"].split())
    model_answer = result.get("model_answer") if isinstance(result.get("model_answer"), str) else None

    problem = output_problem(text, model_answer, max_question_chars=300)
    if not problem and len(text.split()) > MAX_FOLLOWUP_WORDS:
        problem = f"longer than {MAX_FOLLOWUP_WORDS} words"
    if not problem:
        # A follow-up may only build on what was asked and said — no new names, technologies or numbers.
        invented = unsupported_details(text, question + "\n" + answer)
        if invented:
            problem = f"introduces details not in the question or answer: {invented}"
    if problem:
        raise FollowupRejected(problem)

    return {
        "question":     text,
        "difficulty":   result["difficulty"] if result.get("difficulty") in _VALID_DIFFICULTY else None,
        "model_answer": model_answer[:800] if model_answer else None,
    }


# ── Project Question Generation ───────────────────────────────

async def generate_project_questions(
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
    questions = parse_json(await chat(prompt))

    for i, q in enumerate(questions):
        q.setdefault("id", f"p{i+1}")
        q.setdefault("has_answer", True)
        q.setdefault("model_answer", None)
        q["question_id"] = q["id"]

    logger.info(f"Groq generated {len(questions)} project questions")
    return questions

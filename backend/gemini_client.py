"""
gemini_client.py
----------------
LLM wrapper — backed by Groq (llama-3.3-70b-versatile).
Public API is identical to the original Gemini version so no other file changes.

Requires env var: GROQ_API_KEY
Optional env var: GROQ_MODEL  (default: llama-3.3-70b-versatile)
"""

import os
import re
import json
import logging

from groq import Groq

logger = logging.getLogger(__name__)

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _chat(prompt: str) -> str:
    """Send a single user-turn prompt and return the raw text response."""
    response = _client.chat.completions.create(
        model=_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content


def _parse_json(text: str):
    """Strip markdown fences and parse JSON from the model response."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text.strip())


# ── Category Inference ───────────────────────────────────────

_CATEGORY_PROMPT = """Read this resume and return the 3 to 5 most relevant technical interview categories for this candidate.

Choose categories that are clearly evidenced by skills, projects, or work experience in the resume.
Use specific real interview domain names such as:
Machine Learning, Backend Engineering, Frontend Engineering, System Design,
SQL & Databases, Cloud & DevOps, Data Structures & Algorithms, Computer Networks,
Operating Systems, Distributed Systems, Concurrency, Cybersecurity, Data Engineering, etc.

Return ONLY a valid JSON array of strings, no explanation, no markdown fences.
Example: ["Machine Learning", "Backend Engineering", "System Design"]

RESUME:
{resume_text}
"""

def infer_categories(resume_text: str) -> list[str]:
    prompt = _CATEGORY_PROMPT.format(resume_text=resume_text)
    cats   = _parse_json(_chat(prompt))
    if not isinstance(cats, list):
        raise ValueError("Expected a JSON array of category strings")
    cats = [str(c).strip() for c in cats if str(c).strip()]
    logger.info(f"Groq inferred categories: {cats}")
    return cats[:5]


# ── Question Generation ───────────────────────────────────────

_QUESTION_PROMPT = """You are an expert technical interviewer generating questions for a specific candidate.

{job_section}CATEGORIES TO COVER:
{categories_str}
Always include 2 HR & Behavioral questions (open-ended, no model answer needed).

RETRIEVED RESUME CONTEXT — the most relevant sections for each category (retrieved via semantic similarity):
{category_context_str}

RULES:
- Reference the candidate's actual projects, companies, numbers, and technologies shown above
- Do NOT ask generic textbook questions — ask about what THIS candidate specifically has done
- Difficulty: ~25% Easy, 50% Medium, 25% Hard
- For technical questions: write a concise model answer (2-4 sentences)
- For HR & Behavioral: model_answer = null, has_answer = false
- Spread {tech_total} questions across the listed categories + 2 HR & Behavioral

Return ONLY a valid JSON array of exactly {total} questions. Each element:
{{
  "id": "q1",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "..." or null,
  "has_answer": true or false
}}
"""

_QUESTION_PROMPT_FALLBACK = """You are an expert technical interviewer.
Generate exactly {total} interview questions tailored specifically to this candidate.
{job_section}
RULES:
- Every question must relate directly to something in the resume
- Mix: technical depth, system design, behavioral, experience-based
- Difficulty: ~25% Easy, 50% Medium, 25% Hard
- For technical questions: write a concise model answer (2-4 sentences)
- For behavioral questions: model_answer = null, has_answer = false
- Include 2 HR & Behavioral questions

Return ONLY a valid JSON array of exactly {total} questions. Each element:
{{
  "id": "q1",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "..." or null,
  "has_answer": true or false
}}

RESUME:
{resume_text}
"""

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

        prompt = _QUESTION_PROMPT.format(
            total=total,
            tech_total=total - 2,
            job_section=job_section,
            categories_str=categories_str,
            category_context_str=category_context_str,
        )
    else:
        prompt = _QUESTION_PROMPT_FALLBACK.format(
            total=total,
            job_section=job_section,
            resume_text=resume_text,
        )

    questions = _parse_json(_chat(prompt))

    for i, q in enumerate(questions):
        q.setdefault("id", f"q{i+1}")
        q.setdefault("has_answer", q.get("model_answer") is not None)
        q["question_id"] = q["id"]

    logger.info(f"Groq generated {len(questions)} questions")
    return questions


# ── Dataset Question Personalization ─────────────────────────

_PERSONALIZE_PROMPT = """You are a technical interviewer preparing a personalized interview for a specific candidate.

Below are {count} template questions retrieved from a question bank. They define the TOPIC and DIFFICULTY to cover — but they are generic. Your job is to rewrite each one so it references something concrete from this candidate's resume: a specific project, technology choice, tool, or experience they actually have.

RULES:
- Keep the core concept of the template question (do not change the topic)
- Reference the candidate's actual work — name their project, the specific library they used, a decision they made
- If no specific resume detail maps cleanly, ask the concept in the context of their most relevant project
- Rewrite the model answer to reflect the candidate's context too (2–3 sentences)
- Preserve the original difficulty and category
- Return exactly {count} questions — one personalized rewrite per template

Return ONLY a valid JSON array of exactly {count} questions. Each element:
{{
  "id": "<keep original id>",
  "question": "<personalized question>",
  "category": "<keep original category>",
  "difficulty": "<keep original difficulty>",
  "model_answer": "<context-aware model answer>",
  "has_answer": true
}}

TEMPLATE QUESTIONS:
{questions_json}

CANDIDATE RESUME:
{resume_text}
"""

def personalize_dataset_questions(questions: list[dict], resume_text: str) -> list[dict]:
    if not questions:
        return questions

    questions_json = json.dumps(
        [{"id": q["id"], "question": q["question"], "category": q["category"],
          "difficulty": q["difficulty"], "model_answer": q.get("model_answer")}
         for q in questions],
        indent=2,
    )

    prompt    = _PERSONALIZE_PROMPT.format(
        count=len(questions),
        questions_json=questions_json,
        resume_text=resume_text[:3000],
    )
    rewritten = _parse_json(_chat(prompt))

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

_COMBINED_QUESTION_PROMPT = """You are a technical interviewer preparing a personalized interview for a specific candidate.

Complete TWO tasks in a single response:

━━━ TASK 1 — Personalize {dataset_count} template questions ━━━
Rewrite each template question to reference something specific from this candidate's resume.
- Keep the core concept, category, and difficulty unchanged
- Reference the candidate's actual project, technology used, or decision made
- Update the model answer to reflect the candidate's context (2–3 sentences)
- Preserve the original id

━━━ TASK 2 — Generate {project_count} new project questions ━━━
Write {project_count} new questions based strictly on the PROJECTS section below.
- Each must target a specific technical decision or implementation detail from a named project
- Do NOT overlap in topic with the template questions above
- Use ids "p1", "p2", etc.
- Assign the most fitting category (e.g. "Backend Engineering", "System Design", "Databases")
- Model answer: 2–3 sentences grounded in the project detail
- has_answer: true for all

Return ONLY a valid JSON object — no explanation, no markdown fences:
{{
  "dataset": [ ],
  "project": [ ]
}}

Each question element (both arrays use the same shape):
{{
  "id": "...",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "...",
  "has_answer": true
}}

TEMPLATE QUESTIONS — Task 1:
{questions_json}

RESUME:
{resume_text}

PROJECTS — Task 2:
{projects_text}
"""

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

    prompt = _COMBINED_QUESTION_PROMPT.format(
        dataset_count=len(dataset_qs),
        project_count=project_count,
        questions_json=questions_json,
        resume_text=resume_text[:3000],
        projects_text=projects_text,
    )
    result = _parse_json(_chat(prompt))

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

_PROJECT_QUESTION_PROMPT = """You are a technical interviewer preparing questions based on a candidate's project work.

Generate exactly {count} interview questions. Each question must target a specific technical decision, implementation detail, or challenge from one of the projects below — not a generic concept.

RULES:
- Reference a concrete detail from the project (a technology chosen, a problem solved, an architectural tradeoff)
- Write a model answer of 2–3 sentences based on what is described in the projects
- Difficulty mix: roughly half Medium, the rest split between Easy and Hard
- Assign the most fitting technical category (e.g. "Machine Learning", "Backend Engineering", "System Design", "Databases")
{avoid_section}
Return ONLY a valid JSON array of exactly {count} questions. Each element:
{{
  "id": "p1",
  "question": "...",
  "category": "...",
  "difficulty": "Easy" | "Medium" | "Hard",
  "model_answer": "...",
  "has_answer": true
}}

PROJECTS:
{projects_text}
"""

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

    prompt    = _PROJECT_QUESTION_PROMPT.format(
        count=count,
        projects_text=projects_text,
        avoid_section=avoid_section,
    )
    questions = _parse_json(_chat(prompt))

    for i, q in enumerate(questions):
        q.setdefault("id", f"p{i+1}")
        q.setdefault("has_answer", True)
        q.setdefault("model_answer", None)
        q["question_id"] = q["id"]

    logger.info(f"Groq generated {len(questions)} project questions")
    return questions


# ── Answer Scoring ────────────────────────────────────────────

_SCORE_PROMPT = """You are evaluating a candidate's interview answer. Be fair but rigorous.

Question: {question}
Category: {category}
{answer_context}
Candidate's Answer: {user_answer}

Score the answer and return ONLY a valid JSON object, no explanation, no markdown fences:
{{
  "overall": <integer 0-100>,
  "is_behavioral": <true or false>,
  "angles": {{
    "conceptual": <integer 0-100>,
    "technical": <integer 0-100>,
    "completeness": <integer 0-100>
  }},
  "feedback": "<1-2 sentences of constructive feedback>"
}}

Scoring guide:
- For TECHNICAL questions (has model answer): score conceptual correctness, technical accuracy, and completeness vs the expected answer.
- For BEHAVIORAL questions (no model answer): score on effort/detail (conceptual), use of specific examples (technical), and STAR structure (completeness).
- overall should reflect the weighted combination of the three angles.
"""

def score_answer(
    question: str,
    model_answer: str | None,
    user_answer: str,
    category: str,
) -> dict:
    if model_answer and str(model_answer).strip().upper() not in ("", "NULL", "NONE", "NAN"):
        answer_context = f"Expected Answer: {model_answer}"
        is_behavioral_hint = "false"
    else:
        answer_context = "This is a behavioral question — there is no model answer."
        is_behavioral_hint = "true"

    prompt = _SCORE_PROMPT.format(
        question=question,
        category=category,
        answer_context=answer_context,
        user_answer=user_answer,
    )

    result = _parse_json(_chat(prompt))

    result.setdefault("overall", 0)
    result.setdefault("is_behavioral", is_behavioral_hint == "true")
    result.setdefault("angles", {"conceptual": 0, "technical": 0, "completeness": 0})
    result.setdefault("feedback", "")

    result["overall"] = max(0, min(100, int(result["overall"])))
    for k in result["angles"]:
        result["angles"][k] = max(0, min(100, int(result["angles"][k])))

    logger.info(f"Groq scored answer: overall={result['overall']}")
    return result

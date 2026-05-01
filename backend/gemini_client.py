"""
gemini_client.py
----------------
Gemini API wrapper for two tasks:
  1. generate_questions(resume_text, total) -> list of question dicts
  2. score_answer(question, model_answer, user_answer, category) -> score dict

Requires env var: GEMINI_API_KEY
Optional env var: GEMINI_MODEL  (default: gemini-1.5-flash)
"""

import os
import re
import json
import logging

import google.generativeai as genai

logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _model() -> genai.GenerativeModel:
    return genai.GenerativeModel(_MODEL_NAME)


def _parse_json(text: str):
    """Strip markdown fences and parse JSON from Gemini's response."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text.strip())


# ── Question Generation ───────────────────────────────────────

_QUESTION_PROMPT = """You are an expert technical interviewer. I will give you a candidate's resume.
Generate exactly {total} interview questions tailored specifically to this candidate.

RULES:
- Every question must relate directly to something in the resume (a skill, project, technology, role, or achievement)
- Mix question types: technical depth, system design, behavioral, experience-based
- Difficulty distribution: roughly 25% Easy, 50% Medium, 25% Hard
- For technical/experience questions: write a concise model answer (2-4 sentences)
- For behavioral questions: set model_answer to null and has_answer to false
- Use these categories only: "Technical Skills", "System Design", "Behavioral", "Problem Solving", "Domain Knowledge"

Return ONLY a valid JSON array, no explanation, no markdown fences.
Each element must have exactly these fields:
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

def generate_questions(resume_text: str, total: int = 12) -> list[dict]:
    prompt = _QUESTION_PROMPT.format(total=total, resume_text=resume_text)
    response = _model().generate_content(prompt)
    questions = _parse_json(response.text)

    # Normalise fields the rest of the app expects
    for i, q in enumerate(questions):
        q.setdefault("id", f"q{i+1}")
        q.setdefault("has_answer", q.get("model_answer") is not None)
        q["question_id"] = q["id"]

    logger.info(f"Gemini generated {len(questions)} questions")
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

    response = _model().generate_content(prompt)
    result = _parse_json(response.text)

    # Ensure all required fields exist with safe defaults
    result.setdefault("overall", 0)
    result.setdefault("is_behavioral", is_behavioral_hint == "true")
    result.setdefault("angles", {"conceptual": 0, "technical": 0, "completeness": 0})
    result.setdefault("feedback", "")

    # Clamp all scores to 0-100
    result["overall"] = max(0, min(100, int(result["overall"])))
    for k in result["angles"]:
        result["angles"][k] = max(0, min(100, int(result["angles"][k])))

    logger.info(f"Gemini scored answer: overall={result['overall']}")
    return result

"""
answer_scoring.py
------------------
LLM-based answer scoring — the live scoring path (api/routes/scoring.py calls
score_answer() here). Unrelated to the classical TF-IDF/keyword scorer.py that
used to sit in backend/ root; that file was dead code (never imported by
main.py) and has been deleted rather than relocated.
"""

import logging

from app.llm.groq_client import chat, parse_json
from app.llm.prompts import SCORE_PROMPT

logger = logging.getLogger(__name__)


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

    prompt = SCORE_PROMPT.format(
        question=question,
        category=category,
        answer_context=answer_context,
        user_answer=user_answer,
    )

    result = parse_json(chat(prompt))

    result.setdefault("overall", 0)
    result.setdefault("is_behavioral", is_behavioral_hint == "true")
    result.setdefault("angles", {"conceptual": 0, "technical": 0, "completeness": 0})
    result.setdefault("feedback", "")

    result["overall"] = max(0, min(100, int(result["overall"])))
    for k in result["angles"]:
        result["angles"][k] = max(0, min(100, int(result["angles"][k])))

    logger.info(f"Groq scored answer: overall={result['overall']}")
    return result

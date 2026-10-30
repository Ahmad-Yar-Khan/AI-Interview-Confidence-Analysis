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
from app.llm.prompts import SCORE_PROMPT, SCORER_SYSTEM_PROMPT
from app.llm.validation import has_injection, neutralize

logger = logging.getLogger(__name__)


async def score_answer(
    question: str,
    model_answer: str | None,
    user_answer: str,
    category: str,
) -> dict:
    if model_answer and str(model_answer).strip().upper() not in ("", "NULL", "NONE", "NAN"):
        answer_context = "<expected_answer>\n" + neutralize(str(model_answer), "expected_answer") + "\n</expected_answer>"
        is_behavioral_hint = "false"
    else:
        answer_context = "This is a behavioral question — there is no model answer."
        is_behavioral_hint = "true"

    prompt = SCORE_PROMPT.format(
        question=neutralize(question, "question"),
        category=category,
        answer_context=answer_context,
        user_answer=neutralize(user_answer, "candidate_answer"),
    )

    result = parse_json(await chat(prompt, system=SCORER_SYSTEM_PROMPT, temperature=0.2))

    result.setdefault("overall", 0)
    result.setdefault("is_behavioral", is_behavioral_hint == "true")
    result.setdefault("angles", {"conceptual": 0, "technical": 0, "completeness": 0})
    result.setdefault("feedback", "")

    result["overall"] = max(0, min(100, int(result["overall"])))
    for k in result["angles"]:
        result["angles"][k] = max(0, min(100, int(result["angles"][k])))

    # An answer that tries to instruct the grader earns no credit, whatever the model made of it.
    if has_injection(user_answer):
        result["overall"] = min(result["overall"], 20)
        result["angles"] = {k: min(v, 20) for k, v in result["angles"].items()}
        result["feedback"] = (result["feedback"] + " The answer tried to influence the scoring, so it was capped.").strip()
        logger.warning("Answer contained instruction-override phrasing; score capped at 20.")

    logger.info(f"Groq scored answer: overall={result['overall']}")
    return result

"""
scoring.py (route)
--------------------
POST /api/score — Score one answer via Groq.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.answer import AnswerPayload, ScoreResponse
from app.llm import score_answer
from app.services.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/score", response_model=ScoreResponse)
def score_answer_route(payload: AnswerPayload):
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")
    if not payload.user_answer.strip():
        raise HTTPException(400, "Answer cannot be empty.")

    model_text = None if not payload.has_answer else payload.model_answer

    try:
        result = score_answer(
            question=payload.question_text,
            model_answer=model_text,
            user_answer=payload.user_answer,
            category=payload.category,
        )
    except Exception as e:
        logger.exception("Scoring failed")
        raise HTTPException(500, f"Gemini scoring failed: {str(e)}")

    answer_record = {
        "question_id":  payload.question_id,
        "question":     payload.question_text,
        "category":     payload.category,
        "difficulty":   payload.difficulty,
        "has_answer":   payload.has_answer,
        "user_answer":  payload.user_answer,
        "model_answer": payload.model_answer,
        "score": {
            "overall":       result["overall"],
            "is_behavioral": result["is_behavioral"],
            "angles":        result["angles"],
            "feedback":      result.get("feedback", ""),
        },
    }

    idx = next(
        (i for i, a in enumerate(session["answers"]) if a["question_id"] == payload.question_id),
        None,
    )
    if idx is not None:
        session["answers"][idx] = answer_record
    else:
        session["answers"].append(answer_record)

    return ScoreResponse(
        question_id=payload.question_id,
        overall=result["overall"],
        is_behavioral=result["is_behavioral"],
        angles=result["angles"],
        model_answer=payload.model_answer,
        feedback=result.get("feedback", ""),
    )

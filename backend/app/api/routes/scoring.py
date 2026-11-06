"""
scoring.py (route)
--------------------
POST /api/score — Score one answer via Groq.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.answer import AnswerPayload, ScoreResponse
from app.llm.agents.evaluations import evaluate_answer
from app.services import followup_service
from app.services.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_score_result(evaluation: dict) -> dict:
    """Map the 0-10 rubric evaluation onto the existing 0-100 response shape."""
    score = max(0, min(10, int(evaluation.get("score", 0))))
    criteria = evaluation.get("criteria") or {}

    def criterion(name: str) -> int:
        return max(0, min(10, int(criteria.get(name, score))))

    overall = score * 10
    angles = {
        "conceptual": criterion("correctness") * 10,
        "technical": criterion("depth") * 10,
        "completeness": criterion("completeness") * 10,
    }

    feedback = str(evaluation.get("feedback") or "").strip()
    improvements = [
        str(item).strip()
        for item in (evaluation.get("improvements") or [])
        if str(item).strip()
    ]
    if score < 6 and improvements:
        feedback = (feedback + " To improve: " + "; ".join(improvements)).strip()

    return {
        "overall": overall,
        "is_behavioral": bool(evaluation.get("is_behavioral")),
        "angles": angles,
        "feedback": feedback,
        "evaluation_score": score,
        "evaluation_improvements": improvements if score < 6 else [],
        "criteria": criteria,
    }


@router.post("/api/score", response_model=ScoreResponse)
async def score_answer_route(payload: AnswerPayload):
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")
    if not payload.user_answer.strip():
        raise HTTPException(400, "Answer cannot be empty.")

    model_text = None if not payload.has_answer else payload.model_answer

    try:
        evaluation = await evaluate_answer(
            question=payload.question_text,
            model_answer=model_text,
            user_answer=payload.user_answer,
            category=payload.category,
            difficulty=payload.difficulty,
        )
    except Exception as e:
        logger.exception("Evaluation failed")
        raise HTTPException(500, f"Answer evaluation failed: {str(e)}")

    result = _to_score_result(evaluation)

    question = next((q for q in session["questions"] if q.get("id") == payload.question_id), {})

    answer_record = {
        "question_id":  payload.question_id,
        "is_followup":  bool(question.get("is_followup")),
        "parent_id":    question.get("parent_id"),
        "question":     payload.question_text,
        "category":     payload.category,
        "difficulty":   payload.difficulty,
        "has_answer":   payload.has_answer,
        "user_answer":  payload.user_answer,
        "model_answer": payload.model_answer,
        "score": {
            "overall":                 result["overall"],
            "is_behavioral":           result["is_behavioral"],
            "angles":                  result["angles"],
            "feedback":                result.get("feedback", ""),
            "evaluation_score":        result.get("evaluation_score"),
            "evaluation_improvements": result.get("evaluation_improvements", []),
            "criteria":                result.get("criteria", {}),
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
        followup_eligible=followup_service.would_follow_up(session, answer_record),
        question_id=payload.question_id,
        overall=result["overall"],
        is_behavioral=result["is_behavioral"],
        angles=result["angles"],
        model_answer=payload.model_answer,
        feedback=result.get("feedback", ""),
        evaluation_score=result.get("evaluation_score"),
        evaluation_improvements=result.get("evaluation_improvements", []),
        criteria=result.get("criteria", {}),
    )

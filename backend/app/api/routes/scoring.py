"""
scoring.py (route)
--------------------
POST /api/score — Score one answer via Groq.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.answer import AnswerPayload, ScoreResponse
from app.core.config import settings
from app.llm.agents.evaluations import run_evaluation_flow
from app.services.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()

_PLACEHOLDER_ANSWER = "[voice response]"
MAX_INTERVIEW_QUESTIONS = settings.INTERVIEW_MAX_QUESTIONS


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


def _question_depth(session: dict, question_id: str) -> int:
    """Depth of a question in its follow-up chain: base=0, first follow-up=1, ..."""
    by_id = {q.get("id"): q for q in session.get("questions", [])}
    current = by_id.get(question_id)
    depth = 0
    seen: set[str] = set()

    while current and current.get("is_followup") and current.get("parent_id"):
        current_id = current.get("id")
        if current_id in seen or depth >= 10:
            break
        seen.add(current_id)
        depth += 1
        current = by_id.get(current.get("parent_id"))

    return depth


def _has_followup_for(session: dict, question_id: str) -> bool:
    return any(
        q.get("is_followup") and q.get("parent_id") == question_id
        for q in session.get("questions", [])
    )


def _followup_cap(session: dict, payload: AnswerPayload) -> tuple[bool, bool]:
    """Return (allowed, uses_overflow) for a follow-up under the question cap.

    The cap counts every question in the interview. When the queue is already at
    the cap, the last question may still spawn exactly one follow-up (the
    overflow slot); nothing else is added afterwards.
    """
    state = session.setdefault("followups", {})
    storage_total = len(session.get("questions", []))
    queue_total = payload.queue_length if payload.queue_length is not None else storage_total

    if storage_total < MAX_INTERVIEW_QUESTIONS and queue_total < MAX_INTERVIEW_QUESTIONS:
        return True, False

    is_last = (
        payload.queue_length is not None
        and payload.question_position is not None
        and payload.question_position == payload.queue_length - 1
    )
    overflow_used = bool(state.get("overflow_used"))
    uses_overflow = (
        storage_total == MAX_INTERVIEW_QUESTIONS
        and queue_total == MAX_INTERVIEW_QUESTIONS
        and is_last
        and not overflow_used
    )
    return uses_overflow, uses_overflow


def _append_followup(
    session: dict,
    question: dict,
    question_id: str,
    text: str,
    depth: int,
    allow_overflow: bool = False,
) -> dict | None:
    state = session.setdefault("followups", {})
    state.setdefault("count", 0)
    state.setdefault("next_id", 1)
    state.setdefault("depth", {})
    state.setdefault("by_parent", {})
    state.setdefault("pending", set())
    state.setdefault("overflow_used", False)

    total = len(session.get("questions", []))
    if total >= MAX_INTERVIEW_QUESTIONS:
        if not allow_overflow or state["overflow_used"] or total >= MAX_INTERVIEW_QUESTIONS + 1:
            logger.info(
                f"Question cap ({MAX_INTERVIEW_QUESTIONS}) reached; not adding a follow-up."
            )
            return None
        state["overflow_used"] = True

    followup_id = f"f{state['next_id']}"
    state["next_id"] += 1
    state["count"] += 1

    record = {
        "id":          followup_id,
        "question_id": followup_id,
        "question":    text,
        "category":    question.get("category") or "General",
        "difficulty":  question.get("difficulty") or "Medium",
        "model_answer": question.get("model_answer"),
        "has_answer":  question.get("has_answer", True),
        "is_followup": True,
        "parent_id":   question_id,
    }
    state["by_parent"][question_id] = record
    state["depth"][followup_id] = depth + 1
    session["questions"].append(record)
    return record


@router.post("/api/score", response_model=ScoreResponse)
async def score_answer_route(payload: AnswerPayload):
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")
    if not payload.user_answer.strip():
        raise HTTPException(400, "Answer cannot be empty.")

    model_text = None if not payload.has_answer else payload.model_answer
    question = next((q for q in session["questions"] if q.get("id") == payload.question_id), {})
    depth = _question_depth(session, payload.question_id)
    cap_allows, uses_overflow = _followup_cap(session, payload)

    try:
        flow = await run_evaluation_flow(
            question=payload.question_text,
            model_answer=model_text,
            user_answer=payload.user_answer,
            category=payload.category,
            difficulty=payload.difficulty,
            followup_count=depth,
            followup_allowed=(
                payload.user_answer.strip() != _PLACEHOLDER_ANSWER
                and not _has_followup_for(session, payload.question_id)
                and cap_allows
            ),
        )
    except Exception as e:
        logger.exception("Evaluation flow failed")
        raise HTTPException(500, f"Answer evaluation failed: {str(e)}")

    result = _to_score_result(flow.evaluation)

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

    followup = None
    if flow.followup_question:
        followup = _append_followup(
            session,
            question,
            payload.question_id,
            flow.followup_question,
            depth,
            allow_overflow=uses_overflow,
        )

    return ScoreResponse(
        question_id=payload.question_id,
        overall=result["overall"],
        is_behavioral=result["is_behavioral"],
        angles=result["angles"],
        model_answer=payload.model_answer,
        feedback=result.get("feedback", ""),
        evaluation_score=result.get("evaluation_score"),
        evaluation_improvements=result.get("evaluation_improvements", []),
        criteria=result.get("criteria", {}),
        followup=followup,
    )

"""
followup_service.py
--------------------
Decides whether a scored answer earns a follow-up, and creates it.

The score arrives late (transcription + scoring happen after the answer is
submitted), so follow-ups are requested after the fact and the frontend slots
them into the queue — this module only owns the eligibility rules and the
per-session bookkeeping, not the placement.

Per-session state lives in session["followups"]:
    count     follow-ups created so far (reserved before the LLM call, so
              concurrent requests can't overshoot the cap)
    next_id   counter for "f1", "f2", ...
    depth     {question_id: how many follow-ups deep it is} — base questions are 0
    by_parent {parent_question_id: follow-up dict} — makes the request idempotent
    pending   parent ids with a generation in flight
"""

import logging

from app.core.config import settings
from app.llm import generate_followup
from app.llm.validation import FollowupRejected

logger = logging.getLogger(__name__)

# What the frontend submits when speech-to-text produced nothing. A follow-up
# can't be based on this, so it never earns one.
PLACEHOLDER_ANSWER = "[voice response]"


def _state(session: dict) -> dict:
    return session.setdefault(
        "followups", {"count": 0, "next_id": 1, "depth": {}, "by_parent": {}, "pending": set()}
    )


def ineligible_reason(session: dict, answer: dict) -> str | None:
    """None if this scored answer should get a follow-up, else a short reason."""
    state = _state(session)
    qid = answer["question_id"]
    if answer["score"]["overall"] >= settings.FOLLOWUP_SCORE_THRESHOLD:
        return "score_ok"
    if answer["user_answer"].strip() == PLACEHOLDER_ANSWER:
        return "no_transcript"
    if state["depth"].get(qid, 0) >= settings.FOLLOWUP_MAX_DEPTH:
        return "max_depth"
    if state["count"] >= settings.FOLLOWUP_MAX_TOTAL:
        return "max_total"
    if qid in state["by_parent"] or qid in state["pending"]:
        return "already_requested"
    return None


def would_follow_up(session: dict, answer: dict) -> bool:
    return ineligible_reason(session, answer) is None


async def create_followup(session: dict, question_id: str) -> dict | None:
    """
    Generate the follow-up for a scored answer, or return None if it doesn't
    qualify. Calling again for the same question returns the same follow-up.
    """
    state = _state(session)

    existing = state["by_parent"].get(question_id)
    if existing:
        return existing

    answer = next((a for a in session["answers"] if a["question_id"] == question_id), None)
    if answer is None:
        return None
    reason = ineligible_reason(session, answer)
    if reason:
        logger.info(f"No follow-up for {question_id}: {reason}")
        return None

    # Reserve a slot and an id BEFORE awaiting the LLM.
    state["count"] += 1
    followup_id = f"f{state['next_id']}"
    state["next_id"] += 1
    state["pending"].add(question_id)
    try:
        generated = await generate_followup(
            question=answer["question"],
            answer=answer["user_answer"],
            score=answer["score"]["overall"],
            feedback=answer["score"].get("feedback", ""),
            years=session.get("years_experience"),
        )
    except FollowupRejected as e:
        # The generated question failed validation: ask nothing rather than something unsafe.
        state["count"] -= 1
        logger.warning(f"Follow-up for {question_id} rejected: {e}")
        return None
    except Exception:
        state["count"] -= 1
        raise
    finally:
        state["pending"].discard(question_id)

    followup = {
        "id":           followup_id,
        "question_id":  followup_id,
        "question":     generated["question"],
        "category":     answer["category"],
        "difficulty":   generated["difficulty"] or answer["difficulty"],
        "model_answer": generated["model_answer"],
        "has_answer":   True,
        "is_followup":  True,
        "parent_id":    question_id,
    }
    state["by_parent"][question_id] = followup
    state["depth"][followup_id] = state["depth"].get(question_id, 0) + 1
    session["questions"].append(followup)
    logger.info(f"Follow-up {followup_id} created for {question_id} (score {answer['score']['overall']})")
    return followup

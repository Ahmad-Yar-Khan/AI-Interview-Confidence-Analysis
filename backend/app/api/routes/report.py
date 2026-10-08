"""
report.py (route)
-------------------
GET /api/report/{session_id} — Full session report.
DELETE /api/session/{session_id} — Clear session.
"""

from fastapi import APIRouter, HTTPException

from app.services.resume_service import guess_name
from app.services.session_store import session_store

router = APIRouter()


@router.get("/api/report/{session_id}")
def get_report(session_id: str):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    answers = session["answers"]

    if not answers:
        raise HTTPException(400, "No answers recorded yet.")

    scores = [a["score"]["overall"] for a in answers]

    cat_scores: dict[str, list[int]] = {}
    for a in answers:
        cat_scores.setdefault(a["category"], []).append(a["score"]["overall"])

    category_breakdown = {}
    for cat, s in cat_scores.items():
        is_beh = any(a["score"].get("is_behavioral", False) for a in answers if a["category"] == cat)
        category_breakdown[cat] = {
            "average":       round(sum(s) / len(s)),
            "count":         len(s),
            "is_behavioral": is_beh,
        }

    return {
        "session_id":         session_id,
        "candidate_name":     guess_name(session["resume_text"]),
        "candidate_title":    "",
        "total_questions":    len(session["questions"]),
        "answered":           len(answers),
        "average_score":      round(sum(scores) / len(scores)),
        "best_score":         max(scores),
        "worst_score":        min(scores),
        "category_breakdown": category_breakdown,
        "answers":            answers,
    }


@router.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    session_store.delete(session_id)
    return {"deleted": session_id}

"""
questions.py (route)
----------------------
GET /api/questions/{session_id} — Generate (or return cached) questions.
GET /api/debug/chunks/{session_id} — debug: resume section chunks + generated questions.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.core.roles import OTHER_SLUG, get_role
from app.services.session_store import session_store
from app.services import question_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/questions/{session_id}")
async def get_questions(
    session_id: str,
    total: int = Query(5, ge=3, le=8),
    role: str = OTHER_SLUG,
    years: int | None = Query(None, ge=0, le=50),
):
    """
    Generate the opening questions (default 5) from the whole resume, the
    chosen job title's research brief, and years of experience. Further
    questions arrive as follow-ups via POST /api/followup.

    `role` is a slug from GET /api/roles, or "other" (no job title is sent to
    the LLM). `years` is the candidate's years of experience.
    """
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found. Upload a resume first.")

    role = role.strip() or OTHER_SLUG
    if role != OTHER_SLUG and get_role(role) is None:
        raise HTTPException(422, f"Unknown role '{role}'. Use a slug from /api/roles or 'other'.")

    try:
        questions = await question_service.get_or_generate_questions(
            session, total=total, role=role, years=years
        )
    except Exception as e:
        logger.exception("Question generation failed")
        raise HTTPException(500, f"Question generation failed: {str(e)}")

    return {"questions": questions, "role_context": session.get("role_context")}


@router.get("/api/debug/chunks/{session_id}")
def debug_chunks(session_id: str):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")
    if "debug_chunks" not in session:
        raise HTTPException(400, "No chunks yet — generate questions first.")
    retrieval = session.get("debug_retrieval", {})
    return {
        # Raw section splits from the resume (label → text)
        "resume_sections": session["debug_chunks"],
        # The questions Groq produced for this session
        "questions": [q["question"] for q in retrieval.get("questions", [])],
    }

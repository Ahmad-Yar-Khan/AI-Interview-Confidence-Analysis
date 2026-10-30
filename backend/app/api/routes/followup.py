"""
followup.py (route)
---------------------
POST /api/followup — Generate a follow-up question for a weak, already-scored answer.

Called by the frontend after /api/score reports `followup_eligible`. The
backend re-checks eligibility (score threshold, depth, total cap), so a client
can't force extra follow-ups. Returns {"followup": null} when none applies.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas.answer import FollowupRequest
from app.services import followup_service
from app.services.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/followup")
async def request_followup(payload: FollowupRequest):
    session = session_store.get(payload.session_id)
    if session is None:
        raise HTTPException(404, "Session not found.")

    try:
        followup = await followup_service.create_followup(session, payload.question_id)
    except Exception as e:
        logger.exception("Follow-up generation failed")
        raise HTTPException(500, f"Follow-up generation failed: {str(e)}")

    return {"followup": followup}

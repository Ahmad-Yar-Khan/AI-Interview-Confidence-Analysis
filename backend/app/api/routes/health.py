"""
health.py (route)
-------------------
GET / and GET /api/health.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.services.session_store import session_store
from app.services import question_service
from app.api.routes.confidence import is_confidence_available

router = APIRouter()


@router.get("/")
def root():
    return {"status": "ok", "message": "Smart Interview API v3.0 (RAG)"}


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "sessions_active": session_store.count(),
        "groq_key_set": bool(settings.GROQ_API_KEY),
        "confidence_available": is_confidence_available(),
        **question_service.rag_status(),
    }

"""
main.py
-------
Smart Interview API — RAG edition.
Uses Groq to generate questions from the raw resume and score answers.

Run (from the backend/ directory, so relative paths like DATA_PATH resolve
correctly): uvicorn app.main:app --reload --port 8000

This file is intentionally thin — app construction, middleware, lifespan, and
router registration only. All business logic lives in app/services/, app/ml/,
and app/llm/; see those modules for the question-assembly, scoring, and
retrieval logic that used to live directly in this file.

Routes (now split across app/api/routes/*.py):
  POST   /api/upload-resume        — Upload PDF/DOCX/TXT → session
  GET    /api/roles                — Job-title dropdown options
  GET    /api/questions/{sid}      — Generate (or return cached) questions
  POST   /api/score                — Score one answer via Groq
  POST   /api/followup             — Follow-up question for a weak answer
  GET    /api/report/{sid}         — Full session report
  DELETE /api/session/{sid}        — Clear session
  POST   /api/confidence           — Confidence analysis from audio
  POST   /api/tts                  — ElevenLabs TTS proxy
"""

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.services import confidence_service, role_brief_service
from app.api.routes import health, resume, questions, roles, scoring, followup, report, confidence, tts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════
# STARTUP
# ════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Smart Interview API starting...")
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY is not set — question generation will fail.")
    # Starts the worker process(es) and begins loading Whisper in the
    # background — doesn't block startup.
    confidence_service.start()
    # Dataset RAG (FAISS/SBERT) is no longer used for questions, so it isn't loaded.
    # Weekly Tavily research per job title; serves cached briefs, never blocks requests.
    role_brief_service.start_scheduler()
    yield
    logger.info("Shutting down.")
    role_brief_service.stop_scheduler()
    confidence_service.stop()


# ════════════════════════════════════════
# APP
# ════════════════════════════════════════

app = FastAPI(title="Smart Interview API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(resume.router)
app.include_router(questions.router)
app.include_router(roles.router)
app.include_router(scoring.router)
app.include_router(followup.router)
app.include_router(report.router)
app.include_router(confidence.router)
app.include_router(tts.router)

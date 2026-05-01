"""
main.py
-------
Smart Interview API — RAG edition.
Uses Gemini to generate questions from the raw resume and score answers.

Run: uvicorn main:app --reload --port 8000

Routes:
  POST   /api/upload-resume        — Upload PDF/DOCX/TXT → session
  GET    /api/questions/{sid}      — Generate (or return cached) questions
  POST   /api/score                — Score one answer via Gemini
  GET    /api/report/{sid}         — Full session report
  DELETE /api/session/{sid}        — Clear session
  POST   /api/confidence           — Confidence analysis from audio (feature_extractor)
"""

from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import logging
import tempfile
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from text_extractor import extract_text
from gemini_client import generate_questions, score_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Confidence analysis — optional, only fails gracefully if deps missing
try:
    from feature_extractor import predict_confidence_for_audio_vscode
    _confidence_available = True
except Exception as _ce:
    _confidence_available = False
    logger.warning(f"Confidence module unavailable: {_ce}")


# ── In-memory session store ──────────────────────────────────
sessions: dict[str, dict] = {}


# ════════════════════════════════════════
# STARTUP
# ════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Smart Interview API (RAG) starting...")
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY is not set — question generation will fail.")
    yield
    logger.info("Shutting down.")


# ════════════════════════════════════════
# APP
# ════════════════════════════════════════

app = FastAPI(title="Smart Interview API", version="3.0.0", lifespan=lifespan)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════
# SCHEMAS
# ════════════════════════════════════════

class AnswerPayload(BaseModel):
    session_id: str
    question_id: str
    question_text: str
    model_answer: str | None
    user_answer: str
    category: str
    difficulty: str
    has_answer: bool = True


class ScoreResponse(BaseModel):
    question_id: str
    overall: int
    is_behavioral: bool
    angles: dict
    model_answer: str | None
    feedback: str = ""


# ════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "message": "Smart Interview API v3.0 (RAG)"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "sessions_active": len(sessions),
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "confidence_available": _confidence_available,
    }


# ── 1. Upload Resume ─────────────────────────────────────────

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a PDF, DOCX, or TXT resume.
    Extracts raw text and stores it in a new session.
    Returns session_id + a brief profile summary for the UI.
    """
    allowed = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Upload PDF, DOCX, or TXT.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large. Max 10 MB.")

    try:
        resume_text = extract_text(contents, file.filename)
    except Exception as e:
        logger.exception("Text extraction failed")
        raise HTTPException(500, f"Failed to read resume: {str(e)}")

    if not resume_text.strip():
        raise HTTPException(422, "Could not extract any text from the file.")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "resume_text": resume_text,
        "filename": file.filename,
        "questions": [],
        "answers": [],
    }

    logger.info(f"Session {session_id} created — {len(resume_text)} chars from {file.filename}")
    return {
        "session_id": session_id,
        "profile": {
            "name": _guess_name(resume_text),
            "title": "",
            "filename": file.filename,
            "char_count": len(resume_text),
        },
    }


def _guess_name(text: str) -> str:
    """Best-effort: first non-empty line is usually the candidate's name."""
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 5 and not any(c in line for c in "@:/"):
            return line
    return "Candidate"


# ── 2. Generate Questions ─────────────────────────────────────

@app.get("/api/questions/{session_id}")
def get_questions(session_id: str, total: int = 12):
    """
    Generate interview questions from the resume via Gemini.
    Questions are cached in the session after the first call.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found. Upload a resume first.")

    session = sessions[session_id]

    if session["questions"]:
        return {"questions": session["questions"]}

    try:
        questions = generate_questions(session["resume_text"], total=min(total, 20))
    except Exception as e:
        logger.exception("Question generation failed")
        raise HTTPException(500, f"Gemini question generation failed: {str(e)}")

    session["questions"] = questions
    return {"questions": questions}


# ── 3. Score Answer ──────────────────────────────────────────

@app.post("/api/score", response_model=ScoreResponse)
def score_answer_route(payload: AnswerPayload):
    if payload.session_id not in sessions:
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

    session = sessions[payload.session_id]
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


# ── 4. Report ────────────────────────────────────────────────

@app.get("/api/report/{session_id}")
def get_report(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found.")

    session = sessions[session_id]
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
        "candidate_name":     _guess_name(session["resume_text"]),
        "candidate_title":    "",
        "total_questions":    len(session["questions"]),
        "answered":           len(answers),
        "average_score":      round(sum(scores) / len(scores)),
        "best_score":         max(scores),
        "worst_score":        min(scores),
        "category_breakdown": category_breakdown,
        "answers":            answers,
    }


# ── 5. Delete Session ────────────────────────────────────────

@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    sessions.pop(session_id, None)
    return {"deleted": session_id}


# ── 6. Confidence Analysis ────────────────────────────────────

@app.post("/api/confidence")
async def analyze_confidence(audio: UploadFile = File(...)):
    """
    Upload audio → returns predicted_label, confidence_probability, confidence_score_1_to_10.
    Requires CONFIDENCE_MODEL_PATH and CONFIDENCE_FEATURES_PATH env vars.
    """
    if not _confidence_available:
        raise HTTPException(503, "Confidence module failed to load. Check server logs.")

    tmp_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(audio.filename or "recording.webm")[-1] or ".webm"
        tmp_path = os.path.join(tmp_dir, f"audio{ext}")
        with open(tmp_path, "wb") as f:
            f.write(await audio.read())

        result = predict_confidence_for_audio_vscode(tmp_path)
        if not result:
            raise HTTPException(500, "Prediction failed. Check model files and audio.")
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

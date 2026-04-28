"""
main.py
-------
FastAPI application — Smart Interview API.
Run: uvicorn main:app --reload --port 8000

Startup:
  1. Loads master_questions.csv (all 11 categories, built by preprocess_datasets.py)
  2. Fits TF-IDF + builds FAISS index

Routes:
  POST /api/parse-resume          — Upload PDF/DOCX → parsed profile + session
  GET  /api/questions/{sid}       — Get tailored questions for session
  POST /api/score                 — Score one answer
  GET  /api/report/{sid}          — Full session report
  DELETE /api/session/{sid}       — Clear session
"""

import os
import uuid
import logging
import tempfile
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from resume_parser import parse_resume
from embedding_engine import EmbeddingEngine
from data_loader import init_question_bank, get_question_bank, CATEGORIES
from question_selector import select_questions
from scorer import score_answer

try:
    from feature_extractor import predict_confidence_for_audio_vscode
    _confidence_available = True
except Exception as _ce:
    _confidence_available = False
    logging.getLogger(__name__).warning(f"feature_extractor not available: {_ce}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── In-memory session store ──────────────────────────────────
# Replace with Redis in production.
sessions: dict[str, dict] = {}

# ── Shared embedding engine ──────────────────────────────────
engine = EmbeddingEngine()


# ════════════════════════════════════════
# STARTUP
# ════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Smart Interview API starting...")
    csv_path = os.getenv("DATA_PATH", "data/master_questions.csv")

    if not os.path.exists(csv_path):
        logger.error(
            f"❌ master_questions.csv not found at '{csv_path}'.\n"
            "   Run: python preprocess_datasets.py"
        )
    else:
        try:
            init_question_bank(engine, csv_path)
            bank = get_question_bank()
            logger.info(f"✅ Question bank ready — {len(bank.get_all())} questions, {len(bank.get_categories())} categories")
        except Exception as e:
            logger.error(f"❌ Failed to load question bank: {e}")
    yield
    logger.info("Shutting down.")


# ════════════════════════════════════════
# APP
# ════════════════════════════════════════

app = FastAPI(title="Smart Interview API", version="2.0.0", lifespan=lifespan)

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
    model_answer: str | None       # None for HR & Behavioral questions
    user_answer: str
    category: str
    difficulty: str
    has_answer: bool = True        # False = HR question → behavioral scoring


class ScoreResponse(BaseModel):
    question_id: str
    overall: int
    is_behavioral: bool
    angles: dict
    model_answer: str | None


# ════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "message": "Smart Interview API v2.0"}


@app.get("/api/health")
def health():
    try:
        bank = get_question_bank()
        cats = {cat: len(bank.get_by_category(cat)) for cat in bank.get_categories()}
        return {
            "status": "ok",
            "total_questions": len(bank.get_all()),
            "categories": cats,
            "sessions_active": len(sessions),
        }
    except RuntimeError:
        return {"status": "degraded", "error": "Question bank not loaded"}


# ── 1. Upload & Parse Resume ─────────────────────────────────

@app.post("/api/parse-resume")
async def parse_resume_route(file: UploadFile = File(...)):
    """
    Upload a PDF, DOCX, or TXT resume.
    Returns parsed profile + session_id for subsequent calls.
    """
    allowed = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Upload PDF, DOCX, or TXT.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large. Max 10 MB.")

    try:
        profile = parse_resume(contents, file.filename)
    except Exception as e:
        logger.exception("Resume parsing failed")
        raise HTTPException(500, f"Failed to parse resume: {str(e)}")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "profile": profile,
        "questions": [],
        "answers": [],
    }

    return {"session_id": session_id, "profile": profile.to_dict()}


# ── 2. Get Tailored Questions ─────────────────────────────────

@app.get("/api/questions/{session_id}")
def get_questions(session_id: str, total: int = 12):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found. Upload a resume first.")

    session = sessions[session_id]

    # Return cached selection
    if session["questions"]:
        return {"questions": session["questions"]}

    bank    = get_question_bank()
    profile = session["profile"]
    questions = select_questions(profile, bank, engine, total=min(total, 20))
    session["questions"] = questions

    return {"questions": questions}


# ── 3. Score a Single Answer ──────────────────────────────────

@app.post("/api/score", response_model=ScoreResponse)
def score_answer_route(payload: AnswerPayload):
    if payload.session_id not in sessions:
        raise HTTPException(404, "Session not found.")
    if not payload.user_answer.strip():
        raise HTTPException(400, "Answer cannot be empty.")

    # Pass None for model_answer when has_answer=False (HR questions)
    model_text = None if not payload.has_answer else payload.model_answer

    result = score_answer(
        user_text=payload.user_answer,
        model_text=model_text,
        category=payload.category,
        engine=engine,
    )

    answer_record = {
        "question_id": payload.question_id,
        "question":    payload.question_text,
        "category":    payload.category,
        "difficulty":  payload.difficulty,
        "has_answer":  payload.has_answer,
        "user_answer": payload.user_answer,
        "model_answer": payload.model_answer,
        "score":       result.to_dict(),
    }

    session = sessions[payload.session_id]
    existing = next(
        (i for i, a in enumerate(session["answers"]) if a["question_id"] == payload.question_id),
        None,
    )
    if existing is not None:
        session["answers"][existing] = answer_record
    else:
        session["answers"].append(answer_record)

    return ScoreResponse(
        question_id=payload.question_id,
        overall=result.overall,
        is_behavioral=result.is_behavioral,
        angles=result.to_dict()["angles"],
        model_answer=payload.model_answer,
    )


# ── 4. Full Report ────────────────────────────────────────────

@app.get("/api/report/{session_id}")
def get_report(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found.")

    session = sessions[session_id]
    profile = session["profile"]
    answers = session["answers"]

    if not answers:
        raise HTTPException(400, "No answers recorded yet.")

    scores = [a["score"]["overall"] for a in answers]
    avg    = round(sum(scores) / len(scores))

    # Category breakdown — separate technical vs behavioral
    cat_scores: dict[str, list[int]] = {}
    for a in answers:
        cat_scores.setdefault(a["category"], []).append(a["score"]["overall"])

    category_breakdown = {
        cat: {
            "average": round(sum(s) / len(s)),
            "count":   len(s),
            "is_behavioral": a["score"].get("is_behavioral", False),
        }
        for cat, s in cat_scores.items()
        for a in answers
        if a["category"] == cat
    }
    # Deduplicate (the loop above produces duplicates per category)
    category_breakdown = {}
    for cat, s in cat_scores.items():
        is_beh = any(a["score"].get("is_behavioral", False) for a in answers if a["category"] == cat)
        category_breakdown[cat] = {
            "average": round(sum(s) / len(s)),
            "count":   len(s),
            "is_behavioral": is_beh,
        }

    return {
        "session_id":        session_id,
        "candidate_name":    profile.name,
        "candidate_title":   profile.title,
        "total_questions":   len(session["questions"]),
        "answered":          len(answers),
        "average_score":     avg,
        "best_score":        max(scores),
        "worst_score":       min(scores),
        "category_breakdown": category_breakdown,
        "answers":           answers,
    }


# ── 5. Clear Session ─────────────────────────────────────────

@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"deleted": session_id}


# ── 6. Confidence Analysis ───────────────────────────────────

@app.post("/api/confidence")
async def analyze_confidence(audio: UploadFile = File(...)):
    """
    Upload an audio file (webm/wav/mp3/m4a).
    Returns predicted_label, confidence_probability, confidence_score_1_to_10.
    Requires CONFIDENCE_MODEL_PATH and CONFIDENCE_FEATURES_PATH env vars
    pointing to the trained joblib files.
    """
    if not _confidence_available:
        raise HTTPException(503, "Confidence analysis module failed to load. Check server logs.")

    tmp_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(audio.filename or "recording.webm")[-1] or ".webm"
        tmp_path = os.path.join(tmp_dir, f"audio{ext}")
        contents = await audio.read()
        with open(tmp_path, "wb") as f:
            f.write(contents)

        result = predict_confidence_for_audio_vscode(tmp_path)
        if not result:
            raise HTTPException(500, "Prediction failed. Check that model files exist and audio is valid.")
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── 7. Available Categories ──────────────────────────────────

@app.get("/api/categories")
def get_categories():
    """Returns all categories available in the question bank."""
    try:
        bank = get_question_bank()
        return {
            "categories": [
                {
                    "name": cat,
                    "count": len(bank.get_by_category(cat)),
                    "is_behavioral": cat == "HR & Behavioral",
                }
                for cat in bank.get_categories()
            ]
        }
    except RuntimeError:
        return {"categories": []}

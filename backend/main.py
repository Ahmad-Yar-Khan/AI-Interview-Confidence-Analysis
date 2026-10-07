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
load_dotenv(override=True)

import os
import uuid
import random
import logging
import tempfile
import shutil
import numpy as np
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from text_extractor import extract_text
from gemini_client import generate_questions, generate_dataset_and_project_questions, score_answer, infer_categories

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Confidence analysis — optional, only fails gracefully if deps missing
try:
    from feature_extractor import predict_confidence_for_audio_vscode
    _confidence_available = True
except Exception as _ce:
    _confidence_available = False
    logger.warning(f"Confidence module unavailable: {_ce}")

# RAG pipeline — optional, falls back to resume-only generation if unavailable
_rag_ready  = False
_rag_engine = None
_rag_bank   = None
try:
    from embedding_engine import EmbeddingEngine
    from data_loader import init_question_bank
    from resume_parser import (
        ResumeProfile,
        extract_name, extract_title, extract_skills,
        extract_experience, extract_education, extract_projects,
        get_chunks,
    )
    _rag_imports_ok = True
except Exception as _re:
    _rag_imports_ok = False
    logger.warning(f"RAG imports unavailable: {_re}")


# ── In-memory session store ──────────────────────────────────
sessions: dict[str, dict] = {}


# ════════════════════════════════════════
# STARTUP
# ════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag_ready, _rag_engine, _rag_bank
    logger.info("Smart Interview API starting...")
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY is not set — question generation will fail.")
    if _rag_imports_ok:
        try:
            _rag_engine = EmbeddingEngine()
            _rag_bank   = init_question_bank(_rag_engine)
            _rag_ready  = True
            logger.info(f"RAG pipeline ready — {len(_rag_bank.questions)} questions indexed in FAISS.")
        except Exception as _e:
            logger.warning(f"RAG pipeline failed to initialise: {_e}. Falling back to resume-only generation.")
    else:
        logger.warning("RAG pipeline skipped — imports unavailable.")
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
    model_answer: str | None = None
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
# RAG HELPERS
# ════════════════════════════════════════

def _build_profile(resume_text: str):
    """Parse raw resume text into a structured ResumeProfile."""
    profile            = ResumeProfile(raw_text=resume_text)
    profile.name       = extract_name(resume_text)
    profile.title      = extract_title(resume_text, profile.name)
    profile.skills     = extract_skills(resume_text)
    profile.experience = extract_experience(resume_text)
    profile.education  = extract_education(resume_text)
    profile.projects   = extract_projects(resume_text)
    return profile


def _build_category_contexts(resume_text: str, categories: list[str]) -> dict[str, list[str]]:
    """
    For each Gemini-inferred category, retrieve the most relevant resume chunks
    using TF-IDF embeddings + numpy cosine ranking.

    Returns { category: ["[label] chunk text", ...] }
    Returns {} if the RAG pipeline is unavailable.
    """
    if not _rag_ready:
        return {}
    try:
        profile = _build_profile(resume_text)
        chunks  = get_chunks(profile)          # [(label, text), ...]
        if not chunks:
            return {}

        chunk_labels = [label for label, _ in chunks]
        chunk_texts  = [text  for _, text  in chunks]
        chunk_vecs   = _rag_engine.embed_batch(chunk_texts)  # (N, dim)

        result = {}
        for cat in categories:
            query_vec   = _rag_engine.embed(cat)
            top_indices = _rag_engine.rank_chunks(query_vec, chunk_vecs, top_k=2)
            result[cat] = [
                f"[{chunk_labels[i]}] {chunk_texts[i]}"
                for i in top_indices
            ]

        logger.info(f"RAG retrieved chunks for categories: {list(result.keys())}")
        return result, {label: text for label, text in chunks}

    except Exception as e:
        logger.warning(f"RAG chunk retrieval failed: {e}")
        return {}, {}


# ════════════════════════════════════════
# QUESTION ASSEMBLY HELPERS
# ════════════════════════════════════════

def _normalize_dataset_question(q, id_prefix: str = "ds") -> dict:
    """Convert a QuestionBank Question to the frontend-compatible dict format."""
    d = q.to_dict()
    qid = f"{id_prefix}_{d['id']}"
    return {
        "id":           qid,
        "question_id":  qid,
        "question":     d["question"],
        "category":     d["category"],
        "difficulty":   d["difficulty"],
        "model_answer": d.get("answer"),   # dataset stores it as "answer"
        "has_answer":   d["has_answer"],
    }


def _retrieve_dataset_questions(resume_text: str, count: int = 5) -> list[dict]:
    """
    Global SBERT retrieval: embed resume, search FAISS across all tech questions,
    cap per-category to 2 for diversity, return top `count` results.
    """
    if not _rag_ready or not _rag_imports_ok:
        return []
    try:
        resume_vec = _rag_engine.embed(resume_text[:3000])
        search_k   = min(len(_rag_bank.questions), count * 10)
        _, indices = _rag_engine.search(resume_vec, top_k=search_k)

        MAX_PER_CAT = 2
        cat_counts: dict[str, int] = {}
        selected: list[dict] = []
        seen: set[str] = set()

        for idx in indices:
            if len(selected) >= count:
                break
            q = _rag_bank.questions[idx]
            if q.category == "HR & Behavioral":
                continue
            if q.question in seen:
                continue
            if cat_counts.get(q.category, 0) >= MAX_PER_CAT:
                continue
            selected.append(_normalize_dataset_question(q, id_prefix="ds"))
            seen.add(q.question)
            cat_counts[q.category] = cat_counts.get(q.category, 0) + 1

        # Backfill: relax cap if short
        if len(selected) < count:
            for idx in indices:
                if len(selected) >= count:
                    break
                q = _rag_bank.questions[idx]
                if q.category == "HR & Behavioral" or q.question in seen:
                    continue
                selected.append(_normalize_dataset_question(q, id_prefix="ds"))
                seen.add(q.question)

        logger.info(
            f"Global SBERT retrieval: {len(selected)} questions "
            f"from categories {list(dict.fromkeys(q['category'] for q in selected))}"
        )
        return selected
    except Exception as e:
        logger.warning(f"Dataset retrieval failed: {e}")
        return []


def _get_hr_questions(count: int = 3) -> list[dict]:
    """Randomly sample HR & Behavioral questions from the dataset."""
    if not _rag_ready:
        return []
    try:
        hr_pool = _rag_bank.get_by_category("HR & Behavioral")
        if not hr_pool:
            return []
        sampled = random.sample(hr_pool, min(count, len(hr_pool)))
        return [_normalize_dataset_question(q, id_prefix="hr") for q in sampled]
    except Exception as e:
        logger.warning(f"HR question retrieval failed: {e}")
        return []


def _extract_projects_section(resume_text: str) -> str:
    """Return the raw projects section text from the resume, or empty string if not found."""
    if not _rag_imports_ok:
        return ""
    profile = ResumeProfile(raw_text=resume_text)
    for label, text in get_chunks(profile):
        if label == "projects":
            return text
    return ""


def _dedup_questions(questions: list[dict], sim_threshold: float = 0.70) -> list[dict]:
    """
    Remove duplicate questions using SBERT cosine similarity when the RAG engine
    is available, falling back to string-prefix matching otherwise.
    Two questions are considered duplicates when their cosine similarity exceeds
    sim_threshold — the later one (lower priority source) is dropped.
    """
    if not questions:
        return []

    if _rag_ready:
        texts = [q["question"] for q in questions]
        vecs  = _rag_engine.embed_batch(texts)       # (N, dim), L2-normalised
        sim   = vecs @ vecs.T                        # (N, N) cosine similarities

        to_drop: set[int] = set()
        for i in range(len(questions)):
            if i in to_drop:
                continue
            for j in range(i + 1, len(questions)):
                if j not in to_drop and sim[i, j] >= sim_threshold:
                    to_drop.add(j)

        return [q for i, q in enumerate(questions) if i not in to_drop]

    # Fallback: string prefix
    seen:   set[str]  = set()
    result: list[dict] = []
    for q in questions:
        key = q["question"][:80].lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(q)
    return result


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
        "rag_ready": _rag_ready,
        "rag_questions_indexed": len(_rag_bank.questions) if _rag_ready else 0,
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

    if not _looks_like_resume(resume_text):
        raise HTTPException(
            422,
            "The uploaded file does not appear to be a resume. "
            "Please upload a resume containing sections like Experience, Education, or Skills.",
        )

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


import re as _re

_RESUME_SECTIONS = {
    "experience": {
        "work experience", "professional experience", "employment history",
        "work history", "experience", "employment",
    },
    "education": {
        "education", "degree", "bachelor", "master", "gpa",
        "university", "college", "b.sc", "m.sc", "b.tech", "m.tech", "graduated",
    },
    "skills": {
        "technical skills", "core skills", "key skills", "skills",
        "competencies", "proficiencies", "technologies",
    },
    "identity": {
        "curriculum vitae", "linkedin", "github.com", "career objective",
        "professional summary",
    },
    "extras": {
        "certifications", "internship", "publications", "volunteer",
        "achievements", "awards",
    },
}

def _looks_like_resume(text: str) -> bool:
    """
    Requires three independent signals that only co-occur in resumes:
      1. Contact info  — email address or phone number
      2. Date patterns — year ranges from work/education history
      3. Section depth — keywords from at least 2 distinct resume sections
    Falls back to accepting the file if it has 4+ distinct sections (covers
    rare resumes that omit contact details in the extracted text).
    """
    lower = text.lower()

    has_email = bool(_re.search(r'\b[\w.+-]+@[\w-]+\.\w{2,}\b', text))
    has_phone = bool(_re.search(r'(\+?\d[\d\s\-().]{7,14}\d)', text))
    has_years = bool(_re.search(r'\b(19|20)\d{2}\b', text))

    sections_hit = sum(
        1 for kws in _RESUME_SECTIONS.values()
        if any(kw in lower for kw in kws)
    )

    strong_match = (has_email or has_phone) and has_years and sections_hit >= 2
    fallback     = sections_hit >= 4
    return strong_match or fallback


def _guess_name(text: str) -> str:
    """Best-effort: first non-empty line is usually the candidate's name."""
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 5 and not any(c in line for c in "@:/"):
            return line
    return "Candidate"


# ── 2. Generate Questions ─────────────────────────────────────

@app.get("/api/questions/{session_id}")
def get_questions(session_id: str, total: int = 12, role: str = "", jd: str = ""):
    """
    Assemble interview questions from three sources:
      - 5 technical questions retrieved from the dataset via FAISS (resume-matched)
      - 4 project-specific questions generated by Gemini from the projects section
      - 3 HR & Behavioral questions randomly sampled from the dataset
    Falls back to full LLM generation if all three sources fail.
    """
    if session_id not in sessions:
        raise HTTPException(404, "Session not found. Upload a resume first.")

    session = sessions[session_id]

    prev_role = session.get("job_role", "")
    prev_jd   = session.get("job_description", "")
    context_changed = (role.strip() != prev_role or jd.strip() != prev_jd)

    if session["questions"] and not context_changed:
        return {"questions": session["questions"]}

    session["job_role"]        = role.strip()
    session["job_description"] = jd.strip()

    resume_text = session["resume_text"]

    # ── Sources 1 & 2: personalized dataset + project questions ──
    # Single Gemini call handles both tasks to halve quota usage.
    raw_dataset_qs = _retrieve_dataset_questions(resume_text, count=5)
    projects_text  = _extract_projects_section(resume_text)
    dataset_qs: list[dict] = []
    project_qs: list[dict] = []
    try:
        dataset_qs, project_qs = generate_dataset_and_project_questions(
            dataset_qs=raw_dataset_qs,
            projects_text=projects_text,
            resume_text=resume_text,
            project_count=4,
        )
    except Exception as e:
        logger.warning(f"Combined question generation failed: {e}")
        dataset_qs = raw_dataset_qs  # fall back to raw unmodified questions

    # ── Source 3: HR questions from dataset ───────────────────
    hr_qs = _get_hr_questions(count=3)

    # ── Combine, deduplicate, re-index ────────────────────────
    questions = _dedup_questions(dataset_qs + project_qs + hr_qs)

    # Full LLM fallback if every source returned nothing
    if not questions:
        logger.warning("All sources empty — falling back to full LLM generation.")
        try:
            questions = generate_questions(resume_text=resume_text, total=total)
        except Exception as e:
            logger.exception("Fallback question generation failed")
            raise HTTPException(500, f"Question generation failed: {str(e)}")

    for i, q in enumerate(questions):
        q["id"] = f"q{i+1}"
        q["question_id"] = f"q{i+1}"

    logger.info(
        f"Questions assembled: {len(dataset_qs)} dataset + "
        f"{len(project_qs)} project + {len(hr_qs)} HR = {len(questions)} total"
    )

    # Store for debug endpoint
    session["debug_chunks"]    = {label: text for label, text in get_chunks(ResumeProfile(raw_text=resume_text))} if _rag_imports_ok else {}
    session["debug_retrieval"] = {"dataset": dataset_qs, "project": project_qs, "hr": hr_qs}

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


# ── 5. Debug: Chunks ─────────────────────────────────────────

@app.get("/api/debug/chunks/{session_id}")
def debug_chunks(session_id: str):
    if session_id not in sessions:
        raise HTTPException(404, "Session not found.")
    session = sessions[session_id]
    if "debug_chunks" not in session:
        raise HTTPException(400, "No chunks yet — generate questions first.")
    retrieval = session.get("debug_retrieval", {})
    return {
        # Raw section splits from the resume (label → text)
        "resume_sections": session["debug_chunks"],
        # What each source contributed
        "sources": {
            "dataset":  [q["question"] for q in retrieval.get("dataset", [])],
            "project":  [q["question"] for q in retrieval.get("project", [])],
            "hr":       [q["question"] for q in retrieval.get("hr", [])],
        },
    }


# ── 6. Delete Session ────────────────────────────────────────

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


# ── 7. ElevenLabs TTS proxy ──────────────────────────────────

# Voice IDs — swap ELEVENLABS_VOICE_ID in .env to change voice
# Free-tier premade voices (no paid plan needed):
#   Adam  (deep, authoritative male):   pNInz6obpgDQGcFmaJgB  ← default
#   Josh  (warm male):                  TxGEqnHWrfWFTfGW9XjX
#   Bella (soft female):                EXAVITQu4vr4xnSDxMaL
#   Antoni(smooth male):                ErXwobaYiN019PkySvjV
# Paid-plan only (voice library):
#   Rachel (professional female):       21m00Tcm4TlvDq8ikWAM
_EL_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam
_EL_MODEL    = "eleven_turbo_v2"  # fastest, good quality; swap to eleven_multilingual_v2 for more langs

class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key or api_key == "your_elevenlabs_key_here":
        raise HTTPException(503, "ELEVENLABS_API_KEY not set in .env")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{_EL_VOICE_ID}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": req.text,
        "model_id": _EL_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=body, headers=headers)

    if resp.status_code != 200:
        logger.error(f"ElevenLabs error {resp.status_code}: {resp.text[:200]}")
        raise HTTPException(502, f"ElevenLabs API error: {resp.status_code}")

    return StreamingResponse(
        iter([resp.content]),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )

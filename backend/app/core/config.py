"""
config.py
---------
Centralizes every environment variable the app reads. Before this file existed,
os.getenv() calls were scattered across main.py, groq_client.py, and
feature_extractor.py — there was no single place to see what the app needs to
run.

The old provider-specific API key has been removed entirely (not just renamed):
it was a leftover check from before this app migrated to Groq, and it checked
the wrong variable — the startup warning and /api/health's key-status field both
used to read that old key while the actual Groq client only ever reads
GROQ_API_KEY, so a missing GROQ_API_KEY could go unnoticed (and vice versa, a
false warning could fire for a perfectly working setup). Both call sites now
read GROQ_API_KEY directly.
"""

import os
from pathlib import Path

# backend/app/core/config.py -> parents[2] == backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    # --- LLM (Groq) ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    # "llama-3.3-70b-versatile" used to be the default here, but Groq moved it
    # behind an enterprise/sales-negotiated tier — a standard API key now gets
    # a 404 "model_not_found" from it, not because the model stopped existing,
    # but because this tier doesn't have access to it. openai/gpt-oss-120b is
    # Groq's current openly-accessible model closest to that capability class.
    # Override via GROQ_MODEL in .env if you get access to something else.
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # --- Role briefs (weekly Tavily research per dropdown job title) ---
    # Without a key the scheduler stays off and questions are generated from the
    # resume alone — the interview never blocks on search.
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    ROLE_BRIEF_DB_PATH: str = os.getenv(
        "ROLE_BRIEF_DB_PATH",
        str(BACKEND_ROOT / "data" / "role_briefs.db"),
    )
    # A brief older than this is no longer served. The scheduler refreshes at 6/7
    # of the TTL so a healthy brief never lapses between refreshes.
    ROLE_BRIEF_TTL_DAYS: int = int(os.getenv("ROLE_BRIEF_TTL_DAYS", "7"))
    ROLE_BRIEF_SCHEDULER: bool = os.getenv("ROLE_BRIEF_SCHEDULER", "1") not in ("0", "false", "False")

    # --- Follow-up questions ---
    # An answer whose Groq score ("overall", 0-100) is below the threshold triggers
    # a follow-up. Depth 2 means base question -> follow-up -> one more follow-up.
    FOLLOWUP_SCORE_THRESHOLD: int = int(os.getenv("FOLLOWUP_SCORE_THRESHOLD", "60"))
    FOLLOWUP_MAX_DEPTH: int = int(os.getenv("FOLLOWUP_MAX_DEPTH", "2"))
    FOLLOWUP_MAX_TOTAL: int = int(os.getenv("FOLLOWUP_MAX_TOTAL", "7"))

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- RAG / question bank ---
    DATA_PATH: str = os.getenv("DATA_PATH", "data/master_questions.csv")
    # Question-bank embeddings are computed once and cached here (keyed by a
    # hash of the CSV + model name), so startup doesn't re-embed the whole
    # dataset every boot. Delete the directory to force a rebuild.
    EMBEDDING_CACHE_DIR: str = os.getenv(
        "EMBEDDING_CACHE_DIR",
        str(BACKEND_ROOT / "faiss_index"),
    )

    # --- Confidence model (paths are now resolved from BACKEND_ROOT since this
    #     file, and the module that uses it, no longer live at backend/ root) ---
    CONFIDENCE_MODEL_PATH: str = os.getenv(
        "CONFIDENCE_MODEL_PATH",
        str(BACKEND_ROOT / "models" / "ensemble_confidence_model.joblib"),
    )
    CONFIDENCE_FEATURES_PATH: str = os.getenv(
        "CONFIDENCE_FEATURES_PATH",
        str(BACKEND_ROOT / "models" / "features_list.joblib"),
    )
    # Confidence prediction runs in separate worker processes so it never
    # blocks the API's event loop. Transcription is delegated to Groq's hosted
    # Whisper API, so each worker only loads the small ensemble model — no
    # local Whisper weights are needed.
    CONFIDENCE_WORKERS: int = int(os.getenv("CONFIDENCE_WORKERS", "1"))
    GROQ_TRANSCRIBE_MODEL: str = os.getenv(
        "GROQ_TRANSCRIBE_MODEL", "whisper-large-v3-turbo"
    )

    # --- ElevenLabs TTS ---
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam


settings = Settings()

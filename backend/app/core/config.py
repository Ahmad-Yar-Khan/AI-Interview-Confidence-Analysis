"""
config.py
---------
Centralizes every environment variable the app reads. Before this file existed,
os.getenv() calls were scattered across main.py, gemini_client.py, and
feature_extractor.py — there was no single place to see what the app needs to
run.

GEMINI_API_KEY has been removed entirely (not just renamed): it was a leftover
check from before this app migrated from Gemini to Groq, and it checked the
wrong variable — the startup warning and /api/health's "gemini_key_set" field
both used to read GEMINI_API_KEY while the actual Groq client only ever reads
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

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- RAG / question bank ---
    DATA_PATH: str = os.getenv("DATA_PATH", "data/master_questions.csv")

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

    # --- ElevenLabs TTS ---
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam


settings = Settings()

"""
tts.py (route)
----------------
POST /api/tts — ElevenLabs TTS proxy (keeps the API key server-side).

Voice IDs — swap ELEVENLABS_VOICE_ID in .env to change voice
Free-tier premade voices (no paid plan needed):
  Adam  (deep, authoritative male):   pNInz6obpgDQGcFmaJgB  ← default
  Josh  (warm male):                  TxGEqnHWrfWFTfGW9XjX
  Bella (soft female):                EXAVITQu4vr4xnSDxMaL
  Antoni(smooth male):                ErXwobaYiN019PkySvjV
Paid-plan only (voice library):
  Rachel (professional female):       21m00Tcm4TlvDq8ikWAM
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_EL_MODEL = "eleven_turbo_v2"  # fastest, good quality; swap to eleven_multilingual_v2 for more langs


class TTSRequest(BaseModel):
    text: str


@router.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    api_key = settings.ELEVENLABS_API_KEY
    if not api_key or api_key == "your_elevenlabs_key_here":
        raise HTTPException(503, "ELEVENLABS_API_KEY not set in .env")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}"
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

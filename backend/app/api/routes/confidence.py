"""
confidence.py (route)
----------------------
POST /api/confidence — audio -> predicted_label, confidence_probability,
confidence_score_1_to_10, transcript.

The prediction itself (Whisper transcription + ensemble model) runs in a
separate worker process via app.services.confidence_service — this route only
saves the upload to a temp file and awaits the worker's result, so the event
loop stays free to serve other requests while Whisper runs.
"""

import logging
import os
import shutil
import tempfile
from concurrent.futures.process import BrokenProcessPool

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services import confidence_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/confidence")
async def analyze_confidence(audio: UploadFile = File(...)):
    """
    Upload audio → returns predicted_label, confidence_probability, confidence_score_1_to_10.
    Requires CONFIDENCE_MODEL_PATH and CONFIDENCE_FEATURES_PATH env vars.
    """
    if not confidence_service.is_available():
        raise HTTPException(503, "Confidence module failed to load. Check server logs.")

    tmp_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(audio.filename or "recording.webm")[-1] or ".webm"
        tmp_path = os.path.join(tmp_dir, f"audio{ext}")
        with open(tmp_path, "wb") as f:
            f.write(await audio.read())

        try:
            result = await confidence_service.predict(tmp_path)
        except (BrokenProcessPool, RuntimeError) as e:
            logger.error(f"Confidence worker error: {e}")
            raise HTTPException(503, "Confidence worker unavailable. Check server logs.")

        if not result:
            raise HTTPException(500, "Prediction failed. Check model files and audio.")
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

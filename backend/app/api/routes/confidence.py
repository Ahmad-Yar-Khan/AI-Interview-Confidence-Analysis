"""
confidence.py (route)
----------------------
POST /api/confidence — audio -> predicted_label, confidence_probability,
confidence_score_1_to_10 (feature_extractor / now app.ml.confidence_model).

The try/except import guard is kept local to this route module (rather than
moved into confidence_model.py itself) because it's specifically about
"can this ROUTE be offered at all" — the same pattern main.py used to guard
optional dependencies (faster-whisper, pydub, etc.) that might not be
installed in every environment.
"""

import logging
import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

try:
    from app.ml.confidence_model import predict_confidence_for_audio_vscode
    _confidence_available = True
except Exception as _ce:
    _confidence_available = False
    logger.warning(f"Confidence module unavailable: {_ce}")


def is_confidence_available() -> bool:
    return _confidence_available


router = APIRouter()


@router.post("/api/confidence")
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

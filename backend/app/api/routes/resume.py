"""
resume.py (route)
-------------------
POST /api/upload-resume — Upload PDF/DOCX/TXT → session.
"""

import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.text_extractor import extract_text
from app.llm.validation import strip_injection_lines
from app.services.resume_service import looks_like_resume, guess_name
from app.services.session_store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/upload-resume")
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
        # pdfplumber/python-docx are synchronous — run in a thread so parsing
        # a PDF doesn't block the event loop.
        resume_text = await asyncio.to_thread(extract_text, contents, file.filename)
    except Exception as e:
        logger.exception("Text extraction failed")
        raise HTTPException(500, f"Failed to read resume: {str(e)}")

    if not resume_text.strip():
        raise HTTPException(422, "Could not extract any text from the file.")

    if not looks_like_resume(resume_text):
        raise HTTPException(
            422,
            "The uploaded file does not appear to be a resume. "
            "Please upload a resume containing sections like Experience, Education, or Skills.",
        )

    # Lines that try to instruct the interviewer model are removed before the text
    # is stored, so they can neither reach a prompt nor be quoted as "evidence".
    resume_text, removed = strip_injection_lines(resume_text)
    if removed:
        logger.warning(f"Removed {len(removed)} instruction-like line(s) from uploaded resume: {removed}")

    session_id = str(uuid.uuid4())
    session_store.create(session_id, {
        "resume_text": resume_text,
        "filename": file.filename,
        "questions": [],
        "answers": [],
    })

    logger.info(f"Session {session_id} created — {len(resume_text)} chars from {file.filename}")
    return {
        "session_id": session_id,
        "profile": {
            "name": guess_name(resume_text),
            "title": "",
            "filename": file.filename,
            "char_count": len(resume_text),
        },
        "warnings": (
            [f"Removed {len(removed)} line(s) that looked like instructions to the AI."] if removed else []
        ),
    }

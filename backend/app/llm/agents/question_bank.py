"""
question_bank.py
----------------
Loads the fixed 100-question CSV that the asking agent selects from.

The CSV is read once per process and cached; the agent never invents
questions, it only chooses from these rows.
"""

import csv
import logging
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = {"question_id", "question", "topic", "difficulty"}


def _clean(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _normalize_row(row: dict) -> dict:
    return {
        "id": _clean(row.get("question_id")),
        "question": _clean(row.get("question")),
        "role": _clean(row.get("role")),
        "topic": _clean(row.get("topic")),
        "subtopic": _clean(row.get("subtopic")),
        "difficulty": _clean(row.get("difficulty")),
        "question_type": _clean(row.get("question_type")),
        "experience_level": _clean(row.get("experience_level")),
        "expected_answer": _clean(row.get("expected_answer_points")),
        "follow_ups": _clean(row.get("follow_up_questions")),
    }


@lru_cache(maxsize=1)
def load_question_bank(path: str | None = None) -> tuple[dict, ...]:
    """Return the question bank as an immutable tuple of normalized rows."""
    csv_path = Path(path or settings.QUESTION_BANK_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Question bank not found at '{csv_path}'. Set QUESTION_BANK_PATH or add the CSV."
        )

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = _REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Question bank is missing columns: {sorted(missing)}")
        questions = tuple(
            q for q in (_normalize_row(row) for row in reader) if q["id"] and q["question"]
        )

    logger.info(f"Loaded {len(questions)} questions from {csv_path}")
    return questions


def get_question_bank(path: str | None = None) -> list[dict]:
    return list(load_question_bank(path))

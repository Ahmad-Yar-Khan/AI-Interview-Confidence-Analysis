"""
Sanity tests for question_service's pure-logic helpers (the ones that don't
require a live FAISS index / Groq call). Run from backend/ with:
    pytest tests/test_question_service.py
"""

from app.services.question_service import _dedup_questions


def test_dedup_falls_back_to_string_prefix_when_rag_not_ready():
    # _rag_ready is False in a bare test environment (no init_rag() call),
    # so this exercises the string-prefix fallback path, not the SBERT path.
    # The dedup key is question[:80].lower().strip() — an exact match on the
    # first 80 characters, not a fuzzy/substring match — so these two must
    # share an identical first 80 characters to be treated as duplicates.
    shared_prefix = "What is a hash table and how does it work internally in terms of memory layout and design?"
    assert len(shared_prefix) >= 80  # sanity-check the fixture itself

    questions = [
        {"question": shared_prefix},
        {"question": shared_prefix + " Extra trailing context that should not matter."},
        {"question": "Explain the CAP theorem in distributed systems."},
    ]
    result = _dedup_questions(questions)
    # First two share an identical 80-char prefix -> collapse to one; third is distinct.
    assert len(result) == 2


def test_dedup_handles_empty_list():
    assert _dedup_questions([]) == []

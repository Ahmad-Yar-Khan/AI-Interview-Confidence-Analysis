"""
Tests for follow-up eligibility and creation (followup_service). The Groq call
is stubbed. Run from backend/ with:  pytest tests/test_followup_service.py
"""

import asyncio

import pytest

from app.core.config import settings
from app.services import followup_service as fs


def make_session(*answers):
    return {
        "years_experience": 3,
        "questions": [{"id": a["question_id"], "question": a["question"]} for a in answers],
        "answers": list(answers),
    }


def answer(qid="q1", overall=40, text="I used a cache, I think.", category="Backend", difficulty="Medium"):
    return {"question_id": qid, "question": "Why did you add a cache?", "user_answer": text,
            "category": category, "difficulty": difficulty, "score": {"overall": overall, "feedback": "vague"}}


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    calls = []

    async def fake(question, answer, score, feedback, years=None):
        calls.append(question)
        await asyncio.sleep(0)
        return {"question": "Earlier, on caching: what did you invalidate it on?", "difficulty": None, "model_answer": "..."}

    monkeypatch.setattr(fs, "generate_followup", fake)
    return calls


def test_weak_answer_gets_followup_with_parent_metadata():
    s = make_session(answer())
    f = asyncio.run(fs.create_followup(s, "q1"))
    assert f["id"] == "f1" and f["parent_id"] == "q1" and f["is_followup"] is True
    assert f["category"] == "Backend" and f["difficulty"] == "Medium"      # inherited from the parent
    assert s["questions"][-1] is f                                          # visible to the report's totals


def test_strong_answer_and_placeholder_transcript_get_none():
    s = make_session(answer(overall=settings.FOLLOWUP_SCORE_THRESHOLD))
    assert asyncio.run(fs.create_followup(s, "q1")) is None
    s = make_session(answer(text=fs.PLACEHOLDER_ANSWER))
    assert asyncio.run(fs.create_followup(s, "q1")) is None
    assert asyncio.run(fs.create_followup(s, "missing")) is None


def test_request_is_idempotent(stub_llm):
    s = make_session(answer())
    a = asyncio.run(fs.create_followup(s, "q1"))
    b = asyncio.run(fs.create_followup(s, "q1"))
    assert a is b and len(stub_llm) == 1 and s["followups"]["count"] == 1


def test_concurrent_requests_for_one_question_generate_once(stub_llm):
    s = make_session(answer())

    async def both():
        return await asyncio.gather(fs.create_followup(s, "q1"), fs.create_followup(s, "q1"))

    results = asyncio.run(both())
    assert len(stub_llm) == 1 and len([r for r in results if r]) >= 1 and s["followups"]["count"] == 1


def test_depth_limit_stops_follow_up_chains(monkeypatch):
    monkeypatch.setattr(settings, "FOLLOWUP_MAX_DEPTH", 2)
    s = make_session(answer("q1"))
    f1 = asyncio.run(fs.create_followup(s, "q1"))
    s["answers"].append(answer(f1["id"]))
    f2 = asyncio.run(fs.create_followup(s, f1["id"]))
    assert f2 is not None and s["followups"]["depth"][f2["id"]] == 2
    s["answers"].append(answer(f2["id"]))
    assert asyncio.run(fs.create_followup(s, f2["id"])) is None


def test_total_cap(monkeypatch):
    monkeypatch.setattr(settings, "FOLLOWUP_MAX_TOTAL", 2)
    s = make_session(answer("q1"), answer("q2"), answer("q3"))
    assert asyncio.run(fs.create_followup(s, "q1")) and asyncio.run(fs.create_followup(s, "q2"))
    assert asyncio.run(fs.create_followup(s, "q3")) is None


def test_rejected_followup_means_none_and_frees_the_slot(monkeypatch):
    from app.llm.validation import FollowupRejected

    async def reject(**kw):
        raise FollowupRejected("introduces details not in the question or answer: ['Memcached']")
    monkeypatch.setattr(fs, "generate_followup", reject)
    s = make_session(answer())
    assert asyncio.run(fs.create_followup(s, "q1")) is None
    assert s["followups"]["count"] == 0 and not s["followups"]["pending"]
    assert len(s["questions"]) == 1                                          # nothing was added


def test_failed_generation_releases_its_slot(monkeypatch):
    async def boom(**kw):
        raise RuntimeError("groq down")
    monkeypatch.setattr(fs, "generate_followup", boom)
    s = make_session(answer())
    with pytest.raises(RuntimeError):
        asyncio.run(fs.create_followup(s, "q1"))
    assert s["followups"]["count"] == 0 and not s["followups"]["pending"]
    assert fs.would_follow_up(s, s["answers"][0])                           # can be retried

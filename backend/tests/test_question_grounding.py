"""
Tests that generate_interview_questions() enforces grounding in code: a
"resume" question without verifiable evidence is dropped, and a "role"
question is dropped when no job title was chosen or when it presupposes
anything about the candidate. The Groq call is stubbed.
Run from backend/ with:  pytest tests/test_question_grounding.py
"""

import asyncio
import json

from app.llm import question_generation as qg
from app.services.role_brief_service import build_role_context

RESUME = """Jane Doe
Skills: Python, FastAPI, PostgreSQL, Docker
Projects: SmartInterview - built a FastAPI backend with FAISS retrieval and Groq for question generation.
Experience: Backend Intern at Acme, 2023. Wrote ETL jobs in Airflow."""


def run(llm_reply, monkeypatch, has_role=True, count=5):
    async def fake_chat(prompt, **kw):
        return json.dumps(llm_reply)
    monkeypatch.setattr(qg, "chat", fake_chat)
    return asyncio.run(qg.generate_interview_questions(
        resume_text=RESUME, role_context="TARGET ROLE: Back-End Developer", has_role=has_role, count=count,
    ))


def test_ungrounded_resume_questions_are_dropped(monkeypatch):
    reply = [
        {"kind": "resume", "question": "Why FAISS in SmartInterview?", "category": "Backend",
         "difficulty": "Medium", "model_answer": "...", "evidence": "built a FastAPI backend with FAISS retrieval"},
        {"kind": "resume", "question": "How did you scale your Kafka cluster?", "category": "Streaming",
         "difficulty": "Hard", "model_answer": "...", "evidence": "operated a Kafka cluster at 1M msgs/sec"},
        {"kind": "resume", "question": "No evidence at all?", "category": "X", "difficulty": "Easy", "evidence": None},
    ]
    out = run(reply, monkeypatch)
    assert [q["question"] for q in out] == ["Why FAISS in SmartInterview?"]
    assert out[0]["is_followup"] is False and out[0]["has_answer"] is True


def test_role_questions_need_a_role_and_must_not_presuppose(monkeypatch):
    reply = [
        {"kind": "role", "question": "How would you make an ETL job idempotent?", "category": "Data", "difficulty": "Medium"},
        {"kind": "role", "question": "In your previous role, how did you test APIs?", "category": "QA", "difficulty": "Easy"},
        {"kind": "role", "question": "What happened in your project when it failed?", "category": "QA", "difficulty": "Easy"},
    ]
    out = run(reply, monkeypatch, has_role=True)
    assert [q["question"] for q in out] == ["How would you make an ETL job idempotent?"]

    # "Other": no job title was chosen, so general role questions are not accepted at all.
    assert run(reply, monkeypatch, has_role=False) == []


def test_evidence_match_ignores_case_punctuation_and_line_wraps(monkeypatch):
    reply = [{"kind": "resume", "question": "Q?", "difficulty": "Easy",
              "evidence": "Wrote ETL jobs\nin AIRFLOW"}]
    assert len(run(reply, monkeypatch)) == 1


def test_bad_difficulty_defaults_and_count_is_capped(monkeypatch):
    reply = [{"kind": "resume", "question": f"Explain Python topic {'abcdefgh'[i]}?", "difficulty": "Impossible",
              "evidence": "Python, FastAPI, PostgreSQL"}
             for i in range(8)]
    out = run(reply, monkeypatch, count=5)
    assert len(out) == 5 and all(q["difficulty"] == "Medium" for q in out)


def test_non_list_reply_raises(monkeypatch):
    import pytest
    with pytest.raises(ValueError):
        run({"questions": []}, monkeypatch)


def test_other_role_sends_no_job_title_and_years_are_included():
    ctx = asyncio.run(build_role_context("other", 4))
    assert "TARGET ROLE: none specified" in ctx.text
    assert "4 years" in ctx.text and "Mid level" in ctx.text
    assert ctx.role_name is None and ctx.brief_used is False

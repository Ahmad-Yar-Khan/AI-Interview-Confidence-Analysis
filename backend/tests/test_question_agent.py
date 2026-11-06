"""
Tests for the LangGraph question pipeline. Every Groq call is stubbed, so no
network is used. Run from backend/ with:  pytest tests/test_question_agent.py
"""

import asyncio
import json

import pytest

from app.llm.agents import question_agent as qa
from app.llm.agents.questions import (
    reflection_agent,
    relevance_agent,
    selection_agent,
    tailoring_agent,
)
from app.llm.agents.questions.shared import parse_relevance, parse_selection
from app.llm.agents.questions.state import QuestionAgentState


def stub_agents(
    monkeypatch,
    *,
    relevance="8",
    selected_ids=None,
    approved=True,
    feedback="",
    score=9,
):
    calls = {"relevance": 0, "selection": 0, "tailoring": 0, "reflection": 0}
    prompts = {"tailoring": [], "reflection": []}
    ids = selected_ids or [f"JSE-{i:03d}" for i in range(1, 8)]

    async def fake_relevance(prompt, *, system=None, temperature=0.7):
        calls["relevance"] += 1
        return relevance

    async def fake_selection(prompt, *, system=None, temperature=0.7):
        calls["selection"] += 1
        return json.dumps({
            "selected_questions": [
                {"question_id": qid, "category": "Test", "reason": "stub"} for qid in ids
            ]
        })

    async def fake_tailoring(prompt, *, system=None, temperature=0.7):
        calls["tailoring"] += 1
        prompts["tailoring"].append(prompt)
        return json.dumps({
            "tailored_questions": [
                {"question_id": qid, "original_text": "", "tailored_text": f"Tailored {qid}"}
                for qid in ids
            ]
        })

    async def fake_reflection(prompt, *, system=None, temperature=0.7):
        calls["reflection"] += 1
        prompts["reflection"].append(prompt)
        if isinstance(approved, (list, tuple)):
            ok = approved[min(calls["reflection"] - 1, len(approved) - 1)]
        else:
            ok = approved
        return json.dumps({
            "approved": ok,
            "feedback": "" if ok else feedback,
            "score": score,
        })

    monkeypatch.setattr(relevance_agent, "chat", fake_relevance)
    monkeypatch.setattr(selection_agent, "chat", fake_selection)
    monkeypatch.setattr(tailoring_agent, "chat", fake_tailoring)
    monkeypatch.setattr(reflection_agent, "chat", fake_reflection)
    return calls, prompts


def run(**kwargs):
    return asyncio.run(qa.run_question_agent(
        skills="Python, FastAPI, PostgreSQL, Docker",
        projects="SmartInterview - FastAPI backend with Groq and retrieval.",
        resume_text="Python FastAPI backend with Groq and retrieval for SmartInterview.",
        role="Backend Engineer",
        years=3,
        count=7,
        **kwargs,
    ))


def test_pipeline_returns_seven_tailored_approved_questions(monkeypatch):
    calls, _ = stub_agents(monkeypatch)
    result = run()

    assert result.relevance == 8
    assert result.approved is True
    assert result.reflection_score == 9
    assert len(result.questions) == 7
    assert calls == {"relevance": 1, "selection": 1, "tailoring": 1, "reflection": 1}

    assert [q["source_question_id"] for q in result.questions] == [
        f"JSE-{i:03d}" for i in range(1, 8)
    ]
    assert all(q["question"].startswith("Tailored JSE-") for q in result.questions)
    assert all(q["id"] == f"q{i}" for i, q in enumerate(result.questions, 1))
    assert all(q["is_followup"] is False for q in result.questions)

    lines = result.output.splitlines()
    assert lines[0] == "RELEVANCE: 8"
    assert lines[2] == "QUESTIONS:"
    assert len([line for line in lines if line[:2].rstrip(".").isdigit()]) == 7


def test_reflection_rejection_loops_back_with_feedback(monkeypatch):
    calls, prompts = stub_agents(
        monkeypatch,
        approved=[False, True],
        feedback="Use the Couples Marquee project for the SQL question.",
    )
    result = run()

    assert calls["tailoring"] == 2
    assert calls["reflection"] == 2
    assert result.approved is True
    assert "Use the Couples Marquee project" in prompts["tailoring"][1]


def test_reflection_stops_after_max_revisions(monkeypatch):
    calls, _ = stub_agents(monkeypatch, approved=False, feedback="Still wrong.")
    result = run()

    assert calls["tailoring"] == 2  # default max_revisions
    assert calls["reflection"] == 2
    assert result.approved is False
    assert len(result.questions) == 7
    assert result.output.startswith("RELEVANCE: 8")


def test_low_relevance_still_returns_questions(monkeypatch):
    stub_agents(monkeypatch, relevance="0")
    result = run()
    assert result.relevance == 0
    assert len(result.questions) == 7
    assert result.output.startswith("RELEVANCE: 0")


def test_hallucinated_ids_are_dropped_and_backfilled(monkeypatch):
    stub_agents(monkeypatch, selected_ids=["JSE-001", "NOT-A-REAL-ID", "JSE-002"])
    result = run()

    assert len(result.questions) == 7
    ids = [q["source_question_id"] for q in result.questions]
    assert "NOT-A-REAL-ID" not in ids
    assert ids[:2] == ["JSE-001", "JSE-002"]
    assert len(set(ids)) == 7


@pytest.mark.parametrize("raw, expected", [
    ("7", 7), ("RELEVANCE: 9", 9), ("I would say 4/10", 4), ("10", 10), ("0", 0),
])
def test_relevance_parsing(raw, expected):
    assert parse_relevance(raw) == expected


def test_selection_parser_accepts_preferred_object_shape():
    bank = [
        {"id": "JSE-001", "question": "Q1", "topic": "T", "subtopic": "",
         "difficulty": "Easy", "expected_answer": ""},
        {"id": "JSE-002", "question": "Q2", "topic": "T", "subtopic": "",
         "difficulty": "Easy", "expected_answer": ""},
    ]
    raw = json.dumps({"selected_questions": [{"question_id": "JSE-002"}]})
    selected = parse_selection(raw, bank, count=2)
    assert [q["id"] for q in selected] == ["JSE-002"]


def test_state_accepts_partial_updates():
    state: QuestionAgentState = {"relevance": 5}
    assert state["relevance"] == 5

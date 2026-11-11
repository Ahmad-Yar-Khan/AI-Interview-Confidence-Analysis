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
    selection_agent,
    tailoring_agent,
)
from app.llm.agents.questions.shared import (
    DEFAULT_RELEVANCE,
    parse_relevance,
    parse_selection,
)
from app.llm.agents.questions.state import QuestionAgentState

# JSE-081..JSE-090 are the bank's "Projects & Practical" questions; JSE-001..
# are DSA & Coding. Only project questions are tailored.
PROJECT_IDS = [f"JSE-{i:03d}" for i in range(81, 88)]
DSA_IDS = [f"JSE-{i:03d}" for i in range(1, 8)]


def stub_agents(
    monkeypatch,
    *,
    relevance=8,
    selected_ids=None,
    selection_raw=None,
    tailored_ids=None,
    approved=True,
    feedback="",
    score=9,
):
    calls = {"selection": 0, "tailoring": 0, "reflection": 0}
    prompts = {"selection": [], "tailoring": [], "reflection": []}
    kwargs = {"selection": [], "tailoring": [], "reflection": []}
    ids = selected_ids or PROJECT_IDS
    rewrite_ids = ids if tailored_ids is None else tailored_ids

    async def fake_selection(prompt, *, system=None, temperature=0.7, **kw):
        calls["selection"] += 1
        prompts["selection"].append(prompt)
        kwargs["selection"].append(kw)
        if selection_raw is not None:
            return selection_raw
        payload = {
            "selected_questions": [
                {"question_id": qid, "category": "Test", "reason": "stub"} for qid in ids
            ]
        }
        if relevance is not None:
            payload["relevance"] = relevance
        return json.dumps(payload)

    async def fake_tailoring(prompt, *, system=None, temperature=0.7, **kw):
        calls["tailoring"] += 1
        prompts["tailoring"].append(prompt)
        kwargs["tailoring"].append(kw)
        return json.dumps({
            "tailored_questions": [
                {"question_id": qid, "original_text": "", "tailored_text": f"Tailored {qid}"}
                for qid in rewrite_ids
            ]
        })

    async def fake_reflection(prompt, *, system=None, temperature=0.7, **kw):
        calls["reflection"] += 1
        prompts["reflection"].append(prompt)
        kwargs["reflection"].append(kw)
        if isinstance(approved, (list, tuple)):
            ok = approved[min(calls["reflection"] - 1, len(approved) - 1)]
        else:
            ok = approved
        return json.dumps({
            "approved": ok,
            "feedback": "" if ok else feedback,
            "score": score,
        })

    monkeypatch.setattr(selection_agent, "chat", fake_selection)
    monkeypatch.setattr(tailoring_agent, "chat", fake_tailoring)
    monkeypatch.setattr(reflection_agent, "chat", fake_reflection)
    return calls, prompts, kwargs


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
    calls, _, kwargs = stub_agents(monkeypatch)
    result = run()

    assert result.relevance == 8
    assert result.approved is True
    assert result.reflection_score == 9
    assert len(result.questions) == 7
    # Relevance and selection share one call now.
    assert calls == {"selection": 1, "tailoring": 1, "reflection": 1}
    assert all(kw[0]["reasoning_effort"] == "low" for kw in kwargs.values())

    assert [q["source_question_id"] for q in result.questions] == PROJECT_IDS
    assert all(q["question"].startswith("Tailored JSE-") for q in result.questions)
    assert all(q["id"] == f"q{i}" for i, q in enumerate(result.questions, 1))
    assert all(q["is_followup"] is False for q in result.questions)

    lines = result.output.splitlines()
    assert lines[0] == "RELEVANCE: 8"
    assert lines[2] == "QUESTIONS:"
    assert len([line for line in lines if line[:2].rstrip(".").isdigit()]) == 7


def test_reflection_rejection_loops_back_with_feedback(monkeypatch):
    calls, prompts, _ = stub_agents(
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
    calls, _, _ = stub_agents(monkeypatch, approved=False, feedback="Still wrong.")
    result = run()

    assert calls["tailoring"] == 2  # default max_revisions
    assert calls["reflection"] == 2
    assert result.approved is False
    assert len(result.questions) == 7
    assert result.output.startswith("RELEVANCE: 8")


def test_low_relevance_still_returns_questions(monkeypatch):
    stub_agents(monkeypatch, relevance=0)
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


def test_no_project_questions_skips_tailoring_and_reflection(monkeypatch):
    calls, _, _ = stub_agents(monkeypatch, selected_ids=DSA_IDS)
    result = run()

    assert calls == {"selection": 1, "tailoring": 0, "reflection": 0}
    assert [q["source_question_id"] for q in result.questions] == DSA_IDS
    assert result.approved is True
    assert result.output.startswith("RELEVANCE: 8")
    assert len([l for l in result.output.splitlines() if l[:2].rstrip(".").isdigit()]) == 7


def test_only_project_questions_are_sent_and_rewritten(monkeypatch):
    mixed = DSA_IDS[:4] + PROJECT_IDS[:3]
    # The stubbed model tries to rewrite every question, DSA ones included.
    calls, prompts, _ = stub_agents(monkeypatch, selected_ids=mixed)
    result = run()

    assert calls["tailoring"] == 1 and calls["reflection"] == 1
    for qid in DSA_IDS[:4]:
        assert qid not in prompts["tailoring"][0]
        assert qid not in prompts["reflection"][0]
    by_id = {q["source_question_id"]: q["question"] for q in result.questions}
    assert all(by_id[qid] == f"Tailored {qid}" for qid in PROJECT_IDS[:3])
    assert not any(by_id[qid].startswith("Tailored") for qid in DSA_IDS[:4])


def test_unchanged_tailoring_skips_reflection(monkeypatch):
    calls, _, _ = stub_agents(monkeypatch, tailored_ids=[])
    result = run()

    assert calls == {"selection": 1, "tailoring": 1, "reflection": 0}
    assert result.approved is True
    assert not any(q["question"].startswith("Tailored") for q in result.questions)


def test_missing_relevance_uses_default(monkeypatch):
    stub_agents(monkeypatch, relevance=None)
    result = run()
    assert result.relevance == DEFAULT_RELEVANCE
    assert len(result.questions) == 7


def test_unparseable_selection_falls_back_to_keyword_choice(monkeypatch):
    stub_agents(monkeypatch, selection_raw="sorry, I cannot help with that")
    result = run()
    assert result.relevance == DEFAULT_RELEVANCE
    ids = [q["source_question_id"] for q in result.questions]
    assert len(ids) == 7 and len(set(ids)) == 7


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

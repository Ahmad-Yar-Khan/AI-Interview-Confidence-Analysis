import asyncio

from app.api.routes.scoring import (
    MAX_INTERVIEW_QUESTIONS,
    _append_followup,
    _followup_cap,
    _question_depth,
)
from app.api.schemas.answer import AnswerPayload
from app.llm.agents.evaluations import evaluation_flow_agent as ef


def evaluation(score):
    return {
        "score": score,
        "criteria": {
            "correctness": score,
            "completeness": score,
            "clarity": score,
            "depth": score,
        },
        "feedback": "Feedback about the weak areas.",
        "improvements": ["Mention idempotency", "Give an example"],
        "is_behavioral": False,
    }


def stub_flow(monkeypatch, score, followup_text="What about idempotency?"):
    calls = {"eval": 0, "followup": 0, "followup_kwargs": None}

    async def fake_evaluate(**kwargs):
        calls["eval"] += 1
        return evaluation(score)

    async def fake_followup(**kwargs):
        calls["followup"] += 1
        calls["followup_kwargs"] = kwargs
        return {"followup_question": followup_text, "is_valid": bool(followup_text)}

    monkeypatch.setattr(ef, "evaluate_answer", fake_evaluate)
    monkeypatch.setattr(ef, "generate_followup_question", fake_followup)
    return calls


def test_strong_answer_does_not_generate_followup(monkeypatch):
    calls = stub_flow(monkeypatch, score=7)
    result = asyncio.run(ef.run_evaluation_flow(
        question="Q",
        user_answer="A",
        followup_count=0,
    ))

    assert result.evaluation["score"] == 7
    assert result.followup_question is None
    assert result.should_followup is False
    assert calls["followup"] == 0


def test_weak_answer_generates_first_followup(monkeypatch):
    calls = stub_flow(monkeypatch, score=5)
    result = asyncio.run(ef.run_evaluation_flow(
        question="Q",
        user_answer="A",
        followup_count=0,
    ))

    assert result.followup_question == "What about idempotency?"
    assert result.should_followup is True
    assert calls["followup"] == 1
    assert "Feedback about the weak areas." in calls["followup_kwargs"]["feedback"]
    assert "Mention idempotency" in calls["followup_kwargs"]["feedback"]


def test_weak_answer_at_depth_one_gets_second_followup(monkeypatch):
    calls = stub_flow(monkeypatch, score=4)
    result = asyncio.run(ef.run_evaluation_flow(
        question="Q",
        user_answer="A",
        followup_count=1,
    ))

    assert result.should_followup is True
    assert calls["followup"] == 1


def test_no_third_followup_at_depth_two(monkeypatch):
    calls = stub_flow(monkeypatch, score=3)
    result = asyncio.run(ef.run_evaluation_flow(
        question="Q",
        user_answer="A",
        followup_count=2,
    ))

    assert result.followup_question is None
    assert result.should_followup is False
    assert calls["followup"] == 0


def test_already_asked_followup_blocks_another(monkeypatch):
    calls = stub_flow(monkeypatch, score=3)
    result = asyncio.run(ef.run_evaluation_flow(
        question="Q",
        user_answer="A",
        followup_count=0,
        followup_allowed=False,
    ))

    assert result.should_followup is False
    assert calls["followup"] == 0


def test_depth_counts_followup_chain():
    session = {
        "questions": [
            {"id": "q1", "is_followup": False},
            {"id": "f1", "is_followup": True, "parent_id": "q1"},
            {"id": "f2", "is_followup": True, "parent_id": "f1"},
        ]
    }

    assert _question_depth(session, "q1") == 0
    assert _question_depth(session, "f1") == 1
    assert _question_depth(session, "f2") == 2


def test_append_followup_links_parent_and_depth():
    session = {"questions": [{"id": "q1", "category": "Backend", "difficulty": "Medium"}]}

    record = _append_followup(
        session,
        question=session["questions"][0],
        question_id="q1",
        text="What about idempotency?",
        depth=0,
    )

    assert record["id"] == "f1"
    assert record["parent_id"] == "q1"
    assert record["is_followup"] is True
    assert session["questions"][-1] is record
    assert session["followups"]["depth"]["f1"] == 1
    assert _question_depth(session, "f1") == 1


def test_score_route_returns_and_stores_followup(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.routes import scoring as scoring_route
    from app.llm.agents.evaluations import EvaluationFlowResult
    from app.main import app
    from app.services.session_store import session_store

    session_id = "test-score-followup"
    session_store.create(session_id, {
        "questions": [{
            "id": "q1",
            "question": "Explain GET and POST.",
            "category": "Backend",
            "difficulty": "Medium",
            "has_answer": True,
            "model_answer": "GET reads; POST writes.",
        }],
        "answers": [],
    })

    async def fake_flow(**kwargs):
        return EvaluationFlowResult(
            evaluation=evaluation(4),
            followup_question="What about idempotency?",
            should_followup=True,
        )

    monkeypatch.setattr(scoring_route, "run_evaluation_flow", fake_flow)
    client = TestClient(app)
    response = client.post("/api/score", json={
        "session_id": session_id,
        "question_id": "q1",
        "question_text": "Explain GET and POST.",
        "model_answer": "GET reads; POST writes.",
        "user_answer": "GET reads and POST sends.",
        "category": "Backend",
        "difficulty": "Medium",
        "has_answer": True,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["evaluation_score"] == 4
    assert data["followup"]["question"] == "What about idempotency?"
    assert data["followup"]["parent_id"] == "q1"

    stored = session_store.get(session_id)
    assert stored["answers"][0]["score"]["evaluation_score"] == 4
    assert stored["questions"][-1]["question"] == "What about idempotency?"
    session_store.delete(session_id)


def test_score_route_does_not_follow_up_placeholder_answer(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.routes import scoring as scoring_route
    from app.llm.agents.evaluations import EvaluationFlowResult
    from app.main import app
    from app.services.session_store import session_store

    session_id = "test-score-placeholder"
    session_store.create(session_id, {
        "questions": [{
            "id": "q1",
            "question": "Explain GET and POST.",
            "category": "Backend",
            "difficulty": "Medium",
            "has_answer": True,
            "model_answer": "GET reads; POST writes.",
        }],
        "answers": [],
    })

    captured = {}

    async def fake_flow(**kwargs):
        captured.update(kwargs)
        return EvaluationFlowResult(
            evaluation=evaluation(4),
            followup_question=None,
            should_followup=False,
        )

    monkeypatch.setattr(scoring_route, "run_evaluation_flow", fake_flow)
    client = TestClient(app)
    response = client.post("/api/score", json={
        "session_id": session_id,
        "question_id": "q1",
        "question_text": "Explain GET and POST.",
        "model_answer": "GET reads; POST writes.",
        "user_answer": "[voice response]",
        "category": "Backend",
        "difficulty": "Medium",
        "has_answer": True,
    })

    assert response.status_code == 200
    assert captured["followup_allowed"] is False
    assert response.json()["followup"] is None
    session_store.delete(session_id)


def _payload(**overrides):
    data = {
        "session_id": "s",
        "question_id": "q1",
        "question_text": "Q",
        "user_answer": "A",
        "category": "Backend",
        "difficulty": "Medium",
    }
    data.update(overrides)
    return AnswerPayload(**data)


def _session_with_questions(count):
    return {"questions": [{"id": f"q{i}"} for i in range(count)]}


def test_followup_cap_blocks_when_not_last_question():
    session = _session_with_questions(MAX_INTERVIEW_QUESTIONS)
    allowed, overflow = _followup_cap(session, _payload(
        queue_length=MAX_INTERVIEW_QUESTIONS,
        question_position=5,
    ))

    assert allowed is False
    assert overflow is False


def test_followup_cap_allows_followup_of_last_question():
    session = _session_with_questions(MAX_INTERVIEW_QUESTIONS)
    allowed, overflow = _followup_cap(session, _payload(
        queue_length=MAX_INTERVIEW_QUESTIONS,
        question_position=MAX_INTERVIEW_QUESTIONS - 1,
    ))

    assert allowed is True
    assert overflow is True


def test_append_followup_refuses_past_cap_without_overflow():
    session = _session_with_questions(MAX_INTERVIEW_QUESTIONS)

    assert _append_followup(session, {}, "q11", "What about X?", 0) is None
    assert len(session["questions"]) == MAX_INTERVIEW_QUESTIONS


def test_append_followup_allows_one_overflow_followup():
    session = _session_with_questions(MAX_INTERVIEW_QUESTIONS)

    record = _append_followup(
        session, {}, "q11", "What about X?", 0, allow_overflow=True,
    )

    assert record is not None
    assert len(session["questions"]) == MAX_INTERVIEW_QUESTIONS + 1
    assert _append_followup(
        session, {}, "q11", "Another?", 0, allow_overflow=True,
    ) is None


def test_score_route_passes_cap_block_to_flow(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.routes import scoring as scoring_route
    from app.llm.agents.evaluations import EvaluationFlowResult
    from app.main import app
    from app.services.session_store import session_store

    session_id = "test-score-cap"
    questions = [
        {"id": f"q{i + 1}", "question": "Q", "category": "Backend", "difficulty": "Medium"}
        for i in range(MAX_INTERVIEW_QUESTIONS)
    ]
    session_store.create(session_id, {"questions": questions, "answers": []})

    captured = {}

    async def fake_flow(**kwargs):
        captured.update(kwargs)
        return EvaluationFlowResult(
            evaluation=evaluation(3),
            followup_question=None,
            should_followup=False,
        )

    monkeypatch.setattr(scoring_route, "run_evaluation_flow", fake_flow)
    client = TestClient(app)
    response = client.post("/api/score", json={
        "session_id": session_id,
        "question_id": "q6",
        "question_text": "Q",
        "user_answer": "Weak answer.",
        "category": "Backend",
        "difficulty": "Medium",
        "queue_length": MAX_INTERVIEW_QUESTIONS,
        "question_position": 5,
    })

    assert response.status_code == 200
    assert captured["followup_allowed"] is False
    assert response.json()["followup"] is None
    session_store.delete(session_id)

import asyncio
import json

from app.llm.agents.evaluations import followup_agent as fa


def test_generates_a_valid_followup(monkeypatch):
    seen = {}

    async def fake_chat(prompt, **kw):
        seen["prompt"] = prompt
        seen["system"] = kw.get("system")
        return json.dumps({
            "followup_question": "You covered GET and POST; what about idempotency when choosing PUT?"
        })

    monkeypatch.setattr(fa, "chat", fake_chat)
    result = asyncio.run(fa.generate_followup_question(
        question="Explain GET, POST, and PUT.",
        answer="GET reads, POST creates, and PUT replaces.",
        feedback="Did not mention idempotency.",
    ))

    assert result["is_valid"] is True
    assert "idempotency" in result["followup_question"]
    assert "<question>" in seen["prompt"]
    assert "<answer>" in seen["prompt"]
    assert "<weak_points>" in seen["prompt"]
    assert "You are the Interviewer Agent" in seen["system"]


def test_unusable_json_is_retried_then_returns_none(monkeypatch):
    calls = []

    async def fake_chat(prompt, **kw):
        calls.append(prompt)
        return "not json"

    monkeypatch.setattr(fa, "chat", fake_chat)
    result = asyncio.run(fa.generate_followup_question(
        question="Q",
        answer="A",
        feedback="weak",
    ))

    assert result == {"followup_question": None, "is_valid": False}
    assert len(calls) == 2


def test_unsafe_or_too_long_followup_is_rejected(monkeypatch):
    async def fake_chat(prompt, **kw):
        return json.dumps({
            "followup_question": "word " * 60,
        })

    monkeypatch.setattr(fa, "chat", fake_chat)
    result = asyncio.run(fa.generate_followup_question(
        question="Q",
        answer="A",
        feedback="weak",
    ))

    assert result == {"followup_question": None, "is_valid": False}

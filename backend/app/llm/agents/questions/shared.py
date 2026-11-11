"""
Shared helpers for the question agents: prompt context builders, parsers and
deterministic fallbacks.
"""

import json
import logging
import re

from app.llm.agents.questions.state import QuestionAgentState
from app.llm.groq_client import parse_json

logger = logging.getLogger(__name__)

VALID_DIFFICULTY = {"Easy", "Medium", "Hard"}
# The only bank topic the tailoring agent personalizes.
PROJECT_CATEGORY = "Projects & Practical"
# Used when the selection reply omits a readable relevance score.
DEFAULT_RELEVANCE = 5
MAX_CONTEXT_CHARS = 4000
MAX_RESUME_EXCERPT = 3000
MAX_REFLECTION_RESUME = 6000

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "for", "to", "at", "on", "with",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "by", "from", "you", "your", "how", "what",
    "why", "when", "which", "would", "could", "should", "do", "does", "did",
    "explain", "describe", "implement", "write", "find", "given", "using",
}


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def candidate_context(state: QuestionAgentState) -> str:
    skills = (state.get("skills") or "").strip()
    projects = (state.get("projects") or "").strip()
    excerpt = (state.get("resume_text") or "").strip()[:MAX_RESUME_EXCERPT]
    parts = [
        f"<skills>\n{skills[:MAX_CONTEXT_CHARS] or '(none parsed)'}\n</skills>",
        f"<projects>\n{projects[:MAX_CONTEXT_CHARS] or '(none parsed)'}\n</projects>",
        f"<resume_excerpt>\n{excerpt or '(empty resume)'}\n</resume_excerpt>",
    ]
    return "\n\n".join(parts)


def resume_excerpt(state: QuestionAgentState) -> str:
    text = (state.get("resume_text") or "").strip()
    if not text:
        text = "\n".join(
            p for p in ((state.get("skills") or "").strip(), (state.get("projects") or "").strip()) if p
        )
    return text[:MAX_REFLECTION_RESUME] or "(empty resume)"


def bank_block(bank: list[dict]) -> str:
    return "\n".join(
        f"[{q['id']}] ({q['topic']}"
        f"{' / ' + q['subtopic'] if q['subtopic'] else ''}) "
        f"[{q['difficulty']}] {q['question']}"
        for q in bank
    )


def is_project_question(question: dict) -> bool:
    return question.get("category") == PROJECT_CATEGORY


def project_questions(questions: list[dict]) -> list[dict]:
    return [q for q in questions if is_project_question(q)]


def questions_payload(questions: list[dict]) -> str:
    """Render formatted questions as JSON for prompting/reflection."""
    payload = [
        {
            "question_id": q.get("source_question_id"),
            "question": q.get("question"),
            "category": q.get("category"),
            "difficulty": q.get("difficulty"),
        }
        for q in questions
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ── Selection helpers ────────────────────────────────────────────────────────

def question_tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9+#.]+", (text or "").lower())
        if len(t) > 2 and t not in STOPWORDS
    }


def score_question(question: dict, candidate_tokens: set[str]) -> int:
    asked = question_tokens(f"{question['question']} {question['topic']} {question['subtopic']}")
    return len(asked & candidate_tokens)


def fill_from_fallback(
    selected: list[dict], bank: list[dict], candidate_tokens: set[str] | None, count: int,
) -> list[dict]:
    """Fill any shortfall with the highest keyword-overlap questions, deterministically."""
    chosen = {q["id"] for q in selected}
    tokens = candidate_tokens or set()
    ranked = sorted(
        (q for q in bank if q["id"] not in chosen),
        key=lambda q: (-score_question(q, tokens), q["difficulty"] != "Easy", q["id"]),
    )
    for q in ranked:
        selected.append(q)
        if len(selected) >= count:
            break
    return selected


def format_question(index: int, question: dict) -> dict:
    difficulty = question["difficulty"] if question["difficulty"] in VALID_DIFFICULTY else "Medium"
    answer = question["expected_answer"] or None
    return {
        "id": f"q{index}",
        "question_id": f"q{index}",
        "question": question["question"],
        "category": question["topic"] or "General",
        "difficulty": difficulty,
        "model_answer": answer,
        "has_answer": bool(answer),
        "is_followup": False,
        "source_question_id": question["id"],
    }


def normalize_question_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_relevance(raw: str) -> int:
    match = re.search(r"\b(10|[0-9])\b", raw or "")
    if not match:
        raise ValueError(f"Relevance agent returned no score: {raw!r}")
    return max(0, min(10, int(match.group(1))))


def parse_relevance_field(data) -> int:
    """Relevance from the selection reply's "relevance" field, or DEFAULT_RELEVANCE."""
    value = data.get("relevance") if isinstance(data, dict) else None
    if value is None:
        logger.warning(f"Selection reply has no relevance; using {DEFAULT_RELEVANCE}")
        return DEFAULT_RELEVANCE
    try:
        return parse_relevance(str(value))
    except ValueError:
        logger.warning(f"Unreadable relevance {value!r}; using {DEFAULT_RELEVANCE}")
        return DEFAULT_RELEVANCE


def parse_selection(raw, bank: list[dict], count: int) -> list[dict]:
    """
    Parse the selection agent's JSON (raw text or an already-parsed value).
    Accepts both the preferred ``{"selected_questions": [...]}`` shape and a
    bare JSON array.
    """
    data = parse_json(raw) if isinstance(raw, str) else raw
    if isinstance(data, dict):
        items = data.get("selected_questions")
        if items is None:
            items = data.get("questions", [])
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("Question selector did not return a JSON object or array")

    by_id = {q["id"]: q for q in bank}
    selected: list[dict] = []
    seen: set[str] = set()

    for item in items or []:
        qid = item.get("question_id") if isinstance(item, dict) else item
        qid = normalize_question_id(qid)
        if qid in seen or qid not in by_id:
            logger.info(f"Dropped selected question {qid!r}: not in bank or duplicate")
            continue
        seen.add(qid)
        selected.append(by_id[qid])
        if len(selected) >= count:
            break

    return selected


# ── Reflection helpers ───────────────────────────────────────────────────────

def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "approved", "pass"}
    return bool(value)


def clamp_score(value, low: int = 1, high: int = 10) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, score))

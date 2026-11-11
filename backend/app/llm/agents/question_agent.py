"""
question_agent.py
-----------------
LangGraph orchestrator for the question-asking pipeline.

Flow:
    select_questions --(any "Projects & Practical" question?)--no--> compose_output -> END
           |yes
           v
    tailor_questions --(anything rewritten?)--no--> compose_output
           |yes
           v
    reflect_on_questions --approved?--yes--> compose_output
           |no (and revisions left)
           +--> tailor_questions (retry with feedback)

The selection node scores how well the fixed bank matches the candidate and
picks exactly `count` questions (7 by default) in a single LLM call. The
tailoring node personalizes only the "Projects & Practical" questions with the
candidate's real projects/skills. The reflection node reviews those rewrites;
rejected drafts loop back to tailoring with explicit feedback, up to
`max_revisions` attempts. Tailoring and reflection are skipped when there is
nothing to personalize, which keeps the pipeline's token use (and Groq rate
limit pressure) down.

Final output:
    RELEVANCE: <0-10>
    1. ...
    2. ...

The pipeline never invents a question: selection only returns bank IDs, and
tailoring/reflection can only rewrite text for already-selected IDs.
"""

import logging
from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.llm.agents.question_bank import get_question_bank
from app.llm.agents.questions.shared import project_questions
from app.llm.agents.questions import (
    REFLECTION_SYSTEM_PROMPT,
    SELECTION_SYSTEM_PROMPT,
    TAILORING_SYSTEM_PROMPT,
    QuestionAgentState,
    reflect_on_questions,
    select_questions,
    tailor_questions,
)

logger = logging.getLogger(__name__)

__all__ = [
    "QuestionAgentResult",
    "question_agent_graph",
    "run_question_agent",
    "SELECTION_SYSTEM_PROMPT",
    "TAILORING_SYSTEM_PROMPT",
    "REFLECTION_SYSTEM_PROMPT",
]

_MAX_REVISIONS = 2


@dataclass
class QuestionAgentResult:
    relevance: int
    questions: list[dict]
    output: str
    approved: bool = True
    reflection_score: int = 0


def _final_questions(state) -> list[dict]:
    # Tailoring is skipped when no project question was selected, so fall back
    # to the selection's base questions.
    return (
        state.get("tailored_questions")
        or state.get("questions")
        or state.get("base_questions")
        or []
    )


def compose_output(state: QuestionAgentState) -> dict:
    questions = _final_questions(state)
    lines = [f"RELEVANCE: {state['relevance']}", "", "QUESTIONS:"]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q['question']}")
    return {"output": "\n".join(lines)}


def _route_after_selection(state: QuestionAgentState) -> str:
    if project_questions(state.get("base_questions") or []):
        return "tailoring"
    logger.info("No project questions selected; skipping tailoring and reflection.")
    return "compose"


def _route_after_tailoring(state: QuestionAgentState) -> str:
    if state.get("tailored_changed", 0) > 0:
        return "reflection"
    logger.info("Tailoring changed nothing; skipping reflection.")
    return "compose"


def _route_after_reflection(state: QuestionAgentState) -> str:
    if state.get("reflection_approved"):
        return "compose"

    revisions = state.get("revisions", 0)
    max_revisions = state.get("max_revisions", _MAX_REVISIONS)
    if revisions < max_revisions:
        logger.info(
            f"Reflection rejected revision {revisions}; retrying tailoring "
            f"(max {max_revisions})."
        )
        return "tailoring"

    logger.warning(
        f"Reflection still rejected after {revisions} tailoring attempt(s); "
        "returning the best-effort questions."
    )
    return "compose"


def _build_graph():
    graph = StateGraph(QuestionAgentState)
    graph.add_node("select_questions", select_questions)
    graph.add_node("tailor_questions", tailor_questions)
    graph.add_node("reflect_on_questions", reflect_on_questions)
    graph.add_node("compose_output", compose_output)

    graph.add_edge(START, "select_questions")
    graph.add_conditional_edges(
        "select_questions",
        _route_after_selection,
        {"tailoring": "tailor_questions", "compose": "compose_output"},
    )
    graph.add_conditional_edges(
        "tailor_questions",
        _route_after_tailoring,
        {"reflection": "reflect_on_questions", "compose": "compose_output"},
    )
    graph.add_conditional_edges(
        "reflect_on_questions",
        _route_after_reflection,
        {"tailoring": "tailor_questions", "compose": "compose_output"},
    )
    graph.add_edge("compose_output", END)
    return graph.compile()


question_agent_graph = _build_graph()


async def run_question_agent(
    *,
    skills: str = "",
    projects: str = "",
    resume_text: str = "",
    role: str = "",
    years: int | None = None,
    count: int | None = None,
    bank: list[dict] | None = None,
    max_revisions: int | None = None,
) -> QuestionAgentResult:
    """
    Run the asking pipeline and return the relevance score, the frontend-ready
    question dicts, and the rendered `RELEVANCE: ...` output.
    """
    question_bank = bank if bank is not None else get_question_bank()
    if not question_bank:
        raise ValueError("Question bank is empty")

    requested = max(1, min(count or settings.QUESTION_AGENT_COUNT, len(question_bank)))
    final = await question_agent_graph.ainvoke({
        "skills": skills,
        "projects": projects,
        "resume_text": resume_text,
        "role": role,
        "years": years,
        "count": requested,
        "bank": question_bank,
        "max_revisions": max_revisions if max_revisions is not None else _MAX_REVISIONS,
    })
    return QuestionAgentResult(
        relevance=final["relevance"],
        questions=_final_questions(final),
        output=final["output"],
        approved=final.get("reflection_approved", True),
        reflection_score=final.get("reflection_score", 0),
    )

"""
Evaluation Flow Agent
---------------------
LangGraph that evaluates one answer and decides whether to ask a follow-up.

Flow:
    START -> evaluate -> score < 6 and follow-up allowed and depth < 2?
                                | yes                         | no
                                v                             v
                           followup -> END                   END

The graph is run once per submitted answer. The caller passes `followup_count`
(depth of the question being answered) and `followup_allowed` (false when this
question already has a follow-up). A base question has depth 0, its first
follow-up has depth 1, and its second follow-up has depth 2. Once depth reaches
2, the flow stops asking follow-ups and the interview moves to the next question.
"""

import logging
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.llm.agents.evaluations.evaluation_agent import evaluate_answer
from app.llm.agents.evaluations.followup_agent import generate_followup_question

logger = logging.getLogger(__name__)

__all__ = [
    "EvaluationFlowResult",
    "EvaluationFlowState",
    "MAX_FOLLOWUPS",
    "evaluation_flow_graph",
    "run_evaluation_flow",
]

MAX_FOLLOWUPS = 2


class EvaluationFlowState(TypedDict, total=False):
    question: str
    user_answer: str
    model_answer: str | None
    category: str
    difficulty: str
    followup_count: int
    followup_allowed: bool
    evaluation: dict
    followup_question: str | None
    should_followup: bool


@dataclass
class EvaluationFlowResult:
    evaluation: dict
    followup_question: str | None
    should_followup: bool


async def evaluate_node(state: EvaluationFlowState) -> dict:
    evaluation = await evaluate_answer(
        question=state.get("question", ""),
        user_answer=state.get("user_answer", ""),
        model_answer=state.get("model_answer"),
        category=state.get("category", ""),
        difficulty=state.get("difficulty", ""),
    )
    return {"evaluation": dict(evaluation)}


def _route_after_evaluation(state: EvaluationFlowState) -> str:
    evaluation = state.get("evaluation") or {}
    score = int(evaluation.get("score", 0))
    followup_count = int(state.get("followup_count", 0))
    followup_allowed = bool(state.get("followup_allowed", True))

    # A candidate who explicitly says they don't know is acknowledged by the
    # evaluation agent; do not press them with a follow-up.
    if evaluation.get("admits_no_knowledge"):
        logger.info("Candidate admitted not knowing; moving on without a follow-up.")
        return "next"

    if score < 6 and followup_allowed and followup_count < MAX_FOLLOWUPS:
        logger.info(
            f"Score {score}/10 at depth {followup_count}; asking a follow-up."
        )
        return "followup"

    logger.info(
        f"Score {score}/10 at depth {followup_count}; moving to the next question."
    )
    return "next"


async def followup_node(state: EvaluationFlowState) -> dict:
    evaluation = state.get("evaluation") or {}
    feedback = str(evaluation.get("feedback") or "").strip()
    improvements = [
        str(item).strip()
        for item in (evaluation.get("improvements") or [])
        if str(item).strip()
    ]

    weak_points = feedback
    if improvements:
        weak_points = (
            weak_points + " Specific weak points: " + "; ".join(improvements)
        ).strip()

    result = await generate_followup_question(
        question=state.get("question", ""),
        answer=state.get("user_answer", ""),
        feedback=weak_points,
    )
    text = result.get("followup_question")
    return {
        "followup_question": text,
        "should_followup": bool(text),
    }


def _build_graph():
    graph = StateGraph(EvaluationFlowState)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("followup", followup_node)
    graph.add_edge(START, "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        _route_after_evaluation,
        {"followup": "followup", "next": END},
    )
    graph.add_edge("followup", END)
    return graph.compile()


evaluation_flow_graph = _build_graph()


async def run_evaluation_flow(
    *,
    question: str,
    user_answer: str,
    model_answer: str | None = None,
    category: str = "",
    difficulty: str = "",
    followup_count: int = 0,
    followup_allowed: bool = True,
) -> EvaluationFlowResult:
    """Evaluate an answer and, if eligible, generate one follow-up question."""
    final = await evaluation_flow_graph.ainvoke({
        "question": question,
        "user_answer": user_answer,
        "model_answer": model_answer,
        "category": category,
        "difficulty": difficulty,
        "followup_count": followup_count,
        "followup_allowed": followup_allowed,
    })
    return EvaluationFlowResult(
        evaluation=final["evaluation"],
        followup_question=final.get("followup_question"),
        should_followup=bool(final.get("should_followup")),
    )

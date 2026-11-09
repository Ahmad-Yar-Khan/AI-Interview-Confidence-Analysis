"""
evaluations package
-------------------
Answer evaluation agents built with LangGraph.

Public API:
    from app.llm.agents.evaluations import evaluate_answer, EvaluationResult
"""

from app.llm.agents.evaluations.evaluation_agent import (
    EVALUATION_SYSTEM_PROMPT,
    EvaluationResult,
    EvaluationState,
    evaluate_answer,
    evaluation_graph,
)
from app.llm.agents.evaluations.evaluation_flow_agent import (
    EvaluationFlowResult,
    EvaluationFlowState,
    MAX_FOLLOWUPS,
    evaluation_flow_graph,
    run_evaluation_flow,
)
from app.llm.agents.evaluations.followup_agent import (
    FOLLOWUP_SYSTEM_PROMPT,
    FollowupResult,
    FollowupState,
    followup_graph,
    generate_followup_question,
)
from app.llm.agents.evaluations.rubric import CRITERIA, RUBRIC

__all__ = [
    "CRITERIA",
    "RUBRIC",
    "EVALUATION_SYSTEM_PROMPT",
    "EvaluationFlowResult",
    "EvaluationFlowState",
    "EvaluationResult",
    "EvaluationState",
    "FOLLOWUP_SYSTEM_PROMPT",
    "FollowupResult",
    "FollowupState",
    "MAX_FOLLOWUPS",
    "evaluate_answer",
    "evaluation_flow_graph",
    "evaluation_graph",
    "followup_graph",
    "generate_followup_question",
    "run_evaluation_flow",
]

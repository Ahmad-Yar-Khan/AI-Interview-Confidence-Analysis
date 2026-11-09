"""
agents package
--------------
Multi-agent workflows built with LangGraph.

Public API:
    from app.llm.agents import run_question_agent, QuestionAgentResult
    from app.llm.agents import evaluate_answer, EvaluationResult
    from app.llm.agents import run_evaluation_flow, EvaluationFlowResult
"""

from app.llm.agents.evaluations import (
    EvaluationFlowResult,
    EvaluationResult,
    evaluate_answer,
    evaluation_flow_graph,
    evaluation_graph,
    followup_graph,
    generate_followup_question,
    run_evaluation_flow,
)
from app.llm.agents.question_agent import (
    QuestionAgentResult,
    question_agent_graph,
    run_question_agent,
)
from app.llm.agents.question_bank import get_question_bank, load_question_bank

__all__ = [
    "EvaluationFlowResult",
    "EvaluationResult",
    "evaluate_answer",
    "evaluation_flow_graph",
    "evaluation_graph",
    "followup_graph",
    "generate_followup_question",
    "run_evaluation_flow",
    "QuestionAgentResult",
    "question_agent_graph",
    "run_question_agent",
    "get_question_bank",
    "load_question_bank",
]

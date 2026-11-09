"""
llm package
-----------
Re-exports the public API so existing call sites can do:
    from app.llm import generate_questions, score_answer, ...
without needing to know the internal module split (groq_client / prompts /
question_generation / answer_scoring).
"""

from app.llm.question_generation import (
    infer_categories,
    generate_questions,
    personalize_dataset_questions,
    generate_interview_questions,
    generate_project_questions,
)
from app.llm.answer_scoring import score_answer
from app.llm.agents.evaluations import (
    EvaluationFlowResult,
    EvaluationResult,
    evaluate_answer,
    generate_followup_question,
    run_evaluation_flow,
)

__all__ = [
    "infer_categories",
    "generate_questions",
    "personalize_dataset_questions",
    "generate_interview_questions",
    "generate_project_questions",
    "score_answer",
    "EvaluationFlowResult",
    "EvaluationResult",
    "evaluate_answer",
    "generate_followup_question",
    "run_evaluation_flow",
]

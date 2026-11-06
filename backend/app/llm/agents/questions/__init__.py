"""
Question-asking agents.

Each agent lives in its own module so prompts and behavior can evolve
independently:

    relevance_agent  -> assess_relevance
    selection_agent  -> select_questions
    tailoring_agent  -> tailor_questions
    reflection_agent -> reflect_on_questions
"""

from app.llm.agents.questions.reflection_agent import (
    REFLECTION_SYSTEM_PROMPT,
    reflect_on_questions,
)
from app.llm.agents.questions.relevance_agent import (
    RELEVANCE_SYSTEM_PROMPT,
    assess_relevance,
)
from app.llm.agents.questions.selection_agent import (
    SELECTION_SYSTEM_PROMPT,
    select_questions,
)
from app.llm.agents.questions.state import QuestionAgentState
from app.llm.agents.questions.tailoring_agent import (
    TAILORING_SYSTEM_PROMPT,
    tailor_questions,
)

__all__ = [
    "QuestionAgentState",
    "RELEVANCE_SYSTEM_PROMPT",
    "SELECTION_SYSTEM_PROMPT",
    "TAILORING_SYSTEM_PROMPT",
    "REFLECTION_SYSTEM_PROMPT",
    "assess_relevance",
    "select_questions",
    "tailor_questions",
    "reflect_on_questions",
]

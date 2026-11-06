"""
Shared LangGraph state for the question-asking pipeline.
"""

from typing import TypedDict


class QuestionAgentState(TypedDict, total=False):
    # Inputs
    skills: str
    projects: str
    resume_text: str
    role: str
    years: int | None
    count: int
    bank: list[dict]
    max_revisions: int

    # Relevance agent
    relevance: int

    # Selection agent
    selected: list[dict]
    base_questions: list[dict]

    # Tailoring / reflection loop
    tailored_questions: list[dict]
    questions: list[dict]
    reflection_approved: bool
    reflection_feedback: str
    reflection_score: int
    revisions: int

    # Output
    output: str

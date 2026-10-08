"""
answer.py (schemas)
--------------------
Pydantic request/response models for the answer-scoring route.
Pulled out of main.py so route files don't need to redefine or import schemas
from the app factory module.
"""

from pydantic import BaseModel


class AnswerPayload(BaseModel):
    session_id: str
    question_id: str
    question_text: str
    model_answer: str | None = None
    user_answer: str
    category: str
    difficulty: str
    has_answer: bool = True


class ScoreResponse(BaseModel):
    question_id: str
    overall: int
    is_behavioral: bool
    angles: dict
    model_answer: str | None
    feedback: str = ""

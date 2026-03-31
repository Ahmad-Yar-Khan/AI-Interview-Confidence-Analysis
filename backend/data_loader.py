"""
data_loader.py
--------------
Loads the unified master_questions.csv (output of preprocess_datasets.py).
Builds TF-IDF embeddings and a FAISS index for all questions.

Handles NULL answers (HR & Behavioral category) gracefully —
these questions are included in selection but scored differently.
"""

import os
import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from embedding_engine import EmbeddingEngine

logger = logging.getLogger(__name__)

DATA_PATH = os.getenv("DATA_PATH", "data/master_questions.csv")

# ════════════════════════════════════════
# ALL CANONICAL CATEGORIES
# ════════════════════════════════════════
CATEGORIES = [
    "AI & Data Science",
    "Software Engineering",
    "SQL & Databases",
    "Cloud & Containers",
    "DevOps",
    "DSA & Algorithms",
    "Operating Systems",
    "Computer Networks",
    "Distributed Systems",
    "Concurrency",
    "HR & Behavioral",
]

NULL_ANSWER_CATEGORIES = {"HR & Behavioral"}


@dataclass
class Question:
    id: str
    category: str
    question: str
    answer: str | None
    difficulty: str
    source: str
    has_answer: bool
    combined_text: str
    vector: np.ndarray = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "answer": self.answer,
            "difficulty": self.difficulty,
            "source": self.source,
            "has_answer": self.has_answer,
        }


class QuestionBank:
    def __init__(self):
        self.questions: list[Question] = []
        self.engine: EmbeddingEngine | None = None
        self._by_category: dict[str, list[Question]] = {c: [] for c in CATEGORIES}

    def load(self, csv_path: str = DATA_PATH) -> None:
        logger.info(f"Loading master dataset from: {csv_path}")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"Master dataset not found at '{csv_path}'.\n"
                "Run: python preprocess_datasets.py"
            )

        df = pd.read_csv(csv_path)
        required = {"id", "category", "question", "answer", "difficulty"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"master_questions.csv missing columns: {missing}")

        self.questions = []
        for _, row in df.iterrows():
            raw_answer = row.get("answer")
            if pd.isna(raw_answer) or str(raw_answer).strip().upper() in ("", "NAN", "NULL", "NONE"):
                answer = None
                has_answer = False
            else:
                answer = str(raw_answer).strip()
                has_answer = True

            combined = str(row["question"]).strip()
            if has_answer:
                combined += " " + answer

            q = Question(
                id=str(row["id"]),
                category=str(row["category"]).strip(),
                question=str(row["question"]).strip(),
                answer=answer,
                difficulty=str(row.get("difficulty", "Medium")).strip(),
                source=str(row.get("source", "unknown")).strip(),
                has_answer=has_answer,
                combined_text=combined,
            )
            self.questions.append(q)

        logger.info(f"Loaded {len(self.questions)} questions")
        self._index_by_category()
        self._log_summary()

    def _index_by_category(self) -> None:
        self._by_category = {c: [] for c in CATEGORIES}
        for q in self.questions:
            if q.category not in self._by_category:
                self._by_category[q.category] = []
            self._by_category[q.category].append(q)

    def _log_summary(self) -> None:
        logger.info("── Question Bank Summary ──")
        for cat in CATEGORIES:
            qs = self._by_category.get(cat, [])
            null_count = sum(1 for q in qs if not q.has_answer)
            logger.info(f"  {cat:<35} {len(qs):>4} qs  ({null_count} without answers)")

    def build_embeddings(self, engine: EmbeddingEngine) -> None:
        self.engine = engine
        corpus = [q.combined_text for q in self.questions]
        engine.fit(corpus)
        vectors = engine.embed_batch(corpus)
        for i, q in enumerate(self.questions):
            q.vector = vectors[i]
        engine.build_index(vectors)
        logger.info(f"FAISS index ready: {len(self.questions)} vectors, dim={vectors.shape[1]}")

    def get_by_category(self, category: str) -> list[Question]:
        return self._by_category.get(category, [])

    def get_all(self) -> list[Question]:
        return self.questions

    def get_answerable(self) -> list[Question]:
        return [q for q in self.questions if q.has_answer]

    def get_categories(self) -> list[str]:
        return [c for c, qs in self._by_category.items() if qs]


_question_bank: QuestionBank | None = None


def get_question_bank() -> QuestionBank:
    global _question_bank
    if _question_bank is None:
        raise RuntimeError("Question bank not initialized. Call init_question_bank() at startup.")
    return _question_bank


def init_question_bank(engine: EmbeddingEngine, csv_path: str = DATA_PATH) -> QuestionBank:
    global _question_bank
    bank = QuestionBank()
    bank.load(csv_path)
    bank.build_embeddings(engine)
    _question_bank = bank
    return bank

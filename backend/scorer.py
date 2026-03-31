"""
scorer.py
---------
Scores a user's answer against the model answer across 3 semantic angles.

Handles two question types:
  1. Technical questions (has_answer=True):
       - Conceptual  : TF-IDF cosine similarity vs model answer
       - Technical   : Domain keyword overlap per category
       - Completeness: Key-term coverage from model answer
       - Overall     : Weighted composite of all three

  2. HR & Behavioral questions (has_answer=False / NULL):
       - No model answer exists — cannot do cosine comparison
       - Instead, scores on: length/effort, keyword richness, structure signals
       - Presented as "Effort Score" in the UI
       - Overall score reflects answer quality signals, not correctness
"""

import re
import logging
import numpy as np
from dataclasses import dataclass

from embedding_engine import EmbeddingEngine

logger = logging.getLogger(__name__)


# ════════════════════════════════════════
# DOMAIN KEYWORD LISTS PER CATEGORY
# ════════════════════════════════════════
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "AI & Data Science": [
        "model", "training", "data", "feature", "neural", "loss", "gradient",
        "layer", "learning", "classification", "regression", "cluster", "vector",
        "embedding", "overfitting", "accuracy", "prediction", "algorithm",
        "supervised", "unsupervised", "backpropagation", "epoch", "batch",
        "hyperparameter", "validation", "precision", "recall", "f1",
    ],
    "Software Engineering": [
        "function", "class", "object", "interface", "design", "pattern",
        "complexity", "algorithm", "stack", "queue", "tree", "graph",
        "recursion", "loop", "memory", "concurrency", "thread",
        "async", "api", "endpoint", "request", "response", "cache",
        "module", "library", "framework", "testing", "debugging",
    ],
    "SQL & Databases": [
        "table", "query", "join", "index", "key", "constraint", "transaction",
        "acid", "normalization", "schema", "row", "column", "aggregate",
        "group", "having", "where", "select", "insert", "update", "delete",
        "stored procedure", "view", "trigger", "primary", "foreign",
    ],
    "Cloud & Containers": [
        "container", "image", "pod", "node", "cluster", "service", "deployment",
        "scaling", "orchestration", "namespace", "volume", "network", "ingress",
        "replica", "stateful", "stateless", "cloud", "instance", "serverless",
    ],
    "DevOps": [
        "pipeline", "build", "deploy", "test", "integration", "delivery",
        "monitoring", "alert", "log", "metric", "rollback", "release",
        "infrastructure", "automation", "configuration", "environment",
        "artifact", "repository", "version", "branch",
    ],
    "DSA & Algorithms": [
        "complexity", "time", "space", "big o", "sort", "search",
        "tree", "graph", "node", "edge", "recursion", "stack", "queue",
        "dynamic programming", "memoization", "greedy", "divide", "conquer",
        "hash", "pointer", "array", "linked", "heap",
    ],
    "Operating Systems": [
        "process", "thread", "kernel", "memory", "virtual", "paging",
        "scheduling", "deadlock", "semaphore", "mutex", "file", "system",
        "interrupt", "cache", "buffer", "ipc", "socket",
    ],
    "Computer Networks": [
        "protocol", "tcp", "udp", "ip", "packet", "header", "layer",
        "routing", "switch", "dns", "http", "bandwidth", "latency",
        "firewall", "subnet", "address", "port", "socket",
    ],
    "Distributed Systems": [
        "consistency", "availability", "partition", "replication", "shard",
        "node", "consensus", "fault", "tolerance", "latency", "throughput",
        "leader", "follower", "election", "quorum",
    ],
    "Concurrency": [
        "thread", "lock", "mutex", "semaphore", "race", "condition",
        "deadlock", "synchronization", "atomic", "concurrent", "parallel",
        "async", "blocking", "non-blocking", "critical", "section",
    ],
}

# Behavioral signals used to score HR answers (no model answer)
BEHAVIORAL_SIGNALS = [
    "situation", "task", "action", "result",   # STAR method
    "challenge", "problem", "solution", "outcome",
    "team", "collaboration", "communication", "conflict",
    "leadership", "decision", "priority", "deadline",
    "learned", "improved", "achieved", "managed",
]

GENERIC_TECH = [
    "system", "process", "performance", "security", "scalability",
    "reliability", "availability", "latency", "throughput", "efficiency",
]

STOPWORDS = {
    "the", "and", "for", "are", "was", "that", "this", "with", "from",
    "they", "have", "will", "been", "when", "also", "can", "not", "but",
    "its", "all", "one", "has", "more", "into", "than", "such", "each",
    "which", "how", "what", "does", "some", "use", "used", "using",
    "well", "both", "very", "being", "about", "would", "could", "should",
}


# ════════════════════════════════════════
# RESULT MODEL
# ════════════════════════════════════════

@dataclass
class ScoreResult:
    overall: int                    # 0–100 composite
    conceptual: int                 # 0–100 (or effort proxy for HR)
    technical: int                  # 0–100 (or richness proxy for HR)
    completeness: int               # 0–100 (or structure proxy for HR)
    is_behavioral: bool = False     # True for HR & Behavioral questions

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "is_behavioral": self.is_behavioral,
            "angles": {
                "conceptual":   self.conceptual,
                "technical":    self.technical,
                "completeness": self.completeness,
            },
        }


# ════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════

def _tokenize(text: str) -> set[str]:
    tokens = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {t for t in tokens if len(t) > 2}


def _meaningful_tokens(text: str) -> set[str]:
    return _tokenize(text) - STOPWORDS


# ════════════════════════════════════════
# TECHNICAL SCORING ANGLES
# ════════════════════════════════════════

def _score_conceptual(
    user_vec: np.ndarray,
    model_vec: np.ndarray,
    engine: EmbeddingEngine,
) -> int:
    return int(engine.cosine(user_vec, model_vec) * 100)


def _score_technical(user_text: str, model_text: str, category: str) -> int:
    keywords = DOMAIN_KEYWORDS.get(category, GENERIC_TECH)
    model_lower = model_text.lower()
    user_lower  = user_text.lower()

    relevant = [kw for kw in keywords if kw in model_lower]
    if not relevant:
        relevant = [kw for kw in GENERIC_TECH if kw in model_lower]
    if not relevant:
        return 50   # neutral when no keywords apply

    matched = sum(1 for kw in relevant if kw in user_lower)
    return int((matched / len(relevant)) * 100)


def _score_completeness(user_text: str, model_text: str) -> int:
    model_tokens = _meaningful_tokens(model_text)
    user_tokens  = _meaningful_tokens(user_text)
    if not model_tokens:
        return 50
    overlap = model_tokens & user_tokens
    raw = len(overlap) / len(model_tokens)
    scaled = min(1.0, raw * 1.6)   # 60% coverage → 100%
    return int(scaled * 100)


# ════════════════════════════════════════
# BEHAVIORAL SCORING (no model answer)
# Scored on effort/quality signals, not correctness.
# ════════════════════════════════════════

def _score_behavioral(user_text: str) -> ScoreResult:
    """
    Score a behavioral/HR answer when no model answer exists.
    Three proxy angles:
      - Effort      (conceptual slot): answer length relative to ideal
      - Richness    (technical slot) : behavioral keyword density
      - Structure   (completeness)   : STAR method signal coverage
    """
    words = user_text.lower().split()
    word_count = len(words)

    # 1. Effort: ideal is 80–200 words → full marks
    if word_count >= 200:
        effort = 100
    elif word_count >= 80:
        effort = 75 + int(((word_count - 80) / 120) * 25)
    elif word_count >= 30:
        effort = 40 + int(((word_count - 30) / 50) * 35)
    else:
        effort = max(0, int(word_count / 30 * 40))

    # 2. Richness: behavioral signal keywords
    user_lower = user_text.lower()
    matched_signals = sum(1 for s in BEHAVIORAL_SIGNALS if s in user_lower)
    richness = min(100, int((matched_signals / max(len(BEHAVIORAL_SIGNALS) * 0.4, 1)) * 100))

    # 3. Structure: STAR method signals specifically
    star = {
        "situation": any(w in user_lower for w in ["situation", "context", "when", "during", "while"]),
        "task":      any(w in user_lower for w in ["task", "goal", "objective", "needed", "had to"]),
        "action":    any(w in user_lower for w in ["action", "did", "decided", "chose", "implemented", "approached"]),
        "result":    any(w in user_lower for w in ["result", "outcome", "achieved", "improved", "learned", "success"]),
    }
    star_score = int(sum(star.values()) / 4 * 100)

    overall = int(effort * 0.40 + richness * 0.30 + star_score * 0.30)

    return ScoreResult(
        overall=min(100, overall),
        conceptual=min(100, effort),
        technical=min(100, richness),
        completeness=min(100, star_score),
        is_behavioral=True,
    )


# ════════════════════════════════════════
# MAIN SCORING ENTRY POINT
# ════════════════════════════════════════

def score_answer(
    user_text: str,
    model_text: str | None,
    category: str,
    engine: EmbeddingEngine,
) -> ScoreResult:
    """
    Score one answer. Routes to behavioral or technical scoring.

    Args:
        user_text  : The candidate's answer
        model_text : The correct answer from dataset, or None for HR questions
        category   : Question category (drives keyword selection)
        engine     : Fitted EmbeddingEngine

    Returns:
        ScoreResult with overall + 3 angle scores (0–100 each)
    """
    if not user_text or not user_text.strip():
        return ScoreResult(
            overall=0, conceptual=0, technical=0, completeness=0,
            is_behavioral=(model_text is None),
        )

    # Route: NULL answer → behavioral scoring
    if model_text is None or str(model_text).strip().upper() in ("", "NULL", "NONE", "NAN"):
        result = _score_behavioral(user_text)
        logger.debug(
            f"[Behavioral] overall={result.overall} | "
            f"effort={result.conceptual} | richness={result.technical} | "
            f"structure={result.completeness}"
        )
        return result

    # Route: technical scoring
    user_vec  = engine.embed(user_text)
    model_vec = engine.embed(model_text)

    conceptual   = _score_conceptual(user_vec, model_vec, engine)
    technical    = _score_technical(user_text, model_text, category)
    completeness = _score_completeness(user_text, model_text)

    # Weighted composite: 50% conceptual, 30% technical, 20% completeness
    overall = int(conceptual * 0.50 + technical * 0.30 + completeness * 0.20)

    result = ScoreResult(
        overall=min(100, overall),
        conceptual=min(100, conceptual),
        technical=min(100, technical),
        completeness=min(100, completeness),
        is_behavioral=False,
    )
    logger.debug(
        f"[Technical] overall={result.overall} | conceptual={result.conceptual} "
        f"| technical={result.technical} | completeness={result.completeness}"
    )
    return result

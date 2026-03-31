"""
question_selector.py
--------------------
Selects tailored interview questions for any parsed resume.

Supports all 11 canonical categories including HR & Behavioral (NULL answers).
HR questions are always included (2) regardless of resume content,
since behavioral questions are universal to all interviews.
"""

import re
import random
import logging
import numpy as np

from resume_parser import ResumeProfile
from embedding_engine import EmbeddingEngine
from data_loader import QuestionBank, Question, NULL_ANSWER_CATEGORIES, CATEGORIES

logger = logging.getLogger(__name__)

DEFAULT_TOTAL_QUESTIONS = int(__import__("os").getenv("MAX_QUESTIONS", 12))

DIFFICULTY_ORDER = {"Easy": 0, "Medium": 1, "Hard": 2}
DIFFICULTY_BOOST = {"Easy": 1.0, "Medium": 1.08, "Hard": 1.15}

# ════════════════════════════════════════
# CATEGORY KEYWORD MAP
# Keep canonical names in sync with preprocess_datasets.py CATEGORY_MAP values.
# ════════════════════════════════════════
CATEGORY_KEYWORDS = {
    "AI & Data Science": [
        "machine learning", "ml", "deep learning", "neural network", "tensorflow",
        "pytorch", "keras", "scikit-learn", "sklearn", "pandas", "numpy",
        "nlp", "natural language processing", "nltk", "spacy", "bert", "gpt",
        "transformer", "computer vision", "opencv", "cnn", "rnn", "lstm",
        "llm", "generative ai", "gan", "random forest", "xgboost",
        "gradient boosting", "k-means", "clustering", "regression",
        "classification", "feature engineering", "data science", "data analysis",
        "statistics", "featuretools", "gridsearchcv", "fairml",
        "anomaly detection", "time series", "recommender", "embedding",
        "hugging face", "langchain", "rag", "vector database", "faiss",
    ],
    "Software Engineering": [
        "python", "java", "javascript", "typescript", "c++", "c#", "go",
        "rust", "react", "angular", "vue", "node", "express", "django",
        "flask", "fastapi", "spring", "rest api", "graphql", "microservices",
        "oop", "design patterns", "solid", "git", "github", "agile", "scrum",
        "data structures", "algorithms", "system design", "object oriented",
        "software development", "programming", "coding", "backend", "frontend",
    ],
    "SQL & Databases": [
        "sql", "postgresql", "mysql", "sqlite", "oracle", "mssql",
        "database", "relational database", "query", "joins", "stored procedure",
        "index", "normalization", "nosql", "mongodb", "cassandra", "redis",
        "dynamodb", "data warehouse", "etl", "bigquery", "snowflake", "dbt",
    ],
    "Cloud & Containers": [
        "docker", "kubernetes", "k8s", "container", "aws", "azure", "gcp",
        "google cloud", "amazon web services", "ec2", "s3", "lambda",
        "serverless", "cloud", "terraform", "helm", "service mesh",
        "load balancer", "auto scaling", "cdn",
    ],
    "DevOps": [
        "ci/cd", "jenkins", "github actions", "gitlab ci", "circleci",
        "devops", "infrastructure as code", "iac", "ansible", "monitoring",
        "prometheus", "grafana", "elk", "splunk", "datadog", "sre",
        "site reliability", "pipeline", "deployment", "gitops",
    ],
    "DSA & Algorithms": [
        "data structures", "algorithms", "dsa", "sorting", "searching",
        "binary tree", "graph", "dynamic programming", "recursion",
        "hash map", "hash table", "linked list", "stack", "queue",
        "heap", "trie", "big o", "complexity", "leetcode",
    ],
    "Operating Systems": [
        "operating system", "os", "kernel", "process", "thread",
        "memory management", "virtual memory", "paging", "scheduling",
        "deadlock", "semaphore", "mutex", "file system", "linux",
        "unix", "shell", "system call",
    ],
    "Computer Networks": [
        "networking", "tcp", "udp", "ip", "http", "https", "dns",
        "osi model", "network protocol", "socket", "bandwidth",
        "routing", "firewall", "vpn", "load balancing",
    ],
    "Distributed Systems": [
        "distributed system", "distributed computing", "cap theorem",
        "consensus", "replication", "sharding", "partition",
        "eventual consistency", "raft", "paxos", "zookeeper",
        "kafka", "message queue", "microservice",
    ],
    "Concurrency": [
        "concurrency", "parallel", "parallelism", "thread", "mutex",
        "semaphore", "race condition", "deadlock", "async", "await",
        "coroutine", "lock", "synchronization", "multithreading",
    ],
    # HR is universal — always included, no resume keywords needed
    "HR & Behavioral": [],
}


# ════════════════════════════════════════
# RESUME TEXT BUILDER
# ════════════════════════════════════════

def build_resume_text(profile: ResumeProfile) -> str:
    """Compose a weighted text string from resume fields for embedding."""
    parts = []
    if profile.title:
        parts.extend([profile.title] * 3)
    parts.extend(profile.skills * 2)
    for exp in profile.experience:
        parts.append(exp.role)
        parts.append(exp.company)
        parts.extend(exp.highlights)
    parts.extend(profile.projects)
    parts.extend(profile.education)
    return " ".join(parts)


# ════════════════════════════════════════
# CATEGORY WEIGHT CALCULATOR
# ════════════════════════════════════════

def compute_category_weights(profile: ResumeProfile) -> dict[str, float]:
    """
    Compute relevance weight [0.1, 1.0] per category from resume content.
    HR & Behavioral always gets a fixed 0.5 — universal to all interviews.
    """
    full_text = (
        " ".join(profile.skills)
        + " " + " ".join(
            e.role + " " + e.company + " " + " ".join(e.highlights)
            for e in profile.experience
        )
        + " " + " ".join(profile.projects)
        + " " + " ".join(profile.education)
        + " " + profile.title
    ).lower()

    weights = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if cat == "HR & Behavioral":
            weights[cat] = 0.50
            continue
        if not keywords:
            weights[cat] = 0.10
            continue
        matches = sum(
            1 for kw in keywords
            if re.search(r"\b" + re.escape(kw) + r"\b", full_text)
        )
        weight = min(1.0, 0.10 + (matches / max(len(keywords) * 0.25, 1)) * 0.90)
        weights[cat] = round(weight, 3)

    return weights


# ════════════════════════════════════════
# QUOTA ALLOCATOR
# ════════════════════════════════════════

def allocate_quotas(
    category_weights: dict[str, float],
    total: int,
    bank: QuestionBank,
) -> dict[str, int]:
    """
    Distribute question slots across categories.
      - HR & Behavioral: always 2 (reserved)
      - Categories with no questions in bank: 0
      - Categories with weight < 0.15: 0 (not relevant to resume)
      - Others: proportional to weight, minimum 1
    """
    HR_RESERVED = 2
    remaining_total = total - HR_RESERVED

    # Only consider tech categories that have questions in the bank
    tech_cats = {
        cat: w
        for cat, w in category_weights.items()
        if cat != "HR & Behavioral"
        and bank.get_by_category(cat)
        and w >= 0.15
    }

    if not tech_cats:
        # Fallback: give everything to top available categories
        all_tech = {
            cat: category_weights.get(cat, 0.10)
            for cat in CATEGORIES
            if cat != "HR & Behavioral" and bank.get_by_category(cat)
        }
        tech_cats = dict(sorted(all_tech.items(), key=lambda x: x[1], reverse=True)[:5])

    total_weight = sum(tech_cats.values()) or 1.0
    normalized = {cat: w / total_weight for cat, w in tech_cats.items()}
    raw = {cat: w * remaining_total for cat, w in normalized.items()}

    floored = {cat: max(1, int(v)) for cat, v in raw.items()}

    # Adjust to hit remaining_total exactly
    allocated = sum(floored.values())
    diff = remaining_total - allocated

    if diff > 0:
        by_frac = sorted(
            raw.items(), key=lambda x: x[1] - int(x[1]), reverse=True
        )
        for cat, _ in by_frac:
            if diff == 0:
                break
            floored[cat] = floored.get(cat, 0) + 1
            diff -= 1
    elif diff < 0:
        by_weight = sorted(floored.items(), key=lambda x: category_weights.get(x[0], 0))
        for cat, _ in by_weight:
            if diff == 0:
                break
            if floored.get(cat, 0) > 1:
                floored[cat] -= 1
                diff += 1

    floored["HR & Behavioral"] = HR_RESERVED

    # Zero out categories not in tech_cats
    for cat in list(floored.keys()):
        if cat not in tech_cats and cat != "HR & Behavioral":
            floored[cat] = 0

    logger.info(f"Question quotas: { {k:v for k,v in floored.items() if v > 0} }")
    return floored


# ════════════════════════════════════════
# PER-CATEGORY SELECTOR
# ════════════════════════════════════════

def select_questions_for_category(
    category: str,
    quota: int,
    bank: QuestionBank,
    resume_vec: np.ndarray,
    engine: EmbeddingEngine,
) -> list[Question]:
    """
    Pick `quota` questions from `category`, ranked by resume relevance.
    For HR & Behavioral (NULL answers): difficulty-balanced random selection.
    For technical categories: cosine-similarity ranking + difficulty spread.
    """
    candidates = bank.get_by_category(category)
    if not candidates or quota == 0:
        return []

    is_hr = category in NULL_ANSWER_CATEGORIES

    if is_hr:
        # HR: balanced difficulty sampling, no embedding needed
        easy   = [q for q in candidates if q.difficulty == "Easy"]
        medium = [q for q in candidates if q.difficulty == "Medium"]
        hard   = [q for q in candidates if q.difficulty == "Hard"]
        random.seed(42)
        for pool in (easy, medium, hard):
            random.shuffle(pool)
        selected, seen = [], set()
        for pool in (medium, easy, hard):   # prefer medium first
            for q in pool:
                if len(selected) >= quota:
                    break
                if q.question not in seen:
                    selected.append(q)
                    seen.add(q.question)
        return selected[:quota]

    # Technical: cosine-similarity scoring
    scored = []
    for q in candidates:
        if q.vector is None:
            continue
        sim = engine.cosine(resume_vec, q.vector)
        boost = DIFFICULTY_BOOST.get(q.difficulty, 1.0)
        scored.append((q, sim * boost))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Difficulty-balanced picks
    easy   = [(q, s) for q, s in scored if q.difficulty == "Easy"]
    medium = [(q, s) for q, s in scored if q.difficulty == "Medium"]
    hard   = [(q, s) for q, s in scored if q.difficulty == "Hard"]

    n_easy   = max(1, round(quota * 0.25))
    n_hard   = max(1, round(quota * 0.30))
    n_medium = max(1, quota - n_easy - n_hard)

    selected, seen = [], set()
    for pool, n in [(easy, n_easy), (medium, n_medium), (hard, n_hard)]:
        count = 0
        for q, _ in pool:
            if count >= n:
                break
            if q.question not in seen:
                selected.append(q)
                seen.add(q.question)
                count += 1

    # Backfill if short
    for q, _ in scored:
        if len(selected) >= quota:
            break
        if q.question not in seen:
            selected.append(q)
            seen.add(q.question)

    return selected[:quota]


# ════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════

def select_questions(
    profile: ResumeProfile,
    bank: QuestionBank,
    engine: EmbeddingEngine,
    total: int = DEFAULT_TOTAL_QUESTIONS,
) -> list[dict]:
    """
    Full pipeline: resume profile → ranked, tailored question list.
    Returns list of question dicts with 'why' explanation field added.
    Technical questions ordered by category weight desc, HR appended last.
    """
    resume_text = build_resume_text(profile)
    resume_vec  = engine.embed(resume_text)

    # Use profile weights if already computed, else compute fresh
    weights = profile.category_weights if profile.category_weights else compute_category_weights(profile)

    quotas = allocate_quotas(weights, total, bank)

    all_selected = []

    # Technical categories: highest weight first
    tech_order = sorted(
        [c for c in CATEGORIES if c != "HR & Behavioral"],
        key=lambda c: weights.get(c, 0),
        reverse=True,
    )
    for cat in tech_order:
        quota = quotas.get(cat, 0)
        if quota > 0:
            qs = select_questions_for_category(cat, quota, bank, resume_vec, engine)
            all_selected.extend(qs)

    # HR & Behavioral last
    hr_qs = select_questions_for_category(
        "HR & Behavioral", quotas.get("HR & Behavioral", 2), bank, resume_vec, engine
    )
    all_selected.extend(hr_qs)

    logger.info(
        f"Selected {len(all_selected)} questions for '{profile.name}': "
        + ", ".join(
            f"{cat}={sum(1 for q in all_selected if q.category == cat)}"
            for cat in CATEGORIES
            if any(q.category == cat for q in all_selected)
        )
    )

    return [
        {**q.to_dict(), "why": _explain_why(q, profile)}
        for q in all_selected
    ]


def _explain_why(q: Question, profile: ResumeProfile) -> str:
    """Short human-readable reason why this question was selected."""
    if q.category in NULL_ANSWER_CATEGORIES:
        return "Universal behavioral question — asked in every interview"

    # Check skill match
    for skill in profile.skills:
        if skill.lower() in q.combined_text.lower():
            return f"Matched your skill: {skill}"

    # Check experience highlights
    for exp in profile.experience:
        for h in exp.highlights:
            words = [w.lower() for w in h.split() if len(w) > 4]
            if any(w in q.combined_text.lower() for w in words):
                return f"Relevant to your role: {exp.role} at {exp.company}"

    return f"Relevant to {q.category}"

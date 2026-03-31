"""
preprocess_datasets.py
----------------------
Preprocessing pipeline for all interview question datasets.
Run to regenerate master_questions.csv after adding new datasets.

Datasets:
  1. new_interview_questions.csv   — Kaggle (clean, rename categories)
  2. deepseek_questions.json       — DeepSeek generated (map categories)
  3. full_interview_questions_dataset.csv — HR only, drop SE, NULL answers

Deduplication (TWO-PASS):
  Pass 1 — Normalization : strip question prefixes/punctuation → exact match collapse
  Pass 2 — Semantic      : TF-IDF cosine similarity per category, union-find clustering,
                           keep the most informative representative per cluster

Output: data/master_questions.csv
"""

import os
import re
import json
import uuid
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_PATH = os.path.join(DATA_DIR, "master_questions.csv")

CANONICAL_COLS = ["id", "category", "question", "answer", "difficulty", "source"]

# ════════════════════════════════════════════════════════════
# CATEGORY & DIFFICULTY MAPS
# ════════════════════════════════════════════════════════════

CATEGORY_MAP = {
    # Kaggle
    "AI (Data Science)":             "AI & Data Science",
    "General Software Engineering":  "Software Engineering",
    "SQL":                           "SQL & Databases",
    "Containers and Cloud":          "Cloud & Containers",
    "DevOps":                        "DevOps",
    # DeepSeek
    "DSA":                           "DSA & Algorithms",
    "Operating Systems":             "Operating Systems",
    "Computer Networks":             "Computer Networks",
    "Distributed Systems":           "Distributed Systems",
    "Concurrency":                   "Concurrency",
    "Databases":                     "SQL & Databases",
    "Programming Paradigms":         "Software Engineering",
    "Software Design":               "Software Engineering",
    "Web Development":               "Software Engineering",
    # Full interview (HR)
    "Behavioral":                    "HR & Behavioral",
}

DIFFICULTY_MAP = {
    "easy": "Easy", "medium": "Medium", "hard": "Hard",
    "Easy": "Easy", "Medium": "Medium", "Hard": "Hard",
}


# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════

def make_id() -> str:
    return str(uuid.uuid4())[:8]

def normalize_category(raw: str) -> str:
    return CATEGORY_MAP.get(str(raw).strip(), str(raw).strip())

def normalize_difficulty(raw: str) -> str:
    return DIFFICULTY_MAP.get(str(raw).strip(), "Medium")

def clean_answer(text) -> str | None:
    if pd.isna(text) or str(text).strip().upper() in ("", "NAN", "NULL", "NONE"):
        return None
    cleaned = str(text).strip()
    if cleaned.lower().startswith("answer:"):
        cleaned = cleaned[7:].strip()
    return cleaned or None


# ════════════════════════════════════════════════════════════
# DATASET LOADERS
# ════════════════════════════════════════════════════════════

def preprocess_kaggle(path: str) -> pd.DataFrame:
    logger.info(f"[Kaggle] Loading: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({
        "id":         df.get("id", pd.Series(range(len(df)))).astype(str),
        "category":   df["category"].apply(normalize_category),
        "question":   df["question"].str.strip(),
        "answer":     df["answer"].apply(clean_answer),
        "difficulty": df["difficulty"].apply(normalize_difficulty),
        "source":     "kaggle",
    })
    out = out.dropna(subset=["question"])
    out = out[out["question"].str.len() > 5]
    logger.info(f"[Kaggle] {len(out)} rows | categories: {out['category'].value_counts().to_dict()}")
    return out[CANONICAL_COLS]


def preprocess_deepseek(path: str) -> pd.DataFrame:
    logger.info(f"[DeepSeek] Loading: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({
        "id":         [make_id() for _ in range(len(df))],
        "category":   df["category"].apply(normalize_category),
        "question":   df["question"].str.strip(),
        "answer":     df["answer"].apply(clean_answer),
        "difficulty": df["difficulty"].apply(normalize_difficulty),
        "source":     "deepseek",
    })
    out = out.dropna(subset=["question"])
    out = out[out["question"].str.len() > 5]
    logger.info(f"[DeepSeek] {len(out)} rows | categories: {out['category'].value_counts().to_dict()}")
    return out[CANONICAL_COLS]


def preprocess_full_interview(path: str) -> pd.DataFrame:
    logger.info(f"[FullInterview] Loading: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    logger.info(f"[FullInterview] Raw shape: {df.shape} | roles: {df['role'].value_counts().to_dict()}")

    # Keep HR only, reset index to avoid pandas index-alignment NaN bug
    df = df[df["role"].str.strip() == "HR"].copy().reset_index(drop=True)
    logger.info(f"[FullInterview] After keeping HR only: {len(df)} rows")

    out = pd.DataFrame({
        "id":         [make_id() for _ in range(len(df))],
        "category":   "HR & Behavioral",
        "question":   df["question"].str.strip(),
        "answer":     None,               # no answers for HR questions
        "difficulty": df["difficulty"].apply(normalize_difficulty),
        "source":     "full_interview",
    })
    out = out.dropna(subset=["question"])
    out = out[out["question"].str.len() > 5]
    logger.info(f"[FullInterview] {len(out)} rows (all answers NULL)")
    return out[CANONICAL_COLS]


# ════════════════════════════════════════════════════════════
# DEDUPLICATION — PASS 1: Normalization
# ════════════════════════════════════════════════════════════

def _normalize_question(text: str) -> str:
    """
    Strip question prefixes, punctuation, and filler words so that
    semantically identical questions produce the same normalized string.

    Examples:
      "What is NLP?"                         → "nlp"
      "What is natural language processing?" → "natural language processing"
      "Explain the bias-variance tradeoff."  → "bias variance tradeoff"
      "What is the bias-variance tradeoff?"  → "bias variance tradeoff"
    """
    text = text.lower().strip()
    # Remove all quotation/punctuation
    text = re.sub(r'["""\'\'`.,?!():;\-]', " ", text)
    # Remove common question-phrasing prefixes
    prefixes = (
        r"what is|what are|what does|what do you mean by|what do you understand by|"
        r"define|explain what|explain the concept of|explain the|explain|"
        r"describe|how does|how do you|how is|how are|"
        r"can you explain|could you explain|please explain|briefly explain|"
        r"tell me about|give an example of|provide an example of|"
        r"what would you|when would you|why would you|why is|why are"
    )
    text = re.sub(rf"^({prefixes})\s+", "", text).strip()
    # Remove articles, prepositions, conjunctions
    text = re.sub(r"\b(a|an|the|of|in|for|to|and|or|by|is|are|it|its|this|that)\b", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _dedup_pass1(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalization dedup: within each (category, normalized_question) group,
    keep the single best row — defined as longest non-null answer.
    """
    before = len(df)
    df = df.copy()
    df["_norm"] = df["question"].apply(_normalize_question)

    def pick_best(group):
        has_ans = group[group["answer"].notna()]
        pool = has_ans if len(has_ans) > 0 else group
        return pool.loc[pool["answer"].fillna("").str.len().idxmax()]

    df["_ans_len"] = df["answer"].fillna("").str.len()
    df = df.sort_values(["_ans_len"], ascending=False)
    df = df.drop_duplicates(subset=["category", "_norm"], keep="first")
    df = df.drop(columns=["_norm", "_ans_len"]).reset_index(drop=True)
    
    logger.info(f"[Dedup Pass 1 — Normalization]  {before:>5} → {len(df):>5}  (removed {before - len(df)})")
    return df


# ════════════════════════════════════════════════════════════
# DEDUPLICATION — PASS 2: Semantic TF-IDF + Union-Find
# ════════════════════════════════════════════════════════════

def _union_find_components(n: int, pairs: list[tuple[int, int]]) -> dict[int, list[int]]:
    """Build connected components via union-find."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i, j in pairs:
        union(i, j)

    components = defaultdict(list)
    for idx in range(n):
        components[find(idx)].append(idx)
    return components


def _dedup_pass2(df: pd.DataFrame, threshold: float = 0.82) -> pd.DataFrame:
    """
    Semantic dedup per category using TF-IDF cosine similarity.

    threshold=0.82 is calibrated to catch:
      ✅  "What is NLP?" vs "Explain natural language processing"
      ✅  "What is anomaly detection?" vs "Describe anomaly detection"
      ✅  "What is Docker?" vs "What is the purpose of Docker?"  — borderline, kept
      ❌  "What is supervised learning?" vs "What is unsupervised learning?"  (different)
      ❌  "What is overfitting?" vs "What is underfitting?"  (different)

    Within each duplicate cluster, keeps the row with the longest answer
    (most informative). For clusters with equal answer length, keeps the
    shortest, clearest question phrasing (shortest question text).
    """
    before = len(df)
    result_frames = []

    for cat in df["category"].unique():
        cat_df = df[df["category"] == cat].copy().reset_index(drop=True)

        if len(cat_df) < 2:
            result_frames.append(cat_df)
            continue

        # HR & Behavioral: skip semantic dedup (no answers, questions are intentionally similar)
        if cat == "HR & Behavioral":
            result_frames.append(cat_df)
            continue

        # Build TF-IDF matrix on question text
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1)
        mat = vec.fit_transform(cat_df["question"])
        sim = cosine_similarity(mat)
        np.fill_diagonal(sim, 0)   # ignore self-similarity

        # Find all pairs above threshold
        pairs = [(int(i), int(j)) for i, j in np.argwhere(sim > threshold) if i < j]

        # Build connected components
        components = _union_find_components(len(cat_df), pairs)

        # From each component, select the best representative
        kept_indices = []
        for root, indices in components.items():
            if len(indices) == 1:
                kept_indices.append(indices[0])
            else:
                def quality_score(idx):
                    row = cat_df.iloc[idx]
                    ans_len = len(str(row["answer"])) if pd.notna(row["answer"]) else 0
                    # Secondary: prefer shorter (cleaner) question
                    q_len_penalty = -len(str(row["question"]))
                    return (ans_len, q_len_penalty)

                best = max(indices, key=quality_score)
                kept_indices.append(best)

        kept_indices.sort()
        result_frames.append(cat_df.iloc[kept_indices])

    deduped = pd.concat(result_frames, ignore_index=True)
    logger.info(f"[Dedup Pass 2 — Semantic @{threshold}]  {before:>5} → {len(deduped):>5}  (removed {before - len(deduped)})")
    return deduped


def deduplicate(df: pd.DataFrame, similarity_threshold: float = 0.82) -> pd.DataFrame:
    """
    Full two-pass deduplication pipeline.
    Call this after merging all dataset frames.
    """
    logger.info(f"\n[Dedup] Starting with {len(df)} rows across {df['category'].nunique()} categories")
    df = _dedup_pass1(df)
    df = _dedup_pass2(df, threshold=similarity_threshold)
    logger.info(f"[Dedup] Final: {len(df)} unique questions\n")
    return df


# ════════════════════════════════════════════════════════════
# BUILD MASTER
# ════════════════════════════════════════════════════════════

def build_master(
    kaggle_path: str,
    deepseek_path: str,
    full_interview_path: str,
    output_path: str = OUTPUT_PATH,
    similarity_threshold: float = 0.82,
) -> pd.DataFrame:
    frames = []

    if os.path.exists(kaggle_path):
        frames.append(preprocess_kaggle(kaggle_path))
    else:
        logger.warning(f"Kaggle dataset not found at {kaggle_path}")

    if os.path.exists(deepseek_path):
        frames.append(preprocess_deepseek(deepseek_path))
    else:
        logger.warning(f"DeepSeek dataset not found at {deepseek_path}")

    if os.path.exists(full_interview_path):
        frames.append(preprocess_full_interview(full_interview_path))
    else:
        logger.warning(f"Full interview dataset not found at {full_interview_path}")

    if not frames:
        raise RuntimeError("No datasets loaded.")

    # Merge
    master = pd.concat(frames, ignore_index=True)
    logger.info(f"\n[Merge] Combined total: {len(master)} rows")

    # Two-pass deduplication
    master = deduplicate(master, similarity_threshold=similarity_threshold)

    # Clean sequential IDs
    master["id"] = [f"{i+1:05d}" for i in range(len(master))]

    # Summary
    logger.info("══════ MASTER DATASET SUMMARY ══════")
    logger.info(f"Total questions : {len(master)}")
    logger.info(f"Categories      : {master['category'].nunique()}")
    logger.info(f"With answers    : {master['answer'].notna().sum()}")
    logger.info(f"NULL answers    : {master['answer'].isna().sum()}")
    logger.info("\nCategory breakdown:")
    for cat, count in master["category"].value_counts().items():
        null_ans = master[(master["category"] == cat) & master["answer"].isna()].shape[0]
        logger.info(f"  {cat:<35} {count:>4} questions  ({null_ans} without answers)")
    logger.info(f"\nDifficulty: {master['difficulty'].value_counts().to_dict()}")
    logger.info(f"Source:     {master['source'].value_counts().to_dict()}")

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    master.to_csv(output_path, index=False)
    logger.info(f"\n✅ Saved → {output_path}")
    return master


# ════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    kaggle_path         = os.path.join(DATA_DIR, "new_interview_questions.csv")
    deepseek_path       = os.path.join(DATA_DIR, "deepseek_questions.json")
    full_interview_path = os.path.join(DATA_DIR, "full_interview_questions_dataset.csv")

    master = build_master(kaggle_path, deepseek_path, full_interview_path)

    print("\n── Sample rows per category ──")
    for cat in master["category"].unique():
        n = min(2, (master["category"] == cat).sum())
        sample = master[master["category"] == cat].sample(n, random_state=1)
        for _, row in sample.iterrows():
            ans = str(row["answer"])[:70] + "…" if pd.notna(row["answer"]) else "NULL"
            print(f"  [{cat}] {row['question'][:75]}")
            print(f"           → {ans}")
        print()
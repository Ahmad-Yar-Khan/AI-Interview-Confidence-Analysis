"""
dedup_dataset.py
----------------
One-time script to remove near-duplicate questions from master_questions.csv.

Two questions are considered near-duplicates when their TF-IDF cosine similarity
exceeds THRESHOLD. When a pair is found, the question with the shorter combined
text (question + answer) is dropped — keeping the richer entry.

Usage:
    python dedup_dataset.py                        # preview only
    python dedup_dataset.py --apply                # overwrite master_questions.csv
    python dedup_dataset.py --threshold 0.80       # custom threshold (default 0.85)
"""

import argparse
import os
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "master_questions.csv")
THRESHOLD  = 0.85


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"id", "category", "question", "answer"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")
    df["answer"] = df["answer"].fillna("")
    return df


def embed(df: pd.DataFrame) -> np.ndarray:
    texts = (df["question"] + " " + df["answer"]).tolist()
    vec   = TfidfVectorizer(
        max_features=8000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        stop_words="english",
    )
    return normalize(vec.fit_transform(texts).toarray().astype(np.float32))


def find_duplicates(vecs: np.ndarray, df: pd.DataFrame, threshold: float) -> set[int]:
    """
    O(n²) pairwise comparison using batched numpy dot products.
    For each near-duplicate pair, marks the shorter/weaker entry for removal.
    """
    n      = len(df)
    to_drop: set[int] = set()
    lengths = (df["question"].str.len() + df["answer"].str.len()).values

    for i in range(n):
        if i in to_drop:
            continue
        # Similarities between question i and all questions after it
        sims = vecs[i + 1:] @ vecs[i]          # shape (n-i-1,)
        dup_positions = np.where(sims >= threshold)[0]  # relative indices

        for rel in dup_positions:
            j = i + 1 + int(rel)
            if j in to_drop:
                continue
            # Drop whichever has less content; ties go to j
            loser = j if lengths[i] >= lengths[j] else i
            to_drop.add(loser)

    return to_drop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",     action="store_true", help="Overwrite master_questions.csv")
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    args = parser.parse_args()

    print(f"Loading {DATA_PATH} ...")
    df = load(DATA_PATH)
    print(f"  {len(df)} questions across {df['category'].nunique()} categories")

    print(f"Embedding questions (TF-IDF, threshold={args.threshold}) ...")
    vecs = embed(df)

    print("Scanning for near-duplicates ...")
    to_drop = find_duplicates(vecs, df, args.threshold)
    print(f"  Found {len(to_drop)} duplicates to remove")

    if to_drop:
        # Show a sample of what will be removed
        sample = sorted(to_drop)[:10]
        print("\nSample questions marked for removal:")
        for idx in sample:
            row = df.iloc[idx]
            print(f"  [{row['category']}] {row['question'][:80]}")
        if len(to_drop) > 10:
            print(f"  ... and {len(to_drop) - 10} more")

    df_clean = df.drop(index=list(to_drop)).reset_index(drop=True)

    # Per-category summary
    print("\nCategory breakdown (before → after):")
    for cat in sorted(df["category"].unique()):
        before = (df["category"] == cat).sum()
        after  = (df_clean["category"] == cat).sum()
        removed = before - after
        print(f"  {cat:<35} {before:>4} → {after:>4}  (-{removed})")

    print(f"\nTotal: {len(df)} → {len(df_clean)}  ({len(to_drop)} removed)")

    if args.apply:
        df_clean.to_csv(DATA_PATH, index=False)
        print(f"\nSaved cleaned dataset to {DATA_PATH}")
    else:
        preview_path = DATA_PATH.replace(".csv", "_deduped_preview.csv")
        df_clean.to_csv(preview_path, index=False)
        print(f"\nDry run — saved preview to {preview_path}")
        print("Run with --apply to overwrite master_questions.csv")


if __name__ == "__main__":
    main()

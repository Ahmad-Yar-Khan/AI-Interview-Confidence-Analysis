"""
embedding_engine.py
-------------------
Builds TF-IDF embeddings for resume text and all questions.
Stores question vectors in a FAISS index for fast cosine similarity search.
Supports any resume — no hardcoding.
"""

import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
import faiss

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """
    Wraps TF-IDF vectorization + FAISS flat index for cosine search.

    Usage:
        engine = EmbeddingEngine()
        engine.fit(corpus_texts)          # build vocabulary on question corpus
        q_vecs = engine.embed_batch(texts)
        engine.build_index(q_vecs)        # store in FAISS
        results = engine.search(resume_vec, top_k=20)
    """

    def __init__(self, max_features: int = 8000, ngram_range: tuple = (1, 2)):
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            sublinear_tf=True,           # log(1+tf) dampening
            min_df=2,                    # ignore very rare terms
            max_df=0.95,                 # ignore too-common terms
            stop_words="english",
        )
        self.index: faiss.IndexFlatIP | None = None
        self.dim: int = 0
        self._fitted = False

    # ──────────────────────────────────────────
    # FIT
    # ──────────────────────────────────────────

    def fit(self, corpus: list[str]) -> None:
        """
        Fit the TF-IDF vocabulary on the question corpus.
        Call once at startup after loading the question dataset.
        """
        self.vectorizer.fit(corpus)
        self.dim = len(self.vectorizer.get_feature_names_out())
        self._fitted = True
        logger.info(f"EmbeddingEngine fitted. Vocabulary size: {self.dim}")

    # ──────────────────────────────────────────
    # EMBED
    # ──────────────────────────────────────────

    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text → L2-normalized float32 vector of shape (dim,).
        """
        if not self._fitted:
            raise RuntimeError("Call engine.fit(corpus) before embedding.")
        vec = self.vectorizer.transform([text])
        dense = vec.toarray().astype(np.float32)
        normed = normalize(dense, norm="l2")
        return normed[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of texts → shape (N, dim).
        """
        if not self._fitted:
            raise RuntimeError("Call engine.fit(corpus) before embedding.")
        mat = self.vectorizer.transform(texts).toarray().astype(np.float32)
        return normalize(mat, norm="l2")

    # ──────────────────────────────────────────
    # FAISS INDEX
    # ──────────────────────────────────────────

    def build_index(self, vectors: np.ndarray) -> None:
        """
        Build a FAISS inner-product index (= cosine similarity for L2-normalized vecs).
        vectors: shape (N, dim)
        """
        dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(dim)   # Inner Product
        self.index.add(vectors)
        logger.info(f"FAISS index built with {self.index.ntotal} vectors, dim={dim}")

    def search(self, query_vec: np.ndarray, top_k: int = 30) -> tuple[np.ndarray, np.ndarray]:
        """
        Search the FAISS index.
        Returns (scores, indices) each of shape (top_k,).
        Scores are cosine similarities in [0, 1].
        """
        if self.index is None:
            raise RuntimeError("Call build_index() before search().")
        q = query_vec.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(q, top_k)
        return scores[0], indices[0]

    # ──────────────────────────────────────────
    # COSINE (direct, no index)
    # ──────────────────────────────────────────

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        """Direct cosine similarity between two L2-normalized vectors."""
        return float(np.clip(np.dot(a, b), 0.0, 1.0))

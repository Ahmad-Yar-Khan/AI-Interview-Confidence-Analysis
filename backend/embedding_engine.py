"""
embedding_engine.py
-------------------
Builds SBERT embeddings for resume text and all questions.
Stores question vectors in a FAISS index for fast cosine similarity search.
Supports any resume — no hardcoding.
"""

import logging
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingEngine:
    """
    Wraps SBERT vectorization + FAISS flat index for cosine search.

    Usage:
        engine = EmbeddingEngine()
        engine.fit(corpus_texts)          # loads model, no-op for training
        q_vecs = engine.embed_batch(texts)
        engine.build_index(q_vecs)        # store in FAISS
        results = engine.search(resume_vec, top_k=20)
    """

    def __init__(self, model_name: str = _MODEL_NAME):
        self.model = SentenceTransformer(model_name)
        self.dim: int = self.model.get_sentence_embedding_dimension()
        self.index: faiss.IndexFlatIP | None = None
        self._fitted = False

    # ──────────────────────────────────────────
    # FIT  (no-op for SBERT — model is pre-trained)
    # ──────────────────────────────────────────

    def fit(self, corpus: list[str]) -> None:  # noqa: ARG002  kept for API compatibility
        self._fitted = True
        logger.info(f"EmbeddingEngine ready. Model: {_MODEL_NAME}, dim={self.dim}")

    # ──────────────────────────────────────────
    # EMBED
    # ──────────────────────────────────────────

    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text → L2-normalized float32 vector of shape (dim,).
        """
        vec = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return vec[0].astype(np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of texts → shape (N, dim).
        """
        vecs = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        return vecs.astype(np.float32)

    # ──────────────────────────────────────────
    # FAISS INDEX
    # ──────────────────────────────────────────

    def build_index(self, vectors: np.ndarray) -> None:
        """
        Build a FAISS inner-product index (= cosine similarity for L2-normalized vecs).
        vectors: shape (N, dim)
        """
        dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(dim)
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

    @staticmethod
    def rank_chunks(query_vec: np.ndarray, corpus_vecs: np.ndarray, top_k: int = 2) -> list[int]:
        """
        Rank a small corpus of L2-normalized vectors by cosine similarity to query.
        Uses numpy dot product — suitable for small N (resume chunks, not the full bank).
        Returns indices sorted by descending similarity.
        """
        scores = corpus_vecs @ query_vec
        top_k  = min(top_k, len(scores))
        return list(np.argsort(scores)[::-1][:top_k])

# haval_insights/embeddings.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List


class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Return a list of embedding vectors, one per text.
        """
        ...


class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Local embedding using a sentence-transformers model.

    Default: all-MiniLM-L6-v2 (small but solid for POC).
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer  # type: ignore
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        # returns a list of Python lists (not numpy arrays) for compatibility
        vectors = self.model.encode(texts, convert_to_numpy=False, show_progress_bar=False)
        return [v.tolist() for v in vectors]

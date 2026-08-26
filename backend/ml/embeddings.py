"""sentence-transformers wrapper (Phase 5).

Heavy dependencies (torch, sentence-transformers, numpy) are imported lazily so
the rest of the backend runs without them installed. Install with:

    pip install sentence-transformers torch numpy
"""
from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384  # all-MiniLM-L6-v2 output dimension


class MissingMLDeps(RuntimeError):
    """Raised when embedding is attempted without the optional ML deps."""


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:  # pragma: no cover - depends on optional install
        raise MissingMLDeps(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers torch numpy"
        ) from e
    return SentenceTransformer(MODEL_NAME)


def embed(texts: list[str]):
    """Return an (N, EMBED_DIM) numpy array of embeddings for ``texts``."""
    model = _load_model()
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


def embed_one(text: str):
    """Embed a single string -> (EMBED_DIM,) numpy array."""
    return embed([text or ""])[0]

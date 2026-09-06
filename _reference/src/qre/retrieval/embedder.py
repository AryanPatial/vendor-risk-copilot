from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from qre.config import get_settings

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


def embed_passages(texts: list[str], batch_size: int = 64) -> np.ndarray:
    return _model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 500,
    )


def embed_query(text: str, *, instruct: bool = False) -> np.ndarray:
    payload = QUERY_PREFIX + text if instruct else text
    return _model().encode(payload, normalize_embeddings=True)

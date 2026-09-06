from functools import lru_cache

from sentence_transformers import CrossEncoder

from qre.config import get_settings
from qre.retrieval.types import Candidate


@lru_cache(maxsize=1)
def _model() -> CrossEncoder:
    return CrossEncoder(get_settings().rerank_model)


def _pair_text(candidate: Candidate) -> str:
    if candidate.source == "answer_bank":
        return f"{candidate.text} {candidate.answer_text}"
    return candidate.text


def rerank(query: str, candidates: list[Candidate], top_n: int | None = None) -> list[Candidate]:
    if not candidates:
        return []

    top_n = top_n or get_settings().rerank_top_n
    scores = _model().predict([(query, _pair_text(c)) for c in candidates])

    for candidate, score in zip(candidates, scores, strict=True):
        candidate.scores["rerank"] = float(score)

    return sorted(candidates, key=lambda c: c.scores["rerank"], reverse=True)[:top_n]

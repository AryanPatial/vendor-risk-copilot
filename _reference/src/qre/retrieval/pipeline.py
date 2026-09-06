from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from qre.retrieval.rerank import rerank
from qre.retrieval.search import Method, search
from qre.retrieval.types import Candidate


@dataclass
class RetrievalResult:
    query: str
    candidates: list[Candidate]

    @property
    def top_score(self) -> float:
        return self.candidates[0].score if self.candidates else 0.0


def retrieve(
    session: Session,
    query: str,
    company_id: int,
    *,
    top_k: int | None = None,
    top_n: int | None = None,
    use_reranker: bool = True,
    methods: Sequence[Method] = ("dense", "lexical"),
    include_policies: bool = True,
) -> RetrievalResult:
    candidates = search(
        session,
        query,
        company_id,
        limit=top_k,
        methods=methods,
        include_policies=include_policies,
    )
    if use_reranker:
        candidates = rerank(query, candidates, top_n=top_n)
    elif top_n:
        candidates = candidates[:top_n]
    return RetrievalResult(query=query, candidates=candidates)

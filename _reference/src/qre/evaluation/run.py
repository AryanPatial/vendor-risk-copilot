from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from qre.config import get_settings
from qre.db.models import Company
from qre.evaluation.dataset import EvalExample
from qre.evaluation.metrics import RetrievalReport, rank_of
from qre.retrieval.pipeline import retrieve


@dataclass(frozen=True)
class Configuration:
    label: str
    methods: tuple[str, ...]
    use_reranker: bool


BASELINES = [
    Configuration("Dense only (naive RAG)", ("dense",), False),
    Configuration("Lexical only (BM25-style)", ("lexical",), False),
    Configuration("Hybrid (RRF)", ("dense", "lexical"), False),
    Configuration("Hybrid + cross-encoder rerank", ("dense", "lexical"), True),
]


def _abstain_accuracy(scores: list[tuple[float, bool]]) -> float | None:
    """Share of examples where 'top score >= threshold' agrees with whether we can answer."""
    if not scores:
        return None
    threshold = get_settings().min_confidence
    correct = sum((score >= threshold) == answerable for score, answerable in scores)
    return correct / len(scores)


def evaluate(
    session: Session,
    company_slug: str,
    examples: list[EvalExample],
    config: Configuration,
    *,
    depth: int = 10,
) -> RetrievalReport:
    company_id = session.scalar(select(Company.id).where(Company.slug == company_slug))
    if company_id is None:
        raise ValueError(f"unknown company: {company_slug}")

    ranks: list[int | None] = []
    abstain_inputs: list[tuple[float, bool]] = []

    for example in examples:
        result = retrieve(
            session,
            example.question,
            company_id,
            top_n=depth,
            use_reranker=config.use_reranker,
            methods=config.methods,
        )
        abstain_inputs.append((result.top_score, example.answerable))
        if example.answerable and example.expected_id is not None:
            ranks.append(rank_of(result.candidates, example.expected_id))

    return RetrievalReport.build(config.label, ranks, _abstain_accuracy(abstain_inputs))


def compare(
    session: Session,
    company_slug: str,
    examples: list[EvalExample],
    configs: list[Configuration] | None = None,
) -> list[RetrievalReport]:
    return [evaluate(session, company_slug, examples, config) for config in (configs or BASELINES)]

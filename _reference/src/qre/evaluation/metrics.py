from dataclasses import dataclass
from statistics import mean

from qre.retrieval.types import Candidate


def rank_of(candidates: list[Candidate], expected_id: int) -> int | None:
    for i, c in enumerate(candidates, start=1):
        if c.source == "answer_bank" and c.source_id == expected_id:
            return i
    return None


def recall_at_k(ranks: list[int | None], k: int) -> float:
    if not ranks:
        return 0.0
    return mean(1.0 if r is not None and r <= k else 0.0 for r in ranks)


def mrr(ranks: list[int | None]) -> float:
    if not ranks:
        return 0.0
    return mean(1.0 / r if r is not None else 0.0 for r in ranks)


@dataclass
class RetrievalReport:
    label: str
    n: int
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    abstain_accuracy: float | None = None

    @classmethod
    def build(
        cls,
        label: str,
        ranks: list[int | None],
        abstain_accuracy: float | None = None,
    ) -> "RetrievalReport":
        return cls(
            label=label,
            n=len(ranks),
            recall_at_1=recall_at_k(ranks, 1),
            recall_at_5=recall_at_k(ranks, 5),
            recall_at_10=recall_at_k(ranks, 10),
            mrr=mrr(ranks),
            abstain_accuracy=abstain_accuracy,
        )

    def as_row(self) -> str:
        abstain = f"{self.abstain_accuracy:.2f}" if self.abstain_accuracy is not None else "—"
        return (
            f"| {self.label} | {self.n} | {self.recall_at_1:.2f} | {self.recall_at_5:.2f} "
            f"| {self.recall_at_10:.2f} | {self.mrr:.3f} | {abstain} |"
        )


TABLE_HEADER = (
    "| Configuration | N | R@1 | R@5 | R@10 | MRR | Abstain acc. |\n|---|---|---|---|---|---|---|"
)

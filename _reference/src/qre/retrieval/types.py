from dataclasses import dataclass, field
from typing import Literal

SourceKind = Literal["answer_bank", "policy_chunk"]


@dataclass
class Candidate:
    source: SourceKind
    source_id: int
    text: str
    answer_text: str | None
    control_id: str | None
    document_title: str
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.scores.get("rerank", self.scores.get("fused", 0.0))

    def as_context(self) -> str:
        if self.source == "answer_bank":
            return f"Previous question: {self.text}\nPrevious answer: {self.answer_text}"
        return f"Policy extract ({self.document_title}):\n{self.text}"

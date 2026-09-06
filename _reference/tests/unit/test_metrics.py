from qre.evaluation.metrics import RetrievalReport, mrr, rank_of, recall_at_k
from qre.retrieval.types import Candidate


def make(source, source_id):
    return Candidate(
        source=source,
        source_id=source_id,
        text="t",
        answer_text="a",
        control_id=None,
        document_title="doc",
    )


def test_rank_of_ignores_policy_chunks():
    candidates = [make("policy_chunk", 9), make("answer_bank", 4)]
    assert rank_of(candidates, 4) == 2


def test_rank_of_returns_none_when_missing():
    assert rank_of([make("answer_bank", 1)], 99) is None


def test_recall_and_mrr():
    ranks = [1, 3, None, 5]
    assert recall_at_k(ranks, 1) == 0.25
    assert recall_at_k(ranks, 5) == 0.75
    assert mrr(ranks) == (1 + 1 / 3 + 0 + 1 / 5) / 4


def test_empty_inputs_do_not_divide_by_zero():
    assert recall_at_k([], 5) == 0.0
    assert mrr([]) == 0.0


def test_report_row_is_markdown():
    row = RetrievalReport.build("Hybrid", [1, 2], 0.9).as_row()
    assert row.startswith("| Hybrid | 2 |")
    assert row.endswith("| 0.90 |")

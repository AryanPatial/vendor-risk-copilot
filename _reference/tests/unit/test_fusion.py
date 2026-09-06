from qre.retrieval.search import _fuse
from qre.retrieval.types import Candidate


def make(source_id, source="answer_bank"):
    return Candidate(
        source=source,
        source_id=source_id,
        text="t",
        answer_text="a",
        control_id=None,
        document_title="doc",
    )


def test_item_ranked_well_by_both_methods_wins():
    dense = [make(1), make(2), make(3)]
    lexical = [make(3), make(1), make(2)]
    fused = _fuse([dense, lexical], limit=3)
    assert fused[0].source_id == 1


def test_deduplicates_across_lists():
    fused = _fuse([[make(1)], [make(1)]], limit=10)
    assert len(fused) == 1


def test_same_id_from_different_sources_stays_separate():
    fused = _fuse([[make(1, "answer_bank"), make(1, "policy_chunk")]], limit=10)
    assert len(fused) == 2


def test_respects_limit():
    assert len(_fuse([[make(i) for i in range(10)]], limit=3)) == 3

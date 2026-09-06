from pathlib import Path

import pytest
from sqlalchemy import select

from qre.db.engine import session_scope
from qre.db.migrate import run_migrations
from qre.db.models import Company
from qre.ingest.loader import ingest_answer_bank
from qre.retrieval.pipeline import retrieve

pytestmark = pytest.mark.needs_db

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_caiq.csv"
COMPANY = "pytest-acme"


@pytest.fixture(scope="module")
def company_id() -> int:
    run_migrations()
    with session_scope() as session:
        ingest_answer_bank(session, FIXTURE, COMPANY, replace=True)
    with session_scope() as session:
        return session.scalar(select(Company.id).where(Company.slug == COMPANY))


def test_reworded_question_finds_the_original_answer(company_id):
    with session_scope() as session:
        result = retrieve(session, "Do you screen staff before they join?", company_id, top_n=3)
    assert result.candidates
    assert result.candidates[0].control_id == "HRS-02.1"


def test_lexical_only_still_returns_something(company_id):
    with session_scope() as session:
        result = retrieve(
            session, "penetration testing", company_id, methods=("lexical",), use_reranker=False
        )
    assert any(c.control_id == "IVS-04.1" for c in result.candidates)


def test_unrelated_question_scores_low(company_id):
    with session_scope() as session:
        result = retrieve(session, "How many parking spaces do you have?", company_id, top_n=3)
    assert result.top_score < 0.45

from pathlib import Path

import pytest

from qre.ingest import spreadsheet

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_caiq.csv"


def test_finds_header_below_title_rows():
    rows = spreadsheet.parse(FIXTURE)
    assert len(rows) == 5


def test_question_id_column_is_not_read_as_the_question():
    rows = spreadsheet.parse(FIXTURE)
    assert rows[0].control_id == "CEK-03.1"
    assert rows[0].question.startswith("Are cryptographic keys")


def test_answer_merges_the_yes_no_column_and_the_description():
    rows = spreadsheet.parse(FIXTURE)
    assert rows[0].answer.startswith("Yes")
    assert "AWS KMS" in rows[0].answer


def test_row_refs_are_unique():
    rows = spreadsheet.parse(FIXTURE)
    assert len({r.row_ref for r in rows}) == len(rows)


def test_rejects_file_without_a_question_column(tmp_path):
    path = tmp_path / "junk.csv"
    path.write_text("alpha,beta\n1,2\n")
    with pytest.raises(ValueError, match="no question column"):
        spreadsheet.parse(path)

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from qre.answering.generator import DraftAnswer, draft, draft_extractive
from qre.db.models import Citation, Company, Draft, Question, Questionnaire
from qre.ingest import spreadsheet
from qre.retrieval.pipeline import retrieve


def _company_id(session: Session, slug: str) -> int:
    company_id = session.scalar(select(Company.id).where(Company.slug == slug))
    if company_id is None:
        raise ValueError(f"unknown company: {slug}")
    return company_id


def answer_question(
    session: Session, question: str, company_slug: str, *, extractive: bool = False
) -> tuple[DraftAnswer, list]:
    result = retrieve(session, question, _company_id(session, company_slug))
    answer = draft_extractive(result) if extractive else draft(result)
    return answer, result.candidates


def load_questionnaire(
    session: Session, path: Path, company_slug: str, *, sheet: str | int | None = None
) -> Questionnaire:
    company_id = _company_id(session, company_slug)
    rows = spreadsheet.parse(path, sheet=sheet)
    if not rows:
        raise ValueError(f"no questions found in {path.name}")

    questionnaire = Questionnaire(
        company_id=company_id,
        name=path.stem,
        format=path.suffix.lstrip("."),
        status="uploaded",
    )
    session.add(questionnaire)
    session.flush()

    session.add_all(
        Question(
            questionnaire_id=questionnaire.id,
            row_ref=row.row_ref,
            control_id=row.control_id,
            text=row.question,
            ordinal=i,
        )
        for i, row in enumerate(rows)
    )
    session.flush()
    return questionnaire


def _persist(session: Session, question_id: int, answer: DraftAnswer) -> Draft:
    session.query(Draft).filter_by(question_id=question_id).delete()
    record = Draft(
        question_id=question_id,
        answer_text=answer.text,
        confidence=answer.confidence,
        status=answer.status,
        model=answer.model,
    )
    session.add(record)
    session.flush()

    session.add_all(
        Citation(
            draft_id=record.id,
            source=candidate.source,
            source_id=candidate.source_id,
            rank=rank,
            score=candidate.score,
        )
        for rank, candidate in enumerate(answer.citations, start=1)
    )
    return record


def process_questionnaire(
    session: Session,
    questionnaire_id: int,
    *,
    extractive: bool = False,
    progress=None,
) -> dict[str, int]:
    questionnaire = session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        raise ValueError(f"unknown questionnaire: {questionnaire_id}")

    questionnaire.status = "drafting"
    session.flush()

    company_id = questionnaire.company_id
    counts = {"generated": 0, "needs_review": 0}

    for question in questionnaire.questions:
        result = retrieve(session, question.text, company_id)
        answer = draft_extractive(result) if extractive else draft(result)
        _persist(session, question.id, answer)
        counts[answer.status] = counts.get(answer.status, 0) + 1
        if progress:
            progress(question, answer)

    questionnaire.status = "ready"
    session.flush()
    return counts


def approve(session: Session, draft_id: int, edited_text: str | None = None) -> Draft:
    record = session.get(Draft, draft_id)
    if record is None:
        raise ValueError(f"unknown draft: {draft_id}")
    if edited_text is not None:
        record.edited_text = edited_text
    record.status = "approved"
    record.reviewed_at = datetime.now(UTC)
    session.flush()
    return record

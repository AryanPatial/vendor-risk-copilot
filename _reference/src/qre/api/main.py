import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from qre.answering.service import (
    answer_question,
    approve,
    load_questionnaire,
    process_questionnaire,
)
from qre.api.deps import DbSession
from qre.api.schemas import (
    ApproveRequest,
    AskRequest,
    AskResponse,
    CitationOut,
    DraftOut,
    ProcessResponse,
    QuestionnaireOut,
)
from qre.db.models import AnswerBankEntry, Draft, PolicyChunk, Question, Questionnaire

app = FastAPI(title="Questionnaire Response Engine", version="0.1.0")

UPLOAD_SUFFIXES = {".xlsx", ".xls", ".csv"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _hydrate(session: Session, source: str, source_id: int) -> tuple[str | None, str | None]:
    if source == "answer_bank":
        row = session.get(AnswerBankEntry, source_id)
        return (row.control_id, row.answer_text[:400]) if row else (None, None)
    chunk = session.get(PolicyChunk, source_id)
    return (chunk.heading, chunk.content[:400]) if chunk else (None, None)


def _draft_out(session: Session, draft: Draft) -> DraftOut:
    citations = []
    for citation in draft.citations:
        reference, excerpt = _hydrate(session, citation.source, citation.source_id)
        citations.append(
            CitationOut(
                source=citation.source,
                source_id=citation.source_id,
                rank=citation.rank,
                score=citation.score,
                reference=reference,
                excerpt=excerpt,
            )
        )
    return DraftOut(
        id=draft.id,
        question_id=draft.question_id,
        row_ref=draft.question.row_ref,
        control_id=draft.question.control_id,
        question=draft.question.text,
        answer=draft.answer_text,
        edited_text=draft.edited_text,
        confidence=draft.confidence,
        status=draft.status,
        citations=citations,
    )


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, session: DbSession) -> AskResponse:
    try:
        answer, candidates = answer_question(
            session, payload.question, payload.company, extractive=payload.extractive
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AskResponse(
        question=payload.question,
        answer=answer.text,
        confidence=answer.confidence,
        status=answer.status,
        model=answer.model,
        citations=[
            CitationOut(
                source=c.source,
                source_id=c.source_id,
                rank=i,
                score=c.score,
                reference=c.control_id or c.document_title,
                excerpt=(c.answer_text or c.text)[:400],
            )
            for i, c in enumerate(candidates, start=1)
        ],
    )


@app.post("/questionnaires", response_model=QuestionnaireOut, status_code=201)
def upload_questionnaire(
    session: DbSession,
    company: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> QuestionnaireOut:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in UPLOAD_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"unsupported file type: {suffix or 'unknown'}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        questionnaire = load_questionnaire(session, tmp_path, company)
        questionnaire.name = Path(file.filename or tmp_path.name).stem
        session.flush()
        return QuestionnaireOut(
            id=questionnaire.id,
            name=questionnaire.name,
            status=questionnaire.status,
            question_count=len(questionnaire.questions),
            uploaded_at=questionnaire.uploaded_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/questionnaires", response_model=list[QuestionnaireOut])
def list_questionnaires(session: DbSession) -> list[QuestionnaireOut]:
    rows = session.scalars(select(Questionnaire).order_by(Questionnaire.id.desc())).all()
    return [
        QuestionnaireOut(
            id=q.id,
            name=q.name,
            status=q.status,
            question_count=len(q.questions),
            uploaded_at=q.uploaded_at,
        )
        for q in rows
    ]


@app.post("/questionnaires/{questionnaire_id}/process", response_model=ProcessResponse)
def process(
    questionnaire_id: int,
    session: DbSession,
    extractive: bool = False,
) -> ProcessResponse:
    try:
        counts = process_questionnaire(session, questionnaire_id, extractive=extractive)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProcessResponse(questionnaire_id=questionnaire_id, counts=counts)


@app.get("/questionnaires/{questionnaire_id}/drafts", response_model=list[DraftOut])
def list_drafts(questionnaire_id: int, session: DbSession) -> list[DraftOut]:
    drafts = session.scalars(
        select(Draft)
        .join(Question, Question.id == Draft.question_id)
        .where(Question.questionnaire_id == questionnaire_id)
        .order_by(Question.ordinal)
    ).all()
    return [_draft_out(session, d) for d in drafts]


@app.post("/drafts/{draft_id}/approve", response_model=DraftOut)
def approve_draft(
    draft_id: int,
    payload: ApproveRequest,
    session: DbSession,
) -> DraftOut:
    try:
        draft = approve(session, draft_id, payload.edited_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _draft_out(session, draft)

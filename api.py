import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

import db
from answer import draft
from load import read_questionnaire

app = FastAPI(
    title="Questionnaire Response Engine",
    description="Drafts answers to security questionnaires from past answers and policy documents.",
    version="1.0.0",
)

ALLOWED_SUFFIXES = {".xlsx", ".xls", ".csv"}


class Citation(BaseModel):
    n: int
    source: str
    id: int
    label: str | None


class Draft(BaseModel):
    question: str
    answer: str
    confidence: float
    abstained: bool
    model: str
    citations: list[Citation]


class AskRequest(BaseModel):
    question: str = Field(min_length=5)
    extractive: bool = True


class QuestionnaireResponse(BaseModel):
    filename: str
    total: int
    drafted: int
    needs_review: int
    drafts: list[Draft]


def to_draft(question, result):
    return Draft(question=question, answer=result["text"], **{
        k: result[k] for k in ("confidence", "abstained", "model", "citations")
    })


@app.get("/health")
def health():
    with db.connect() as conn:
        answers = conn.execute("SELECT count(*) FROM answer_bank").fetchone()[0]
        chunks = conn.execute("SELECT count(*) FROM policy_chunks").fetchone()[0]
    return {"status": "ok", "answer_bank": answers, "policy_chunks": chunks}


@app.post("/ask", response_model=Draft)
def ask(payload: AskRequest):
    try:
        result = draft(payload.question, extractive=payload.extractive)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return to_draft(payload.question, result)


@app.post("/questionnaire", response_model=QuestionnaireResponse)
def questionnaire(
    file: Annotated[UploadFile, File()],
    extractive: Annotated[bool, Query()] = True,
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"unsupported file type: {suffix or 'unknown'}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        path = Path(tmp.name)

    try:
        rows = read_questionnaire(path)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)

    drafts = [to_draft(r["question"], draft(r["question"], extractive=extractive)) for r in rows]
    flagged = sum(d.abstained for d in drafts)

    return QuestionnaireResponse(
        filename=file.filename or path.name,
        total=len(drafts),
        drafted=len(drafts) - flagged,
        needs_review=flagged,
        drafts=drafts,
    )

from datetime import datetime

from pydantic import BaseModel, Field


class CitationOut(BaseModel):
    source: str
    source_id: int
    rank: int
    score: float
    reference: str | None = None
    excerpt: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=5)
    company: str
    extractive: bool = False


class AskResponse(BaseModel):
    question: str
    answer: str
    confidence: float
    status: str
    model: str
    citations: list[CitationOut]


class QuestionnaireOut(BaseModel):
    id: int
    name: str
    status: str
    question_count: int
    uploaded_at: datetime


class DraftOut(BaseModel):
    id: int
    question_id: int
    row_ref: str
    control_id: str | None
    question: str
    answer: str
    edited_text: str | None
    confidence: float
    status: str
    citations: list[CitationOut]


class ProcessResponse(BaseModel):
    questionnaire_id: int
    counts: dict[str, int]


class ApproveRequest(BaseModel):
    edited_text: str | None = None

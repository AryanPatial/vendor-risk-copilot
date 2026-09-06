import hashlib
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from qre.db.models import AnswerBankEntry, Company, Document, PolicyChunk
from qre.ingest import spreadsheet
from qre.ingest.chunking import chunk_markdown
from qre.retrieval.embedder import embed_passages


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_or_create_company(session: Session, slug: str, name: str | None = None) -> Company:
    company = session.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        company = Company(slug=slug, name=name or slug)
        session.add(company)
        session.flush()
    return company


def _existing_document(session: Session, company_id: int, digest: str) -> Document | None:
    return session.scalar(
        select(Document).where(Document.company_id == company_id, Document.checksum == digest)
    )


def ingest_answer_bank(
    session: Session,
    path: Path,
    company_slug: str,
    *,
    answered_on: date | None = None,
    sheet: str | int | None = None,
    replace: bool = False,
) -> tuple[Document, int]:
    company = get_or_create_company(session, company_slug)
    digest = checksum(path)

    existing = _existing_document(session, company.id, digest)
    if existing and not replace:
        return existing, 0
    if existing:
        session.query(AnswerBankEntry).filter_by(document_id=existing.id).delete()
        document = existing
    else:
        document = Document(
            company_id=company.id,
            kind="completed_questionnaire",
            title=path.stem,
            source_uri=str(path),
            checksum=digest,
        )
        session.add(document)
        session.flush()

    rows = [r for r in spreadsheet.parse(path, sheet=sheet) if r.answer]
    if not rows:
        return document, 0

    vectors = embed_passages([r.question for r in rows])
    session.add_all(
        AnswerBankEntry(
            company_id=company.id,
            document_id=document.id,
            control_id=row.control_id,
            question_text=row.question,
            answer_text=row.answer,
            answered_on=answered_on,
            embedding=vector.tolist(),
        )
        for row, vector in zip(rows, vectors, strict=True)
    )
    return document, len(rows)


def ingest_policy_file(
    session: Session, path: Path, company_slug: str, *, replace: bool = False
) -> tuple[Document, int]:
    company = get_or_create_company(session, company_slug)
    digest = checksum(path)

    existing = _existing_document(session, company.id, digest)
    if existing and not replace:
        return existing, 0
    if existing:
        session.query(PolicyChunk).filter_by(document_id=existing.id).delete()
        document = existing
    else:
        document = Document(
            company_id=company.id,
            kind="policy",
            title=path.stem.replace("-", " ").replace("_", " ").title(),
            source_uri=str(path),
            checksum=digest,
        )
        session.add(document)
        session.flush()

    chunks = chunk_markdown(path.read_text(encoding="utf-8", errors="ignore"))
    if not chunks:
        return document, 0

    vectors = embed_passages([c.content for c in chunks])
    session.add_all(
        PolicyChunk(
            company_id=company.id,
            document_id=document.id,
            heading=chunk.heading,
            content=chunk.content,
            ordinal=chunk.ordinal,
            embedding=vector.tolist(),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    )
    return document, len(chunks)


def ingest_policy_dir(
    session: Session, directory: Path, company_slug: str, *, replace: bool = False
) -> dict[str, int]:
    results: dict[str, int] = {}
    for path in sorted(directory.rglob("*.md")):
        _, count = ingest_policy_file(session, path, company_slug, replace=replace)
        results[path.name] = count
    return results

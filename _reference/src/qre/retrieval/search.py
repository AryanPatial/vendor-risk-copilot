from collections import defaultdict
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from qre.config import get_settings
from qre.retrieval.embedder import embed_query
from qre.retrieval.types import Candidate, SourceKind

Method = Literal["dense", "lexical"]
RRF_K = 60

_ANSWER_VECTOR_SQL = text("""
    SELECT a.id, a.question_text, a.answer_text, a.control_id, d.title,
           1 - (a.embedding <=> :vec) AS score
    FROM answer_bank a
    JOIN documents d ON d.id = a.document_id
    WHERE a.company_id = :company_id AND a.embedding IS NOT NULL
    ORDER BY a.embedding <=> :vec
    LIMIT :limit
""")

_ANSWER_LEXICAL_SQL = text("""
    SELECT a.id, a.question_text, a.answer_text, a.control_id, d.title,
           ts_rank_cd(a.tsv, query) AS score
    FROM answer_bank a
    JOIN documents d ON d.id = a.document_id,
         websearch_to_tsquery('english', :q) AS query
    WHERE a.company_id = :company_id AND a.tsv @@ query
    ORDER BY score DESC
    LIMIT :limit
""")

_POLICY_VECTOR_SQL = text("""
    SELECT p.id, p.content, p.heading, d.title,
           1 - (p.embedding <=> :vec) AS score
    FROM policy_chunks p
    JOIN documents d ON d.id = p.document_id
    WHERE p.company_id = :company_id AND p.embedding IS NOT NULL
    ORDER BY p.embedding <=> :vec
    LIMIT :limit
""")

_POLICY_LEXICAL_SQL = text("""
    SELECT p.id, p.content, p.heading, d.title,
           ts_rank_cd(p.tsv, query) AS score
    FROM policy_chunks p
    JOIN documents d ON d.id = p.document_id,
         websearch_to_tsquery('english', :q) AS query
    WHERE p.company_id = :company_id AND p.tsv @@ query
    ORDER BY score DESC
    LIMIT :limit
""")


def _answer_candidates(rows) -> list[Candidate]:
    return [
        Candidate(
            source="answer_bank",
            source_id=r.id,
            text=r.question_text,
            answer_text=r.answer_text,
            control_id=r.control_id,
            document_title=r.title,
        )
        for r in rows
    ]


def _policy_candidates(rows) -> list[Candidate]:
    return [
        Candidate(
            source="policy_chunk",
            source_id=r.id,
            text=r.content,
            answer_text=None,
            control_id=None,
            document_title=f"{r.title} — {r.heading}" if r.heading else r.title,
        )
        for r in rows
    ]


def _fuse(lists: list[list[Candidate]], limit: int) -> list[Candidate]:
    fused: dict[tuple[SourceKind, int], float] = defaultdict(float)
    seen: dict[tuple[SourceKind, int], Candidate] = {}

    for ranked in lists:
        for rank, candidate in enumerate(ranked, start=1):
            key = (candidate.source, candidate.source_id)
            fused[key] += 1.0 / (RRF_K + rank)
            seen.setdefault(key, candidate)

    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    out = []
    for key, score in ordered:
        candidate = seen[key]
        candidate.scores["fused"] = score
        out.append(candidate)
    return out


def search(
    session: Session,
    query: str,
    company_id: int,
    *,
    limit: int | None = None,
    include_policies: bool = True,
    methods: Sequence[Method] = ("dense", "lexical"),
) -> list[Candidate]:
    settings = get_settings()
    limit = limit or settings.retrieval_top_k
    per_list = limit * 2
    lists: list[list[Candidate]] = []

    if "dense" in methods:
        params = {
            "vec": str(embed_query(query).tolist()),
            "company_id": company_id,
            "limit": per_list,
        }
        lists.append(_answer_candidates(session.execute(_ANSWER_VECTOR_SQL, params)))
        if include_policies:
            lists.append(_policy_candidates(session.execute(_POLICY_VECTOR_SQL, params)))

    if "lexical" in methods:
        params = {"q": query, "company_id": company_id, "limit": per_list}
        lists.append(_answer_candidates(session.execute(_ANSWER_LEXICAL_SQL, params)))
        if include_policies:
            lists.append(_policy_candidates(session.execute(_POLICY_LEXICAL_SQL, params)))

    return _fuse(lists, limit)

import sys

import db
from embed import embed_query

TOP_K = 5
RRF_K = 60

# Both tables are ranked in ONE query per method. Ranking them separately would give the
# small answer_bank the same top position as the much larger policy_chunks table.
BY_VECTOR = """
    SELECT source, id, label, text, answer, source_file, ordinal FROM (
        SELECT 'answer_bank' AS source, id, control_id AS label,
               question_text AS text, answer_text AS answer, source_file, 0 AS ordinal,
               embedding <=> %(vec)s AS distance
        FROM answer_bank
        UNION ALL
        SELECT 'policy_chunk', id, heading, content, NULL, source_file, ordinal,
               embedding <=> %(vec)s
        FROM policy_chunks
    ) ranked
    ORDER BY distance
    LIMIT %(limit)s
"""

BY_KEYWORD = """
    SELECT source, id, label, text, answer, source_file, ordinal FROM (
        SELECT 'answer_bank' AS source, id, control_id AS label,
               question_text AS text, answer_text AS answer, source_file, 0 AS ordinal,
               ts_rank_cd(tsv, q) AS rank
        FROM answer_bank, websearch_to_tsquery('english', %(query)s) AS q
        WHERE tsv @@ q
        UNION ALL
        SELECT 'policy_chunk', id, heading, content, NULL, source_file, ordinal,
               ts_rank_cd(tsv, q)
        FROM policy_chunks, websearch_to_tsquery('english', %(query)s) AS q
        WHERE tsv @@ q
    ) ranked
    ORDER BY rank DESC
    LIMIT %(limit)s
"""


def as_results(rows):
    return [
        {"source": r[0], "id": r[1], "label": r[2], "text": r[3], "answer": r[4],
         "source_file": r[5], "ordinal": r[6]}
        for r in rows
    ]


def fuse(ranked_lists, limit):
    """Reciprocal rank fusion: score by position in each list, not by raw score."""
    scores = {}
    seen = {}

    for results in ranked_lists:
        for position, result in enumerate(results, start=1):
            key = (result["source"], result["id"])
            scores[key] = scores.get(key, 0) + 1 / (RRF_K + position)
            seen.setdefault(key, result)

    best = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [seen[key] | {"score": score} for key, score in best]


def search(query, limit=TOP_K, methods=("dense", "keyword")):
    params = {"vec": embed_query(query), "query": query, "limit": limit * 2}
    lists = []

    with db.connect() as conn:
        if "dense" in methods:
            lists.append(as_results(conn.execute(BY_VECTOR, params).fetchall()))
        if "keyword" in methods:
            lists.append(as_results(conn.execute(BY_KEYWORD, params).fetchall()))

    return fuse(lists, limit)


def show(query, limit=TOP_K):
    print(f'\n"{query}"')
    for r in search(query, limit):
        print(f"  {r['score']:.4f}  {r['source']:13} {str(r['label'])[:36]:36} {r['text'][:42]}")


if __name__ == "__main__":
    show(" ".join(sys.argv[1:]))

import sys
from functools import lru_cache

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_N = 5


@lru_cache(maxsize=1)
def get_model():
    return CrossEncoder(MODEL_NAME)


def pair_text(result):
    """A past answer is only useful together with its question."""
    if result["source"] == "answer_bank":
        return f"{result['text']} {result['answer']}"
    return result["text"]


def rerank(query, results, top_n=TOP_N):
    if not results:
        return []

    scores = get_model().predict([(query, pair_text(r)) for r in results])
    scored = [r | {"rerank_score": float(s)} for r, s in zip(results, scores)]
    return sorted(scored, key=lambda r: r["rerank_score"], reverse=True)[:top_n]


if __name__ == "__main__":
    from search import search

    query = " ".join(sys.argv[1:])
    found = search(query, limit=10)

    print(f'\n"{query}"\n')
    print("BEFORE reranking (RRF order):")
    for i, r in enumerate(found[:5], 1):
        print(f"  {i}. {str(r['label'])[:52]}")

    print("\nAFTER reranking (cross-encoder order):")
    for i, r in enumerate(rerank(query, found), 1):
        print(f"  {i}. [{r['rerank_score']:+.2f}] {str(r['label'])[:52]}")

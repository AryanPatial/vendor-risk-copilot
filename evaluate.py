import json
import sys
from pathlib import Path

from rerank import rerank
from search import search

EVAL_FILE = Path("data/eval/policies.jsonl")
DEPTH = 10
RETRIEVE_BEFORE_RERANK = 10

CONFIGURATIONS = [
    ("Semantic only (naive RAG)", ("dense",), False),
    ("Keyword only (BM25-style)", ("keyword",), False),
    ("Hybrid (RRF)", ("dense", "keyword"), False),
    ("Hybrid + cross-encoder rerank", ("dense", "keyword"), True),
]


def retrieve(query, methods, use_reranker, depth):
    if not use_reranker:
        return search(query, limit=depth, methods=methods)
    candidates = search(query, limit=RETRIEVE_BEFORE_RERANK, methods=methods)
    return rerank(query, candidates, top_n=depth)


def load_examples(path=EVAL_FILE):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def is_correct(result, example):
    """Chunks are identified by file and position, not database id. Serial ids
    change every time the corpus is re-indexed; file and ordinal do not."""
    if result["source"] == "policy_chunk":
        want = {(c["file"], c["ordinal"]) for c in example.get("chunks", [])}
        return (result["source_file"], result["ordinal"]) in want
    return result["label"] == example.get("answer_control")


def rank_of_correct(results, example):
    """Position of the first correct result, or None if it never appeared."""
    for position, result in enumerate(results, start=1):
        if is_correct(result, example):
            return position
    return None


def score(examples, methods, use_reranker=False, depth=DEPTH):
    ranks = [
        rank_of_correct(retrieve(e["question"], methods, use_reranker, depth), e)
        for e in examples
    ]
    found = [r for r in ranks if r is not None]
    if not ranks:
        return {"n": 0, "recall@1": 0, "recall@5": 0, "recall@10": 0, "mrr": 0, "ranks": []}

    return {
        "n": len(ranks),
        "recall@1": sum(r == 1 for r in found) / len(ranks),
        "recall@5": sum(r <= 5 for r in found) / len(ranks),
        "recall@10": len(found) / len(ranks),
        "mrr": sum(1 / r for r in found) / len(ranks),
        "ranks": ranks,
    }


def compare(examples):
    return [
        (label, score(examples, methods, use_reranker))
        for label, methods, use_reranker in CONFIGURATIONS
    ]


def by_style(examples, style):
    return [e for e in examples if e.get("style", "reworded") == style]


def print_table(results):
    print("| Configuration | N | R@1 | R@5 | R@10 | MRR |")
    print("|---|---|---|---|---|---|")
    for label, s in results:
        print(
            f"| {label} | {s['n']} | {s['recall@1']:.2f} | {s['recall@5']:.2f} "
            f"| {s['recall@10']:.2f} | {s['mrr']:.3f} |"
        )


def print_failures(examples, results):
    label, best = max(results, key=lambda r: r[1]["mrr"])
    print(f"\nquestions {label} still gets wrong:")
    misses = [
        (e, r) for e, r in zip(examples, best["ranks"]) if r is None or r > 5
    ]
    if not misses:
        print("  none")
    for example, rank in misses:
        where = "not in top 10" if rank is None else f"rank {rank}"
        print(f"  [{where}] {example['question']}")


if __name__ == "__main__":
    examples = load_examples()

    print(f"ALL {len(examples)} QUESTIONS")
    results = compare(examples)
    print_table(results)

    for style in ("reworded", "exact", "answer"):
        subset = by_style(examples, style)
        print(f"\n{style.upper()} QUESTIONS ONLY ({len(subset)})")
        print_table(compare(subset))

    if "-v" in sys.argv:
        print_failures(examples, results)

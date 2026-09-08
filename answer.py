import math
import os
import sys

from dotenv import load_dotenv

from rerank import rerank
from search import search

load_dotenv()

MIN_CONFIDENCE = 0.5
CANDIDATES = 10
CONTEXT_SIZE = 5
MODEL = os.environ.get("ANSWER_MODEL", "gpt-4o-mini")
ABSTAIN = "INSUFFICIENT_EVIDENCE"

SYSTEM = """You draft responses to security questionnaires on behalf of a company.

You get a question and numbered extracts from that company's approved answers and policy
documents. Write the response using only what those extracts say.

Rules:
- Never mention a control, certification, tool or timeframe that is not in the extracts.
- If the extracts do not answer the question, reply with exactly: INSUFFICIENT_EVIDENCE
- Two to four sentences. Plain and factual, no marketing language.
- Start with a direct answer (Yes / No / a specific value) when the question asks for one.
- Cite the extracts you used as [1], [2] at the end of the sentence they support."""

USER = """Question: {question}

Extracts:
{context}

Response:"""


def confidence(results):
    if not results:
        return 0.0
    score = results[0].get("rerank_score")
    if score is None:
        return 0.0
    return round(1 / (1 + math.exp(-score)), 4)


def build_context(results):
    blocks = []
    for i, r in enumerate(results, start=1):
        if r["source"] == "answer_bank":
            blocks.append(f"[{i}] Previous question: {r['text']}\n    Previous answer: {r['answer']}")
        else:
            blocks.append(f"[{i}] Policy extract ({r['label']}):\n    {r['text']}")
    return "\n\n".join(blocks)


def citations(results):
    return [
        {"n": i, "source": r["source"], "id": r["id"], "label": r["label"]}
        for i, r in enumerate(results, start=1)
    ]


def retrieve(question):
    return rerank(question, search(question, limit=CANDIDATES), top_n=CONTEXT_SIZE)


def draft_extractive(question):
    """Return the closest stored text as-is. No model call, no cost."""
    results = retrieve(question)
    score = confidence(results)

    if not results or score < MIN_CONFIDENCE:
        return {"text": ABSTAIN, "confidence": score, "citations": citations(results),
                "model": "extractive", "abstained": True}

    best = results[0]
    text = best["answer"] if best["source"] == "answer_bank" else best["text"]
    return {"text": text, "confidence": score, "citations": citations(results[:1]),
            "model": "extractive", "abstained": False}


def draft_llm(question):
    from openai import OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; use --extractive")

    results = retrieve(question)
    score = confidence(results)

    if not results or score < MIN_CONFIDENCE:
        return {"text": ABSTAIN, "confidence": score, "citations": citations(results),
                "model": MODEL, "abstained": True}

    response = OpenAI().chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER.format(
                question=question, context=build_context(results))},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    return {"text": text, "confidence": score, "citations": citations(results),
            "model": MODEL, "abstained": ABSTAIN in text}


def draft(question, extractive=False):
    return draft_extractive(question) if extractive else draft_llm(question)


def show(result, question):
    flag = "NEEDS HUMAN" if result["abstained"] else "drafted"
    print(f'\n"{question}"\n')
    print(f"  {result['text']}\n")
    print(f"  confidence {result['confidence']:.3f}  |  {flag}  |  {result['model']}")
    for c in result["citations"]:
        print(f"    [{c['n']}] {c['source']:13} {str(c['label'])[:55]}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--extractive"]
    question = " ".join(args)
    show(draft(question, extractive="--extractive" in sys.argv), question)

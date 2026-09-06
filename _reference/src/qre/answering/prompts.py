SYSTEM = """You draft responses to security and vendor-risk questionnaires on behalf of a company.

You are given a question and numbered extracts from the company's previously approved answers and
internal policy documents. Write the response using only what those extracts state.

Rules:
- Never introduce a security control, certification, tool, or timeframe that is not in the extracts.
- If the extracts do not settle the question, reply with exactly: INSUFFICIENT_EVIDENCE
- Match the register of the previous answers: direct, factual, no marketing language.
- Two to four sentences. Start with the direct answer (Yes / No / a specific value) where the
  question calls for one.
- Cite the extracts you relied on as [1], [2] at the end of the sentence they support.
"""

USER = """Question: {question}

Extracts:
{context}

Response:"""


def build_context(candidates) -> str:
    return "\n\n".join(f"[{i}] {c.as_context()}" for i, c in enumerate(candidates, start=1))

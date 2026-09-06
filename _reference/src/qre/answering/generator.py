from dataclasses import dataclass

from openai import OpenAI

from qre.answering import prompts
from qre.config import get_settings
from qre.retrieval.pipeline import RetrievalResult
from qre.retrieval.types import Candidate

ABSTAIN = "INSUFFICIENT_EVIDENCE"

_client: OpenAI | None = None


@dataclass
class DraftAnswer:
    text: str
    confidence: float
    citations: list[Candidate]
    model: str
    abstained: bool

    @property
    def status(self) -> str:
        settings = get_settings()
        if self.abstained or self.confidence < settings.min_confidence:
            return "needs_review"
        return "generated"


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = get_settings().openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set; use extractive mode instead")
        _client = OpenAI(api_key=key)
    return _client


def _confidence(result: RetrievalResult) -> float:
    if not result.candidates:
        return 0.0
    top = result.candidates[0].score
    runner_up = result.candidates[1].score if len(result.candidates) > 1 else 0.0
    margin = max(0.0, top - runner_up)
    return round(min(1.0, 0.8 * top + 0.2 * margin), 4)


def draft_extractive(result: RetrievalResult) -> DraftAnswer:
    """Return the closest previously approved answer verbatim. No model call."""
    confidence = _confidence(result)
    prior = next((c for c in result.candidates if c.source == "answer_bank"), None)

    if prior is None or prior.answer_text is None:
        return DraftAnswer(ABSTAIN, confidence, result.candidates[:3], "extractive", True)

    return DraftAnswer(prior.answer_text, confidence, [prior], "extractive", False)


def draft(result: RetrievalResult, *, temperature: float = 0.0) -> DraftAnswer:
    settings = get_settings()
    confidence = _confidence(result)

    if not result.candidates:
        return DraftAnswer(ABSTAIN, 0.0, [], settings.answer_model, True)

    response = _get_client().chat.completions.create(
        model=settings.answer_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": prompts.SYSTEM},
            {
                "role": "user",
                "content": prompts.USER.format(
                    question=result.query,
                    context=prompts.build_context(result.candidates),
                ),
            },
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    abstained = ABSTAIN in text
    return DraftAnswer(text, confidence, result.candidates, settings.answer_model, abstained)

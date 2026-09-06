import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from qre.answering.generator import _get_client
from qre.config import DATA_DIR, get_settings
from qre.db.models import AnswerBankEntry, Company

EVAL_DIR = DATA_DIR / "eval"

PARAPHRASE_SYSTEM = """You rewrite security questionnaire questions.

Given a question, write one alternative that a different customer might send to ask for the same
information. Change the wording and sentence structure substantially. Keep the meaning identical.
Do not include the answer. Reply with the rewritten question only."""


@dataclass
class EvalExample:
    question: str
    expected_id: int | None
    original_question: str | None
    answerable: bool


def path_for(company_slug: str) -> Path:
    return EVAL_DIR / f"{company_slug}.jsonl"


def load(company_slug: str) -> list[EvalExample]:
    file = path_for(company_slug)
    if not file.exists():
        raise FileNotFoundError(f"no eval set at {file}; run `qre eval build` first")
    return [EvalExample(**json.loads(line)) for line in file.read_text().splitlines() if line]


def save(company_slug: str, examples: list[EvalExample]) -> Path:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    file = path_for(company_slug)
    file.write_text("\n".join(json.dumps(asdict(e)) for e in examples) + "\n")
    return file


def _paraphrase(question: str) -> str:
    response = _get_client().chat.completions.create(
        model=get_settings().answer_model,
        temperature=0.7,
        messages=[
            {"role": "system", "content": PARAPHRASE_SYSTEM},
            {"role": "user", "content": question},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def build(
    session: Session,
    company_slug: str,
    *,
    size: int = 50,
    negatives: list[str] | None = None,
    seed: int = 7,
) -> list[EvalExample]:
    """Sample answered questions and reword them, so retrieval is tested on unseen phrasing."""
    company_id = session.scalar(select(Company.id).where(Company.slug == company_slug))
    if company_id is None:
        raise ValueError(f"unknown company: {company_slug}")

    rows = session.scalars(
        select(AnswerBankEntry).where(AnswerBankEntry.company_id == company_id)
    ).all()
    if not rows:
        raise ValueError(f"answer bank is empty for {company_slug}")

    random.Random(seed).shuffle(list(rows))
    sample = list(rows)[:size]

    examples = [
        EvalExample(
            question=_paraphrase(row.question_text),
            expected_id=row.id,
            original_question=row.question_text,
            answerable=True,
        )
        for row in sample
    ]

    for text in negatives or []:
        examples.append(
            EvalExample(question=text, expected_id=None, original_question=None, answerable=False)
        )

    return examples

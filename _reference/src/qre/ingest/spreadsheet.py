import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MAX_HEADER_SCAN = 40

QUESTION_HINTS = ("question", "assessment question", "control specification", "requirement")
ANSWER_HINTS = ("answer", "response", "sp response", "vendor response")
DETAIL_HINTS = ("implementation description", "additional information", "notes", "comments")
CONTROL_HINTS = ("question id", "control id", "cgid", "ccm", "control identifier")

SKIP_QUESTION_VALUES = {"question", "n/a", "na", "-", ""}


@dataclass
class QARow:
    row_ref: str
    control_id: str | None
    question: str
    answer: str | None


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _match(
    columns: list[str], hints: tuple[str, ...], exclude: set[int] | None = None
) -> int | None:
    exclude = exclude or set()
    for idx, col in enumerate(columns):
        if idx not in exclude and any(hint in col for hint in hints):
            return idx
    return None


def find_header_row(frame: pd.DataFrame) -> int | None:
    for i in range(min(MAX_HEADER_SCAN, len(frame))):
        cells = [_norm(c) for c in frame.iloc[i].tolist()]
        control = _match(cells, CONTROL_HINTS)
        exclude = {control} if control is not None else set()
        if _match(cells, QUESTION_HINTS, exclude=exclude) is not None:
            return i
    return None


def _read_raw(path: Path, sheet: str | int | None) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    return pd.read_excel(
        path, sheet_name=sheet if sheet is not None else 0, header=None, dtype=str
    ).fillna("")


def parse(path: Path, *, sheet: str | int | None = None) -> list[QARow]:
    raw = _read_raw(path, sheet)
    header_idx = find_header_row(raw)
    if header_idx is None:
        raise ValueError(f"no question column found in {path.name}")

    columns = [_norm(c) for c in raw.iloc[header_idx].tolist()]
    # Control columns are matched first so that headers like "Question ID"
    # are not mistaken for the question itself.
    c_col = _match(columns, CONTROL_HINTS)
    taken = {c_col} if c_col is not None else set()
    q_col = _match(columns, QUESTION_HINTS, exclude=taken)
    if q_col is None:
        raise ValueError(f"no question column found in {path.name}")
    taken.add(q_col)
    a_col = _match(columns, ANSWER_HINTS, exclude=taken)
    if a_col is not None:
        taken.add(a_col)
    d_col = _match(columns, DETAIL_HINTS, exclude=taken)

    rows: list[QARow] = []
    body = raw.iloc[header_idx + 1 :]

    for offset, (_, row) in enumerate(body.iterrows(), start=header_idx + 2):
        question = str(row.iloc[q_col]).strip()
        if _norm(question) in SKIP_QUESTION_VALUES or len(question) < 15:
            continue

        parts = []
        if a_col is not None and str(row.iloc[a_col]).strip():
            parts.append(str(row.iloc[a_col]).strip())
        if d_col is not None and str(row.iloc[d_col]).strip():
            parts.append(str(row.iloc[d_col]).strip())

        control = str(row.iloc[c_col]).strip() if c_col is not None else ""
        rows.append(
            QARow(
                row_ref=f"row{offset}",
                control_id=control or None,
                question=question,
                answer="\n\n".join(parts) or None,
            )
        )

    return rows

import sys
from pathlib import Path

import pandas as pd

ID_WORDS = ("question id", "control id", "ccm", "cgid")
QUESTION_WORDS = ("question", "control specification", "requirement")
ANSWER_WORDS = ("answer", "response")
DETAIL_WORDS = ("implementation description", "additional information", "notes")

MAX_HEADER_SCAN = 40
MIN_QUESTION_LENGTH = 15


def clean(value):
    return " ".join(str(value).split()).lower()


def read_file(path):
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    return pd.read_excel(path, header=None, dtype=str).fillna("")


def find_column(headers, words, skip=()):
    for i, header in enumerate(headers):
        if i not in skip and any(word in header for word in words):
            return i
    return None


def find_header_row(table):
    for i in range(min(MAX_HEADER_SCAN, len(table))):
        headers = [clean(cell) for cell in table.iloc[i]]
        id_col = find_column(headers, ID_WORDS)
        skip = {id_col} if id_col is not None else set()
        if find_column(headers, QUESTION_WORDS, skip) is not None:
            return i
    return None


def find_columns(headers):
    # The id column is matched first, otherwise a header called "Question ID"
    # gets picked as the question itself.
    id_col = find_column(headers, ID_WORDS)
    used = {id_col} if id_col is not None else set()

    question_col = find_column(headers, QUESTION_WORDS, used)
    used.add(question_col)

    answer_col = find_column(headers, ANSWER_WORDS, used)
    if answer_col is not None:
        used.add(answer_col)

    detail_col = find_column(headers, DETAIL_WORDS, used)
    return id_col, question_col, answer_col, detail_col


def read_questionnaire(path):
    table = read_file(path)

    header_row = find_header_row(table)
    if header_row is None:
        raise ValueError(f"could not find a question column in {path.name}")

    headers = [clean(cell) for cell in table.iloc[header_row]]
    id_col, question_col, answer_col, detail_col = find_columns(headers)

    rows = []
    for _, row in table.iloc[header_row + 1 :].iterrows():
        question = str(row.iloc[question_col]).strip()
        if len(question) < MIN_QUESTION_LENGTH:
            continue

        parts = []
        for col in (answer_col, detail_col):
            if col is not None and str(row.iloc[col]).strip():
                parts.append(str(row.iloc[col]).strip())

        rows.append({
            "control_id": str(row.iloc[id_col]).strip() if id_col is not None else "",
            "question": question,
            "answer": "\n\n".join(parts),
            "source_file": path.name,
        })

    return rows


if __name__ == "__main__":
    path = Path(sys.argv[1])
    rows = read_questionnaire(path)

    print(f"{path.name}: found {len(rows)} rows\n")
    for row in rows[:3]:
        print(f"  control_id : {row['control_id']}")
        print(f"  question   : {row['question'][:70]}")
        print(f"  answer     : {row['answer'][:70]}")
        print()

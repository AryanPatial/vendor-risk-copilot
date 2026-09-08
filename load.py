import sys
from pathlib import Path

import pandas as pd

ID_WORDS = ("question id", "control id", "ccm", "cgid")
QUESTION_WORDS = ("question", "control specification", "requirement")
ANSWER_WORDS = ("answer", "response")
DETAIL_WORDS = ("implementation description", "additional information", "notes")

MAX_HEADER_SCAN = 40
MIN_QUESTION_LENGTH = 15
MAX_HEADER_LENGTH = 60
MIN_HEADER_MATCHES = 2


def clean(value):
    return " ".join(str(value).split()).lower()


def read_file(path, sheet=None):
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, header=None, dtype=str, keep_default_na=False)

    def read_sheet(name):
        return pd.read_excel(path, sheet_name=name, header=None, dtype=str).fillna("")

    if sheet is not None:
        return read_sheet(sheet)

    # Real questionnaires ship with cover sheets and instructions. Take the first
    # sheet that actually has a question column in it.
    names = pd.ExcelFile(path).sheet_names
    for name in names:
        table = read_sheet(name)
        if find_header_row(table) is not None:
            return table
    return read_sheet(names[0])


def find_column(headers, words, skip=()):
    for i, header in enumerate(headers):
        if i in skip or len(header) > MAX_HEADER_LENGTH:
            continue
        if any(word in header for word in words):
            return i
    return None


def find_header_row(table):
    """A title row can contain the word "questionnaire". A real header row has
    several recognisable columns, so require more than one match."""
    for i in range(min(MAX_HEADER_SCAN, len(table))):
        headers = [clean(cell) for cell in table.iloc[i]]
        id_col, question_col, answer_col, detail_col = find_columns(headers)
        if question_col is None:
            continue
        matches = sum(c is not None for c in (id_col, question_col, answer_col, detail_col))
        if matches >= MIN_HEADER_MATCHES:
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


def read_questionnaire(path, sheet=None):
    table = read_file(path, sheet=sheet)

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

import sys
import time
from pathlib import Path

import db
from chunk import chunk_directory
from embed import embed_texts
from load import read_questionnaire


def replace_rows(conn, table, source_file):
    conn.execute(f"DELETE FROM {table} WHERE source_file = %s", (source_file,))


def index_answers(path):
    rows = read_questionnaire(path)
    if not rows:
        print(f"  {path.name}: nothing to index")
        return 0

    # Embed the question AND the answer. Embedding the question alone loses every fact that
    # only appears in the answer text - "we hold ISO 27001" sits under a question about audit
    # policy. Measured: +0.223 MRR on answer-based questions, -0.015 on reworded ones.
    vectors = embed_texts([f'{row["question"]} {row["answer"]}' for row in rows])

    with db.connect() as conn:
        replace_rows(conn, "answer_bank", path.name)
        conn.cursor().executemany(
            """INSERT INTO answer_bank
                   (control_id, question_text, answer_text, source_file, embedding)
               VALUES (%s, %s, %s, %s, %s)""",
            [
                (r["control_id"], r["question"], r["answer"], r["source_file"], v)
                for r, v in zip(rows, vectors)
            ],
        )
    return len(rows)


def index_policies(directory):
    chunks = chunk_directory(directory)
    if not chunks:
        print(f"  {directory}: nothing to index")
        return 0

    vectors = embed_texts([c["content"] for c in chunks])

    with db.connect() as conn:
        for source_file in {c["source_file"] for c in chunks}:
            replace_rows(conn, "policy_chunks", source_file)
        conn.cursor().executemany(
            """INSERT INTO policy_chunks
                   (heading, content, ordinal, source_file, embedding)
               VALUES (%s, %s, %s, %s, %s)""",
            [
                (c["heading"], c["content"], c["ordinal"], c["source_file"], v)
                for c, v in zip(chunks, vectors)
            ],
        )
    return len(chunks)


def counts():
    with db.connect() as conn:
        answers = conn.execute("SELECT count(*) FROM answer_bank").fetchone()[0]
        policies = conn.execute("SELECT count(*) FROM policy_chunks").fetchone()[0]
    return answers, policies


if __name__ == "__main__":
    started = time.perf_counter()

    for target in sys.argv[1:]:
        path = Path(target)
        print(f"indexing {path}...")
        if path.is_dir():
            print(f"  {index_policies(path)} policy chunks")
        else:
            print(f"  {index_answers(path)} answers")

    answers, policies = counts()
    print(f"\ndatabase now holds {answers} answers and {policies} policy chunks")
    print(f"took {time.perf_counter() - started:.1f}s")

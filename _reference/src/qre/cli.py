from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from qre.db.engine import session_scope
from qre.db.migrate import run_migrations

app = typer.Typer(no_args_is_help=True, add_completion=False)
db_app = typer.Typer(no_args_is_help=True)
ingest_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)

app.add_typer(db_app, name="db")
app.add_typer(ingest_app, name="ingest")
app.add_typer(eval_app, name="eval")

console = Console()


@db_app.command("migrate")
def db_migrate() -> None:
    applied = run_migrations()
    console.print(f"applied {len(applied)} migration(s): {', '.join(applied) or 'none'}")


@ingest_app.command("answers")
def ingest_answers(
    path: Path,
    company: str = typer.Option(..., "--company", "-c"),
    sheet: str | None = typer.Option(None, "--sheet"),
    replace: bool = typer.Option(False, "--replace"),
) -> None:
    from qre.ingest.loader import ingest_answer_bank

    with session_scope() as session:
        document, count = ingest_answer_bank(session, path, company, sheet=sheet, replace=replace)
        console.print(f"{document.title}: {count} answer(s) indexed")


@ingest_app.command("policies")
def ingest_policies(
    directory: Path,
    company: str = typer.Option(..., "--company", "-c"),
    replace: bool = typer.Option(False, "--replace"),
) -> None:
    from qre.ingest.loader import ingest_policy_dir

    with session_scope() as session:
        results = ingest_policy_dir(session, directory, company, replace=replace)
        for name, count in results.items():
            console.print(f"{name}: {count} chunk(s)")


@app.command("ask")
def ask(
    question: str,
    company: str = typer.Option(..., "--company", "-c"),
    extractive: bool = typer.Option(
        False, "--extractive", help="Skip the LLM, reuse a past answer"
    ),
) -> None:
    from qre.answering.service import answer_question

    with session_scope() as session:
        answer, candidates = answer_question(session, question, company, extractive=extractive)

    console.print(f"\n[bold]{answer.text}[/bold]\n")
    console.print(f"confidence {answer.confidence:.2f}   status {answer.status}\n")

    table = Table("#", "source", "score", "reference")
    for i, c in enumerate(candidates, start=1):
        table.add_row(str(i), c.source, f"{c.score:.3f}", c.control_id or c.document_title)
    console.print(table)


@app.command("run")
def run_questionnaire(
    path: Path,
    company: str = typer.Option(..., "--company", "-c"),
    sheet: str | None = typer.Option(None, "--sheet"),
    extractive: bool = typer.Option(False, "--extractive"),
) -> None:
    from qre.answering.service import load_questionnaire, process_questionnaire

    with session_scope() as session:
        questionnaire = load_questionnaire(session, path, company, sheet=sheet)
        total = len(questionnaire.questions)
        console.print(f"loaded {total} question(s) from {path.name}")

        with console.status("drafting...") as status:
            seen = 0

            def tick(question, answer):
                nonlocal seen
                seen += 1
                status.update(f"drafting {seen}/{total} — {question.text[:60]}")

            counts = process_questionnaire(
                session, questionnaire.id, extractive=extractive, progress=tick
            )

    console.print(f"questionnaire #{questionnaire.id}: {counts}")


@eval_app.command("build")
def eval_build(
    company: str = typer.Option(..., "--company", "-c"),
    size: int = typer.Option(50, "--size", "-n"),
) -> None:
    from qre.evaluation.dataset import build, save

    negatives = [
        "What is your company's policy on remote working from overseas?",
        "How many parking spaces are available at your head office?",
        "Which payroll provider do you use for contractors in Germany?",
    ]

    with session_scope() as session:
        examples = build(session, company, size=size, negatives=negatives)
    path = save(company, examples)
    console.print(f"wrote {len(examples)} example(s) to {path}")


@eval_app.command("run")
def eval_run(company: str = typer.Option(..., "--company", "-c")) -> None:
    from qre.evaluation.dataset import load
    from qre.evaluation.metrics import TABLE_HEADER
    from qre.evaluation.run import compare

    examples = load(company)
    with session_scope() as session:
        reports = compare(session, company, examples)

    console.print()
    print(TABLE_HEADER)
    for report in reports:
        print(report.as_row())


if __name__ == "__main__":
    app()

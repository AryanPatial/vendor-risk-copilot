from pathlib import Path

from sqlalchemy import text

from qre.db.engine import get_engine

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def pending(applied: set[str]) -> list[Path]:
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.stem not in applied]


def run_migrations() -> list[str]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(_TRACKING_TABLE))
        applied = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}

    done = []
    for path in pending(applied):
        with engine.begin() as conn:
            conn.execute(text(path.read_text()))
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                {"v": path.stem},
            )
        done.append(path.stem)
    return done

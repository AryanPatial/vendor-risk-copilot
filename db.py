import os
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

DB_URL = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/rag")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect():
    conn = psycopg.connect(DB_URL, autocommit=True)
    register_vector(conn)
    return conn

# reading the schema.sql file and executing it to create tables in the database
def create_tables():
    sql = SCHEMA_PATH.read_text()
    with connect() as conn:
        conn.execute(sql)

# showing the tables in the database along with the number of columns in each table
def show_tables():
    with connect() as conn:
        rows = conn.execute("""
            SELECT table_name, count(*) AS columns
            FROM information_schema.columns
            WHERE table_schema = 'public'
            GROUP BY table_name
            ORDER BY table_name
        """).fetchall()
    for name, columns in rows:
        print(f"  {name}  ({columns} columns)")


if __name__ == "__main__":
    create_tables()
    print("tables created:")
    show_tables()

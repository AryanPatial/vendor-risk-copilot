# Questionnaire Response Engine

Drafts answers to security and vendor-risk questionnaires (CAIQ, HECVAT, custom vendor
assessments) from a company's own previously approved answers and policy documents.

A large customer sends a 250-question security questionnaire. Most of those questions have already
been answered before, worded differently, in a spreadsheet nobody can find. This service finds the
prior answer, drafts a response, cites where it came from, and flags the ones a human has to write.

## What it does

- Ingests completed questionnaires into an **answer bank** and policy documents into **chunks**
- Retrieves with **hybrid search**: dense vectors and Postgres full-text, fused with reciprocal
  rank fusion, then reordered by a cross-encoder
- Drafts an answer grounded only in retrieved extracts, with citations
- **Abstains** when the evidence is thin, instead of inventing a control that does not exist
- Scores confidence per answer so a reviewer can work through the flagged ones first
- Ships an **evaluation harness** that compares retrieval configurations on held-out questions

## Why abstention matters here

A wrong answer on a security questionnaire is a contractual statement about controls the company
may not have. Saying "a human needs to write this one" is the correct output for anything the
corpus does not clearly support, and the system is measured on getting that call right.

## Architecture

```
spreadsheet / markdown
        │
        ▼
   ingest ──► embed ──► Postgres + pgvector
                          │  answer_bank   (past Q&A, embedded on the question)
                          │  policy_chunks (heading-aware markdown chunks)
                          ▼
   query ──► hybrid search ──► RRF ──► cross-encoder rerank
                                              │
                                              ▼
                                    draft + citations + confidence
                                              │
                                     ┌────────┴────────┐
                                     ▼                 ▼
                              auto-drafted      needs human review
```

Retrieval runs entirely on the machine. The only external call is the final wording step, and
`--extractive` skips even that by returning the closest approved answer verbatim.

## Layout

```
src/qre/
  config.py           settings from .env
  db/                 engine, ORM models, SQL migrations
  ingest/             spreadsheet parser, markdown chunking, loaders
  retrieval/          embedder, hybrid search, reranker, pipeline
  answering/          prompts, generator, questionnaire service
  evaluation/         eval set builder, metrics, baseline comparison
  api/                FastAPI app
  cli.py              typer CLI
ui/app.py             Streamlit review screen
tests/                unit tests + integration tests behind --run-db
```

Migrations are plain numbered SQL files applied by `src/qre/db/migrate.py`. The schema uses
generated `tsvector` columns and HNSW indexes, which are easier to read as SQL than as ORM
declarations.

## Setup

Requires Python 3.11+, Postgres 17 and pgvector.

```bash
make install
make db
make migrate
cp .env.example .env      # then put your OpenAI key in .env
```

Postgres lives outside the default PATH on Homebrew. Add this to `~/.zshrc`:

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
```

## Use

```bash
qre ingest answers data/raw/vendor_caiq.xlsx --company acme
qre ingest policies data/raw/policies --company acme

qre ask "Do you encrypt customer data at rest?" --company acme
qre ask "Do you encrypt customer data at rest?" --company acme --extractive   # no LLM call

qre run data/raw/incoming_hecvat.xlsx --company acme

make api    # http://127.0.0.1:8000/docs
make ui     # http://localhost:8501
```

## Evaluation

The eval set is built by **rewording** questions that are already in the answer bank, then checking
whether retrieval still finds the original entry. That measures the actual problem: the same
question arrives phrased differently every time. Unanswerable questions are added as negatives to
measure abstention.

```bash
qre eval build --company acme --size 50
qre eval run --company acme
```

| Configuration | N | R@1 | R@5 | R@10 | MRR | Abstain acc. |
|---|---|---|---|---|---|---|
| Dense only (naive RAG) | — | — | — | — | — | — |
| Lexical only (BM25-style) | — | — | — | — | — | — |
| Hybrid (RRF) | — | — | — | — | — | — |
| Hybrid + cross-encoder rerank | — | — | — | — | — | — |

Numbers are filled in once a real corpus is ingested — see [docs/data-sources.md](docs/data-sources.md).

## Development

```bash
make test        # unit tests only
make test-all    # includes Postgres integration tests
make lint
```

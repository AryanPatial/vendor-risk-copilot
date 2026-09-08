# Security Questionnaire Response Engine

Drafts answers to security questionnaires from a company's past answers and its policy documents.

## The problem

When a big company buys software from a smaller one, it sends a security questionnaire first.
Usually a spreadsheet with 150-300 questions. Things like "do you encrypt data at rest" and
"how often do you run penetration tests".

Someone at the smaller company then spends two or three weeks answering it by hand. Most of
those questions have already been answered before, for a different customer, in a spreadsheet
nobody can find any more. So the work is mostly hunting, not writing.

This project does the hunting. You give it the old questionnaires and the company's policy
documents, and it drafts an answer for each new question with a link back to where the answer
came from. When it isn't confident, it says so instead of guessing.

## How it works

Two phases that run at different times.

**Phase A - loading.** Runs once, takes a few minutes. Past questionnaires and policy documents
get read, cut into pieces, turned into vectors, and stored in Postgres.

**Phase B - answering.** Runs per question, takes milliseconds. The question is turned into a
vector with the same model, the closest pieces are pulled out of Postgres, and those go to an
LLM as context. The LLM only sees the few pieces that were retrieved, never the whole database.

```
Phase A:   spreadsheet ─┐
                        ├─► chunk ─► embed ─► Postgres
           policy .md  ─┘

Phase B:   question ─► embed ─► search Postgres ─► rerank ─► LLM ─► draft + citations

Serving:   Streamlit ──HTTP──► FastAPI ──► the pipeline above
```

## Two tables, not one

`answer_bank` holds past question-and-answer pairs. You search the question column and return
the answer column - two different fields.

`policy_chunks` holds pieces of policy documents. You search the content and return that same
content - one field.

That asymmetry is why they aren't one table with a `kind` column. Also: Q&A pairs don't get
chunked because they're already short. Policy documents do, because 22 of the 27 are longer
than the embedding model can read in one go.

## Why Postgres and not a vector database

Honestly, at this size it's overkill. Brute-force search over 100,000 vectors in numpy takes
6ms, so speed isn't the reason.

The reason is that Postgres gives you keyword search (`tsvector`) and vector search (`pgvector`)
on the same row. Hybrid retrieval needs both, and a dedicated vector database would only give
you half.

## Does any of it work

30 test questions written against the policy corpus, held in `data/eval/policies.jsonl`.
20 are reworded questions, 10 are exact-string lookups like a control ID or "7 years".
Scored on MRR, higher is better. Corpus: 261 real CAIQ answers plus 130 policy chunks.

| Question type | Semantic | Keyword | Hybrid | Hybrid + rerank |
|---|---|---|---|---|
| Reworded (20) | 0.759 | 0.100 | 0.759 | **0.789** |
| Exact strings (10) | 0.800 | **1.000** | 0.950 | 0.883 |
| Answer-based (8) | 0.365 | 0.042 | 0.369 | **0.390** |
| All 38 | 0.687 | 0.325 | 0.727 | **0.730** |

The three question types are different jobs. Reworded questions are asked in different words
from the stored text. Exact-string questions are lookups like a control ID. Answer-based
questions are ones where the fact lives in a past answer rather than in its question - "are you
ISO 27001 certified" is answered by a row whose question is about audit policy review.

Answer-based questions are the weakest slice at 0.390 and the most realistic thing a customer
sends. That is the obvious place to work next.

No configuration wins everywhere. Keyword search alone is perfect on exact strings and nearly
useless on reworded questions. The reranker is the reverse - it adds 0.194 on reworded questions
and loses 0.067 on exact ones, because a cross-encoder reads a control ID and finds no meaning
in it either, so it demotes a result keyword search had correctly ranked first.

Corpus size changed the conclusions. With a 5-row placeholder answer bank the same tests scored
semantic 0.817, hybrid 0.850, hybrid+rerank 0.861 - the reranker looked like noise and hybrid
looked marginal. Swapping in 261 real answers dropped every score and widened every gap:

| | 5 placeholder answers | 261 real answers |
|---|---|---|
| hybrid over semantic | +0.033 | +0.071 |
| reranker over hybrid | +0.011 | +0.081 |

A small corpus makes every technique look the same. That is worth knowing before deciding
anything on a toy dataset.

Reranker model choice mattered too. bge-reranker-base scored below no reranker at all;
ms-marco-MiniLM-L-6-v2 on identical candidates was the best configuration.

The answer bank embeds the question and the answer together. Embedding the question alone -
which is what I built first, on the reasoning that an incoming question matches a stored
question - was measurably wrong:

| question type | question only | question + answer |
|---|---|---|
| reworded | 0.804 | 0.789 |
| exact strings | 0.883 | 0.883 |
| answer-based | 0.167 | **0.390** |
| all 38 | 0.691 | **0.730** |

Losing 0.015 on reworded questions to gain 0.223 on answer-based ones.

Run it with `python evaluate.py -v`.

## What's built

| File | Does |
|---|---|
| `schema.sql` | the two tables |
| `db.py` | connects Python to Postgres |
| `load.py` | reads CAIQ/HECVAT spreadsheets, finds the header row and the right columns |
| `chunk.py` | cuts policy markdown into pieces, heading-aware, 1500 char cap |
| `embed.py` | text to 384 numbers, using bge-small-en-v1.5 |
| `index.py` | runs all of the above and writes to Postgres |
| `search.py` | hybrid retrieval - vector and keyword, fused with RRF |
| `evaluate.py` | scores the four retrieval configurations |
| `rerank.py` | cross-encoder reordering of the top 10 |
| `answer.py` | drafts the response, cites sources, refuses when evidence is thin |
| `api.py` | FastAPI service - /ask, /questionnaire, /health |
| `app.py` | Streamlit screen, talks to the API over HTTP |

Currently in the database: 261 real CAIQ answers and 130 policy chunks from 25 files.

## Refusing to answer

A wrong answer on a security questionnaire is a contractual claim about controls the company
may not have. So the system scores its own evidence and refuses below a threshold.

The confidence score is the sigmoid of the reranker's top logit. That model outputs about +3.5
for a good match and -11 for a bad one, which separates cleanly:

| Question | Confidence | Result |
|---|---|---|
| How quickly must I report an incident? | 1.000 | drafted |
| Are you ISO 27001 certified? | 0.000 | refused |
| Do you hold a SOC 2 Type II report? | 0.000 | refused |
| How many parking spaces at head office? | 0.000 | refused |
| Do you encrypt database backups? | 0.607 | drafted |

The certification questions are the ones worth noticing. The corpus is full of security policies,
so a system without a refusal rule would happily claim a certification the company does not hold.

The 0.5 threshold is currently a guess. Tuning it needs a labelled set of should-answer and
should-refuse questions, which does not exist yet.

## Not built yet

- a labelled set for tuning the refusal threshold
- the LLM path in `answer.py` is written but untested, since no API key is configured

## Known gaps

The 30 evaluation questions were written by hand, by me, after reading the chunks they point
at. That is better than testing on queries picked at random but it is still self-authored, and
30 is a small number. Questions written by someone who has not seen the corpus would be a
fairer test.

Ingestion only handles markdown. Real policy documents are PDFs and Word files, often scanned.
That's the messiest part of real RAG work and this project skips it for now. The chunking
functions take strings rather than files, so swapping the reader is the only change needed.

Table handling is weak. Markdown tables get their borders stripped and the cell text kept,
which reads awkwardly.

## Data

Answer bank: 2C2P's CAIQ v4.0.2 self-assessment, published on the CSA STAR Registry. 261 real
question-and-answer pairs from a real payments company. Public data.

Policy documents: SOC 2 templates from [strongdm/comply](https://github.com/strongdm/comply),
Apache 2.0. Generic templates, not 2C2P's actual policies, so the two halves of the corpus come
from different places and are paired here for testing.

Nothing here is confidential and none of it came from an employer.

## Setup

Needs Python 3.11+, Postgres 17, pgvector.

```bash
brew install postgresql@17 pgvector
brew services start postgresql@17
createdb rag

python3 -m venv .venv
.venv/bin/pip install psycopg[binary] pgvector sentence-transformers pandas openpyxl

export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
.venv/bin/python db.py
.venv/bin/python index.py data/raw/sample_caiq.csv data/raw/policies
```

Then check it worked:

```bash
psql -d rag -c "SELECT count(*) FROM answer_bank;"
psql -d rag -c "SELECT count(*) FROM policy_chunks;"
```

Then use it:

```bash
.venv/bin/python answer.py --extractive "How quickly must I report an incident?"
.venv/bin/python evaluate.py
```

The web version is two processes. API first, then the screen:

```bash
.venv/bin/uvicorn api:app --port 8000      # http://localhost:8000/docs
.venv/bin/streamlit run app.py             # http://localhost:8501
```

The Streamlit screen has no logic of its own - it calls the API over HTTP, same as any other
client would. That means the engine is usable from a Slack bot or an internal portal without
touching this code.

## Notes

`_reference/` is an earlier version of this project with a full src/ package layout, an
evaluation harness and a FastAPI app. It works, but I rebuilt it flat to understand each piece
properly. Ignore it, or read it if you want to see where this is heading.

Running `python db.py` drops and recreates both tables. Fine while the schema is still moving,
not fine once there's data worth keeping. Use `ALTER TABLE` after that point.

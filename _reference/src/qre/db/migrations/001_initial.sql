CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE companies (
    id          bigserial PRIMARY KEY,
    slug        text NOT NULL UNIQUE,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE document_kind AS ENUM ('completed_questionnaire', 'policy', 'whitepaper');

CREATE TABLE documents (
    id          bigserial PRIMARY KEY,
    company_id  bigint NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    kind        document_kind NOT NULL,
    title       text NOT NULL,
    source_uri  text,
    checksum    text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, checksum)
);

-- Past question/answer pairs lifted out of completed questionnaires.
-- The embedding is over the question, because that is what an incoming question matches against.
CREATE TABLE answer_bank (
    id            bigserial PRIMARY KEY,
    company_id    bigint NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_id   bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    control_id    text,
    question_text text NOT NULL,
    answer_text   text NOT NULL,
    answered_on   date,
    embedding     vector(384),
    tsv           tsvector GENERATED ALWAYS AS (
                      to_tsvector('english', question_text || ' ' || answer_text)
                  ) STORED
);

CREATE TABLE policy_chunks (
    id          bigserial PRIMARY KEY,
    company_id  bigint NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_id bigint NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    heading     text,
    content     text NOT NULL,
    ordinal     int NOT NULL,
    embedding   vector(384),
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE TYPE questionnaire_status AS ENUM ('uploaded', 'drafting', 'ready', 'failed');

CREATE TABLE questionnaires (
    id           bigserial PRIMARY KEY,
    company_id   bigint NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name         text NOT NULL,
    format       text NOT NULL,
    status       questionnaire_status NOT NULL DEFAULT 'uploaded',
    uploaded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id               bigserial PRIMARY KEY,
    questionnaire_id bigint NOT NULL REFERENCES questionnaires(id) ON DELETE CASCADE,
    row_ref          text NOT NULL,
    control_id       text,
    text             text NOT NULL,
    ordinal          int NOT NULL,
    UNIQUE (questionnaire_id, row_ref)
);

CREATE TYPE draft_status AS ENUM ('generated', 'needs_review', 'approved', 'rejected');

CREATE TABLE drafts (
    id            bigserial PRIMARY KEY,
    question_id   bigint NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    answer_text   text NOT NULL,
    confidence    real NOT NULL,
    status        draft_status NOT NULL,
    model         text,
    edited_text   text,
    generated_at  timestamptz NOT NULL DEFAULT now(),
    reviewed_at   timestamptz,
    UNIQUE (question_id)
);

CREATE TYPE citation_source AS ENUM ('answer_bank', 'policy_chunk');

CREATE TABLE citations (
    id          bigserial PRIMARY KEY,
    draft_id    bigint NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    source      citation_source NOT NULL,
    source_id   bigint NOT NULL,
    rank        int NOT NULL,
    score       real NOT NULL
);

CREATE INDEX answer_bank_company_idx ON answer_bank (company_id);
CREATE INDEX answer_bank_tsv_idx ON answer_bank USING gin (tsv);
CREATE INDEX answer_bank_embedding_idx ON answer_bank
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX policy_chunks_company_idx ON policy_chunks (company_id);
CREATE INDEX policy_chunks_tsv_idx ON policy_chunks USING gin (tsv);
CREATE INDEX policy_chunks_embedding_idx ON policy_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX questions_questionnaire_idx ON questions (questionnaire_id, ordinal);
CREATE INDEX citations_draft_idx ON citations (draft_id, rank);

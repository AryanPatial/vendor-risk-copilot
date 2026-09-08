CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS answer_bank;
DROP TABLE IF EXISTS policy_chunks;

-- Past questions and the answers we gave. We search question_text, we return answer_text.
CREATE TABLE answer_bank (
    id            serial PRIMARY KEY,
    control_id    text,
    question_text text NOT NULL,
    answer_text   text NOT NULL,
    source_file   text NOT NULL,
    embedding     vector(384),
    tsv           tsvector GENERATED ALWAYS AS (
                      to_tsvector('english',
                          coalesce(control_id, '') || ' ' || question_text || ' ' || answer_text)
                  ) STORED
);

-- Pieces of policy documents. We search content and we return that same content.
CREATE TABLE policy_chunks (
    id          serial PRIMARY KEY,
    heading     text,
    content     text NOT NULL,
    ordinal     int NOT NULL DEFAULT 0,
    source_file text NOT NULL,
    embedding   vector(384),
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX answer_bank_tsv_idx  ON answer_bank  USING gin (tsv);
CREATE INDEX policy_chunks_tsv_idx ON policy_chunks USING gin (tsv);

CREATE INDEX answer_bank_embedding_idx  ON answer_bank
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX policy_chunks_embedding_idx ON policy_chunks
    USING hnsw (embedding vector_cosine_ops);

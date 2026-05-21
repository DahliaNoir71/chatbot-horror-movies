-- =============================================================================
-- HORRORBOT VECTORS - Popularity floor on RAG retrieval
-- =============================================================================
-- The RAG corpus holds ~63k films, but roughly 87% are obscure zero-vote
-- shorts. Pure cosine similarity has no notion of notoriety, so famous films
-- end up ranked in the thousands behind obscure films whose overviews match
-- the query wording more literally — vector retrieval becomes unusable.
--
-- Fix: carry TMDB `vote_count` on `rag_documents` and let
-- `search_similar_documents` discard films below a popularity floor
-- (`min_vote_count`, default 100 — every benchmarked film clears 200 votes).
-- That restricts retrieval to ~3.3k notable films.
--
-- `vote_count` lives in the `horrorbot.films` table (a separate database);
-- it is copied here by `scripts/migrations/backfill_rag_vote_count.py`, which
-- must be run once after this script (and after any ETL load).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS, and a
-- drop-then-recreate of the function (its arity changes). Safe to rerun.
-- =============================================================================

\connect horrorbot_vectors

-- -----------------------------------------------------------------------------
-- 1. vote_count column + btree index
-- -----------------------------------------------------------------------------
-- DEFAULT 0 means freshly loaded rows are treated as obscure until the
-- backfill script copies the real value — retrieval then returns nothing,
-- which is the safe failure mode (no obscure noise) rather than silent junk.

ALTER TABLE rag_documents
    ADD COLUMN IF NOT EXISTS vote_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_rag_documents_vote_count
    ON rag_documents (vote_count);

-- -----------------------------------------------------------------------------
-- 2. Drop the HNSW index — superseded
-- -----------------------------------------------------------------------------
-- Retrieval now filters to ~3.3k notable films at query time. Over a set
-- that small an exact cosine scan is both fast and perfectly accurate, and
-- it sidesteps the approximate-index pitfall where pgvector post-filters an
-- HNSW scan and returns fewer than `match_count` rows.

DROP INDEX IF EXISTS idx_rag_documents_embedding;

-- -----------------------------------------------------------------------------
-- 3. Redefine search_similar_documents with the popularity floor
-- -----------------------------------------------------------------------------
-- The arity changes (new 5th parameter), so CREATE OR REPLACE cannot act on
-- the old 4-argument signature — it is dropped explicitly first. The new
-- `min_vote_count` parameter defaults to 100, so existing 4-argument callers
-- (e.g. DocumentRetriever) get the popularity filter without code changes.

DROP FUNCTION IF EXISTS search_similar_documents(vector, integer, numeric, varchar);

CREATE OR REPLACE FUNCTION search_similar_documents(
    query_embedding vector(384),
    match_count INTEGER DEFAULT 20,
    similarity_threshold NUMERIC DEFAULT 0.3,
    filter_source_type VARCHAR DEFAULT NULL,
    min_vote_count INTEGER DEFAULT 100
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    source_type VARCHAR,
    source_id INTEGER,
    metadata JSONB,
    similarity NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.content,
        d.source_type,
        d.source_id,
        d.metadata,
        (1 - (d.embedding <=> query_embedding))::NUMERIC AS similarity
    FROM rag_documents d
    WHERE
        (filter_source_type IS NULL OR d.source_type = filter_source_type)
        AND d.vote_count >= min_vote_count
        AND (1 - (d.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

\connect horrorbot

DO $$
BEGIN
    RAISE NOTICE '✅ rag_documents.vote_count added; search_similar_documents now filters by popularity';
    RAISE NOTICE '   → run scripts/migrations/backfill_rag_vote_count.py to populate vote_count';
END $$;

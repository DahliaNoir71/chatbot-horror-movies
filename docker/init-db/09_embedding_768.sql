-- =============================================================================
-- HORRORBOT VECTORS - Embedding upgrade: MiniLM (384d) -> e5-base (768d)
-- =============================================================================
-- `paraphrase-multilingual-MiniLM-L12-v2` is a paraphrase model: it matches on
-- surface lexical overlap (mostly title words) and cannot bridge a thematic
-- query ("films about possessed children") to a plot synopsis. Benchmarking
-- showed thematic recall stuck regardless of corpus-text engineering.
--
-- `intfloat/multilingual-e5-base` is retrieval-trained (query/document
-- asymmetry) and emits 768-dim vectors, so the pgvector columns and the
-- `search_similar_documents` signature must widen from 384 to 768.
--
-- The stored 384-dim vectors come from the old model and are meaningless under
-- the new one. `rag_documents` is truncated here and MUST be rebuilt:
--   1. apply this script
--   2. python -m src.database.importer.rag_importer --clear
--   3. python -m scripts.migrations.backfill_rag_vote_count_20260520
--
-- Idempotent: the destructive TRUNCATE/ALTER fires only while the column is
-- still vector(384) -- any other state is left untouched. The function is
-- dropped and recreated unconditionally (cheap, late-bound plpgsql body).
-- =============================================================================

\connect horrorbot_vectors

-- -----------------------------------------------------------------------------
-- 1. Widen the embedding columns to 768 dimensions
-- -----------------------------------------------------------------------------
-- pgvector cannot cast vector(384) to vector(768), so the column type can only
-- change on an empty table. The guard fires the TRUNCATE exactly once -- on a
-- confirmed vector(384) column -- and never on an already-migrated database.

DO $$
DECLARE
    col_type TEXT;
BEGIN
    SELECT format_type(a.atttypid, a.atttypmod)
    INTO col_type
    FROM pg_attribute a
    WHERE a.attrelid = 'rag_documents'::regclass
      AND a.attname = 'embedding'
      AND NOT a.attisdropped;

    IF col_type = 'vector(384)' THEN
        RAISE NOTICE 'Migrating embedding columns 384 -> 768; truncating rag_documents ...';
        TRUNCATE TABLE rag_documents;
        ALTER TABLE rag_documents
            ALTER COLUMN embedding TYPE vector(768);
        ALTER TABLE rag_queries
            ALTER COLUMN query_embedding TYPE vector(768) USING NULL::vector(768);
        RAISE NOTICE 'Columns widened to vector(768). Re-embed + vote_count backfill required.';
    ELSE
        RAISE NOTICE 'embedding column is % -- migration skipped (already migrated or unexpected).', col_type;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 2. Redefine search_similar_documents for vector(768)
-- -----------------------------------------------------------------------------
-- Body identical to 08_rag_vote_count.sql (popularity floor preserved) -- only
-- the query_embedding parameter widens. Dropped first: a parameter-type change
-- under CREATE OR REPLACE is brittle, and the arity is unchanged.

DROP FUNCTION IF EXISTS search_similar_documents(vector, integer, numeric, varchar, integer);

CREATE OR REPLACE FUNCTION search_similar_documents(
    query_embedding vector(768),
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
    RAISE NOTICE 'Embedding schema upgraded to vector(768) for e5-base.';
    RAISE NOTICE 'Next: rag_importer --clear, then backfill_rag_vote_count_20260520.';
END $$;

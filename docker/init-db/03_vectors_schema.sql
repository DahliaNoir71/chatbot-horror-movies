-- =============================================================================
-- HORRORBOT VECTORS - RAG Embeddings Schema
-- =============================================================================
-- Vector store for RAG chatbot. Uses 384 dimensions (all-MiniLM-L6-v2).
-- Executed on 'horrorbot_vectors' database.
-- =============================================================================

\connect horrorbot_vectors

-- -----------------------------------------------------------------------------
-- RAG DOCUMENTS (Chunked content with embeddings)
-- -----------------------------------------------------------------------------

CREATE TABLE rag_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Content
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL,

    -- Source tracking
    source_type VARCHAR(50) NOT NULL,
    source_id INTEGER NOT NULL,

    -- Metadata for filtering and display
    metadata JSONB NOT NULL DEFAULT '{}',

    -- Chunking info
    chunk_index INTEGER DEFAULT 0,
    chunk_total INTEGER DEFAULT 1,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_source_type CHECK (source_type IN (
        'film_overview',
        'critics_consensus',
        'video_transcript'
    ))
);

-- -----------------------------------------------------------------------------
-- INDEXES FOR VECTOR SIMILARITY SEARCH
-- -----------------------------------------------------------------------------

-- IVFFlat index for approximate nearest neighbor search
-- Lists = sqrt(n) where n = expected row count (~10000 -> 100 lists)
CREATE INDEX idx_rag_documents_embedding ON rag_documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- B-tree indexes for filtering
CREATE INDEX idx_rag_documents_source_type ON rag_documents(source_type);
CREATE INDEX idx_rag_documents_source_id ON rag_documents(source_id);
CREATE INDEX idx_rag_documents_created ON rag_documents(created_at DESC);

-- GIN index for JSONB metadata queries
CREATE INDEX idx_rag_documents_metadata ON rag_documents USING GIN (metadata);

-- -----------------------------------------------------------------------------
-- RAG QUERIES LOG (Optional: track chatbot queries for analytics)
-- -----------------------------------------------------------------------------

CREATE TABLE rag_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Query content
    query_text TEXT NOT NULL,
    query_embedding vector(384),

    -- Results
    documents_retrieved INTEGER DEFAULT 0,
    top_similarity_score NUMERIC(5, 4),

    -- Response tracking
    response_generated BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER,

    -- User tracking (anonymized)
    session_id UUID,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rag_queries_created ON rag_queries(created_at DESC);
CREATE INDEX idx_rag_queries_session ON rag_queries(session_id);

-- -----------------------------------------------------------------------------
-- HELPER FUNCTIONS
-- -----------------------------------------------------------------------------

-- Function: Search similar documents by embedding
CREATE OR REPLACE FUNCTION search_similar_documents(
    query_embedding vector(384),
    match_count INTEGER DEFAULT 5,
    similarity_threshold NUMERIC DEFAULT 0.7,
    filter_source_type VARCHAR DEFAULT NULL
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
        AND (1 - (d.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function: Get document count by source type
CREATE OR REPLACE FUNCTION get_document_stats()
RETURNS TABLE (
    source_type VARCHAR,
    doc_count BIGINT,
    avg_chunk_size NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        d.source_type,
        COUNT(*) AS doc_count,
        ROUND(AVG(LENGTH(d.content))::NUMERIC, 0) AS avg_chunk_size
    FROM rag_documents d
    GROUP BY d.source_type
    ORDER BY doc_count DESC;
$$;

-- -----------------------------------------------------------------------------
-- RETURN TO MAIN DATABASE
-- -----------------------------------------------------------------------------

\connect horrorbot

-- -----------------------------------------------------------------------------
-- SUCCESS LOG
-- -----------------------------------------------------------------------------

DO $$
BEGIN
    RAISE NOTICE '✅ horrorbot_vectors schema created successfully';
    RAISE NOTICE '   - rag_documents: vector store (384 dims)';
    RAISE NOTICE '   - rag_queries: query analytics';
    RAISE NOTICE '   - IVFFlat index for similarity search';
END $$;
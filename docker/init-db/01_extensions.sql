-- =============================================================================
-- HORRORBOT - PostgreSQL Initialization Script
-- =============================================================================
-- This script runs automatically when the container is first created.
-- It sets up required extensions for the HorrorBot application.
-- =============================================================================

-- Enable pgvector for RAG embeddings (1536 dimensions for OpenAI)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable trigram similarity for film-video title matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE '✅ HorrorBot database extensions initialized successfully';
    RAISE NOTICE '   - vector (pgvector for embeddings)';
    RAISE NOTICE '   - pg_trgm (trigram similarity)';
    RAISE NOTICE '   - uuid-ossp (UUID generation)';
END $$;
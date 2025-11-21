-- init_pgvector.sql
-- Executed automatically on first container start

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
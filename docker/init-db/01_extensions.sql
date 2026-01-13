-- =============================================================================
-- HORRORBOT - Database Creation & Extensions
-- =============================================================================
-- Creates both databases and installs required extensions.
-- Executed automatically on first container start.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Extensions on horrorbot (current database from POSTGRES_DB)
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 2. Create vectors database for RAG embeddings
-- -----------------------------------------------------------------------------
CREATE DATABASE horrorbot_vectors
    OWNER horrorbot_user
    ENCODING 'UTF8'
    LC_COLLATE 'en_US.UTF-8'
    LC_CTYPE 'en_US.UTF-8'
    TEMPLATE template0;

-- -----------------------------------------------------------------------------
-- 3. Extensions on horrorbot_vectors (requires reconnection)
-- -----------------------------------------------------------------------------
\connect horrorbot_vectors

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 4. Return to main database for subsequent scripts
-- -----------------------------------------------------------------------------
\connect horrorbot

-- Log success
DO $$
BEGIN
    RAISE NOTICE '✅ Databases created successfully';
    RAISE NOTICE '   - horrorbot: relational data (films, credits, etc.)';
    RAISE NOTICE '   - horrorbot_vectors: RAG embeddings store';
END $$;
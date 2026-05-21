-- =============================================================================
-- HORRORBOT VECTORS - HNSW Index Migration (replaces IVFFlat)
-- =============================================================================
-- The original ANN index on rag_documents.embedding was IVFFlat with
-- `lists = 100`, created at bootstrap on an empty table. Two consequences
-- crippled recall once the ETL loaded the full corpus (~63 700 docs):
--
--   * IVFFlat k-means centroids were trained on 0 rows -> meaningless
--     partitioning of the vector space.
--   * With the default `ivfflat.probes = 1`, every query scans a single
--     list (~1 % of the corpus). A film whose embedding lands in another
--     list is unreachable regardless of its true cosine similarity.
--
-- HNSW needs no centroid training, builds incrementally (insertion order
-- is irrelevant), and reaches near-exact recall with the default
-- `hnsw.ef_search` — no query-time probe tuning required.
--
-- Idempotent: builds the HNSW index when absent, replaces a non-HNSW index
-- in place, and is a no-op when the HNSW index already exists. Safe to
-- rerun at container startup or manually via `psql -f`.
-- =============================================================================

\connect horrorbot_vectors

-- HNSW graph construction is memory-hungry; lift the per-session budget
-- above the server default (128MB) so the build stays in memory.
SET maintenance_work_mem = '512MB';

-- Build single-threaded. A parallel build allocates a dynamic shared memory
-- segment in /dev/shm, which Docker caps at 64MB by default — too small, so
-- the build fails with "No space left on device". A single-threaded build
-- uses only process-local memory and sidesteps the limit entirely.
SET max_parallel_maintenance_workers = 0;

DO $$
DECLARE
    index_method TEXT;
BEGIN
    SELECT am.amname
    INTO index_method
    FROM pg_class c
    JOIN pg_index i ON i.indexrelid = c.oid
    JOIN pg_am am ON am.oid = c.relam
    WHERE c.relname = 'idx_rag_documents_embedding';

    IF index_method = 'hnsw' THEN
        RAISE NOTICE 'HNSW index already present on rag_documents.embedding — skipping.';
    ELSE
        IF index_method IS NOT NULL THEN
            RAISE NOTICE 'Dropping legacy % index on rag_documents.embedding ...', index_method;
            DROP INDEX idx_rag_documents_embedding;
        END IF;

        RAISE NOTICE 'Building HNSW index on rag_documents.embedding (may take a few minutes) ...';
        EXECUTE
            'CREATE INDEX idx_rag_documents_embedding ON rag_documents '
            'USING hnsw (embedding vector_cosine_ops) '
            'WITH (m = 16, ef_construction = 200)';
        RAISE NOTICE 'HNSW index ready.';
    END IF;

    RAISE NOTICE '✅ Vector index migration complete (rag_documents.embedding → HNSW)';
END $$;

\connect horrorbot

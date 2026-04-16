-- =============================================================================
-- HORRORBOT - Search Vectors & Embeddings Change Tracking
-- =============================================================================
-- Adds FR title/synopsis columns, denormalized director/cast/keyword arrays,
-- weighted bilingual tsvectors (FR/EN) with an auto-update trigger on `films`,
-- plus a `content_hash` column on `rag_documents` for embedding regen tracking.
-- 100% idempotent: rejoué at startup (docker entrypoint) ou via `psql -f`.
-- =============================================================================

-- =============================================================================
-- SECTION 1 — horrorbot (relational database)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1a. New columns on films (FR content + denormalizations + tsvectors)
-- -----------------------------------------------------------------------------
-- Denormalizations (director/cast_names/keyword_names) are populated by the ETL
-- in write-through from credits/film_keywords. The trigger reads only columns of
-- `films` → deterministic and atomic, no cross-table lookup inside the trigger.

ALTER TABLE films ADD COLUMN IF NOT EXISTS title_fr            TEXT;
ALTER TABLE films ADD COLUMN IF NOT EXISTS overview_fr         TEXT;
ALTER TABLE films ADD COLUMN IF NOT EXISTS alternative_titles  TEXT[];
ALTER TABLE films ADD COLUMN IF NOT EXISTS director            TEXT;
ALTER TABLE films ADD COLUMN IF NOT EXISTS cast_names          TEXT[];
ALTER TABLE films ADD COLUMN IF NOT EXISTS keyword_names       TEXT[];
ALTER TABLE films ADD COLUMN IF NOT EXISTS search_vector_fr    TSVECTOR;
ALTER TABLE films ADD COLUMN IF NOT EXISTS search_vector_en    TSVECTOR;

-- -----------------------------------------------------------------------------
-- 1b. GIN indexes on tsvectors
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_films_search_vector_fr
    ON films USING GIN (search_vector_fr);

CREATE INDEX IF NOT EXISTS idx_films_search_vector_en
    ON films USING GIN (search_vector_en);

-- -----------------------------------------------------------------------------
-- 1c. Auto-update function (weighted tsvector composition)
-- -----------------------------------------------------------------------------
-- Weights: A = titles + director, B = cast, C = overview + keywords.
-- Uses `simple` dictionary for proper nouns (names, keywords) to avoid
-- language-specific stemming that would break exact-match retrieval.

CREATE OR REPLACE FUNCTION films_update_search_vectors()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector_fr :=
        setweight(to_tsvector('french', coalesce(NEW.title_fr, '')), 'A') ||
        setweight(to_tsvector('french',
            array_to_string(coalesce(NEW.alternative_titles, '{}'), ' ')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.director, '')), 'A') ||
        setweight(to_tsvector('simple',
            array_to_string(coalesce(NEW.cast_names, '{}'), ' ')), 'B') ||
        setweight(to_tsvector('french', coalesce(NEW.overview_fr, '')), 'C') ||
        setweight(to_tsvector('simple',
            array_to_string(coalesce(NEW.keyword_names, '{}'), ' ')), 'C');

    NEW.search_vector_en :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(NEW.director, '')), 'A') ||
        setweight(to_tsvector('simple',
            array_to_string(coalesce(NEW.cast_names, '{}'), ' ')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.overview, '')), 'C') ||
        setweight(to_tsvector('simple',
            array_to_string(coalesce(NEW.keyword_names, '{}'), ' ')), 'C');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1d. Idempotent trigger install
-- -----------------------------------------------------------------------------

DROP TRIGGER IF EXISTS films_tsvector_update ON films;

CREATE TRIGGER films_tsvector_update
    BEFORE INSERT OR UPDATE OF
        title, title_fr, overview, overview_fr,
        alternative_titles, director, cast_names, keyword_names
    ON films
    FOR EACH ROW
    EXECUTE FUNCTION films_update_search_vectors();

-- -----------------------------------------------------------------------------
-- 1e. Touch historical rows so the trigger populates search_vector_{fr,en}
-- -----------------------------------------------------------------------------
-- Touch des lignes historiques : force le trigger BEFORE UPDATE OF à recalculer
-- les tsvector pour les films ajoutés avant ce script. `SET title = title` est
-- valide : `title` est NOT NULL et dans la clause OF du trigger (PostgreSQL se
-- base sur la colonne mentionnée dans le SET, pas sur un changement effectif).
-- Fresh DB: 0 row matches → no-op.

UPDATE films
SET title = title
WHERE search_vector_fr IS NULL
   OR search_vector_en IS NULL;

-- =============================================================================
-- SECTION 2 — horrorbot_vectors (embedding store)
-- =============================================================================

\connect horrorbot_vectors

-- MD5 of `content`. Enables the embedding regeneration script (Phase 0.B.2) to
-- detect documents whose content changed after FR enrichment, so only those
-- get re-embedded instead of rerunning on the full corpus.

ALTER TABLE rag_documents
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_rag_documents_content_hash
    ON rag_documents (content_hash);

-- =============================================================================
-- SECTION 3 — return to main database
-- =============================================================================

\connect horrorbot

-- =============================================================================
-- SECTION 4 — success log
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Search vectors schema applied successfully';
    RAISE NOTICE '   - films: +3 FR columns, +3 denorm columns, +2 tsvectors';
    RAISE NOTICE '   - films: GIN indexes + auto-update trigger installed';
    RAISE NOTICE '   - rag_documents: +content_hash column for change detection';
END $$;

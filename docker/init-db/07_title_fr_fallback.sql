-- =============================================================================
-- HORRORBOT - FR Search Vector: title fallback to the English title
-- =============================================================================
-- `films_update_search_vectors()` built the FR title slot of search_vector_fr
-- from `coalesce(title_fr, '')`. When a film keeps its original (English)
-- title in France, `title_fr` is NULL — so search_vector_fr carried no title
-- token at all, and BM25 could never match those films by name on the FR
-- column (Get Out, Suspiria, Inferno, WolfCop, Late Phases, ...).
--
-- Fix: an empty `title_fr` means the French title *is* the English `title`.
-- Fall back accordingly — coalesce(NULLIF(title_fr, ''), title) — so the FR
-- vector always carries a title, indexed in the 'french' config (consistent
-- with how FR queries are parsed).
--
-- Idempotent: CREATE OR REPLACE FUNCTION + a full recompute touch. Safe to
-- rerun at container startup or manually via `psql -f`. On a fresh volume the
-- recompute matches 0 rows (films still empty); on an existing database it
-- rebuilds every search_vector_fr / search_vector_en.
-- =============================================================================

\connect horrorbot

-- -----------------------------------------------------------------------------
-- 1. Redefine the trigger function — only the FR title slot changes
-- -----------------------------------------------------------------------------
-- Weights: A = titles + director, B = cast, C = overview + keywords.
-- `simple` dictionary for proper nouns (names, keywords) to avoid
-- language-specific stemming that would break exact-match retrieval.
-- The existing `films_tsvector_update` trigger (installed by 05) keeps
-- working unchanged — it resolves the function by name at call time.

CREATE OR REPLACE FUNCTION films_update_search_vectors()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector_fr :=
        setweight(to_tsvector('french',
            coalesce(NULLIF(NEW.title_fr, ''), NEW.title)), 'A') ||
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
-- 2. Recompute search vectors for all existing rows
-- -----------------------------------------------------------------------------
-- `SET title = title` is valid: `title` is NOT NULL and listed in the
-- trigger's `UPDATE OF` clause, so the BEFORE UPDATE trigger fires and
-- rebuilds both tsvectors with the corrected function. Fresh DB: 0 rows.

UPDATE films SET title = title;

DO $$
BEGIN
    RAISE NOTICE '✅ FR search vector title fallback applied (title_fr → title when empty)';
END $$;

-- ============================================================================
-- IMDB - Base externe simulée (Port 5433)
-- Base : horror_imdb
-- Tables remplies par ETL (import dataset Kaggle IMDB)
-- Dataset: carolzhangdc/imdb-5000-movie-dataset
-- Valide compétence C2 : Extraction SQL depuis base externe
-- ============================================================================

-- ============================================================================
-- TABLE PRINCIPALE MOVIES (pour import dataset IMDB)
-- ============================================================================

CREATE TABLE IF NOT EXISTS movies (
    id SERIAL PRIMARY KEY,

    -- Identifiants
    imdb_id VARCHAR(20) UNIQUE,

    -- Informations de base
    title VARCHAR(500),
    year INTEGER,

    -- Genres et classification
    genres TEXT,
    content_rating VARCHAR(20),

    -- Détails techniques
    runtime INTEGER,
    country TEXT,
    language TEXT,

    -- Équipe
    director TEXT,
    actors TEXT,

    -- Description
    overview TEXT,

    -- Scores IMDB
    vote_average FLOAT,
    vote_count INTEGER,

    -- Finances
    budget BIGINT,
    revenue_worldwide BIGINT,

    -- Scores critiques
    user_reviews INTEGER,
    critic_reviews INTEGER,

    -- Source et audit
    source VARCHAR(50) DEFAULT 'imdb',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- INDEX
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies(imdb_id);
CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);
CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title);
CREATE INDEX IF NOT EXISTS idx_movies_vote_avg ON movies(vote_average DESC);
CREATE INDEX IF NOT EXISTS idx_movies_genres ON movies USING gin(to_tsvector('english', genres));

-- ============================================================================
-- VUES
-- ============================================================================

-- Vue filtrée pour extraction films d'horreur
CREATE OR REPLACE VIEW v_horror_movies AS
SELECT
    id,
    imdb_id,
    title,
    year,
    genres,
    content_rating,
    runtime,
    country,
    language,
    director,
    actors,
    overview,
    vote_average,
    vote_count,
    budget,
    revenue_worldwide,
    user_reviews,
    critic_reviews,
    source,
    created_at
FROM movies
WHERE
    LOWER(genres) LIKE '%horror%'
    OR LOWER(genres) LIKE '%thriller%';

-- Vue stats par année
CREATE OR REPLACE VIEW v_movies_by_year AS
SELECT
    year,
    COUNT(*) as film_count,
    ROUND(AVG(vote_average)::numeric, 2) as avg_rating,
    SUM(vote_count) as total_votes
FROM movies
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year DESC;

-- ============================================================================
-- COMMENTAIRES
-- ============================================================================

COMMENT ON TABLE movies IS 'Films importés depuis dataset Kaggle carolzhangdc/imdb-5000-movie-dataset - Source C2';
COMMENT ON VIEW v_horror_movies IS 'Vue filtrée films horreur/thriller IMDB';
COMMENT ON VIEW v_movies_by_year IS 'Statistiques films par année';
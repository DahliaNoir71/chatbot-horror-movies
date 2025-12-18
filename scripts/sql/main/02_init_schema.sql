-- ============================================================================
-- HorrorBot - Schéma principal PostgreSQL + pgvector
-- Base principale : horrorbot (Port 5432)
-- Supporte les 5 sources hétérogènes (E1 complet)
-- ============================================================================

-- ============================================================================
-- TABLE CENTRALE DES FILMS
-- ============================================================================

CREATE TABLE IF NOT EXISTS films (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    imdb_id VARCHAR(15),

    -- Informations de base
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    year INTEGER NOT NULL CHECK (year >= 1888 AND year <= 2100),
    release_date DATE,

    -- Scores TMDB
    vote_average FLOAT CHECK (vote_average >= 0 AND vote_average <= 10),
    vote_count INTEGER DEFAULT 0,
    popularity FLOAT DEFAULT 0,

    -- Scores Rotten Tomatoes (source 2: scraping)
    tomatometer_score INTEGER CHECK (tomatometer_score >= 0 AND tomatometer_score <= 100),
    audience_score INTEGER CHECK (audience_score >= 0 AND audience_score <= 100),
    certified_fresh BOOLEAN DEFAULT FALSE,
    critics_count INTEGER DEFAULT 0,
    audience_count INTEGER DEFAULT 0,

    -- Textes descriptifs
    critics_consensus TEXT,
    overview TEXT,
    tagline VARCHAR(500),

    -- Métadonnées techniques
    runtime INTEGER CHECK (runtime > 0),
    budget BIGINT DEFAULT 0,
    revenue BIGINT DEFAULT 0,
    original_language VARCHAR(10),
    status VARCHAR(50),

    -- URLs et médias
    rotten_tomatoes_url TEXT,
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    homepage TEXT,

    -- Embedding vectoriel (384 dimensions pour all-MiniLM-L6-v2)
    embedding vector(384),

    -- Flags de source
    source_tmdb BOOLEAN DEFAULT FALSE,
    source_rt BOOLEAN DEFAULT FALSE,
    source_kaggle BOOLEAN DEFAULT FALSE,
    source_imdb BOOLEAN DEFAULT FALSE,
    source_youtube BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index recherche vectorielle
CREATE INDEX IF NOT EXISTS idx_films_embedding
    ON films USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index performances
CREATE INDEX IF NOT EXISTS idx_films_tmdb_id ON films(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_films_imdb_id ON films(imdb_id);
CREATE INDEX IF NOT EXISTS idx_films_year ON films(year);
CREATE INDEX IF NOT EXISTS idx_films_title ON films(title);
CREATE INDEX IF NOT EXISTS idx_films_tomatometer ON films(tomatometer_score);
CREATE INDEX IF NOT EXISTS idx_films_popularity ON films(popularity DESC);

-- ============================================================================
-- TABLES DE RÉFÉRENCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS genres (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS persons (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(300) NOT NULL,
    profile_path VARCHAR(255),
    known_for_department VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS collections (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(300) NOT NULL,
    overview TEXT,
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- TABLES DE LIAISON (MANY-TO-MANY)
-- ============================================================================

CREATE TABLE IF NOT EXISTS film_genres (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (film_id, genre_id)
);

CREATE TABLE IF NOT EXISTS film_keywords (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    PRIMARY KEY (film_id, keyword_id)
);

CREATE TABLE IF NOT EXISTS film_collections (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (film_id, collection_id)
);

-- ============================================================================
-- TABLES CAST & CREW
-- ============================================================================

CREATE TABLE IF NOT EXISTS film_cast (
    id SERIAL PRIMARY KEY,
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    character VARCHAR(500),
    cast_order INTEGER,
    UNIQUE (film_id, person_id, character)
);

CREATE INDEX IF NOT EXISTS idx_film_cast_film ON film_cast(film_id);
CREATE INDEX IF NOT EXISTS idx_film_cast_person ON film_cast(person_id);

CREATE TABLE IF NOT EXISTS film_crew (
    id SERIAL PRIMARY KEY,
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    department VARCHAR(100),
    job VARCHAR(200),
    UNIQUE (film_id, person_id, job)
);

CREATE INDEX IF NOT EXISTS idx_film_crew_film ON film_crew(film_id);
CREATE INDEX IF NOT EXISTS idx_film_crew_person ON film_crew(person_id);
CREATE INDEX IF NOT EXISTS idx_film_crew_job ON film_crew(job);

-- ============================================================================
-- TABLES SOURCES EXTERNES
-- ============================================================================

-- Source 3 : Données Kaggle (CSV)
CREATE TABLE IF NOT EXISTS kaggle_movies (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE,
    imdb_id VARCHAR(15),
    title VARCHAR(500),
    year INTEGER,
    vote_average FLOAT,
    vote_count INTEGER,
    runtime INTEGER,
    budget BIGINT,
    revenue BIGINT,
    genres TEXT,
    overview TEXT,
    raw_data JSONB,
    imported_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kaggle_tmdb ON kaggle_movies(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_kaggle_imdb ON kaggle_movies(imdb_id);
CREATE INDEX IF NOT EXISTS idx_kaggle_title_year ON kaggle_movies(title, year);

-- Source 4 : Base externe (PostgreSQL IMDB port 5433)
-- Note: Les données IMDB sont dans une base séparée
-- Cette table stocke les données importées/synchronisées
CREATE TABLE IF NOT EXISTS imdb_sync (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER,
    imdb_id VARCHAR(50),
    title VARCHAR(500),
    year INTEGER,
    imdb_rating NUMERIC(3, 2),
    rating_count INTEGER,
    review_count INTEGER,
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_imdb_tmdb ON imdb_sync(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_imdb_title_year ON imdb_sync(title, year);

-- Source 5 : YouTube Stats (Big Data / SQL externe)
-- Compatible avec YouTubeSQLExtractor
CREATE TABLE IF NOT EXISTS youtube_stats (
    id SERIAL PRIMARY KEY,

    -- Colonnes pour matching avec films
    tmdb_id INTEGER,
    title VARCHAR(500),
    year INTEGER,

    -- Statistiques agrégées (pour l'extracteur)
    trailer_views BIGINT,
    trailer_likes BIGINT,

    -- Détails vidéo (optionnel, pour traçabilité)
    video_id VARCHAR(20),
    video_title VARCHAR(500),
    channel_name VARCHAR(200),
    view_count BIGINT,
    like_count BIGINT,
    comment_count BIGINT,
    published_at TIMESTAMP,
    video_type VARCHAR(50),

    -- Métadonnées
    raw_data JSONB,
    imported_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_youtube_tmdb ON youtube_stats(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_youtube_title_year ON youtube_stats(title, year);
CREATE INDEX IF NOT EXISTS idx_youtube_video ON youtube_stats(video_id);

-- ============================================================================
-- TABLES AUDIT ET RGPD
-- ============================================================================

CREATE TABLE IF NOT EXISTS rgpd_processing_registry (
    id SERIAL PRIMARY KEY,
    treatment_name VARCHAR(200) NOT NULL,
    purpose TEXT NOT NULL,
    data_categories TEXT NOT NULL,
    retention_period VARCHAR(100),
    legal_basis VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_access_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(20) NOT NULL,
    user_identifier VARCHAR(200),
    ip_address INET,
    query_hash VARCHAR(64),
    row_count INTEGER,
    executed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_log_table ON data_access_log(table_name);
CREATE INDEX IF NOT EXISTS idx_access_log_date ON data_access_log(executed_at);

-- ============================================================================
-- VUES UTILITAIRES
-- ============================================================================

-- Vue complète d'un film avec toutes les sources
CREATE OR REPLACE VIEW v_films_complete AS
SELECT
    f.id,
    f.tmdb_id,
    f.imdb_id,
    f.title,
    f.year,
    f.vote_average AS tmdb_score,
    f.tomatometer_score,
    f.audience_score,
    f.critics_consensus,
    f.overview,
    f.runtime,
    f.popularity,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN f.source_tmdb THEN 'TMDB' END,
        CASE WHEN f.source_rt THEN 'RottenTomatoes' END,
        CASE WHEN f.source_kaggle THEN 'Kaggle' END,
        CASE WHEN f.source_imdb THEN 'IMDB' END,
        CASE WHEN f.source_youtube THEN 'YouTube' END
    ], NULL) AS data_sources,
    COALESCE(f.tomatometer_score::float / 10, f.vote_average) AS combined_score,
    f.created_at,
    f.updated_at
FROM films f;

-- Vue pour recherche RAG
CREATE OR REPLACE VIEW v_films_rag AS
SELECT
    f.id,
    f.tmdb_id,
    f.title,
    f.year,
    CONCAT_WS(' | ',
        f.title || ' (' || f.year || ')',
        f.tagline,
        COALESCE(f.critics_consensus, f.overview)
    ) AS rag_text,
    f.embedding
FROM films f;

-- ============================================================================
-- FONCTIONS
-- ============================================================================

-- Recherche vectorielle
CREATE OR REPLACE FUNCTION search_similar_films(
    query_embedding vector(384),
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    film_id INTEGER,
    title VARCHAR(500),
    year INTEGER,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id,
        f.title,
        f.year,
        1 - (f.embedding <=> query_embedding) AS similarity
    FROM films f
    WHERE f.embedding IS NOT NULL
    ORDER BY f.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_films_updated_at ON films;
CREATE TRIGGER trigger_films_updated_at
    BEFORE UPDATE ON films
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DONNÉES INITIALES
-- ============================================================================

-- Genres Horror
INSERT INTO genres (tmdb_id, name) VALUES
    (27, 'Horror'),
    (53, 'Thriller'),
    (9648, 'Mystery'),
    (878, 'Science Fiction'),
    (14, 'Fantasy'),
    (28, 'Action'),
    (18, 'Drama'),
    (35, 'Comedy'),
    (80, 'Crime'),
    (12, 'Adventure')
ON CONFLICT (tmdb_id) DO NOTHING;

-- Registre RGPD
INSERT INTO rgpd_processing_registry (treatment_name, purpose, data_categories, retention_period, legal_basis) VALUES
    ('ETL_TMDB', 'Collecte métadonnées films API TMDB', 'Données publiques films', '5 ans', 'Intérêt légitime'),
    ('ETL_RT', 'Scraping scores Rotten Tomatoes', 'Données publiques critiques', '5 ans', 'Intérêt légitime'),
    ('ETL_Kaggle', 'Import dataset CSV Kaggle', 'Données publiques films', '5 ans', 'Intérêt légitime'),
    ('ETL_IMDB', 'Extraction base PostgreSQL externe', 'Données partenaire', '3 ans', 'Contrat'),
    ('ETL_YouTube', 'Stats YouTube via extraction SQL', 'Données publiques vidéos', '2 ans', 'Intérêt légitime'),
    ('API_Access', 'Accès API chatbot', 'Logs requêtes anonymisés', '30 jours', 'Intérêt légitime')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- COMMENTAIRES
-- ============================================================================

COMMENT ON TABLE films IS 'Table centrale - agrège les 5 sources hétérogènes';
COMMENT ON TABLE kaggle_movies IS 'Source 3: Import CSV Kaggle (C1)';
COMMENT ON TABLE imdb_sync IS 'Source 4: Sync depuis PostgreSQL externe port 5433 (C2)';
COMMENT ON TABLE youtube_stats IS 'Source 5: Stats YouTube - compatible YouTubeSQLExtractor (C2)';
COMMENT ON TABLE rgpd_processing_registry IS 'Registre traitements RGPD Article 30';
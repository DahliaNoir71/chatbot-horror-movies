-- ============================================================================
-- MLD HorrorBot - Base de données films avec recherche vectorielle
-- PostgreSQL 16 + pgvector 0.5.1
-- ============================================================================

-- Extension pgvector (à activer une seule fois)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Table principale : FILMS
-- ============================================================================
CREATE TABLE films (
    -- Identifiants
    tmdb_id INTEGER PRIMARY KEY,
    imdb_id VARCHAR(10) CHECK (imdb_id ~ '^tt\d{7,8}$'),
    
    -- Informations de base
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    year INTEGER NOT NULL CHECK (year >= 1888 AND year <= 2030),
    release_date DATE,
    
    -- Scores TMDB
    vote_average NUMERIC(3,1) NOT NULL CHECK (vote_average >= 0 AND vote_average <= 10),
    vote_count INTEGER NOT NULL CHECK (vote_count >= 0),
    popularity NUMERIC(10,3) NOT NULL CHECK (popularity >= 0),
    
    -- Scores Rotten Tomatoes (optionnels)
    tomatometer_score INTEGER CHECK (tomatometer_score >= 0 AND tomatometer_score <= 100),
    audience_score INTEGER CHECK (audience_score >= 0 AND audience_score <= 100),
    certified_fresh BOOLEAN DEFAULT FALSE,
    critics_count INTEGER DEFAULT 0 CHECK (critics_count >= 0),
    audience_count INTEGER DEFAULT 0 CHECK (audience_count >= 0),
    
    -- Textes descriptifs (RAG)
    critics_consensus TEXT CHECK (LENGTH(critics_consensus) <= 2000),
    overview TEXT CHECK (LENGTH(overview) <= 2000),
    tagline VARCHAR(500),
    
    -- Métadonnées
    runtime INTEGER CHECK (runtime >= 1 AND runtime <= 1000),
    genres JSONB NOT NULL DEFAULT '[]',  -- ✅ ["Horror", "Thriller"]
    original_language VARCHAR(2) CHECK (original_language ~ '^[a-z]{2}$'),
    
    -- URLs et références
    rotten_tomatoes_url TEXT,
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    
    -- Flags
    incomplete BOOLEAN DEFAULT FALSE,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- Table embeddings : FILM_EMBEDDINGS
-- ============================================================================
CREATE TABLE film_embeddings (
    id SERIAL PRIMARY KEY,
    film_id INTEGER NOT NULL REFERENCES films(tmdb_id) ON DELETE CASCADE,
    
    -- Vecteur d'embedding (384 dimensions pour sentence-transformers/all-MiniLM-L6-v2)
    embedding vector(384) NOT NULL,
    
    -- Source du texte utilisé pour l'embedding
    source_text TEXT NOT NULL,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('critics_consensus', 'overview')),
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- ✅ Contrainte unique : 1 seul embedding par film
    UNIQUE(film_id)
);

-- ============================================================================
-- INDEX
-- ============================================================================

-- Index sur films
CREATE INDEX idx_films_year ON films(year);
CREATE INDEX idx_films_vote_average ON films(vote_average DESC);
CREATE INDEX idx_films_popularity ON films(popularity DESC);
CREATE INDEX idx_films_title ON films USING gin(to_tsvector('english', title));
CREATE INDEX idx_films_genres ON films USING gin(genres);  -- ✅ Index JSONB

-- Index pgvector HNSW (haute performance recherche vectorielle)
-- m=16 : nombre de connexions par couche (trade-off vitesse/précision)
-- ef_construction=64 : précision de construction (plus = meilleur mais plus lent)
CREATE INDEX idx_film_embeddings_vector ON film_embeddings 
USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_film_embeddings_film_id ON film_embeddings(film_id);

-- ============================================================================
-- TRIGGERS (audit automatique)
-- ============================================================================

-- Mise à jour automatique du champ updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_films_updated_at
BEFORE UPDATE ON films
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTAIRES (documentation schéma)
-- ============================================================================

COMMENT ON TABLE films IS 'Films d''horreur agrégés depuis TMDB et Rotten Tomatoes';
COMMENT ON TABLE film_embeddings IS 'Embeddings vectoriels pour recherche sémantique (RAG)';

COMMENT ON COLUMN films.tmdb_id IS 'Identifiant unique TMDB (source de vérité)';
COMMENT ON COLUMN films.genres IS 'Liste des genres en JSONB (ex: ["Horror", "Thriller"])';
COMMENT ON COLUMN films.critics_consensus IS 'Consensus critique RT (prioritaire pour RAG)';

COMMENT ON COLUMN film_embeddings.embedding IS 'Vecteur 384D (sentence-transformers/all-MiniLM-L6-v2)';
COMMENT ON COLUMN film_embeddings.source_type IS 'Type de texte source : critics_consensus ou overview';
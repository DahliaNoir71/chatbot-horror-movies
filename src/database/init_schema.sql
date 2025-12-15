-- Extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Table principale films
CREATE TABLE IF NOT EXISTS films (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    imdb_id VARCHAR(10),
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    year INTEGER NOT NULL,
    release_date DATE,

    -- Scores
    vote_average FLOAT CHECK (vote_average BETWEEN 0 AND 10),
    vote_count INTEGER DEFAULT 0,
    popularity FLOAT DEFAULT 0,

    tomatometer_score INTEGER CHECK (tomatometer_score BETWEEN 0 AND 100),
    audience_score INTEGER CHECK (audience_score BETWEEN 0 AND 100),
    certified_fresh BOOLEAN DEFAULT FALSE,

    -- Textes
    critics_consensus TEXT,
    overview TEXT,
    tagline VARCHAR(500),

    -- Métadonnées
    runtime INTEGER,
    original_language VARCHAR(2),
    genres JSONB,

    -- URLs
    rotten_tomatoes_url TEXT,
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),

    -- Embedding vectoriel (dimension 384 pour all-MiniLM-L6-v2)
    embedding vector(384),

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index pour recherche vectorielle
CREATE INDEX IF NOT EXISTS films_embedding_idx ON films
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index classiques
CREATE INDEX IF NOT EXISTS films_tmdb_id_idx ON films(tmdb_id);
CREATE INDEX IF NOT EXISTS films_year_idx ON films(year);
CREATE INDEX IF NOT EXISTS films_tomatometer_idx ON films(tomatometer_score);

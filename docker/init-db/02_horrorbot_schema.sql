-- =============================================================================
-- HORRORBOT - Relational Schema (horrorbot database)
-- =============================================================================
-- Tables for extracted data from TMDB, Rotten Tomatoes, YouTube, Kaggle/Spark.
-- Executed on 'horrorbot' database after 01_create_databases.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- REFERENCE TABLES
-- -----------------------------------------------------------------------------

CREATE TABLE genres (
    id SERIAL PRIMARY KEY,
    tmdb_genre_id INTEGER NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE keywords (
    id SERIAL PRIMARY KEY,
    tmdb_keyword_id INTEGER UNIQUE,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE production_companies (
    id SERIAL PRIMARY KEY,
    tmdb_company_id INTEGER UNIQUE,
    name VARCHAR(255) NOT NULL,
    origin_country VARCHAR(10)
);

CREATE TABLE spoken_languages (
    id SERIAL PRIMARY KEY,
    iso_639_1 VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL
);

-- -----------------------------------------------------------------------------
-- FILMS (Main entity)
-- -----------------------------------------------------------------------------

CREATE TABLE films (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER NOT NULL UNIQUE,
    imdb_id VARCHAR(20),

    -- Basic info
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    release_date DATE,
    tagline VARCHAR(500),
    overview TEXT,

    -- TMDB metrics
    popularity NUMERIC(10, 4) DEFAULT 0,
    vote_average NUMERIC(3, 1) DEFAULT 0,
    vote_count INTEGER DEFAULT 0,

    -- Metadata
    runtime INTEGER,
    original_language VARCHAR(10),
    status VARCHAR(50) DEFAULT 'Released',
    adult BOOLEAN DEFAULT FALSE,

    -- Media URLs
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    homepage TEXT,

    -- Financial (Kaggle/Spark enrichment)
    budget BIGINT DEFAULT 0,
    revenue BIGINT DEFAULT 0,

    -- ETL tracking
    source VARCHAR(50) DEFAULT 'tmdb',
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_vote_average CHECK (vote_average >= 0 AND vote_average <= 10),
    CONSTRAINT chk_runtime CHECK (runtime IS NULL OR (runtime > 0 AND runtime < 1000))
);

CREATE INDEX idx_films_tmdb_id ON films(tmdb_id);
CREATE INDEX idx_films_imdb_id ON films(imdb_id);
CREATE INDEX idx_films_release_date ON films(release_date);
CREATE INDEX idx_films_popularity ON films(popularity DESC);

-- -----------------------------------------------------------------------------
-- FILM ASSOCIATIONS
-- -----------------------------------------------------------------------------

CREATE TABLE film_genres (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (film_id, genre_id)
);

CREATE TABLE film_keywords (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    source VARCHAR(50) DEFAULT 'tmdb',
    PRIMARY KEY (film_id, keyword_id)
);

CREATE TABLE film_companies (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES production_companies(id) ON DELETE CASCADE,
    PRIMARY KEY (film_id, company_id)
);

CREATE TABLE film_languages (
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    language_id INTEGER NOT NULL REFERENCES spoken_languages(id) ON DELETE CASCADE,
    PRIMARY KEY (film_id, language_id)
);

-- -----------------------------------------------------------------------------
-- CREDITS (Directors, Actors, etc.)
-- -----------------------------------------------------------------------------

CREATE TABLE credits (
    id SERIAL PRIMARY KEY,
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    tmdb_person_id INTEGER,

    -- Person info
    person_name VARCHAR(255) NOT NULL,

    -- Role info
    role_type VARCHAR(20) NOT NULL,
    character_name VARCHAR(255),
    department VARCHAR(100),
    job VARCHAR(100),

    -- Display
    display_order INTEGER DEFAULT 0,
    profile_path VARCHAR(255),

    CONSTRAINT chk_role_type CHECK (role_type IN ('director', 'actor', 'writer', 'producer'))
);

CREATE INDEX idx_credits_film_id ON credits(film_id);
CREATE INDEX idx_credits_person_name ON credits(person_name);
CREATE INDEX idx_credits_role_type ON credits(role_type);

-- -----------------------------------------------------------------------------
-- ROTTEN TOMATOES SCORES
-- -----------------------------------------------------------------------------

CREATE TABLE rt_scores (
    id SERIAL PRIMARY KEY,
    film_id INTEGER NOT NULL UNIQUE REFERENCES films(id) ON DELETE CASCADE,

    -- Critic scores
    tomatometer_score INTEGER,
    tomatometer_state VARCHAR(20),
    critics_count INTEGER DEFAULT 0,
    critics_average_rating NUMERIC(3, 2),

    -- Audience scores
    audience_score INTEGER,
    audience_state VARCHAR(20),
    audience_count INTEGER DEFAULT 0,
    audience_average_rating NUMERIC(3, 2),

    -- Content (valuable for RAG)
    critics_consensus TEXT,

    -- RT metadata
    rt_url VARCHAR(500),
    rt_rating VARCHAR(20),

    -- Timestamps
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rt_scores_film_id ON rt_scores(film_id);
CREATE INDEX idx_rt_scores_tomatometer ON rt_scores(tomatometer_score);

-- -----------------------------------------------------------------------------
-- YOUTUBE VIDEOS
-- -----------------------------------------------------------------------------

CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    youtube_id VARCHAR(20) NOT NULL UNIQUE,

    -- Content
    title VARCHAR(500) NOT NULL,
    description TEXT,

    -- Channel info
    channel_id VARCHAR(50),
    channel_title VARCHAR(255),

    -- Metrics
    view_count BIGINT DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,

    -- Metadata
    duration VARCHAR(50),
    published_at TIMESTAMPTZ,
    thumbnail_url VARCHAR(500),
    video_type VARCHAR(50),

    -- ETL tracking
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_videos_youtube_id ON videos(youtube_id);
CREATE INDEX idx_videos_channel_id ON videos(channel_id);
CREATE INDEX idx_videos_published ON videos(published_at);

-- -----------------------------------------------------------------------------
-- VIDEO TRANSCRIPTS
-- -----------------------------------------------------------------------------

CREATE TABLE video_transcripts (
    id SERIAL PRIMARY KEY,
    video_id INTEGER NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,

    -- Content
    transcript TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    is_generated BOOLEAN DEFAULT FALSE,
    word_count INTEGER,

    -- ETL tracking
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_video_transcripts_video_id ON video_transcripts(video_id);

-- -----------------------------------------------------------------------------
-- FILM-VIDEO MATCHING
-- -----------------------------------------------------------------------------

CREATE TABLE film_videos (
    id SERIAL PRIMARY KEY,
    film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,

    -- Match quality
    match_score NUMERIC(4, 3) NOT NULL,
    match_method VARCHAR(50) NOT NULL,

    -- Metadata
    matched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_match_score CHECK (match_score >= 0 AND match_score <= 1),
    CONSTRAINT uq_film_video UNIQUE (film_id, video_id)
);

CREATE INDEX idx_film_videos_film_id ON film_videos(film_id);
CREATE INDEX idx_film_videos_video_id ON film_videos(video_id);
CREATE INDEX idx_film_videos_score ON film_videos(match_score);

-- -----------------------------------------------------------------------------
-- AUDIT & COMPLIANCE (RGPD)
-- -----------------------------------------------------------------------------

CREATE TABLE rgpd_processing_registry (
    id SERIAL PRIMARY KEY,
    processing_name VARCHAR(255) NOT NULL,
    processing_purpose TEXT NOT NULL,
    data_categories TEXT[] NOT NULL,
    data_subjects TEXT[] NOT NULL,
    recipients TEXT[],
    retention_period VARCHAR(100) NOT NULL,
    security_measures TEXT,
    legal_basis VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_legal_basis CHECK (legal_basis IN (
        'consent', 'contract', 'legal_obligation',
        'vital_interests', 'public_task', 'legitimate_interests'
    ))
);

CREATE TABLE data_retention_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(50) NOT NULL,
    records_affected INTEGER NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    executed_by VARCHAR(100) DEFAULT 'system',
    details JSONB
);

-- -----------------------------------------------------------------------------
-- ETL TRACKING
-- -----------------------------------------------------------------------------

CREATE TABLE etl_runs (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),

    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Status
    status VARCHAR(20) DEFAULT 'running',

    -- Counts per source
    tmdb_count INTEGER DEFAULT 0,
    rt_count INTEGER DEFAULT 0,
    youtube_count INTEGER DEFAULT 0,
    spark_count INTEGER DEFAULT 0,
    total_films INTEGER DEFAULT 0,

    -- Errors
    errors JSONB,

    CONSTRAINT chk_etl_status CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);

CREATE INDEX idx_etl_runs_status ON etl_runs(status);
CREATE INDEX idx_etl_runs_started ON etl_runs(started_at DESC);

-- -----------------------------------------------------------------------------
-- SUCCESS LOG
-- -----------------------------------------------------------------------------

DO $$
BEGIN
    RAISE NOTICE '✅ horrorbot schema created successfully';
    RAISE NOTICE '   - 18 tables created';
    RAISE NOTICE '   - Indexes and constraints applied';
END $$;
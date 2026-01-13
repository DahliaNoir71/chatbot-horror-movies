-- =============================================================================
-- HORRORBOT - Seed Reference Data
-- =============================================================================
-- Initial data for genres, languages, and RGPD registry.
-- Executed on 'horrorbot' database after schema creation.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- TMDB GENRES (Horror + related genres)
-- -----------------------------------------------------------------------------

INSERT INTO genres (tmdb_genre_id, name) VALUES
    (27, 'Horror'),
    (53, 'Thriller'),
    (9648, 'Mystery'),
    (878, 'Science Fiction'),
    (14, 'Fantasy'),
    (28, 'Action'),
    (12, 'Adventure'),
    (16, 'Animation'),
    (35, 'Comedy'),
    (80, 'Crime'),
    (99, 'Documentary'),
    (18, 'Drama'),
    (10751, 'Family'),
    (36, 'History'),
    (10402, 'Music'),
    (10749, 'Romance'),
    (10770, 'TV Movie'),
    (10752, 'War'),
    (37, 'Western')
ON CONFLICT (tmdb_genre_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- SPOKEN LANGUAGES (Common languages in horror films)
-- -----------------------------------------------------------------------------

INSERT INTO spoken_languages (iso_639_1, name) VALUES
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    ('de', 'German'),
    ('it', 'Italian'),
    ('ja', 'Japanese'),
    ('ko', 'Korean'),
    ('zh', 'Chinese'),
    ('pt', 'Portuguese'),
    ('ru', 'Russian'),
    ('hi', 'Hindi'),
    ('th', 'Thai'),
    ('id', 'Indonesian'),
    ('tr', 'Turkish'),
    ('pl', 'Polish'),
    ('nl', 'Dutch'),
    ('sv', 'Swedish'),
    ('no', 'Norwegian'),
    ('da', 'Danish'),
    ('fi', 'Finnish')
ON CONFLICT (iso_639_1) DO NOTHING;

-- -----------------------------------------------------------------------------
-- RGPD PROCESSING REGISTRY (Article 30 compliance)
-- -----------------------------------------------------------------------------

INSERT INTO rgpd_processing_registry (
    processing_name,
    processing_purpose,
    data_categories,
    data_subjects,
    recipients,
    retention_period,
    security_measures,
    legal_basis
) VALUES
(
    'Film Metadata Extraction',
    'Extract and store film metadata from TMDB API for horror movie recommendations.',
    ARRAY['Film titles', 'Release dates', 'Plot summaries', 'Ratings', 'Cast names'],
    ARRAY['Public figures (actors, directors)'],
    ARRAY['Internal application only'],
    '5 years or until data refresh',
    'Database encryption at rest, access control via application layer',
    'legitimate_interests'
),
(
    'Rotten Tomatoes Scraping',
    'Scrape critic scores and consensus text for film quality assessment.',
    ARRAY['Critic scores', 'Audience scores', 'Critics consensus text'],
    ARRAY['Public figures (film critics)'],
    ARRAY['Internal application only'],
    '5 years or until data refresh',
    'Database encryption at rest, rate-limited scraping',
    'legitimate_interests'
),
(
    'YouTube Video Extraction',
    'Extract video metadata and transcripts from horror film review channels.',
    ARRAY['Video titles', 'Channel names', 'Transcripts', 'View counts'],
    ARRAY['Content creators (YouTube channels)'],
    ARRAY['Internal application only'],
    '3 years or until channel removal request',
    'Database encryption at rest, API-based extraction only',
    'legitimate_interests'
),
(
    'RAG Chatbot Queries',
    'Process user queries to provide film recommendations via RAG architecture.',
    ARRAY['Query text', 'Session identifiers (anonymized)'],
    ARRAY['Application users'],
    ARRAY['Internal application only'],
    '90 days for analytics, then anonymized',
    'No PII stored, session IDs are UUID without user linkage',
    'legitimate_interests'
),
(
    'ETL Pipeline Logging',
    'Track extraction pipeline runs for monitoring and debugging.',
    ARRAY['Execution timestamps', 'Record counts', 'Error messages'],
    ARRAY['System processes'],
    ARRAY['Internal application only'],
    '1 year',
    'No PII involved, internal system data only',
    'legitimate_interests'
);

-- -----------------------------------------------------------------------------
-- SUCCESS LOG
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    genre_count INTEGER;
    lang_count INTEGER;
    rgpd_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO genre_count FROM genres;
    SELECT COUNT(*) INTO lang_count FROM spoken_languages;
    SELECT COUNT(*) INTO rgpd_count FROM rgpd_processing_registry;

    RAISE NOTICE '✅ Seed data inserted successfully';
    RAISE NOTICE '   - Genres: % entries', genre_count;
    RAISE NOTICE '   - Languages: % entries', lang_count;
    RAISE NOTICE '   - RGPD Registry: % entries', rgpd_count;
END $$;
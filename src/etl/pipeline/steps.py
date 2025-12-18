"""ETL pipeline extraction steps (1-7).

Each step handles extraction from a specific data source:
    - Step 1: TMDB API (REST)
    - Step 2: Rotten Tomatoes (Web scraping)
    - Step 3: Spotify API (REST OAuth2)
    - Step 4: YouTube Data API v3 (REST)
    - Step 5: Kaggle CSV (File)
    - Step 6: PostgreSQL IMDB (External DB)
    - Step 7: Polars (BigData aggregation)
"""

from pathlib import Path

from src.etl.extractors.kaggle_extractor import KaggleExtractor
from src.etl.extractors.postgres_extractor import PostgresExtractor
from src.etl.extractors.rt_enricher import RottenTomatoesEnricher
from src.etl.extractors.spotify_extractor import SpotifyExtractor
from src.etl.extractors.tmdb_extractor import TMDBExtractor
from src.etl.extractors.youtube_extractor import YouTubeExtractor
from src.etl.polars_processor import PolarsProcessor
from src.etl.types import (
    FilmDict,
    IMDBDataDict,
    PodcastEpisodeDict,
    VideoDict,
)
from src.etl.utils import setup_logger
from src.settings import settings

logger = setup_logger("etl.pipeline.steps")


# =============================================================================
# STEP 1: TMDB (REST API)
# =============================================================================


def step_1_extract_tmdb(max_pages: int | None = None) -> list[FilmDict]:
    """Extract horror films from TMDB API.

    Args:
        max_pages: Maximum pages to extract (None = config default).

    Returns:
        List of raw TMDB film dictionaries.

    Raises:
        Exception: If TMDB extraction fails.
    """
    logger.info("=" * 80)
    logger.info("🎬 ÉTAPE 1/7 : EXTRACTION TMDB (API REST)")
    logger.info("=" * 80)

    try:
        extractor = TMDBExtractor()
        movies = extractor.extract(
            max_pages=max_pages,
            enrich=False,
            save_checkpoint=True,
        )
        logger.info(f"✅ Étape 1 terminée : {len(movies)} films extraits")
        return movies

    except Exception as e:
        logger.error(f"❌ Échec étape 1 (TMDB) : {e}", exc_info=True)
        raise


# =============================================================================
# STEP 2: ROTTEN TOMATOES (WEB SCRAPING)
# =============================================================================


async def step_2_enrich_rt(tmdb_movies: list[FilmDict]) -> list[FilmDict]:
    """Enrich films with Rotten Tomatoes scores via web scraping.

    Args:
        tmdb_movies: Films from TMDB extraction.

    Returns:
        List of enriched film dictionaries.

    Raises:
        Exception: If RT enrichment fails.
    """
    logger.info("=" * 80)
    logger.info("🍅 ÉTAPE 2/7 : ENRICHISSEMENT ROTTEN TOMATOES (SCRAPING)")
    logger.info("=" * 80)

    try:
        enricher = RottenTomatoesEnricher()
        enriched = await enricher.enrich_films_async(
            tmdb_movies,
            max_concurrent=3,
        )
        enriched_count = sum(1 for film in enriched if "tomatometer_score" in film)
        logger.info(f"✅ Étape 2 terminée : {enriched_count}/{len(tmdb_movies)} enrichis")
        return enriched

    except Exception as e:
        logger.error(f"❌ Échec étape 2 (RT) : {e}", exc_info=True)
        raise


# =============================================================================
# STEP 3: SPOTIFY (REST API OAUTH2)
# =============================================================================


def step_3_extract_spotify() -> list[PodcastEpisodeDict]:
    """Extract horror podcasts from Spotify API.

    Returns:
        List of podcast episode dictionaries (empty if not configured).
    """
    logger.info("=" * 80)
    logger.info("🎧 ÉTAPE 3/7 : EXTRACTION SPOTIFY (API REST OAuth2)")
    logger.info("=" * 80)

    try:
        extractor = SpotifyExtractor()

        if not settings.spotify.is_configured:
            logger.warning("⚠️ Spotify non configuré, étape ignorée")
            return []

        episodes = extractor.extract()
        logger.info(f"✅ Étape 3 terminée : {len(episodes)} épisodes extraits")
        return episodes

    except Exception as e:
        logger.error(f"❌ Échec étape 3 (Spotify) : {e}", exc_info=True)
        return []


# =============================================================================
# STEP 4: YOUTUBE (REST API)
# =============================================================================


def step_4_extract_youtube(max_videos: int | None = None) -> list[VideoDict]:
    """Extract horror videos from YouTube Data API.

    Args:
        max_videos: Maximum videos per channel.

    Returns:
        List of video dictionaries (empty if not configured).
    """
    logger.info("=" * 80)
    logger.info("📺 ÉTAPE 4/7 : EXTRACTION YOUTUBE (API REST)")
    logger.info("=" * 80)

    try:
        extractor = YouTubeExtractor()

        if not settings.youtube.is_configured:
            logger.warning("⚠️ YouTube non configuré, étape ignorée")
            return []

        videos = extractor.extract(max_videos=max_videos)
        logger.info(f"✅ Étape 4 terminée : {len(videos)} vidéos extraites")
        return videos

    except Exception as e:
        logger.error(f"❌ Échec étape 4 (YouTube) : {e}", exc_info=True)
        return []


# =============================================================================
# STEP 5: KAGGLE (CSV FILE)
# =============================================================================


def step_5_extract_kaggle() -> list[FilmDict]:
    """Extract horror films from Kaggle CSV dataset.

    Returns:
        List of film dictionaries (empty if not configured).
    """
    logger.info("=" * 80)
    logger.info("📊 ÉTAPE 5/7 : EXTRACTION KAGGLE (FICHIER CSV)")
    logger.info("=" * 80)

    try:
        extractor = KaggleExtractor()

        if not settings.kaggle.is_configured:
            logger.warning("⚠️ Kaggle non configuré, étape ignorée")
            return []

        films = extractor.extract(use_cache=True)
        logger.info(f"✅ Étape 5 terminée : {len(films)} films extraits")
        return films

    except Exception as e:
        logger.error(f"❌ Échec étape 5 (Kaggle) : {e}", exc_info=True)
        return []


# =============================================================================
# STEP 6: POSTGRESQL IMDB (EXTERNAL DB)
# =============================================================================


def step_6_extract_postgres() -> IMDBDataDict:
    """Extract data from external IMDB PostgreSQL database.

    Returns:
        Dictionary with films, reviews, ratings lists.
    """
    logger.info("=" * 80)
    logger.info("🗄️ ÉTAPE 6/7 : EXTRACTION POSTGRESQL (BDD EXTERNE)")
    logger.info("=" * 80)

    empty_result: IMDBDataDict = {"films": [], "reviews": [], "ratings": []}

    try:
        extractor = PostgresExtractor()

        if not settings.imdb_db.is_configured:
            logger.warning("⚠️ IMDB DB non configurée, étape ignorée")
            return empty_result

        data = extractor.extract(tables=["films", "reviews", "ratings"])
        total = sum(len(v) for v in data.values())

        if total == 0:
            logger.warning(
                "⚠️ Base Letterboxd vide. Exécuter d'abord : "
                "python -m src.scripts.import_imdb --limit 500"
            )

        logger.info(f"✅ Étape 6 terminée : {total} enregistrements extraits")
        return data

    except Exception as e:
        logger.error(f"❌ Échec étape 6 (PostgreSQL) : {e}", exc_info=True)
        return empty_result


# =============================================================================
# STEP 7: POLARS (BIGDATA AGGREGATION)
# =============================================================================


def step_7_aggregate_polars(
    tmdb_films: list[FilmDict],
    kaggle_films: list[FilmDict],
    imdb_films: list[FilmDict],
    output_path: Path | None = None,
) -> list[FilmDict]:
    """Aggregate all film sources using Polars BigData processing.

    Args:
        tmdb_films: Films from TMDB.
        kaggle_films: Films from Kaggle CSV.
        imdb_films: Films from IMDB DB.
        output_path: Optional path to save aggregated data.

    Returns:
        List of aggregated, deduplicated films.
    """
    logger.info("=" * 80)
    logger.info("⚡ ÉTAPE 7/7 : AGRÉGATION POLARS (BIGDATA)")
    logger.info("=" * 80)

    try:
        processor = PolarsProcessor()
        sources = _build_sources_dict(tmdb_films, kaggle_films, imdb_films)

        if not sources:
            logger.warning("⚠️ Aucune source de films à agréger")
            return []

        df = processor.extract(sources=sources, output_path=output_path)
        result = processor.to_dicts(df)

        logger.info(f"✅ Étape 7 terminée : {len(result)} films agrégés")
        return result

    except Exception as e:
        logger.error(f"❌ Échec étape 7 (Polars) : {e}", exc_info=True)
        return tmdb_films


def _build_sources_dict(
    tmdb_films: list[FilmDict],
    kaggle_films: list[FilmDict],
    imdb_films: list[FilmDict],
) -> dict[str, list[FilmDict]]:
    """Build sources dictionary for Polars aggregation.

    Args:
        tmdb_films: Films from TMDB.
        kaggle_films: Films from Kaggle.
        imdb_films: Films from IMDB.

    Returns:
        Dictionary mapping source names to film lists.
    """
    sources: dict[str, list[FilmDict]] = {}

    if tmdb_films:
        sources["tmdb"] = tmdb_films
    if kaggle_films:
        sources["kaggle"] = kaggle_films
    if imdb_films:
        sources["imdb"] = imdb_films

    return sources

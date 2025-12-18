"""Pipeline helper functions for orchestration.

Provides utility functions for:
    - Data validation and defaults
    - Checkpoint management wrappers
    - Extraction result handling
    - Logging utilities
"""

from collections.abc import Callable
from datetime import datetime

from src.etl.types import (
    FilmDict,
    IMDBDataDict,
    PipelineResult,
    PodcastEpisodeDict,
    VideoDict,
)
from src.etl.utils import CheckpointManager, setup_logger

logger = setup_logger("etl.pipeline.helpers")
checkpoint_manager = CheckpointManager()

# Type alias for extraction results
ExtractedData = list[FilmDict] | list[PodcastEpisodeDict] | list[VideoDict] | IMDBDataDict


# =============================================================================
# DATA DEFAULTS AND VALIDATION
# =============================================================================


def get_empty_imdb_result() -> IMDBDataDict:
    """Return empty IMDB data structure.

    Returns:
        Empty IMDBDataDict with all lists initialized.
    """
    return {"films": [], "reviews": [], "ratings": []}


def has_extracted_data(result: list | dict) -> bool:
    """Check if extraction result contains data.

    Args:
        result: Extraction result (list or dict).

    Returns:
        True if result contains data.
    """
    if isinstance(result, dict):
        return bool(result.get("films"))
    return bool(result)


def get_default_for_source(source_name: str) -> ExtractedData:
    """Get default empty value for a source.

    Args:
        source_name: Source identifier.

    Returns:
        Empty list or IMDBDataDict depending on source.
    """
    if source_name == "postgres":
        return get_empty_imdb_result()
    return []


# =============================================================================
# EXTRACTION RESULT HANDLING
# =============================================================================


def handle_extraction_result(
    result: ExtractedData,
    source_name: str,
    checkpoint_key: str,
    sources_completed: list[str],
    sources_failed: list[str],
) -> None:
    """Handle extraction result with checkpoint and status tracking.

    Args:
        result: Extraction result.
        source_name: Source identifier.
        checkpoint_key: Key for checkpoint storage.
        sources_completed: List to append on success.
        sources_failed: List to append on failure.
    """
    if has_extracted_data(result):
        checkpoint_manager.save(checkpoint_key, result)
        sources_completed.append(source_name)
    else:
        sources_failed.append(source_name)
        logger.warning(f"Aucune donnée trouvée pour {source_name}")


def process_optional_source(
    source_name: str,
    extractor_fn: Callable[[], ExtractedData],
    checkpoint_key: str,
    skip: set[str],
    sources_completed: list[str],
    sources_failed: list[str],
) -> ExtractedData:
    """Process an optional source with error handling.

    Args:
        source_name: Source identifier for logging.
        extractor_fn: Extraction function to call.
        checkpoint_key: Key for checkpoint storage.
        skip: Set of sources to skip.
        sources_completed: List to append on success.
        sources_failed: List to append on failure.

    Returns:
        Extracted data or empty list/dict on failure.
    """
    if source_name in skip:
        return get_default_for_source(source_name)

    try:
        result = extractor_fn()
        handle_extraction_result(
            result, source_name, checkpoint_key, sources_completed, sources_failed
        )
        return result

    except Exception as e:
        logger.error(f"❌ Erreur {source_name}: {e}")
        sources_failed.append(source_name)
        return get_default_for_source(source_name)


def load_or_execute_step(
    step_number: int,
    current_step: int,
    checkpoint_key: str,
    executor_fn: Callable[[], ExtractedData],
    sources_completed: list[str],
    source_name: str,
) -> ExtractedData:
    """Load checkpoint or execute step if needed.

    Args:
        step_number: Step number for this source (2-6).
        current_step: Step to resume from.
        checkpoint_key: Key for checkpoint load/save.
        executor_fn: Function to execute if needed.
        sources_completed: List to append source name on success.
        source_name: Source identifier.

    Returns:
        Loaded or extracted data.
    """
    cached = checkpoint_manager.load(checkpoint_key)

    if current_step <= step_number and not cached:
        result = executor_fn()
        if has_extracted_data(result):
            checkpoint_manager.save(checkpoint_key, result)
    else:
        result = cached or get_default_for_source(source_name)

    if has_extracted_data(result):
        sources_completed.append(source_name)

    return result


# =============================================================================
# LOGGING UTILITIES
# =============================================================================


def log_pipeline_stats(
    films: list[FilmDict],
    podcasts: list[PodcastEpisodeDict],
    videos: list[VideoDict],
    imdb: IMDBDataDict,
    duration: float,
    sources_completed: list[str],
    sources_failed: list[str],
) -> None:
    """Log final pipeline statistics.

    Args:
        films: Aggregated films.
        podcasts: Podcast episodes.
        videos: YouTube videos.
        imdb: IMDB data.
        duration: Execution duration in seconds.
        sources_completed: Successful sources.
        sources_failed: Failed sources.
    """
    logger.info("=" * 80)
    logger.info("📊 STATISTIQUES PIPELINE E1 COMPLET")
    logger.info("=" * 80)

    _log_extracted_data_stats(films, podcasts, videos, imdb)
    _log_sources_status(sources_completed, sources_failed)
    _log_performance_stats(duration, films)

    logger.info("=" * 80)


def _log_extracted_data_stats(
    films: list[FilmDict],
    podcasts: list[PodcastEpisodeDict],
    videos: list[VideoDict],
    imdb: IMDBDataDict,
) -> None:
    """Log extracted data statistics."""
    logger.info("📦 DONNÉES EXTRAITES :")
    logger.info(f"   Films (agrégés)     : {len(films):,}")
    logger.info(f"   Podcasts (épisodes) : {len(podcasts):,}")
    logger.info(f"   Vidéos YouTube      : {len(videos):,}")
    logger.info(f"   IMDB films          : {len(imdb.get('films', [])):,}")
    logger.info(f"   IMDB reviews        : {len(imdb.get('reviews', [])):,}")
    logger.info(f"   IMDB ratings        : {len(imdb.get('ratings', [])):,}")


def _log_sources_status(
    sources_completed: list[str],
    sources_failed: list[str],
) -> None:
    """Log sources completion status."""
    logger.info("-" * 40)
    logger.info(f"✅ Sources réussies : {', '.join(sources_completed)}")
    if sources_failed:
        logger.info(f"❌ Sources échouées : {', '.join(sources_failed)}")


def _log_performance_stats(duration: float, films: list[FilmDict]) -> None:
    """Log performance statistics."""
    logger.info("-" * 40)
    logger.info(f"⏱️ Durée totale : {duration:.2f}s ({duration / 60:.1f} min)")
    if duration > 0 and films:
        logger.info(f"📈 Débit films  : {len(films) / duration:.2f} films/s")


# =============================================================================
# PIPELINE RESULT BUILDING
# =============================================================================


def finalize_pipeline(
    start_time: datetime,
    all_films: list[FilmDict],
    podcasts: list[PodcastEpisodeDict],
    videos: list[VideoDict],
    imdb: IMDBDataDict,
    sources_completed: list[str],
    sources_failed: list[str],
) -> PipelineResult:
    """Finalize pipeline execution with logging and result preparation.

    Args:
        start_time: Pipeline start timestamp.
        all_films: Aggregated film data.
        podcasts: Podcast episodes.
        videos: YouTube videos.
        imdb: IMDB data.
        sources_completed: Successful sources.
        sources_failed: Failed sources.

    Returns:
        PipelineResult instance.
    """
    duration = (datetime.now() - start_time).total_seconds()

    log_pipeline_stats(
        films=all_films,
        podcasts=podcasts,
        videos=videos,
        imdb=imdb,
        duration=duration,
        sources_completed=sources_completed,
        sources_failed=sources_failed,
    )

    return PipelineResult(
        films=all_films,
        podcasts=podcasts,
        videos=videos,
        imdb=imdb,
        duration_seconds=duration,
        sources_completed=sources_completed,
        sources_failed=sources_failed,
    )


def build_resume_result(
    start_time: datetime,
    rt: ExtractedData,
    spotify: ExtractedData,
    youtube: ExtractedData,
    kaggle: ExtractedData,
    imdb: ExtractedData,
    sources_completed: list[str],
    aggregate_fn: Callable[[list[FilmDict], list[FilmDict], list[FilmDict]], list[FilmDict]],
) -> PipelineResult:
    """Build PipelineResult from resume operation data.

    Args:
        start_time: Resume start timestamp.
        rt: Rotten Tomatoes enriched data.
        spotify: Spotify podcast data.
        youtube: YouTube video data.
        kaggle: Kaggle film data.
        imdb: IMDB data.
        sources_completed: Completed sources list.
        aggregate_fn: Aggregation function (step_7_aggregate_polars).

    Returns:
        PipelineResult instance.
    """
    imdb_dict = imdb if isinstance(imdb, dict) else get_empty_imdb_result()

    films = aggregate_fn(
        rt if isinstance(rt, list) else [],
        kaggle if isinstance(kaggle, list) else [],
        imdb_dict.get("films", []),
    )

    duration = (datetime.now() - start_time).total_seconds()

    return PipelineResult(
        films=films,
        podcasts=spotify if isinstance(spotify, list) else [],
        videos=youtube if isinstance(youtube, list) else [],
        imdb=imdb_dict,
        duration_seconds=duration,
        sources_completed=sources_completed,
        sources_failed=[],
    )

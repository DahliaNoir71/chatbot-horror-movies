"""Pipeline orchestration - execution, resume, and single source extraction.

Provides high-level functions for pipeline control:
    - run_full_pipeline: Complete 7-source extraction
    - resume_from_step: Checkpoint-based resume
    - extract_single_source: Individual source extraction
"""

import asyncio
from collections.abc import Callable
from datetime import datetime

from src.etl.pipeline.helpers import (
    ExtractedData,
    build_resume_result,
    checkpoint_manager,
    finalize_pipeline,
    get_empty_imdb_result,
    load_or_execute_step,
    process_optional_source,
)
from src.etl.pipeline.steps import (
    step_1_extract_tmdb,
    step_2_enrich_rt,
    step_3_extract_spotify,
    step_4_extract_youtube,
    step_5_extract_kaggle,
    step_6_extract_postgres,
    step_7_aggregate_polars,
)
from src.etl.types import (
    ExtractionParams,
    FilmDict,
    PipelineResult,
)
from src.etl.utils import setup_logger

logger = setup_logger("etl.pipeline.orchestrator")


# =============================================================================
# REQUIRED STEP EXECUTION
# =============================================================================


def _execute_required_step_tmdb(
    max_pages: int | None,
    sources_completed: list[str],
    sources_failed: list[str],
) -> list[FilmDict] | None:
    """Execute required TMDB extraction step.

    Args:
        max_pages: Maximum pages to extract.
        sources_completed: List to append on success.
        sources_failed: List to append on failure.

    Returns:
        List of films or None on failure.
    """
    try:
        tmdb_movies = step_1_extract_tmdb(max_pages)
        checkpoint_manager.save("pipeline_step1_tmdb", tmdb_movies)
        sources_completed.append("tmdb")
        return tmdb_movies
    except Exception as e:
        logger.error(f"❌ Erreur TMDB: {e}")
        sources_failed.append("tmdb")
        return None


async def _execute_required_step_rt(
    tmdb_movies: list[FilmDict],
    sources_completed: list[str],
    sources_failed: list[str],
) -> list[FilmDict] | None:
    """Execute required Rotten Tomatoes enrichment step.

    Args:
        tmdb_movies: Films from TMDB.
        sources_completed: List to append on success.
        sources_failed: List to append on failure.

    Returns:
        Enriched films or None on failure.
    """
    try:
        rt_enriched = await step_2_enrich_rt(tmdb_movies)
        checkpoint_manager.save("pipeline_step2_rt", rt_enriched)
        sources_completed.append("rotten_tomatoes")
        return rt_enriched
    except Exception as e:
        logger.error(f"❌ Erreur Rotten Tomatoes: {e}")
        sources_failed.append("rotten_tomatoes")
        return None


def _execute_aggregation_step(
    rt_enriched: list[FilmDict],
    kaggle_films: ExtractedData,
    imdb: ExtractedData,
    sources_completed: list[str],
    sources_failed: list[str],
) -> list[FilmDict]:
    """Execute Polars aggregation step.

    Args:
        rt_enriched: Films enriched with RT data.
        kaggle_films: Films from Kaggle.
        imdb: IMDB data dictionary.
        sources_completed: List to append on success.
        sources_failed: List to append on failure.

    Returns:
        Aggregated film list.
    """
    try:
        kaggle_list = kaggle_films if isinstance(kaggle_films, list) else []
        imdb_dict = imdb if isinstance(imdb, dict) else get_empty_imdb_result()

        all_films = step_7_aggregate_polars(
            tmdb_films=rt_enriched,
            kaggle_films=kaggle_list,
            imdb_films=imdb_dict.get("films", []),
        )
        checkpoint_manager.save("pipeline_step7_polars", all_films)
        sources_completed.append("polars")
        return all_films

    except Exception as e:
        logger.error(f"❌ Erreur Polars: {e}")
        sources_failed.append("polars")
        return rt_enriched


# =============================================================================
# MAIN PIPELINE EXECUTION
# =============================================================================


async def run_full_pipeline(
    max_pages: int | None = None,
    max_videos: int | None = None,
    skip_sources: list[str] | None = None,
) -> PipelineResult:
    """Execute complete ETL pipeline with all 7 sources.

    Args:
        max_pages: TMDB pages limit.
        max_videos: YouTube videos limit.
        skip_sources: Sources to skip ("spotify", "youtube", "kaggle", "postgres").

    Returns:
        PipelineResult with all extracted data.
    """
    start_time = datetime.now()
    skip = set(skip_sources or [])
    sources_completed: list[str] = []
    sources_failed: list[str] = []

    logger.info("🚀 DÉMARRAGE PIPELINE ETL HORRORBOT - 7 SOURCES")
    logger.info(f"Timestamp : {start_time.isoformat()}")
    logger.info(f"Skip sources : {skip or 'aucune'}")

    # Step 1: TMDB (required)
    tmdb_result = _execute_required_step_tmdb(max_pages, sources_completed, sources_failed)
    if tmdb_result is None:
        return finalize_pipeline(
            start_time, [], [], [], get_empty_imdb_result(), sources_completed, sources_failed
        )

    # Step 2: Rotten Tomatoes (required)
    rt_result = await _execute_required_step_rt(tmdb_result, sources_completed, sources_failed)
    if rt_result is None:
        return finalize_pipeline(
            start_time,
            tmdb_result,
            [],
            [],
            get_empty_imdb_result(),
            sources_completed,
            sources_failed,
        )

    # Process optional sources
    podcasts = process_optional_source(
        "spotify",
        step_3_extract_spotify,
        "pipeline_step3_spotify",
        skip,
        sources_completed,
        sources_failed,
    )

    videos = process_optional_source(
        "youtube",
        lambda: step_4_extract_youtube(max_videos),
        "pipeline_step4_youtube",
        skip,
        sources_completed,
        sources_failed,
    )

    kaggle_films = process_optional_source(
        "kaggle",
        step_5_extract_kaggle,
        "pipeline_step5_kaggle",
        skip,
        sources_completed,
        sources_failed,
    )

    imdb = process_optional_source(
        "postgres",
        step_6_extract_postgres,
        "pipeline_step6_postgres",
        skip,
        sources_completed,
        sources_failed,
    )

    # Step 7: Polars Aggregation
    all_films = _execute_aggregation_step(
        rt_result, kaggle_films, imdb, sources_completed, sources_failed
    )

    return finalize_pipeline(
        start_time,
        all_films,
        podcasts if isinstance(podcasts, list) else [],
        videos if isinstance(videos, list) else [],
        imdb if isinstance(imdb, dict) else get_empty_imdb_result(),
        sources_completed,
        sources_failed,
    )


# =============================================================================
# RESUME FROM CHECKPOINT
# =============================================================================


async def resume_from_step(
    step: int,
    max_pages: int | None = None,
) -> PipelineResult:
    """Resume pipeline from specific step using checkpoints.

    Args:
        step: Step number (1-7).
        max_pages: TMDB pages if step=1.

    Returns:
        PipelineResult with extracted data.
    """
    logger.info(f"🔄 Reprise pipeline depuis étape {step}")

    if step == 1:
        return await run_full_pipeline(max_pages)

    start_time = datetime.now()
    sources_completed: list[str] = []

    # Load TMDB baseline (required)
    tmdb = checkpoint_manager.load("pipeline_step1_tmdb") or []
    sources_completed.append("tmdb")

    # Execute or load remaining steps
    rt = load_or_execute_step(
        step_number=2,
        current_step=step,
        checkpoint_key="pipeline_step2_rt",
        executor_fn=lambda: asyncio.get_event_loop().run_until_complete(step_2_enrich_rt(tmdb)),
        sources_completed=sources_completed,
        source_name="rotten_tomatoes",
    )

    spotify = load_or_execute_step(
        step_number=3,
        current_step=step,
        checkpoint_key="pipeline_step3_spotify",
        executor_fn=step_3_extract_spotify,
        sources_completed=sources_completed,
        source_name="spotify",
    )

    youtube = load_or_execute_step(
        step_number=4,
        current_step=step,
        checkpoint_key="pipeline_step4_youtube",
        executor_fn=step_4_extract_youtube,
        sources_completed=sources_completed,
        source_name="youtube",
    )

    kaggle = load_or_execute_step(
        step_number=5,
        current_step=step,
        checkpoint_key="pipeline_step5_kaggle",
        executor_fn=step_5_extract_kaggle,
        sources_completed=sources_completed,
        source_name="kaggle",
    )

    imdb = load_or_execute_step(
        step_number=6,
        current_step=step,
        checkpoint_key="pipeline_step6_imdb",
        executor_fn=step_6_extract_postgres,
        sources_completed=sources_completed,
        source_name="postgres",
    )

    return build_resume_result(
        start_time, rt, spotify, youtube, kaggle, imdb, sources_completed, step_7_aggregate_polars
    )


# =============================================================================
# SINGLE SOURCE EXTRACTION
# =============================================================================


def extract_single_source(
    source: str,
    params: ExtractionParams | None = None,
) -> list[FilmDict]:
    """Extract data from a single source.

    Args:
        source: Source name (tmdb, spotify, youtube, kaggle, postgres).
        params: Extraction parameters (max_pages, max_videos).

    Returns:
        Extracted film data list.

    Raises:
        ValueError: If source name is unknown.
    """
    params = params or ExtractionParams()

    extractors: dict[str, Callable[[], ExtractedData]] = {
        "tmdb": lambda: step_1_extract_tmdb(params.max_pages),
        "spotify": step_3_extract_spotify,
        "youtube": lambda: step_4_extract_youtube(params.max_videos),
        "kaggle": step_5_extract_kaggle,
        "postgres": step_6_extract_postgres,
    }

    if source not in extractors:
        valid = list(extractors.keys())
        raise ValueError(f"Source inconnue: {source}. Valides: {valid}")

    logger.info(f"🎯 Extraction source unique : {source}")
    result = extractors[source]()

    if isinstance(result, dict):
        return result.get("films", [])
    return result

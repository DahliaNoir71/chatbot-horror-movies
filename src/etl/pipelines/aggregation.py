"""Aggregation pipeline for RAG export.

Reads films and RT scores from PostgreSQL, calculates
aggregated scores, and exports JSON for RAG ingestion.

This is the final step (Step 6) of the E1 ETL pipeline.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import get_database
from src.etl.aggregation import (
    AggregatedFilm,
    ScoreCalculator,
)
from src.etl.utils.logger import setup_logger

logger = setup_logger("etl.pipelines.aggregation")


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_OUTPUT_DIR = Path("data/processed")
DEFAULT_OUTPUT_FILENAME = "rag_films.json"
JSON_INDENT = 2

# SQL query to fetch films with RT scores
FILMS_WITH_SCORES_QUERY = """
SELECT
    f.id,
    f.tmdb_id,
    f.imdb_id,
    f.title,
    f.original_title,
    f.release_date,
    f.tagline,
    f.overview,
    f.popularity,
    f.vote_average,
    f.vote_count,
    f.runtime,
    f.original_language,
    f.adult,
    f.status,
    f.poster_path,
    f.backdrop_path,
    f.homepage,
    f.budget,
    f.revenue,
    f.source,
    rt.tomatometer_score,
    rt.tomatometer_state,
    rt.audience_score,
    rt.critics_count,
    rt.audience_count,
    rt.critics_consensus,
    rt.rt_url
FROM films f
LEFT JOIN rt_scores rt ON f.id = rt.film_id
ORDER BY f.popularity DESC
"""

# SQL query to fetch ALL genres in bulk (eliminates N+1)
GENRES_BULK_QUERY = """
SELECT fg.film_id, array_agg(g.name ORDER BY g.name) as genres
FROM film_genres fg
JOIN genres g ON fg.genre_id = g.id
GROUP BY fg.film_id
"""

# SQL query to fetch ALL keywords in bulk (eliminates N+1)
KEYWORDS_BULK_QUERY = """
SELECT fk.film_id, array_agg(k.name ORDER BY k.name) as keywords
FROM film_keywords fk
JOIN keywords k ON fk.keyword_id = k.id
GROUP BY fk.film_id
"""


# =============================================================================
# PIPELINE RESULT
# =============================================================================


@dataclass
class AggregationPipelineResult:
    """Results from aggregation pipeline execution.

    Attributes:
        films_read: Films read from database.
        films_with_rt: Films with RT scores.
        films_exported: Films exported to JSON.
        avg_score: Average aggregated score.
        duration_seconds: Total execution time.
        output_path: Path to exported JSON.
        error_messages: List of error descriptions.
    """

    films_read: int = 0
    films_with_rt: int = 0
    films_exported: int = 0
    avg_score: float = 0.0
    duration_seconds: float = 0.0
    output_path: str = ""
    error_messages: list[str] = field(default_factory=list)

    @property
    def rt_coverage(self) -> float:
        """Calculate RT coverage percentage."""
        if self.films_read == 0:
            return 0.0
        return round((self.films_with_rt / self.films_read) * 100, 2)


# =============================================================================
# AGGREGATION PIPELINE
# =============================================================================


class AggregationPipeline:
    """Pipeline for aggregating film data and exporting to JSON.

    Reads from PostgreSQL tables (films, rt_scores, genres, keywords),
    calculates weighted aggregated scores, and exports RAG-ready JSON.

    Usage:
        pipeline = AggregationPipeline()
        result = pipeline.run()
    """

    def __init__(
        self,
        session: Session | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize aggregation pipeline.

        Args:
            session: Optional SQLAlchemy session.
            output_dir: Output directory for JSON export.
        """
        self._session = session
        self._output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self._logger = setup_logger("etl.pipelines.aggregation")
        self._result = AggregationPipelineResult()
        self._score_calculator = ScoreCalculator()

    # =========================================================================
    # Public API
    # =========================================================================

    def run(self, limit: int | None = None) -> AggregationPipelineResult:
        """Execute aggregation pipeline.

        Args:
            limit: Max films to process (None = all).

        Returns:
            AggregationPipelineResult with statistics.
        """
        start_time = datetime.now()
        self._log_start()
        self._result = AggregationPipelineResult()

        try:
            self._execute_pipeline(limit)
        except Exception as e:
            self._handle_error(e)

        self._result.duration_seconds = self._calculate_duration(start_time)
        self._log_final_results()

        return self._result

    # =========================================================================
    # Pipeline Execution
    # =========================================================================

    def _execute_pipeline(self, limit: int | None) -> None:
        """Execute pipeline stages.

        Args:
            limit: Max films to process.
        """
        session = self._get_session()

        # Stage 1: Read films from database
        films_data = self._read_films_from_db(session, limit)
        self._result.films_read = len(films_data)

        if not films_data:
            self._logger.warning("No films found in database")
            return

        # Stage 2: Convert to AggregatedFilm and calculate scores
        aggregated_films = self._process_films(films_data)

        # Stage 3: Export to JSON
        output_path = self._export_to_json(aggregated_films)
        self._result.output_path = str(output_path)
        self._result.films_exported = len(aggregated_films)

    def _read_films_from_db(
        self,
        session: Session,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        """Read films with RT scores from database.

        Args:
            session: Database session.
            limit: Max films to read.

        Returns:
            List of film dictionaries.
        """
        self._logger.info("Stage 1: Reading films from database...")

        query = FILMS_WITH_SCORES_QUERY
        if limit:
            query += f" LIMIT {limit}"

        result = session.execute(text(query))
        rows = result.fetchall()
        columns = result.keys()

        films = [dict(zip(columns, row, strict=True)) for row in rows]
        self._logger.info(f"Read {len(films)} films from database")

        return self._enrich_with_relations(session, films)

    def _enrich_with_relations(
        self,
        session: Session,
        films: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Enrich films with genres and keywords (bulk load).

        Args:
            session: Database session.
            films: Films to enrich.

        Returns:
            Enriched films with genres and keywords lists.
        """
        genres_map = self._load_all_genres(session)
        keywords_map = self._load_all_keywords(session)

        for film in films:
            film_id = film["id"]
            film["genres"] = genres_map.get(film_id, [])
            film["keywords"] = keywords_map.get(film_id, [])

        return films

    @staticmethod
    def _load_all_genres(session: Session) -> dict[int, list[str]]:
        """Load all genres in single query.

        Args:
            session: Database session.

        Returns:
            Mapping of film_id to genre list.
        """
        result = session.execute(text(GENRES_BULK_QUERY))
        return {row[0]: list(row[1]) for row in result.fetchall()}

    @staticmethod
    def _load_all_keywords(session: Session) -> dict[int, list[str]]:
        """Load all keywords in single query.

        Args:
            session: Database session.

        Returns:
            Mapping of film_id to keyword list.
        """
        result = session.execute(text(KEYWORDS_BULK_QUERY))
        return {row[0]: list(row[1]) for row in result.fetchall()}

    # =========================================================================
    # Film Processing
    # =========================================================================

    def _process_films(
        self,
        films_data: list[dict[str, Any]],
    ) -> list[AggregatedFilm]:
        """Process films: convert and calculate scores.

        Args:
            films_data: Raw film data from database.

        Returns:
            List of processed AggregatedFilm objects.
        """
        self._logger.info("Stage 2: Processing and scoring films...")

        aggregated: list[AggregatedFilm] = []
        rt_count = 0

        for film_dict in films_data:
            film = self._convert_to_aggregated(film_dict)
            if film:
                aggregated.append(film)
                if film.tomatometer_score is not None:
                    rt_count += 1

        self._result.films_with_rt = rt_count

        # Calculate aggregated scores
        aggregated = self._score_calculator.calculate_scores(aggregated)
        self._result.avg_score = self._score_calculator.stats.avg_score

        self._logger.info(f"Processed {len(aggregated)} films (RT: {rt_count})")
        return aggregated

    def _convert_to_aggregated(
        self,
        film_dict: dict[str, Any],
    ) -> AggregatedFilm | None:
        """Convert database row to AggregatedFilm.

        Args:
            film_dict: Film data from database.

        Returns:
            AggregatedFilm or None if conversion fails.
        """
        try:
            return AggregatedFilm(
                tmdb_id=film_dict["tmdb_id"],
                imdb_id=film_dict.get("imdb_id"),
                title=film_dict["title"],
                original_title=film_dict.get("original_title"),
                release_date=film_dict.get("release_date"),
                tagline=film_dict.get("tagline"),
                overview=film_dict.get("overview"),
                popularity=film_dict.get("popularity", 0.0),
                vote_average=film_dict.get("vote_average", 0.0),
                vote_count=film_dict.get("vote_count", 0),
                runtime=film_dict.get("runtime"),
                original_language=film_dict.get("original_language"),
                adult=film_dict.get("adult", False),
                status=film_dict.get("status", "Released"),
                poster_path=film_dict.get("poster_path"),
                backdrop_path=film_dict.get("backdrop_path"),
                homepage=film_dict.get("homepage"),
                budget=film_dict.get("budget", 0),
                revenue=film_dict.get("revenue", 0),
                genres=film_dict.get("genres", []),
                keywords=film_dict.get("keywords", []),
                tomatometer_score=film_dict.get("tomatometer_score"),
                tomatometer_state=film_dict.get("tomatometer_state"),
                audience_score=film_dict.get("audience_score"),
                critics_count=film_dict.get("critics_count") or 0,
                audience_count=film_dict.get("audience_count") or 0,
                critics_consensus=film_dict.get("critics_consensus"),
                rt_url=film_dict.get("rt_url"),
                sources=self._determine_sources(film_dict),
            )
        except Exception as e:
            self._logger.warning(f"Conversion failed for {film_dict.get('title')}: {e}")
            return None

    @staticmethod
    def _determine_sources(film_dict: dict[str, Any]) -> list[str]:
        """Determine data sources for a film.

        Args:
            film_dict: Film data.

        Returns:
            List of source identifiers.
        """
        sources = ["tmdb"]
        if film_dict.get("tomatometer_score") is not None:
            sources.append("rotten_tomatoes")
        if film_dict.get("source") == "kaggle":
            sources.append("kaggle")
        return sources

    # =========================================================================
    # JSON Export
    # =========================================================================

    def _export_to_json(self, films: list[AggregatedFilm]) -> Path:
        """Export aggregated films to JSON file.

        Args:
            films: Films to export.

        Returns:
            Path to created JSON file.
        """
        self._logger.info("Stage 3: Exporting to JSON...")

        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / DEFAULT_OUTPUT_FILENAME

        export_data = self._build_export_data(films)
        self._write_json(export_data, output_path)

        self._logger.info(f"Exported {len(films)} films to {output_path}")
        return output_path

    def _build_export_data(self, films: list[AggregatedFilm]) -> dict[str, Any]:
        """Build export data structure.

        Args:
            films: Films to include.

        Returns:
            Export data dictionary.
        """
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "count": len(films),
            "avg_aggregated_score": self._result.avg_score,
            "rt_coverage_percent": self._result.rt_coverage,
            "films": [self._film_to_dict(f) for f in films],
        }

    @staticmethod
    def _film_to_dict(film: AggregatedFilm) -> dict[str, Any]:
        """Convert film to dictionary with serialization.

        Args:
            film: Film to convert.

        Returns:
            Serializable dictionary.
        """
        data = film.model_dump()
        if data.get("release_date"):
            data["release_date"] = data["release_date"].isoformat()
        # Add RAG text for convenience
        data["rag_text"] = film.rag_text
        return data

    @staticmethod
    def _write_json(data: dict[str, Any], path: Path) -> None:
        """Write data to JSON file.

        Args:
            data: Data to write.
            path: Target file path.
        """
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=JSON_INDENT, ensure_ascii=False, default=str)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_session(self) -> Session:
        """Get or create database session.

        Returns:
            SQLAlchemy session.
        """
        if self._session is None:
            self._session = get_database().get_sync_session()
        return self._session

    def _handle_error(self, error: Exception) -> None:
        """Handle pipeline error.

        Args:
            error: Exception that occurred.
        """
        self._logger.error(f"Pipeline failed: {error}")
        self._result.error_messages.append(str(error))

    @staticmethod
    def _calculate_duration(start_time: datetime) -> float:
        """Calculate duration since start.

        Args:
            start_time: Pipeline start time.

        Returns:
            Duration in seconds.
        """
        return (datetime.now() - start_time).total_seconds()

    # =========================================================================
    # Logging
    # =========================================================================

    def _log_start(self) -> None:
        """Log pipeline start."""
        self._logger.info("=" * 60)
        self._logger.info("Starting Aggregation Pipeline (Step 6)")
        self._logger.info("=" * 60)
        self._logger.info(f"Output directory: {self._output_dir}")

    def _log_final_results(self) -> None:
        """Log pipeline results summary."""
        self._logger.info("=" * 60)
        self._logger.info("Aggregation Pipeline Complete")
        self._logger.info("=" * 60)
        self._logger.info(f"Films read: {self._result.films_read}")
        self._logger.info(f"Films with RT: {self._result.films_with_rt}")
        self._logger.info(f"RT coverage: {self._result.rt_coverage}%")
        self._logger.info(f"Films exported: {self._result.films_exported}")
        self._logger.info(f"Average score: {self._result.avg_score}")
        self._logger.info(f"Output: {self._result.output_path}")
        self._logger.info(f"Duration: {self._result.duration_seconds:.1f}s")


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================


def run_aggregation_pipeline(
    limit: int | None = None,
    output_dir: Path | None = None,
) -> AggregationPipelineResult:
    """Run aggregation pipeline.

    Args:
        limit: Max films to process.
        output_dir: Output directory for JSON.

    Returns:
        AggregationPipelineResult with statistics.
    """
    pipeline = AggregationPipeline(output_dir=output_dir)
    return pipeline.run(limit=limit)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """Entry point for aggregation pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Aggregation Pipeline (Step 6)")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max films to process",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for JSON",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    result = run_aggregation_pipeline(limit=args.limit, output_dir=output_dir)

    _print_results(result)


def _print_results(result: AggregationPipelineResult) -> None:
    """Print pipeline results to stdout.

    Args:
        result: Pipeline execution result.
    """
    print(f"\nFilms read: {result.films_read}")
    print(f"Films with RT: {result.films_with_rt} ({result.rt_coverage}%)")
    print(f"Films exported: {result.films_exported}")
    print(f"Average score: {result.avg_score}")
    print(f"Output: {result.output_path}")
    print(f"Duration: {result.duration_seconds:.1f}s")

    if result.error_messages:
        print(f"Errors: {len(result.error_messages)}")


if __name__ == "__main__":
    main()

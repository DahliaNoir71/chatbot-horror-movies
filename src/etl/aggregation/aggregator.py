"""Main aggregator orchestrator for ETL pipeline.

Coordinates merger, deduplicator, and score calculator
to produce final RAG-ready JSON dataset.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.etl.aggregation.deduplicator import Deduplicator
from src.etl.aggregation.merger import DataMerger
from src.etl.aggregation.schemas import AggregatedFilm
from src.etl.aggregation.score_calculator import ScoreCalculator

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_OUTPUT_FILENAME = "aggregated_films.json"
"""Default output filename for JSON export."""

JSON_INDENT = 2
"""JSON indentation for readable output."""


# =============================================================================
# AGGREGATION STATISTICS
# =============================================================================


@dataclass
class AggregationStats:
    """Complete aggregation pipeline statistics.

    Attributes:
        start_time: Pipeline start timestamp.
        end_time: Pipeline end timestamp.
        input_tmdb: TMDB films received.
        input_rt: RT enrichments received.
        input_imdb: IMDB enrichments received.
        input_kaggle: Kaggle enrichments received.
        input_spark: Spark enrichments received.
        after_merge: Films after merge.
        after_dedup: Films after deduplication.
        final_count: Final output count.
    """

    start_time: datetime | None = None
    end_time: datetime | None = None
    input_tmdb: int = 0
    input_rt: int = 0
    input_imdb: int = 0
    input_kaggle: int = 0
    input_spark: int = 0
    after_merge: int = 0
    after_dedup: int = 0
    final_count: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate pipeline duration in seconds."""
        if not self.start_time or not self.end_time:
            return 0.0
        delta = self.end_time - self.start_time
        return round(delta.total_seconds(), 2)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for JSON export."""
        return {
            "duration_seconds": self.duration_seconds,
            "input": {
                "tmdb": self.input_tmdb,
                "rotten_tomatoes": self.input_rt,
                "imdb": self.input_imdb,
                "kaggle": self.input_kaggle,
                "spark": self.input_spark,
            },
            "pipeline": {
                "after_merge": self.after_merge,
                "after_dedup": self.after_dedup,
                "final_count": self.final_count,
            },
        }

    def log_summary(self) -> None:
        """Log complete aggregation summary."""
        logger.info(
            "Aggregation complete in %.2fs: %d films (merged=%d, deduped=%d)",
            self.duration_seconds,
            self.final_count,
            self.after_merge,
            self.after_dedup,
        )


# =============================================================================
# MAIN AGGREGATOR
# =============================================================================


class Aggregator:
    """Main orchestrator for multi-source data aggregation.

    Pipeline stages:
    1. Merge: Combine TMDB + RT + IMDB + Kaggle + Spark
    2. Deduplicate: Remove duplicates by ID and fuzzy match
    3. Score: Calculate weighted aggregated scores
    4. Export: Output to JSON for RAG ingestion

    Attributes:
        stats: Pipeline execution statistics.
    """

    def __init__(self) -> None:
        """Initialize aggregator with component instances."""
        self.stats = AggregationStats()
        self._merger = DataMerger()
        self._deduplicator = Deduplicator()
        self._score_calculator = ScoreCalculator()

    # =========================================================================
    # Public API
    # =========================================================================

    def aggregate(
        self,
        tmdb_films: list[dict[str, Any]],
        rt_data: list[dict[str, Any]] | None = None,
        imdb_data: list[dict[str, Any]] | None = None,
        kaggle_data: list[dict[str, Any]] | None = None,
        spark_data: list[dict[str, Any]] | None = None,
    ) -> list[AggregatedFilm]:
        """Execute full aggregation pipeline.

        Args:
            tmdb_films: Primary TMDB film data (required).
            rt_data: Rotten Tomatoes enrichment.
            imdb_data: IMDB enrichment.
            kaggle_data: Kaggle CSV enrichment.
            spark_data: Spark Big Data enrichment.

        Returns:
            List of aggregated, deduplicated, scored films.
        """
        self._start_pipeline()
        self._record_inputs(tmdb_films, rt_data, imdb_data, kaggle_data, spark_data)

        films = self._execute_merge(tmdb_films, rt_data, imdb_data, kaggle_data, spark_data)
        films = self._execute_deduplication(films)
        films = self._execute_scoring(films)

        self._finish_pipeline(films)
        return films

    def export_json(
        self,
        films: list[AggregatedFilm],
        output_path: Path | None = None,
        include_stats: bool = True,
    ) -> Path:
        """Export aggregated films to JSON file.

        Args:
            films: Films to export.
            output_path: Target path (default: data/processed/).
            include_stats: Include pipeline stats in output.

        Returns:
            Path to created JSON file.
        """
        output_path = self._resolve_output_path(output_path)
        data = self._build_export_data(films, include_stats)
        self._write_json(data, output_path)
        return output_path

    def to_dicts(self, films: list[AggregatedFilm]) -> list[dict[str, Any]]:
        """Convert films to list of dictionaries.

        Args:
            films: Films to convert.

        Returns:
            List of film dictionaries.
        """
        return [self._film_to_dict(film) for film in films]

    # =========================================================================
    # Pipeline Execution
    # =========================================================================

    def _start_pipeline(self) -> None:
        """Initialize pipeline execution."""
        self.stats = AggregationStats()
        self.stats.start_time = datetime.now(UTC)
        logger.info("Starting aggregation pipeline")

    def _finish_pipeline(self, films: list[AggregatedFilm]) -> None:
        """Finalize pipeline execution."""
        self.stats.end_time = datetime.now(UTC)
        self.stats.final_count = len(films)
        self.stats.log_summary()

    def _record_inputs(
        self,
        tmdb_films: list[dict[str, Any]],
        rt_data: list[dict[str, Any]] | None,
        imdb_data: list[dict[str, Any]] | None,
        kaggle_data: list[dict[str, Any]] | None,
        spark_data: list[dict[str, Any]] | None,
    ) -> None:
        """Record input counts for statistics."""
        self.stats.input_tmdb = len(tmdb_films)
        self.stats.input_rt = len(rt_data) if rt_data else 0
        self.stats.input_imdb = len(imdb_data) if imdb_data else 0
        self.stats.input_kaggle = len(kaggle_data) if kaggle_data else 0
        self.stats.input_spark = len(spark_data) if spark_data else 0

    def _execute_merge(
        self,
        tmdb_films: list[dict[str, Any]],
        rt_data: list[dict[str, Any]] | None,
        imdb_data: list[dict[str, Any]] | None,
        kaggle_data: list[dict[str, Any]] | None,
        spark_data: list[dict[str, Any]] | None,
    ) -> list[AggregatedFilm]:
        """Execute merge stage."""
        logger.info("Stage 1: Merging %d TMDB films", len(tmdb_films))
        films = self._merger.merge(tmdb_films, rt_data, imdb_data, kaggle_data, spark_data)
        self.stats.after_merge = len(films)
        return films

    def _execute_deduplication(self, films: list[AggregatedFilm]) -> list[AggregatedFilm]:
        """Execute deduplication stage."""
        logger.info("Stage 2: Deduplicating %d films", len(films))
        films = self._deduplicator.deduplicate(films)
        self.stats.after_dedup = len(films)
        return films

    def _execute_scoring(self, films: list[AggregatedFilm]) -> list[AggregatedFilm]:
        """Execute scoring stage."""
        logger.info("Stage 3: Calculating scores for %d films", len(films))
        return self._score_calculator.calculate_scores(films)

    # =========================================================================
    # JSON Export
    # =========================================================================

    @staticmethod
    def _resolve_output_path(output_path: Path | None) -> Path:
        """Resolve and create output path.

        Args:
            output_path: Provided path or None for default.

        Returns:
            Resolved output path.
        """
        if output_path is None:
            output_path = Path("data/processed") / DEFAULT_OUTPUT_FILENAME
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path

    def _build_export_data(
        self, films: list[AggregatedFilm], include_stats: bool
    ) -> dict[str, Any]:
        """Build export data structure.

        Args:
            films: Films to include.
            include_stats: Whether to include stats.

        Returns:
            Export data dictionary.
        """
        data: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "count": len(films),
            "films": self.to_dicts(films),
        }
        if include_stats:
            data["stats"] = self.stats.to_dict()
        return data

    @staticmethod
    def _write_json(data: dict[str, Any], output_path: Path) -> None:
        """Write data to JSON file.

        Args:
            data: Data to write.
            output_path: Target file path.
        """
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=JSON_INDENT, ensure_ascii=False, default=str)
        logger.info("Exported %d films to %s", data["count"], output_path)

    @staticmethod
    def _film_to_dict(film: AggregatedFilm) -> dict[str, Any]:
        """Convert single film to dictionary.

        Args:
            film: Film to convert.

        Returns:
            Film as dictionary with date serialization.
        """
        data = film.model_dump()
        # Convert date to ISO string for JSON
        if data.get("release_date"):
            data["release_date"] = data["release_date"].isoformat()
        return data

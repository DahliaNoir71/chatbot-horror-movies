"""Multi-source data merger for film aggregation.

Merges film data from TMDB, Rotten Tomatoes, IMDB, Kaggle and Spark
sources using tmdb_id as primary key and imdb_id as fallback.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from src.etl.aggregation.schemas import (
    AggregatedFilm,
    IMDBFilmData,
    KaggleFilmData,
    RTEnrichmentData,
    SparkFilmData,
    TMDBFilmData,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

SOURCE_TMDB = "tmdb"
SOURCE_RT = "rotten_tomatoes"
SOURCE_IMDB = "imdb"
SOURCE_KAGGLE = "kaggle"
SOURCE_SPARK = "spark"


# =============================================================================
# MERGE STATISTICS
# =============================================================================


@dataclass
class MergeStats:
    """Statistics for merge operations.

    Attributes:
        total_tmdb: Total TMDB films processed.
        merged_rt: Films enriched with RT data.
        merged_imdb: Films enriched with IMDB data.
        merged_kaggle: Films enriched with Kaggle data.
        merged_spark: Films enriched with Spark data.
        failed_validations: Films that failed validation.
    """

    total_tmdb: int = 0
    merged_rt: int = 0
    merged_imdb: int = 0
    merged_kaggle: int = 0
    merged_spark: int = 0
    failed_validations: int = 0

    def log_summary(self) -> None:
        """Log merge statistics summary."""
        logger.info(
            "Merge complete: %d TMDB films, RT=%d, IMDB=%d, Kaggle=%d, Spark=%d",
            self.total_tmdb,
            self.merged_rt,
            self.merged_imdb,
            self.merged_kaggle,
            self.merged_spark,
        )


# =============================================================================
# INDEX BUILDER
# =============================================================================


@dataclass
class SourceIndex:
    """Index for fast lookup by tmdb_id and imdb_id.

    Attributes:
        by_tmdb_id: Mapping of tmdb_id to source data.
        by_imdb_id: Mapping of imdb_id to source data.
    """

    by_tmdb_id: dict[int, dict[str, Any]] = field(default_factory=dict)
    by_imdb_id: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, data: dict[str, Any]) -> None:
        """Add data to index by available identifiers.

        Args:
            data: Source data with tmdb_id and/or imdb_id.
        """
        tmdb_id = data.get("tmdb_id")
        imdb_id = data.get("imdb_id")

        if tmdb_id:
            self.by_tmdb_id[tmdb_id] = data
        if imdb_id:
            self.by_imdb_id[imdb_id] = data

    def find(self, tmdb_id: int | None, imdb_id: str | None) -> dict[str, Any] | None:
        """Find data by tmdb_id (priority) or imdb_id (fallback).

        Args:
            tmdb_id: TMDB identifier to search.
            imdb_id: IMDB identifier as fallback.

        Returns:
            Source data if found, None otherwise.
        """
        if tmdb_id and tmdb_id in self.by_tmdb_id:
            return self.by_tmdb_id[tmdb_id]
        if imdb_id and imdb_id in self.by_imdb_id:
            return self.by_imdb_id[imdb_id]
        return None


# =============================================================================
# DATA MERGER
# =============================================================================


class DataMerger:
    """Merges film data from multiple sources.

    Uses TMDB as primary source and enriches with data from
    RT, IMDB, Kaggle, and Spark sources.

    Attributes:
        stats: Merge operation statistics.
    """

    def __init__(self) -> None:
        """Initialize merger with empty statistics."""
        self.stats = MergeStats()
        self._rt_index: SourceIndex = SourceIndex()
        self._imdb_index: SourceIndex = SourceIndex()
        self._kaggle_index: SourceIndex = SourceIndex()
        self._spark_index: SourceIndex = SourceIndex()

    # =========================================================================
    # Public API
    # =========================================================================

    def merge(
        self,
        tmdb_films: list[dict[str, Any]],
        rt_data: list[dict[str, Any]] | None = None,
        imdb_data: list[dict[str, Any]] | None = None,
        kaggle_data: list[dict[str, Any]] | None = None,
        spark_data: list[dict[str, Any]] | None = None,
    ) -> list[AggregatedFilm]:
        """Merge all sources into unified film records.

        Args:
            tmdb_films: Primary film data from TMDB (required).
            rt_data: Rotten Tomatoes enrichment data.
            imdb_data: IMDB enrichment data.
            kaggle_data: Kaggle CSV enrichment data.
            spark_data: Spark Big Data enrichment data.

        Returns:
            List of aggregated films with all available enrichments.
        """
        self._reset_state()
        self._build_indices(rt_data, imdb_data, kaggle_data, spark_data)

        aggregated: list[AggregatedFilm] = []
        for tmdb_dict in tmdb_films:
            film = self._process_tmdb_film(tmdb_dict)
            if film:
                aggregated.append(film)

        self.stats.log_summary()
        return aggregated

    # =========================================================================
    # Index Building
    # =========================================================================

    def _reset_state(self) -> None:
        """Reset internal state for new merge operation."""
        self.stats = MergeStats()
        self._rt_index = SourceIndex()
        self._imdb_index = SourceIndex()
        self._kaggle_index = SourceIndex()
        self._spark_index = SourceIndex()

    def _build_indices(
        self,
        rt_data: list[dict[str, Any]] | None,
        imdb_data: list[dict[str, Any]] | None,
        kaggle_data: list[dict[str, Any]] | None,
        spark_data: list[dict[str, Any]] | None,
    ) -> None:
        """Build lookup indices for all enrichment sources.

        Args:
            rt_data: Rotten Tomatoes data to index.
            imdb_data: IMDB data to index.
            kaggle_data: Kaggle data to index.
            spark_data: Spark data to index.
        """
        self._index_source(rt_data, self._rt_index, "RT")
        self._index_source(imdb_data, self._imdb_index, "IMDB")
        self._index_source(kaggle_data, self._kaggle_index, "Kaggle")
        self._index_source(spark_data, self._spark_index, "Spark")

    @staticmethod
    def _index_source(
        data: list[dict[str, Any]] | None,
        index: SourceIndex,
        source_name: str,
    ) -> None:
        """Index a single source for fast lookup.

        Args:
            data: Source data to index.
            index: Target index to populate.
            source_name: Name for logging.
        """
        if not data:
            return
        for item in data:
            index.add(item)
        logger.debug("Indexed %d %s records", len(data), source_name)

    # =========================================================================
    # Film Processing
    # =========================================================================

    def _process_tmdb_film(self, tmdb_dict: dict[str, Any]) -> AggregatedFilm | None:
        """Process single TMDB film with all enrichments.

        Args:
            tmdb_dict: Raw TMDB film data.

        Returns:
            Aggregated film or None if validation fails.
        """
        tmdb_film = self._validate_tmdb(tmdb_dict)
        if not tmdb_film:
            self.stats.failed_validations += 1
            return None

        self.stats.total_tmdb += 1
        merged = self._create_base_record(tmdb_film)

        self._enrich_with_rt(merged, tmdb_film)
        self._enrich_with_imdb(merged, tmdb_film)
        self._enrich_with_kaggle(merged, tmdb_film)
        self._enrich_with_spark(merged, tmdb_film)

        return self._finalize_record(merged)

    @staticmethod
    def _validate_tmdb(tmdb_dict: dict[str, Any]) -> TMDBFilmData | None:
        """Validate TMDB data against schema.

        Args:
            tmdb_dict: Raw TMDB data.

        Returns:
            Validated TMDBFilmData or None if invalid.
        """
        try:
            return TMDBFilmData.model_validate(tmdb_dict)
        except Exception as e:
            logger.warning("TMDB validation failed: %s", e)
            return None

    @staticmethod
    def _create_base_record(tmdb: TMDBFilmData) -> dict[str, Any]:
        """Create base aggregated record from TMDB data.

        Args:
            tmdb: Validated TMDB film data.

        Returns:
            Base record dict for enrichment.
        """
        return {
            "tmdb_id": tmdb.tmdb_id,
            "imdb_id": tmdb.imdb_id,
            "title": tmdb.title,
            "original_title": tmdb.original_title,
            "release_date": tmdb.release_date,
            "overview": tmdb.overview,
            "tagline": tmdb.tagline,
            "popularity": tmdb.popularity,
            "vote_average": tmdb.vote_average,
            "vote_count": tmdb.vote_count,
            "runtime": tmdb.runtime,
            "original_language": tmdb.original_language,
            "adult": tmdb.adult,
            "status": tmdb.status,
            "poster_path": tmdb.poster_path,
            "backdrop_path": tmdb.backdrop_path,
            "homepage": tmdb.homepage,
            "budget": tmdb.budget,
            "revenue": tmdb.revenue,
            "genres": tmdb.genres,
            "keywords": tmdb.keywords,
            "sources": [SOURCE_TMDB],
        }

    # =========================================================================
    # Source Enrichment
    # =========================================================================

    def _enrich_with_rt(self, merged: dict[str, Any], tmdb: TMDBFilmData) -> None:
        """Enrich with Rotten Tomatoes data.

        Args:
            merged: Record to enrich.
            tmdb: TMDB film for identifier lookup.
        """
        rt_dict = self._rt_index.find(tmdb.tmdb_id, tmdb.imdb_id)
        if not rt_dict:
            return

        rt_data = self._validate_rt(rt_dict)
        if not rt_data:
            return

        self._apply_rt_fields(merged, rt_data)
        merged["sources"].append(SOURCE_RT)
        self.stats.merged_rt += 1

    @staticmethod
    def _validate_rt(rt_dict: dict[str, Any]) -> RTEnrichmentData | None:
        """Validate RT data against schema.

        Args:
            rt_dict: Raw RT data.

        Returns:
            Validated RTEnrichmentData or None.
        """
        try:
            return RTEnrichmentData.model_validate(rt_dict)
        except Exception as e:
            logger.debug("RT validation failed: %s", e)
            return None

    @staticmethod
    def _apply_rt_fields(merged: dict[str, Any], rt: RTEnrichmentData) -> None:
        """Apply RT fields to merged record.

        Args:
            merged: Target record.
            rt: Validated RT data.
        """
        merged["tomatometer_score"] = rt.tomatometer_score
        merged["tomatometer_state"] = rt.tomatometer_state
        merged["audience_score"] = rt.audience_score
        merged["critics_count"] = rt.critics_count
        merged["audience_count"] = rt.audience_count
        merged["critics_consensus"] = rt.critics_consensus
        merged["rt_url"] = rt.rt_url

    def _enrich_with_imdb(self, merged: dict[str, Any], tmdb: TMDBFilmData) -> None:
        """Enrich with IMDB data.

        Args:
            merged: Record to enrich.
            tmdb: TMDB film for identifier lookup.
        """
        imdb_dict = self._imdb_index.find(tmdb.tmdb_id, tmdb.imdb_id)
        if not imdb_dict:
            return

        imdb_data = self._validate_imdb(imdb_dict)
        if not imdb_data:
            return

        self._apply_imdb_fields(merged, imdb_data)
        merged["sources"].append(SOURCE_IMDB)
        self.stats.merged_imdb += 1

    @staticmethod
    def _validate_imdb(imdb_dict: dict[str, Any]) -> IMDBFilmData | None:
        """Validate IMDB data against schema.

        Args:
            imdb_dict: Raw IMDB data.

        Returns:
            Validated IMDBFilmData or None.
        """
        try:
            return IMDBFilmData.model_validate(imdb_dict)
        except Exception as e:
            logger.debug("IMDB validation failed: %s", e)
            return None

    @staticmethod
    def _apply_imdb_fields(merged: dict[str, Any], imdb: IMDBFilmData) -> None:
        """Apply IMDB fields to merged record.

        Args:
            merged: Target record.
            imdb: Validated IMDB data.
        """
        merged["imdb_rating"] = imdb.imdb_rating
        merged["imdb_votes"] = imdb.imdb_votes
        # Fill imdb_id if missing from TMDB
        if not merged.get("imdb_id"):
            merged["imdb_id"] = imdb.imdb_id

    def _enrich_with_kaggle(self, merged: dict[str, Any], tmdb: TMDBFilmData) -> None:
        """Enrich with Kaggle data.

        Args:
            merged: Record to enrich.
            tmdb: TMDB film for identifier lookup.
        """
        kaggle_dict = self._kaggle_index.find(tmdb.tmdb_id, tmdb.imdb_id)
        if not kaggle_dict:
            return

        kaggle_data = self._validate_kaggle(kaggle_dict)
        if not kaggle_data:
            return

        self._apply_kaggle_fields(merged, kaggle_data)
        merged["sources"].append(SOURCE_KAGGLE)
        self.stats.merged_kaggle += 1

    @staticmethod
    def _validate_kaggle(kaggle_dict: dict[str, Any]) -> KaggleFilmData | None:
        """Validate Kaggle data against schema.

        Args:
            kaggle_dict: Raw Kaggle data.

        Returns:
            Validated KaggleFilmData or None.
        """
        try:
            return KaggleFilmData.model_validate(kaggle_dict)
        except Exception as e:
            logger.debug("Kaggle validation failed: %s", e)
            return None

    @staticmethod
    def _apply_kaggle_fields(merged: dict[str, Any], kaggle: KaggleFilmData) -> None:
        """Apply Kaggle fields to merged record.

        Args:
            merged: Target record.
            kaggle: Validated Kaggle data.
        """
        merged["kaggle_rating"] = kaggle.rating
        # Fill overview if missing
        if not merged.get("overview") and kaggle.overview:
            merged["overview"] = kaggle.overview

    def _enrich_with_spark(self, merged: dict[str, Any], tmdb: TMDBFilmData) -> None:
        """Enrich with Spark data.

        Args:
            merged: Record to enrich.
            tmdb: TMDB film for identifier lookup.
        """
        spark_dict = self._spark_index.find(tmdb.tmdb_id, tmdb.imdb_id)
        if not spark_dict:
            return

        spark_data = self._validate_spark(spark_dict)
        if not spark_data:
            return

        self._apply_spark_fields(merged, spark_data)
        merged["sources"].append(SOURCE_SPARK)
        self.stats.merged_spark += 1

    @staticmethod
    def _validate_spark(spark_dict: dict[str, Any]) -> SparkFilmData | None:
        """Validate Spark data against schema.

        Args:
            spark_dict: Raw Spark data.

        Returns:
            Validated SparkFilmData or None.
        """
        try:
            return SparkFilmData.model_validate(spark_dict)
        except Exception as e:
            logger.debug("Spark validation failed: %s", e)
            return None

    @staticmethod
    def _apply_spark_fields(merged: dict[str, Any], spark: SparkFilmData) -> None:
        """Apply Spark fields to merged record.

        Args:
            merged: Target record.
            spark: Validated Spark data.
        """
        merged["spark_rating"] = spark.rating

    # =========================================================================
    # Finalization
    # =========================================================================

    def _finalize_record(self, merged: dict[str, Any]) -> AggregatedFilm | None:
        """Finalize and validate aggregated record.

        Args:
            merged: Merged data dict.

        Returns:
            Validated AggregatedFilm or None.
        """
        merged["enrichment_count"] = len(merged.get("sources", []))
        try:
            return AggregatedFilm.model_validate(merged)
        except Exception as e:
            logger.warning("Final validation failed for %s: %s", merged.get("title"), e)
            self.stats.failed_validations += 1
            return None

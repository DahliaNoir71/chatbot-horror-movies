"""Aggregation module for multi-source film data fusion.

This module provides tools for merging, deduplicating, and scoring
film data from TMDB, Rotten Tomatoes, IMDB, Kaggle, and Spark sources.

Example:
    >>> from src.etl.aggregation import Aggregator
    >>> aggregator = Aggregator()
    >>> films = aggregator.aggregate(tmdb_films, rt_data=rt_enrichments)
    >>> aggregator.export_json(films, Path("output.json"))
"""

from src.etl.aggregation.aggregator import AggregationStats, Aggregator
from src.etl.aggregation.deduplicator import DeduplicationStats, Deduplicator
from src.etl.aggregation.merger import DataMerger, MergeStats
from src.etl.aggregation.schemas import (
    IMDB_ID_PATTERN,
    AggregatedFilm,
    IMDBFilmData,
    KaggleFilmData,
    RTEnrichmentData,
    SparkFilmData,
    TMDBFilmData,
)
from src.etl.aggregation.score_calculator import ScoreCalculator, ScoreStats

__all__ = [
    # Main orchestrator
    "Aggregator",
    "AggregationStats",
    # Components
    "DataMerger",
    "MergeStats",
    "Deduplicator",
    "DeduplicationStats",
    "ScoreCalculator",
    "ScoreStats",
    # Schemas
    "AggregatedFilm",
    "TMDBFilmData",
    "RTEnrichmentData",
    "IMDBFilmData",
    "KaggleFilmData",
    "SparkFilmData",
    "IMDB_ID_PATTERN",
]

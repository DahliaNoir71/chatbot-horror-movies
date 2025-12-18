"""ETL Pipeline package for HorrorBot - 7 heterogeneous sources.

This package provides the complete ETL pipeline implementation
for extracting, transforming and loading horror film data from:
    1. TMDB API (REST)
    2. Rotten Tomatoes (Web scraping)
    3. Spotify API (REST OAuth2)
    4. YouTube Data API v3 (REST)
    5. Kaggle CSV (File)
    6. PostgreSQL IMDB (External DB)
    7. Polars (BigData aggregation)

Public API:
    - run_full_pipeline: Execute complete pipeline
    - resume_from_step: Resume from checkpoint
    - extract_single_source: Extract single source
    - main: CLI entry point
"""

from src.etl.pipeline.cli import main
from src.etl.pipeline.helpers import checkpoint_manager
from src.etl.pipeline.orchestrator import (
    extract_single_source,
    resume_from_step,
    run_full_pipeline,
)

__all__ = [
    "run_full_pipeline",
    "resume_from_step",
    "extract_single_source",
    "checkpoint_manager",
    "main",
]

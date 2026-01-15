"""ETL pipelines package.

Contains all extraction pipelines for E1 validation:
- TMDB: REST API extraction (Source 1)
- Kaggle: CSV file processing (Source 2)
- Spark: Big Data extraction - C1/C2 (Source 3)
- IMDB: SQLite extraction - C2 (Source 4)
- RT: Web scraping enrichment (Source 5)

Usage:
    # Run all pipelines (stops on any failure)
    python -m src.etl.pipelines.main

    # Run single pipelines
    python -m src.etl.pipelines.main --only spark

    # Skip specific pipelines
    python -m src.etl.pipelines.main --skip-rt --skip-imdb
"""

from src.etl.pipelines.main import (
    ETLOrchestrator,
    OrchestratorResult,
    PipelineStatus,
    PipelineStepResult,
    run_all_pipelines,
)

__all__ = [
    "ETLOrchestrator",
    "OrchestratorResult",
    "PipelineStatus",
    "PipelineStepResult",
    "run_all_pipelines",
]

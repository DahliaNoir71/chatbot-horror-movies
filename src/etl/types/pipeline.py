"""ETL pipelines data types.

TypedDict definitions for pipelines control structures,
checkpoints, and results.
"""

from typing import NotRequired, TypedDict

from src.etl.types.normalized import NormalizedCreditData


class ETLResult(TypedDict):
    """Result of an ETL extraction step."""

    source: str
    success: bool
    count: int
    errors: NotRequired[list[str]]
    duration_seconds: NotRequired[float]


class ETLCheckpoint(TypedDict):
    """Checkpoint data for resumable ETL.

    Stores progress state to allow resumption after
    interruption or failure.
    """

    source: str
    last_page: NotRequired[int]
    last_year: NotRequired[int]
    last_id: NotRequired[int | str]
    processed_ids: NotRequired[list[int]]
    timestamp: str
    source_type: NotRequired[str]
    source_id: NotRequired[str]


class ETLRunConfig(TypedDict):
    """Configuration for an ETL run."""

    sources: list[str]
    year_min: NotRequired[int]
    year_max: NotRequired[int]
    max_films: NotRequired[int]
    enrich: NotRequired[bool]
    resume: NotRequired[bool]


class ETLProgress(TypedDict):
    """Progress tracking for ETL run."""

    source: str
    current: int
    total: int
    percentage: float
    elapsed_seconds: float
    eta_seconds: NotRequired[float]


class FilmMatchResult(TypedDict):
    """Result of matching a video to a film."""

    film_id: int
    video_id: int
    match_score: float
    match_method: str
    matched_title: str


class FilmMatchCandidate(TypedDict):
    """Candidate for film-video matching."""

    film_id: int
    title: str
    year: int | None
    score: float


class ExtractionStats(TypedDict):
    """Statistics for extraction phase."""

    total_extracted: int
    new_records: int
    updated_records: int
    skipped: int
    errors: int
    duration_seconds: float


class TransformationStats(TypedDict):
    """Statistics for transformation phase."""

    total_processed: int
    valid: int
    invalid: int
    cleaned: int
    duration_seconds: float


class LoadStats(TypedDict):
    """Statistics for load phase."""

    total_loaded: int
    inserted: int
    updated: int
    failed: int
    duration_seconds: float


class ETLPipelineStats(TypedDict):
    """Complete statistics for ETL pipelines run."""

    run_id: str
    started_at: str
    completed_at: NotRequired[str]
    status: str
    extraction: NotRequired[ExtractionStats]
    transformation: NotRequired[TransformationStats]
    load: NotRequired[LoadStats]
    total_duration_seconds: NotRequired[float]


class CreditLoadInput(TypedDict):
    """Input data structure for CreditLoader.load().

    Bundles credits list and film_id into a single parameter
    to match BaseLoader.load(data: object) signature.

    Attributes:
        credits: List of normalized credit data.
        film_id: Internal database film ID.
    """

    credits: list[NormalizedCreditData]
    film_id: int


class FilmToEnrich(TypedDict):
    """Film data for enrichment pipelines (RT).

    Attributes:
        id: Internal database film ID.
        title: Film title.
        original_title: Alternative title (for search fallback).
        year: Release year (for search validation).
    """

    id: int
    title: str
    original_title: str | None
    year: int | None

"""ETL pipeline data types.

TypedDict definitions for pipeline control structures,
checkpoints, and results.
"""

from typing import NotRequired, TypedDict


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
    """Complete statistics for ETL pipeline run."""

    run_id: str
    started_at: str
    completed_at: NotRequired[str]
    status: str
    extraction: NotRequired[ExtractionStats]
    transformation: NotRequired[TransformationStats]
    load: NotRequired[LoadStats]
    total_duration_seconds: NotRequired[float]

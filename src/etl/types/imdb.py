"""IMDB SQLite data types.

TypedDict definitions for data structures extracted
from IMDB SQLite database (imdb-sqlite package).
"""

from typing import NotRequired, TypedDict


class IMDBTitleRaw(TypedDict):
    """Raw title data from IMDB titles table.

    Attributes:
        title_id: IMDB tconst (e.g., 'tt0078748').
        type: Title type (movie, tvSeries, etc.).
        primary_title: Display title.
        original_title: Original language title.
        is_adult: Adult content flag.
        premiered: Release year.
        ended: End year (for series).
        runtime_minutes: Duration in minutes.
        genres: Comma-separated genre list.
    """

    title_id: str
    type: str
    primary_title: str
    original_title: NotRequired[str | None]
    is_adult: NotRequired[int | None]
    premiered: NotRequired[int | None]
    ended: NotRequired[int | None]
    runtime_minutes: NotRequired[int | None]
    genres: NotRequired[str | None]


class IMDBRatingRaw(TypedDict):
    """Raw rating data from IMDB ratings table.

    Attributes:
        title_id: IMDB tconst.
        rating: Average rating (0-10).
        votes: Number of votes.
    """

    title_id: str
    rating: float
    votes: int


class IMDBCrewRaw(TypedDict):
    """Raw crew data from IMDB crew table.

    Attributes:
        title_id: IMDB tconst.
        directors: Comma-separated director nconsts.
        writers: Comma-separated writer nconsts.
    """

    title_id: str
    directors: NotRequired[str | None]
    writers: NotRequired[str | None]


class IMDBPrincipalRaw(TypedDict):
    """Raw principal (cast/crew) data from IMDB principals table.

    Attributes:
        title_id: IMDB tconst.
        ordering: Display order.
        name_id: IMDB nconst.
        category: Role category (actor, director, etc.).
        job: Specific job title.
        characters: Character names (JSON array as string).
    """

    title_id: str
    ordering: int
    name_id: str
    category: NotRequired[str | None]
    job: NotRequired[str | None]
    characters: NotRequired[str | None]


class IMDBNameRaw(TypedDict):
    """Raw name data from IMDB names table.

    Attributes:
        name_id: IMDB nconst (e.g., 'nm0000229').
        primary_name: Person's name.
        birth_year: Year of birth.
        death_year: Year of death (if applicable).
        primary_profession: Comma-separated professions.
        known_for_titles: Comma-separated tconsts.
    """

    name_id: str
    primary_name: str
    birth_year: NotRequired[int | None]
    death_year: NotRequired[int | None]
    primary_profession: NotRequired[str | None]
    known_for_titles: NotRequired[str | None]


class IMDBHorrorMovieJoined(TypedDict):
    """Joined horror movie data from SQL query.

    Result of JOIN between titles, ratings, and crew tables
    filtered for horror genre.

    Attributes:
        imdb_id: IMDB tconst (tt format).
        title: Primary title.
        original_title: Original language title.
        year: Release year.
        runtime: Duration in minutes.
        genres: Genre list.
        rating: Average IMDB rating.
        votes: Number of votes.
        directors: Director nconsts.
        writers: Writer nconsts.
    """

    imdb_id: str
    title: str
    original_title: str | None
    year: int | None
    runtime: int | None
    genres: str | None
    rating: float | None
    votes: int | None
    directors: str | None
    writers: str | None


class IMDBNormalized(TypedDict):
    """Normalized IMDB data for database enrichment.

    Used to enrich existing films with IMDB ratings
    and link via imdb_id.

    Attributes:
        imdb_id: IMDB tconst for matching.
        imdb_rating: IMDB average rating.
        imdb_votes: IMDB vote count.
        runtime: Runtime in minutes (if missing).
    """

    imdb_id: str
    imdb_rating: float
    imdb_votes: int
    runtime: int | None


class IMDBExtractionResult(TypedDict):
    """Result of IMDB extraction operation."""

    total_titles: int
    horror_movies: int
    with_ratings: int
    matched_films: int
    duration_seconds: float


class IMDBEnrichmentStats(TypedDict):
    """Statistics for IMDB enrichment operation."""

    films_matched: int
    ratings_updated: int
    runtime_updated: int
    not_found: int
    errors: int

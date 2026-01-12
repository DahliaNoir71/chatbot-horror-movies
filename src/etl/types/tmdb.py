"""TMDB API data types.

TypedDict definitions for data structures returned by
The Movie Database (TMDB) API endpoints.
"""

from typing import NotRequired, TypedDict


class TMDBGenreData(TypedDict):
    """Genre data from TMDB API."""

    id: int
    name: str


class TMDBKeywordData(TypedDict):
    """Keyword data from TMDB API."""

    id: int
    name: str


class TMDBCastData(TypedDict):
    """Cast member data from TMDB credits endpoint."""

    id: int
    name: str
    character: str
    order: int
    profile_path: NotRequired[str | None]


class TMDBCrewData(TypedDict):
    """Crew member data from TMDB credits endpoint."""

    id: int
    name: str
    department: str
    job: str
    profile_path: NotRequired[str | None]


class TMDBCreditsData(TypedDict):
    """Combined credits data from TMDB API."""

    cast: list[TMDBCastData]
    crew: list[TMDBCrewData]


class TMDBProductionCompanyData(TypedDict):
    """Production company data from TMDB API."""

    id: int
    name: str
    origin_country: NotRequired[str | None]
    logo_path: NotRequired[str | None]


class TMDBSpokenLanguageData(TypedDict):
    """Spoken language data from TMDB API."""

    iso_639_1: str
    name: str
    english_name: NotRequired[str]


class TMDBFilmData(TypedDict):
    """Film data from TMDB discover/details endpoints.

    This represents the merged data from discover API
    and optional details enrichment.
    """

    # Required fields (from discover)
    id: int
    title: str
    overview: str | None
    release_date: str | None
    popularity: float
    vote_average: float
    vote_count: int
    adult: bool
    genre_ids: list[int]

    # Media paths
    poster_path: NotRequired[str | None]
    backdrop_path: NotRequired[str | None]

    # Optional fields (from details enrichment)
    imdb_id: NotRequired[str | None]
    original_title: NotRequired[str | None]
    original_language: NotRequired[str | None]
    tagline: NotRequired[str | None]
    runtime: NotRequired[int | None]
    status: NotRequired[str | None]
    homepage: NotRequired[str | None]
    budget: NotRequired[int]
    revenue: NotRequired[int]

    # Nested data (from details)
    genres: NotRequired[list[TMDBGenreData]]
    keywords: NotRequired[list[TMDBKeywordData]]
    credits: NotRequired[TMDBCreditsData]
    production_companies: NotRequired[list[TMDBProductionCompanyData]]
    spoken_languages: NotRequired[list[TMDBSpokenLanguageData]]


class TMDBDiscoverResponse(TypedDict):
    """Response from TMDB discover/movie endpoint."""

    page: int
    total_pages: int
    total_results: int
    results: list[TMDBFilmData]


class TMDBKeywordsResponse(TypedDict):
    """Response from TMDB movie/keywords endpoint."""

    id: int
    keywords: list[TMDBKeywordData]

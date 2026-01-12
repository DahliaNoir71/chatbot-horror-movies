"""Normalized data types for database insertion.

TypedDict definitions for data structures that have been
transformed and are ready for database insertion.
"""

from datetime import date, datetime
from typing import NotRequired, TypedDict


class NormalizedFilmData(TypedDict):
    """Normalized film data ready for database insertion."""

    tmdb_id: int
    imdb_id: str | None
    title: str
    original_title: str | None
    release_date: date | None
    tagline: str | None
    overview: str | None
    popularity: float
    vote_average: float
    vote_count: int
    runtime: int | None
    original_language: str | None
    status: str
    adult: bool
    poster_path: str | None
    backdrop_path: str | None
    homepage: str | None
    budget: int
    revenue: int
    source: str


class NormalizedCreditData(TypedDict):
    """Normalized credit data ready for database insertion."""

    film_id: NotRequired[int]
    tmdb_person_id: int | None
    person_name: str
    role_type: str
    character_name: str | None
    department: str | None
    job: str | None
    display_order: int
    profile_path: str | None


class NormalizedGenreData(TypedDict):
    """Normalized genre data ready for database insertion."""

    tmdb_genre_id: int
    name: str


class NormalizedKeywordData(TypedDict):
    """Normalized keyword data ready for database insertion."""

    tmdb_keyword_id: int | None
    name: str


class NormalizedVideoData(TypedDict):
    """Normalized video data ready for database insertion."""

    youtube_id: str
    title: str
    description: str | None
    channel_id: str | None
    channel_title: str | None
    view_count: int
    like_count: int
    comment_count: int
    duration: str | None
    published_at: datetime | None
    thumbnail_url: str | None
    video_type: str | None


class NormalizedTranscriptData(TypedDict):
    """Normalized transcript data ready for database insertion."""

    video_id: int
    transcript: str
    language: str
    is_generated: bool
    word_count: int


class NormalizedRTScoreData(TypedDict):
    """Normalized RT score data ready for database insertion."""

    film_id: int
    tomatometer_score: int | None
    tomatometer_state: str | None
    critics_count: int
    critics_average_rating: float | None
    audience_score: int | None
    audience_state: str | None
    audience_count: int
    audience_average_rating: float | None
    critics_consensus: str | None
    rt_url: str | None
    rt_rating: str | None


class NormalizedCompanyData(TypedDict):
    """Normalized production company data."""

    tmdb_company_id: int | None
    name: str
    origin_country: str | None


class NormalizedLanguageData(TypedDict):
    """Normalized spoken language data."""

    iso_639_1: str
    name: str

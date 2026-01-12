"""Rotten Tomatoes scraped data types.

TypedDict definitions for data structures scraped
from Rotten Tomatoes website.
"""

from typing import NotRequired, TypedDict


class RTScoreData(TypedDict):
    """Scraped score data from Rotten Tomatoes."""

    # Film reference
    film_id: NotRequired[int]
    tmdb_id: NotRequired[int]

    # Tomatometer (critics)
    tomatometer_score: int | None
    tomatometer_state: NotRequired[str | None]
    critics_count: NotRequired[int]
    critics_average_rating: NotRequired[float | None]

    # Audience score
    audience_score: int | None
    audience_state: NotRequired[str | None]
    audience_count: NotRequired[int]
    audience_average_rating: NotRequired[float | None]

    # Consensus text (valuable for RAG)
    critics_consensus: NotRequired[str | None]

    # Metadata
    rt_url: NotRequired[str | None]
    rt_rating: NotRequired[str | None]


class RTSearchResult(TypedDict):
    """Search result from RT search."""

    title: str
    year: int | None
    url: str
    tomatometer_score: int | None


class RTMoviePageData(TypedDict):
    """Full movie page data from RT scraping."""

    # Basic info
    title: str
    year: NotRequired[int | None]
    rt_url: str

    # Scores
    tomatometer_score: int | None
    tomatometer_state: str | None
    audience_score: int | None
    audience_state: str | None

    # Counts
    critics_count: int
    audience_count: int

    # Ratings
    critics_average_rating: float | None
    audience_average_rating: float | None

    # Content
    critics_consensus: str | None
    synopsis: NotRequired[str | None]

    # Metadata
    rt_rating: str | None
    runtime: NotRequired[str | None]
    genre: NotRequired[str | None]
    director: NotRequired[str | None]

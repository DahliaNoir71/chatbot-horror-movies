"""Type definitions for ETL pipeline data structures.

Provides strict typing to replace generic dict[str, Any] patterns
and improve code quality for SonarQube compliance.
"""

from dataclasses import dataclass, field
from typing import TypedDict


class FilmDict(TypedDict, total=False):
    """Film data structure from TMDB/Kaggle/IMDB sources.

    Attributes:
        id: Unique identifier (TMDB ID or source-specific).
        title: Film title.
        original_title: Original language title.
        release_date: Release date (YYYY-MM-DD format).
        year: Release year.
        overview: Plot synopsis.
        genres: List of genre names.
        vote_average: Average rating (0-10).
        vote_count: Number of votes.
        popularity: TMDB popularity score.
        poster_path: Poster image path.
        backdrop_path: Backdrop image path.
        original_language: ISO 639-1 language code.
        runtime: Duration in minutes.
        budget: Production budget in USD.
        revenue: Box office revenue in USD.
        source: Data source identifier.
        tomatometer_score: Rotten Tomatoes critic score.
        audience_score: Rotten Tomatoes audience score.
        rt_url: Rotten Tomatoes page URL.
    """

    id: int
    title: str
    original_title: str
    release_date: str
    year: int
    overview: str
    genres: list[str]
    vote_average: float
    vote_count: int
    popularity: float
    poster_path: str | None
    backdrop_path: str | None
    original_language: str
    runtime: int | None
    budget: int
    revenue: int
    source: str
    tomatometer_score: int | None
    audience_score: int | None
    rt_url: str | None


class PodcastEpisodeDict(TypedDict, total=False):
    """Podcast episode data structure from Spotify.

    Attributes:
        id: Spotify episode ID.
        name: Episode title.
        description: Episode description.
        release_date: Publication date.
        duration_ms: Duration in milliseconds.
        explicit: Whether episode contains explicit content.
        external_url: Spotify URL.
        show_id: Parent show ID.
        show_name: Parent show name.
        language: Episode language.
    """

    id: str
    name: str
    description: str
    release_date: str
    duration_ms: int
    explicit: bool
    external_url: str
    show_id: str
    show_name: str
    language: str


class VideoDict(TypedDict, total=False):
    """Video data structure from YouTube.

    Attributes:
        id: YouTube video ID.
        title: Video title.
        description: Video description.
        published_at: Publication datetime (ISO format).
        channel_id: Channel ID.
        channel_title: Channel name.
        view_count: Number of views.
        like_count: Number of likes.
        comment_count: Number of comments.
        duration: ISO 8601 duration.
        tags: Video tags list.
        thumbnail_url: Thumbnail image URL.
    """

    id: str
    title: str
    description: str
    published_at: str
    channel_id: str
    channel_title: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    tags: list[str]
    thumbnail_url: str


class IMDBReviewDict(TypedDict, total=False):
    """IMDB review data structure.

    Attributes:
        id: Review ID.
        film_id: Associated film ID.
        author: Review author.
        content: Review text.
        rating: Author's rating.
        date: Review date.
    """

    id: int
    film_id: int
    author: str
    content: str
    rating: float | None
    date: str


class IMDBRatingDict(TypedDict, total=False):
    """IMDB rating data structure.

    Attributes:
        film_id: Associated film ID.
        average_rating: Average rating.
        num_votes: Number of votes.
    """

    film_id: int
    average_rating: float
    num_votes: int


class IMDBDataDict(TypedDict):
    """Combined IMDB extraction result.

    Attributes:
        films: List of film records.
        reviews: List of review records.
        ratings: List of rating records.
    """

    films: list[FilmDict]
    reviews: list[IMDBReviewDict]
    ratings: list[IMDBRatingDict]


@dataclass
class PipelineResult:
    """Pipeline execution result container.

    Attributes:
        films: Aggregated film data from all sources.
        podcasts: Podcast episodes from Spotify.
        videos: Videos from YouTube.
        imdb: Raw IMDB data (films, reviews, ratings).
        duration_seconds: Total execution time.
        sources_completed: Successfully processed sources.
        sources_failed: Failed source extractions.
    """

    films: list[FilmDict] = field(default_factory=list)
    podcasts: list[PodcastEpisodeDict] = field(default_factory=list)
    videos: list[VideoDict] = field(default_factory=list)
    imdb: IMDBDataDict = field(default_factory=lambda: {"films": [], "reviews": [], "ratings": []})
    duration_seconds: float = 0.0
    sources_completed: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)


@dataclass
class ExtractionParams:
    """Parameters for single source extraction.

    Attributes:
        max_pages: Maximum pages for TMDB extraction.
        max_videos: Maximum videos per YouTube channel.
    """

    max_pages: int | None = None
    max_videos: int | None = None

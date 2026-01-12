"""TMDB API client with rate limiting.

Handles HTTP communication with The Movie Database API
including authentication, rate limiting, and retries.
"""

import logging
import time
from types import TracebackType
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.settings import settings

logger = logging.getLogger(__name__)


class TMDBClientError(Exception):
    """Base exception for TMDB client errors."""

    pass


class TMDBRateLimitError(TMDBClientError):
    """Raised when rate limit is exceeded."""

    pass


class TMDBNotFoundError(TMDBClientError):
    """Raised when resource is not found."""

    pass


class TMDBClient:
    """HTTP client for TMDB API with rate limiting.

    Implements token bucket rate limiting to respect
    TMDB's API limits (40 requests per 10 seconds).

    Attributes:
        base_url: TMDB API base URL.
        api_key: TMDB API key.
    """

    def __init__(self) -> None:
        """Initialize TMDB client with settings."""
        self._base_url = settings.tmdb.base_url
        self._api_key = settings.tmdb.api_key
        self._language = settings.tmdb.language

        # Rate limiting state
        self._requests_per_period = settings.tmdb.requests_per_period
        self._period_seconds = settings.tmdb.period_seconds
        self._min_delay = settings.tmdb.min_request_delay
        self._request_times: list[float] = []

        # HTTP client
        self._client: httpx.Client | None = None

    # -------------------------------------------------------------------------
    # Context Manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> "TMDBClient":
        """Enter context and create HTTP client."""
        self._client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": settings.etl.user_agent},
        )
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Exit context and close HTTP client.

        Args:
            _exc_type: Exception type if raised.
            _exc_val: Exception value if raised.
            _exc_tb: Exception traceback if raised.
        """
        if self._client:
            self._client.close()
            self._client = None

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits."""
        now = time.time()

        # Remove old request times outside the window
        cutoff = now - self._period_seconds
        self._request_times = [t for t in self._request_times if t > cutoff]

        # Check if we need to wait
        if len(self._request_times) >= self._requests_per_period:
            oldest = self._request_times[0]
            wait_time = oldest + self._period_seconds - now
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                time.sleep(wait_time)

        # Enforce minimum delay between requests
        if self._request_times:
            elapsed = now - self._request_times[-1]
            if elapsed < self._min_delay:
                time.sleep(self._min_delay - elapsed)

        # Record this request
        self._request_times.append(time.time())

    # -------------------------------------------------------------------------
    # HTTP Methods
    # -------------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, TMDBRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute GET request with rate limiting and retries.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            JSON response as dictionary.

        Raises:
            TMDBClientError: On API errors.
            TMDBNotFoundError: When resource not found.
            TMDBRateLimitError: When rate limit exceeded.
        """
        if self._client is None:
            msg = "Client not initialized. Use context manager."
            raise TMDBClientError(msg)

        self._wait_for_rate_limit()

        # Build request parameters
        request_params = {"api_key": self._api_key, "language": self._language}
        if params:
            request_params.update(params)

        url = f"{self._base_url}{endpoint}"

        try:
            response = self._client.get(url, params=request_params)
        except httpx.TimeoutException as e:
            logger.warning(f"Request timeout: {endpoint}")
            raise e

        return self._handle_response(response, endpoint)

    @staticmethod
    def _handle_response(
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any]:
        """Handle HTTP response and extract JSON.

        Args:
            response: HTTP response object.
            endpoint: API endpoint (for logging).

        Returns:
            JSON response as dictionary.

        Raises:
            TMDBClientError: On API errors.
            TMDBNotFoundError: When resource not found (404).
            TMDBRateLimitError: When rate limit exceeded (429).
        """
        if response.status_code == 200:
            return response.json()

        if response.status_code == 404:
            raise TMDBNotFoundError(f"Not found: {endpoint}")

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "10")
            logger.warning(f"Rate limited. Retry after {retry_after}s")
            raise TMDBRateLimitError(f"Rate limited: {endpoint}")

        # Other errors
        error_msg = f"TMDB API error {response.status_code}: {endpoint}"
        logger.error(error_msg)
        raise TMDBClientError(error_msg)

    # -------------------------------------------------------------------------
    # API Endpoints
    # -------------------------------------------------------------------------

    def discover_movies(
        self,
        page: int = 1,
        year: int | None = None,
        genre_id: int | None = None,
        sort_by: str = "popularity.desc",
    ) -> dict[str, Any]:
        """Discover movies with filters.

        Args:
            page: Page number (1-500).
            year: Release year filter.
            genre_id: Genre ID filter (27 for Horror).
            sort_by: Sort order.

        Returns:
            Discover response with results.
        """
        params: dict[str, Any] = {
            "page": page,
            "sort_by": sort_by,
            "include_adult": str(settings.tmdb.include_adult).lower(),
        }

        if year:
            params["primary_release_year"] = year
        if genre_id:
            params["with_genres"] = genre_id

        return self._get("/discover/movie", params)

    def get_movie_details(self, movie_id: int) -> dict[str, Any]:
        """Get detailed movie information.

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Movie details response.
        """
        return self._get(f"/movie/{movie_id}")

    def get_movie_credits(self, movie_id: int) -> dict[str, Any]:
        """Get movie cast and crew.

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Credits response with cast and crew.
        """
        return self._get(f"/movie/{movie_id}/credits")

    def get_movie_keywords(self, movie_id: int) -> dict[str, Any]:
        """Get movie keywords.

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Keywords response.
        """
        return self._get(f"/movie/{movie_id}/keywords")

    def get_movie_full(self, movie_id: int) -> dict[str, Any]:
        """Get movie with appended responses (single request).

        Uses append_to_response for efficiency.

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Movie details with credits and keywords.
        """
        params: dict[str, Any] = {"append_to_response": "credits,keywords"}
        return self._get(f"/movie/{movie_id}", params)

    def get_genres(self) -> dict[str, Any]:
        """Get list of movie genres.

        Returns:
            Genres response with list of genre objects.
        """
        return self._get("/genre/movie/list")

    def search_movies(
        self,
        query: str,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Search movies by title.

        Args:
            query: Search query string.
            year: Optional release year.

        Returns:
            Search results response.
        """
        params: dict[str, Any] = {"query": query}
        if year:
            params["year"] = year
        return self._get("/search/movie", params)

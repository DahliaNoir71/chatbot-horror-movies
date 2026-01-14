"""YouTube Data API v3 client.

Handles API requests with rate limiting, error handling,
and quota management.
"""

import time
from types import TracebackType
from typing import Any, Final

import httpx

from src.etl.utils.logger import setup_logger
from src.settings import settings


class YouTubeAPIError(Exception):
    """Base exception for YouTube API errors."""

    pass


class YouTubeQuotaExceededError(YouTubeAPIError):
    """Raised when daily quota is exceeded."""

    pass


class YouTubeNotFoundError(YouTubeAPIError):
    """Raised when resource is not found."""

    pass


class YouTubeClient:
    """YouTube Data API v3 client.

    Provides methods to fetch channels, playlists, and video metadata
    with automatic rate limiting and error handling.

    Attributes:
        base_url: YouTube API base URL.
        api_key: YouTube API key.
    """

    # API endpoints
    _ENDPOINT_CHANNELS = "/channels"
    _ENDPOINT_PLAYLISTS = "/playlists"
    _ENDPOINT_PLAYLIST_ITEMS = "/playlistItems"
    _ENDPOINT_VIDEOS = "/videos"
    _ENDPOINT_SEARCH = "/search"

    # Quota costs per request type
    _QUOTA_COST_LIST = 1
    _QUOTA_COST_SEARCH = 100

    # YouTube API part parameters
    _PART_SNIPPET_CONTENT_DETAILS: Final[str] = "snippet,contentDetails"
    _PART_VIDEO_DETAILS: Final[str] = "snippet,statistics,contentDetails"
    _PART_CHANNEL_DETAILS: Final[str] = "snippet,contentDetails,statistics"

    def __init__(self) -> None:
        """Initialize YouTube client."""
        self._logger = setup_logger("etl.youtube.client")
        self._client: httpx.Client | None = None
        self._quota_used: int = 0
        self._last_request_time: float = 0.0

    # -------------------------------------------------------------------------
    # Context Manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> "YouTubeClient":
        """Enter context and create HTTP client."""
        self._client = httpx.Client(
            base_url=settings.youtube.base_url,
            timeout=30.0,
        )
        return self

    def __exit__(
        self,
        _exc_type: type | None,
        _exc_val: Exception | None,
        _exc_tb: TracebackType,
    ) -> None:
        """Exit context and close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
        self._logger.debug(f"Session closed. Quota used: {self._quota_used}")

    # -------------------------------------------------------------------------
    # Channel Methods
    # -------------------------------------------------------------------------

    def get_channel_by_handle(self, handle: str) -> dict[str, Any]:
        """Get channel info by handle (e.g., @ChannelName).

        Args:
            handle: Channel handle starting with @.

        Returns:
            Channel data dict with id, title, uploads playlist ID.

        Raises:
            YouTubeNotFoundError: If channel not found.
        """
        clean_handle = self._normalize_handle(handle)
        params = {
            "part": self._PART_SNIPPET_CONTENT_DETAILS,
            "forHandle": clean_handle,
        }
        response = self._request(self._ENDPOINT_CHANNELS, params)
        return self._extract_single_item(response, f"Channel {handle}")

    def get_channel_by_id(self, channel_id: str) -> dict[str, Any]:
        """Get channel info by ID.

        Args:
            channel_id: YouTube channel ID.

        Returns:
            Channel data dict.

        Raises:
            YouTubeNotFoundError: If channel not found.
        """
        params = {
            "part": self._PART_CHANNEL_DETAILS,
            "id": channel_id,
        }
        response = self._request(self._ENDPOINT_CHANNELS, params)
        return self._extract_single_item(response, f"Channel {channel_id}")

    @staticmethod
    def _normalize_handle(handle: str) -> str:
        """Normalize channel handle by removing @ prefix.

        Args:
            handle: Raw handle string.

        Returns:
            Handle without @ prefix.
        """
        return handle.lstrip("@")

    @staticmethod
    def get_uploads_playlist_id(channel_data: dict[str, Any]) -> str | None:
        """Extract uploads playlist ID from channel data.

        Args:
            channel_data: Channel response from API.

        Returns:
            Uploads playlist ID or None.
        """
        content_details = channel_data.get("contentDetails", {})
        related = content_details.get("relatedPlaylists", {})
        return related.get("uploads")

    # -------------------------------------------------------------------------
    # Playlist Methods
    # -------------------------------------------------------------------------

    def get_playlist_items(
        self,
        playlist_id: str,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Get videos from a playlist.

        Args:
            playlist_id: YouTube playlist ID.
            max_results: Max items per page (max 50).
            page_token: Token for pagination.

        Returns:
            Playlist items response with items and nextPageToken.
        """
        params = {
            "part": self._PART_SNIPPET_CONTENT_DETAILS,
            "playlistId": playlist_id,
            "maxResults": min(max_results, 50),
        }
        if page_token:
            params["pageToken"] = page_token

        return self._request(self._ENDPOINT_PLAYLIST_ITEMS, params)

    def iter_playlist_videos(
        self,
        playlist_id: str,
        max_videos: int | None = None,
    ) -> list[dict[str, Any]]:
        """Iterate all videos in a playlist with pagination.

        Args:
            playlist_id: YouTube playlist ID.
            max_videos: Maximum videos to fetch (None = all).

        Returns:
            List of playlist item dicts.
        """
        videos: list[dict[str, Any]] = []
        page_token: str | None = None
        limit = max_videos or settings.youtube.max_videos

        while len(videos) < limit:
            response = self.get_playlist_items(playlist_id, 50, page_token)
            items = response.get("items", [])

            videos.extend(items[: limit - len(videos)])
            page_token = response.get("nextPageToken")

            if not page_token or not items:
                break

        return videos

    # -------------------------------------------------------------------------
    # Video Methods
    # -------------------------------------------------------------------------

    def get_video_details(self, video_id: str) -> dict[str, Any]:
        """Get full video details.

        Args:
            video_id: YouTube video ID.

        Returns:
            Video data with snippet, statistics, contentDetails.

        Raises:
            YouTubeNotFoundError: If video not found.
        """
        params = {
            "part": self._PART_VIDEO_DETAILS,
            "id": video_id,
        }
        response = self._request(self._ENDPOINT_VIDEOS, params)
        return self._extract_single_item(response, f"Video {video_id}")

    def get_videos_batch(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Get details for multiple videos in one request.

        Args:
            video_ids: List of video IDs (max 50).

        Returns:
            List of video data dicts.
        """
        if not video_ids:
            return []

        # API limit: 50 IDs per request
        batch_ids = video_ids[:50]
        params = {
            "part": self._PART_VIDEO_DETAILS,
            "id": ",".join(batch_ids),
        }
        response = self._request(self._ENDPOINT_VIDEOS, params)
        return response.get("items", [])

    # -------------------------------------------------------------------------
    # Search Methods (High quota cost - use sparingly)
    # -------------------------------------------------------------------------

    def search_videos(
        self,
        query: str,
        channel_id: str | None = None,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """Search for videos (costs 100 quota units).

        Args:
            query: Search query string.
            channel_id: Limit search to specific channel.
            max_results: Maximum results (max 50).

        Returns:
            List of search result items.
        """
        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
        }
        if channel_id:
            params["channelId"] = channel_id

        response = self._request(
            self._ENDPOINT_SEARCH,
            params,
            quota_cost=self._QUOTA_COST_SEARCH,
        )
        return response.get("items", [])

    # -------------------------------------------------------------------------
    # Request Handling
    # -------------------------------------------------------------------------

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        quota_cost: int = _QUOTA_COST_LIST,
    ) -> dict[str, Any]:
        """Execute API request with rate limiting.

        Args:
            endpoint: API endpoint path.
            params: Query parameters.
            quota_cost: Quota units consumed.

        Returns:
            JSON response dict.

        Raises:
            YouTubeAPIError: On API errors.
            YouTubeQuotaExceededError: If quota exceeded.
        """
        self._check_quota(quota_cost)
        self._apply_rate_limit()

        params["key"] = settings.youtube.api_key
        response = self._execute_request(endpoint, params)

        self._quota_used += quota_cost
        return response

    def _check_quota(self, cost: int) -> None:
        """Check if quota allows request.

        Args:
            cost: Quota cost of planned request.

        Raises:
            YouTubeQuotaExceededError: If quota exceeded.
        """
        if self._quota_used + cost > settings.youtube.daily_quota_limit:
            raise YouTubeQuotaExceededError(
                f"Daily quota exceeded: {self._quota_used}/{settings.youtube.daily_quota_limit}"
            )

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting delay between requests."""
        elapsed = time.time() - self._last_request_time
        delay = settings.youtube.request_delay

        if elapsed < delay:
            time.sleep(delay - elapsed)

        self._last_request_time = time.time()

    def _execute_request(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute HTTP request and handle response.

        Args:
            endpoint: API endpoint.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            YouTubeAPIError: On HTTP or API errors.
        """
        if not self._client:
            raise YouTubeAPIError("Client not initialized. Use context manager.")

        try:
            response = self._client.get(endpoint, params=params)
            return self._handle_response(response)
        except httpx.HTTPError as e:
            raise YouTubeAPIError(f"HTTP error: {e}") from e

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and errors.

        Args:
            response: HTTP response object.

        Returns:
            Parsed JSON data.

        Raises:
            YouTubeNotFoundError: On 404.
            YouTubeQuotaExceededError: On quota errors.
            YouTubeAPIError: On other errors.
        """
        if response.status_code == 404:
            raise YouTubeNotFoundError("Resource not found")

        if response.status_code == 403:
            self._handle_forbidden_error(response)

        if response.status_code >= 400:
            raise YouTubeAPIError(f"API error {response.status_code}: {response.text}")

        return response.json()

    def _handle_forbidden_error(self, response: httpx.Response) -> None:
        """Handle 403 errors (quota or permission).

        Args:
            response: HTTP response.

        Raises:
            YouTubeQuotaExceededError: If quota related.
            YouTubeAPIError: For other 403 errors.
        """
        try:
            error_data = response.json()
            reason = self._extract_error_reason(error_data)

            if "quota" in reason.lower():
                raise YouTubeQuotaExceededError(f"Quota exceeded: {reason}")

            raise YouTubeAPIError(f"Forbidden: {reason}")
        except ValueError:
            raise YouTubeAPIError(f"Forbidden: {response.text}") from None

    @staticmethod
    def _extract_error_reason(error_data: dict[str, Any]) -> str:
        """Extract error reason from API error response.

        Args:
            error_data: Parsed error JSON.

        Returns:
            Error reason string.
        """
        error = error_data.get("error", {})
        errors = error.get("errors", [{}])
        return errors[0].get("reason", "Unknown error")

    @staticmethod
    def _extract_single_item(
        response: dict[str, Any],
        resource_name: str,
    ) -> dict[str, Any]:
        """Extract single item from response or raise error.

        Args:
            response: API response dict.
            resource_name: Name for error message.

        Returns:
            First item from response.

        Raises:
            YouTubeNotFoundError: If no items found.
        """
        items = response.get("items", [])
        if not items:
            raise YouTubeNotFoundError(f"{resource_name} not found")
        return items[0]

    # -------------------------------------------------------------------------
    # Quota Tracking
    # -------------------------------------------------------------------------

    @property
    def quota_used(self) -> int:
        """Get total quota used in this session."""
        return self._quota_used

    @property
    def quota_remaining(self) -> int:
        """Get estimated remaining quota."""
        return settings.youtube.daily_quota_limit - self._quota_used

"""YouTube Data API v3 client.

Handles communication with YouTube API for
channel, playlist, and video data retrieval.
"""

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

from src.etl.utils.logger import setup_logger
from src.settings import settings

logger = setup_logger("etl.yt.client")


# =============================================================================
# EXCEPTIONS
# =============================================================================


class YouTubeClientError(Exception):
    """Base exception for YouTube client errors."""

    pass


class YouTubeQuotaError(YouTubeClientError):
    """Raised when API quota is exceeded."""

    pass


class YouTubeNotFoundError(YouTubeClientError):
    """Raised when resource is not found."""

    pass


# =============================================================================
# QUOTA COSTS
# =============================================================================

QUOTA_SEARCH = 100
QUOTA_CHANNELS = 1
QUOTA_VIDEOS = 1
QUOTA_PLAYLIST_ITEMS = 1


# =============================================================================
# CLIENT
# =============================================================================


class YouTubeClient:
    """HTTP client for YouTube Data API v3.

    Provides methods to fetch channels, playlists,
    and video metadata with quota tracking.

    Attributes:
        quota_used: Total quota units consumed.
        api_calls: Total API calls made.
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self) -> None:
        """Initialize YouTube client."""
        self._api_key = settings.youtube.api_key
        self._request_delay = settings.youtube.request_delay
        self._timeout = 30.0
        self._last_request_time: float = 0.0
        self.quota_used = 0
        self.api_calls = 0

    def __enter__(self) -> "YouTubeClient":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit."""
        pass

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------

    def _enforce_rate_limit(self) -> None:
        """Enforce minimum delay between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)
        self._last_request_time = time.time()

    # -------------------------------------------------------------------------
    # HTTP Request
    # -------------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _get(
        self,
        endpoint: str,
        params: dict[str, Any],
        quota_cost: int = 1,
    ) -> dict[str, Any]:
        """Make authenticated GET request.

        Args:
            endpoint: API endpoint (e.g., "channels", "videos").
            params: Query parameters.
            quota_cost: Quota units for this request.

        Returns:
            JSON response as dictionary.

        Raises:
            YouTubeQuotaError: When quota is exceeded.
            YouTubeNotFoundError: When resource not found.
            YouTubeClientError: On other API errors.
        """
        self._enforce_rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"
        params["key"] = self._api_key

        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(url, params=params)

        self._handle_response_errors(response)

        self.quota_used += quota_cost
        self.api_calls += 1

        return response.json()

    def _handle_response_errors(self, response: httpx.Response) -> None:
        """Handle HTTP response errors.

        Args:
            response: HTTP response object.

        Raises:
            YouTubeQuotaError: On 403 quota exceeded.
            YouTubeNotFoundError: On 404 not found.
            YouTubeClientError: On other errors.
        """
        if response.status_code == 200:
            return

        if response.status_code == 403:
            error_data = response.json()
            reason = self._extract_error_reason(error_data)
            if "quota" in reason.lower():
                raise YouTubeQuotaError(f"API quota exceeded: {reason}")
            raise YouTubeClientError(f"Forbidden: {reason}")

        if response.status_code == 404:
            raise YouTubeNotFoundError("Resource not found")

        response.raise_for_status()

    @staticmethod
    def _extract_error_reason(error_data: dict[str, Any]) -> str:
        """Extract error reason from API response.

        Args:
            error_data: Error response JSON.

        Returns:
            Error reason string.
        """
        try:
            errors = error_data.get("error", {}).get("errors", [])
            if errors:
                return errors[0].get("reason", "Unknown error")
        except (KeyError, IndexError):
            pass
        return "Unknown error"

    # -------------------------------------------------------------------------
    # Channel Operations
    # -------------------------------------------------------------------------

    def resolve_channel_handle(self, handle: str) -> dict[str, str] | None:
        """Resolve channel handle to channel ID and uploads playlist.

        Args:
            handle: Channel handle (e.g., "@Monstresdefilms").

        Returns:
            Dict with id, title, uploads_playlist_id or None.
        """
        clean_handle = handle.lstrip("@")

        try:
            data = self._get(
                "channels",
                params={
                    "part": "snippet,contentDetails",
                    "forHandle": clean_handle,
                },
                quota_cost=QUOTA_CHANNELS,
            )
        except YouTubeClientError as e:
            logger.warning(f"Channel resolve failed for {handle}: {e}")
            return None

        items = data.get("items", [])
        if not items:
            logger.warning(f"Channel not found: {handle}")
            return None

        channel = items[0]
        return {
            "id": channel["id"],
            "title": channel["snippet"]["title"],
            "uploads_playlist_id": channel["contentDetails"]["relatedPlaylists"]["uploads"],
        }

    def get_channel_by_id(self, channel_id: str) -> dict[str, Any] | None:
        """Get channel details by ID.

        Args:
            channel_id: YouTube channel ID.

        Returns:
            Channel data or None if not found.
        """
        try:
            data = self._get(
                "channels",
                params={
                    "part": "snippet,contentDetails,statistics",
                    "id": channel_id,
                },
                quota_cost=QUOTA_CHANNELS,
            )
            items = data.get("items", [])
            return items[0] if items else None
        except YouTubeClientError:
            return None

    # -------------------------------------------------------------------------
    # Playlist Operations
    # -------------------------------------------------------------------------

    def get_playlist_videos(
        self,
        playlist_id: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch all videos from a playlist.

        Args:
            playlist_id: YouTube playlist ID.
            max_results: Maximum videos to retrieve.

        Returns:
            List of playlist item data.
        """
        videos: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(videos) < max_results:
            params: dict[str, Any] = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": min(50, max_results - len(videos)),
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                data = self._get(
                    "playlistItems",
                    params=params,
                    quota_cost=QUOTA_PLAYLIST_ITEMS,
                )
            except YouTubeClientError as e:
                logger.warning(f"Playlist fetch failed for {playlist_id}: {e}")
                break

            items = data.get("items", [])
            videos.extend(items)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return videos

    # -------------------------------------------------------------------------
    # Video Operations
    # -------------------------------------------------------------------------

    def get_video_details(self, video_id: str) -> dict[str, Any] | None:
        """Get details for a single video.

        Args:
            video_id: YouTube video ID.

        Returns:
            Video data or None if not found.
        """
        results = self.get_videos_details([video_id])
        return results[0] if results else None

    def get_videos_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch detailed metadata for multiple videos.

        Args:
            video_ids: List of video IDs (max 50 per call).

        Returns:
            List of video details.
        """
        if not video_ids:
            return []

        all_details: list[dict[str, Any]] = []

        # API limit: 50 IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]

            try:
                data = self._get(
                    "videos",
                    params={
                        "part": "snippet,contentDetails,statistics",
                        "id": ",".join(batch),
                    },
                    quota_cost=QUOTA_VIDEOS,
                )
                all_details.extend(data.get("items", []))
            except YouTubeClientError as e:
                logger.warning(f"Video details failed: {e}")

        return all_details

    # -------------------------------------------------------------------------
    # Search (High Quota Cost)
    # -------------------------------------------------------------------------

    def search_videos(
        self,
        query: str,
        channel_id: str | None = None,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """Search for videos (high quota cost - use sparingly).

        Args:
            query: Search query string.
            channel_id: Optional channel filter.
            max_results: Max results (1-50).

        Returns:
            List of search results.
        """
        params: dict[str, Any] = {
            "part": "id,snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
        }

        if channel_id:
            params["channelId"] = channel_id

        try:
            response = self._get("search", params, quota_cost=QUOTA_SEARCH)
            return response.get("items", [])
        except YouTubeClientError as e:
            logger.error(f"Search failed: {e}")
            return []

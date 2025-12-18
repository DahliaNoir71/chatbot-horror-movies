"""YouTube Data API v3 extractor for horror video content.

Source 3 (E1): REST API with API Key authentication.
Channel: @Monstresdefilms (French horror movie reviews).
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings


@dataclass
class YouTubeStats:
    """Extraction statistics."""

    channels_processed: int = 0
    total_videos: int = 0
    api_calls: int = 0
    quota_used: int = 0
    errors: int = 0


class YouTubeExtractor(BaseExtractor):
    """Extract video metadata from YouTube Data API v3.

    Uses API Key authentication.
    Rate limited to 0.5 request/second by default.
    Daily quota: 10,000 units.
    """

    # Quota costs per endpoint
    QUOTA_SEARCH = 100
    QUOTA_CHANNELS = 1
    QUOTA_VIDEOS = 1

    def __init__(self) -> None:
        """Initialize YouTube extractor."""
        super().__init__("YouTubeExtractor")
        self.logger = setup_logger("etl.youtube")
        self.cfg = settings.youtube
        self.session = requests.Session()
        self.stats = YouTubeStats()
        self._last_request_time: float = 0.0

    def validate_config(self) -> None:
        """Validate YouTube API key is configured.

        Raises:
            ValueError: If API key is missing.
        """
        if not self.cfg.is_configured:
            raise ValueError("YouTube API key missing. Set YOUTUBE_API_KEY in .env")

    # =========================================================================
    # API REQUESTS
    # =========================================================================

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        min_interval = 1.0 / self.cfg.requests_per_second
        elapsed = time.time() - self._last_request_time

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _request(
        self, endpoint: str, params: dict[str, Any], quota_cost: int = 1
    ) -> dict[str, Any]:
        """Make API request with rate limiting and quota tracking.

        Args:
            endpoint: API endpoint (e.g., "channels", "search").
            params: Query parameters.
            quota_cost: Quota units consumed by this request.

        Returns:
            JSON response as dictionary.

        Raises:
            requests.RequestException: On API errors.
        """
        self._rate_limit()

        # Add API key to params
        params["key"] = self.cfg.api_key

        url = f"{self.cfg.api_base_url}/{endpoint}"
        response = self.session.get(url, params=params, timeout=30)

        self.stats.api_calls += 1
        self.stats.quota_used += quota_cost

        # Check quota exceeded
        if response.status_code == 403:
            error = response.json().get("error", {})
            if "quotaExceeded" in str(error):
                self.logger.error("youtube_quota_exceeded")
                raise ValueError("YouTube daily quota exceeded")

        response.raise_for_status()
        return response.json()

    # =========================================================================
    # CHANNEL RESOLUTION
    # =========================================================================

    def _get_channel_id(self, handle: str) -> str | None:
        """Resolve channel handle to channel ID.

        Args:
            handle: Channel handle (e.g., "@Monstresdefilms").

        Returns:
            Channel ID or None if not found.
        """
        # Remove @ if present
        handle_clean = handle.lstrip("@")

        params = {
            "part": "id,snippet",
            "forHandle": handle_clean,
        }

        try:
            response = self._request("channels", params, self.QUOTA_CHANNELS)
            items = response.get("items", [])

            if not items:
                self.logger.warning(f"channel_not_found: {handle}")
                return None

            channel_id = items[0]["id"]
            channel_title = items[0]["snippet"]["title"]

            self.logger.info(f"channel_resolved: {handle} -> {channel_id} ({channel_title})")
            return channel_id

        except requests.RequestException as e:
            self.logger.error(f"channel_resolution_failed: {handle} - {e}")
            return None

    # =========================================================================
    # VIDEO EXTRACTION
    # =========================================================================

    def _search_videos(self, channel_id: str, page_token: str | None = None) -> dict[str, Any]:
        """Search for videos in a channel.

        Args:
            channel_id: YouTube channel ID.
            page_token: Pagination token.

        Returns:
            Search response with video IDs and pagination.
        """
        params: dict[str, Any] = {
            "part": "id,snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": 50,
        }

        if page_token:
            params["pageToken"] = page_token

        return self._request("search", params, self.QUOTA_SEARCH)

    def _get_video_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch detailed metadata for videos.

        Args:
            video_ids: List of video IDs (max 50).

        Returns:
            List of video detail dictionaries.
        """
        if not video_ids:
            return []

        params = {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(video_ids[:50]),
        }

        response = self._request("videos", params, self.QUOTA_VIDEOS)
        return response.get("items", [])

    def _normalize_video(self, video: dict[str, Any]) -> dict[str, Any]:
        """Normalize video to standard schema.

        Args:
            video: Raw video data from API.

        Returns:
            Normalized video dictionary.
        """
        snippet = video.get("snippet", {})
        content = video.get("contentDetails", {})
        stats = video.get("statistics", {})

        return {
            # Identifiers
            "youtube_video_id": video.get("id"),
            "source": "youtube",
            # Content
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            # Channel info
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            # Media
            "thumbnails": snippet.get("thumbnails", {}),
            "duration": content.get("duration"),
            "definition": content.get("definition"),
            # Dates
            "published_at": snippet.get("publishedAt"),
            # Statistics
            "view_count": self._safe_int(stats.get("viewCount")),
            "like_count": self._safe_int(stats.get("likeCount")),
            "comment_count": self._safe_int(stats.get("commentCount")),
            # Metadata
            "tags": snippet.get("tags", []),
            "category_id": snippet.get("categoryId"),
            "default_language": snippet.get("defaultLanguage"),
            "default_audio_language": snippet.get("defaultAudioLanguage"),
            # Extraction timestamp
            "extracted_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _safe_int(value: str | int | float | None) -> int | None:
        """Safely convert value to int.

        Args:
            value: Value to convert.

        Returns:
            Integer or None if conversion fails.
        """
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _extract_channel(self, handle: str, max_videos: int) -> list[dict[str, Any]]:
        """Extract all videos from a single channel.

        Args:
            handle: Channel handle (e.g., "@Monstresdefilms").
            max_videos: Maximum videos to extract.

        Returns:
            List of normalized video dictionaries.
        """
        self.logger.info(f"extracting_channel: {handle}")

        channel_id = self._get_channel_id(handle)
        if not channel_id:
            self.stats.errors += 1
            return []

        try:
            videos = self._paginate_channel_videos(channel_id, max_videos)
            self._update_channel_stats(handle, len(videos))
            return videos

        except (requests.RequestException, ValueError) as e:
            self.stats.errors += 1
            self.logger.error(f"channel_extraction_failed: {handle} - {e}")
            return []

    def _paginate_channel_videos(self, channel_id: str, max_videos: int) -> list[dict[str, Any]]:
        """Paginate through channel videos.

        Args:
            channel_id: YouTube channel ID.
            max_videos: Maximum videos to extract.

        Returns:
            List of normalized video dictionaries.
        """
        videos: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(videos) < max_videos:
            if self._is_quota_exceeded():
                break

            search_response = self._search_videos(channel_id, page_token)
            items = search_response.get("items", [])

            if not items:
                break

            videos = self._process_search_page(items, videos, max_videos)

            page_token = search_response.get("nextPageToken")
            if not page_token:
                break

        return videos

    def _is_quota_exceeded(self) -> bool:
        """Check if quota limit is approaching.

        Returns:
            True if quota would be exceeded by next search call.
        """
        exceeded = self.stats.quota_used + self.QUOTA_SEARCH > self.cfg.daily_quota_limit

        if exceeded:
            self.logger.warning("youtube_quota_limit_approaching")

        return exceeded

    def _process_search_page(
        self,
        items: list[dict[str, Any]],
        videos: list[dict[str, Any]],
        max_videos: int,
    ) -> list[dict[str, Any]]:
        """Process a single page of search results.

        Args:
            items: Search result items.
            videos: Current list of videos.
            max_videos: Maximum videos to collect.

        Returns:
            Updated videos list.
        """
        video_ids = self._extract_video_ids(items)

        if not video_ids:
            return videos

        details = self._get_video_details(video_ids)

        for video in details:
            if len(videos) >= max_videos:
                break
            videos.append(self._normalize_video(video))

        return videos

    def _extract_video_ids(self, items: list[dict[str, Any]]) -> list[str]:
        """Extract video IDs from search items.

        Args:
            items: Search result items.

        Returns:
            List of video IDs.
        """
        return [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]

    def _update_channel_stats(self, handle: str, video_count: int) -> None:
        """Update statistics after channel extraction.

        Args:
            handle: Channel handle.
            video_count: Number of videos extracted.
        """
        self.stats.channels_processed += 1
        self.stats.total_videos += video_count
        self.logger.info(f"channel_extracted: {handle} - {video_count} videos")

    # =========================================================================
    # MAIN EXTRACTION
    # =========================================================================

    def extract(
        self,
        channel_filter: list[str] | None = None,
        max_videos: int | None = None,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Extract videos from configured YouTube channels.

        Args:
            channel_filter: Optional list of channel handles to extract.
                           If None, extracts all configured channels.
            max_videos: Maximum videos per channel (default from config).

        Returns:
            List of normalized video dictionaries.
        """
        self._start_extraction()
        self.validate_config()

        self.logger.info("=" * 60)
        self.logger.info("🎬 YOUTUBE EXTRACTION STARTED")
        self.logger.info("=" * 60)

        all_videos: list[dict[str, Any]] = []
        channels = self.cfg.channel_handles

        # Filter channels if specified
        if channel_filter:
            channels = [c for c in channels if c in channel_filter]

        # Use config default if not specified
        if max_videos is None:
            max_videos = self.cfg.max_videos_per_channel

        for handle in channels:
            videos = self._extract_channel(handle, max_videos)
            all_videos.extend(videos)

        self._end_extraction()
        self._log_stats()

        return all_videos

    def _log_stats(self) -> None:
        """Log extraction statistics."""
        self.logger.info("=" * 60)
        self.logger.info("📊 YOUTUBE EXTRACTION STATS")
        self.logger.info("-" * 60)
        self.logger.info(f"Channels processed : {self.stats.channels_processed}")
        self.logger.info(f"Total videos       : {self.stats.total_videos}")
        self.logger.info(f"API calls          : {self.stats.api_calls}")
        self.logger.info(f"Quota used         : {self.stats.quota_used}")
        self.logger.info(f"Errors             : {self.stats.errors}")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)

"""Spotify Web API extractor for horror podcasts.

Source 2 (E1): REST API with OAuth2 Client Credentials flow.
Podcasts: JUMPSCARE, Monster Squad, ShadowzCast (French horror content).
"""

import base64
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings


@dataclass
class SpotifyToken:
    """OAuth2 access token with expiration tracking."""

    access_token: str
    token_type: str
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 60s margin)."""
        return datetime.now() >= self.expires_at - timedelta(seconds=60)


@dataclass
class SpotifyStats:
    """Extraction statistics."""

    podcasts_processed: int = 0
    total_episodes: int = 0
    api_calls: int = 0
    errors: int = 0
    skipped: int = 0


class SpotifyExtractor(BaseExtractor):
    """Extract podcast episodes from Spotify Web API.

    Uses OAuth2 Client Credentials flow for authentication.
    Rate limited to 1 request/second by default.
    """

    def __init__(self) -> None:
        """Initialize Spotify extractor."""
        super().__init__("SpotifyExtractor")
        self.logger = setup_logger("etl.spotify")
        self.cfg = settings.spotify
        self.session = requests.Session()
        self.token: SpotifyToken | None = None
        self.stats = SpotifyStats()
        self._last_request_time: float = 0.0

    def validate_config(self) -> None:
        """Validate Spotify credentials are configured.

        Raises:
            ValueError: If credentials are missing.
        """
        if not self.cfg.is_configured:
            raise ValueError(
                "Spotify credentials missing. "
                "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"
            )

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    def _authenticate(self) -> SpotifyToken:
        """Authenticate using OAuth2 Client Credentials flow.

        Returns:
            SpotifyToken with access token and expiration.

        Raises:
            requests.RequestException: If authentication fails.
        """
        self.logger.info("spotify_auth_started")

        # Build Basic auth header
        credentials = f"{self.cfg.client_id}:{self.cfg.client_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        response = requests.post(self.cfg.auth_url, headers=headers, data=data, timeout=30)
        response.raise_for_status()

        token_data = response.json()
        expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])

        self.logger.info(f"spotify_auth_success: expires_in={token_data['expires_in']}")

        return SpotifyToken(
            access_token=token_data["access_token"],
            token_type=token_data["token_type"],
            expires_at=expires_at,
        )

    def _ensure_token(self) -> None:
        """Ensure valid token exists, refresh if expired."""
        if self.token is None or self.token.is_expired:
            self.token = self._authenticate()
            self.session.headers.update({"Authorization": f"Bearer {self.token.access_token}"})

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
    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make authenticated API request with rate limiting.

        Args:
            endpoint: API endpoint (e.g., "/shows/{id}").
            params: Optional query parameters.

        Returns:
            JSON response as dictionary.

        Raises:
            requests.RequestException: On API errors.
        """
        self._ensure_token()
        self._rate_limit()

        url = f"{self.cfg.api_base_url}{endpoint}"
        response = self.session.get(url, params=params, timeout=30)

        self.stats.api_calls += 1

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            self.logger.warning(f"spotify_rate_limited: retry_after={retry_after}s")
            time.sleep(retry_after)
            raise requests.RequestException("Rate limited")

        response.raise_for_status()
        return response.json()

    # =========================================================================
    # DATA EXTRACTION
    # =========================================================================

    def _get_show(self, show_id: str) -> dict[str, Any]:
        """Fetch podcast (show) metadata.

        Args:
            show_id: Spotify show ID.

        Returns:
            Show metadata dictionary.
        """
        return self._request(f"/shows/{show_id}", params={"market": "FR"})

    def _get_episodes(self, show_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Fetch episodes for a podcast with pagination.

        Args:
            show_id: Spotify show ID.
            limit: Episodes per page (max 50).
            offset: Pagination offset.

        Returns:
            Episodes response with items and pagination info.
        """
        return self._request(
            f"/shows/{show_id}/episodes",
            params={"market": "FR", "limit": min(limit, 50), "offset": offset},
        )

    def _normalize_episode(self, episode: dict[str, Any], show: dict[str, Any]) -> dict[str, Any]:
        """Normalize episode to standard schema.

        Args:
            episode: Raw episode data from API.
            show: Parent show metadata.

        Returns:
            Normalized episode dictionary.
        """
        return {
            # Identifiers
            "spotify_episode_id": episode.get("id"),
            "spotify_show_id": show.get("id"),
            "source": "spotify",
            # Content
            "title": episode.get("name"),
            "description": episode.get("description"),
            "html_description": episode.get("html_description"),
            # Show info
            "show_name": show.get("name"),
            "show_publisher": show.get("publisher"),
            # Media
            "audio_preview_url": episode.get("audio_preview_url"),
            "duration_ms": episode.get("duration_ms"),
            "images": episode.get("images", []),
            # Dates
            "release_date": episode.get("release_date"),
            "release_date_precision": episode.get("release_date_precision"),
            # Metadata
            "language": episode.get("language"),
            "languages": episode.get("languages", []),
            "explicit": episode.get("explicit", False),
            "external_urls": episode.get("external_urls", {}),
            # Extraction timestamp
            "extracted_at": datetime.now().isoformat(),
        }

    def _extract_podcast(self, podcast_name: str, show_id: str) -> list[dict[str, Any]]:
        """Extract all episodes from a single podcast.

        Args:
            podcast_name: Human-readable podcast name.
            show_id: Spotify show ID.

        Returns:
            List of normalized episode dictionaries.
        """
        self.logger.info(f"extracting_podcast: {podcast_name} ({show_id})")

        try:
            # Get show metadata
            show = self._get_show(show_id)
            episodes: list[dict[str, Any]] = []
            offset = 0
            max_episodes = self.cfg.max_episodes_per_podcast

            # Paginate through episodes
            while len(episodes) < max_episodes:
                response = self._get_episodes(show_id, limit=50, offset=offset)
                items = response.get("items", [])

                if not items:
                    break

                for episode in items:
                    if len(episodes) >= max_episodes:
                        break
                    normalized = self._normalize_episode(episode, show)
                    episodes.append(normalized)

                # Check for more pages
                if response.get("next") is None:
                    break

                offset += 50

            self.stats.podcasts_processed += 1
            self.stats.total_episodes += len(episodes)

            self.logger.info(f"podcast_extracted: {podcast_name} - {len(episodes)} episodes")
            return episodes

        except requests.RequestException as e:
            self.stats.errors += 1
            self.logger.error(f"podcast_extraction_failed: {podcast_name} - {e}")
            return []

    # =========================================================================
    # MAIN EXTRACTION
    # =========================================================================

    def extract(
        self,
        podcast_filter: list[str] | None = None,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Extract episodes from configured horror podcasts.

        Args:
            podcast_filter: Optional list of podcast keys to extract.
                           If None, extracts all configured podcasts.

        Returns:
            List of normalized episode dictionaries.
        """
        self._start_extraction()
        self.validate_config()

        self.logger.info("=" * 60)
        self.logger.info("🎙️ SPOTIFY EXTRACTION STARTED")
        self.logger.info("=" * 60)

        all_episodes: list[dict[str, Any]] = []
        podcasts = self.cfg.podcast_ids

        # Filter podcasts if specified
        if podcast_filter:
            podcasts = {k: v for k, v in podcasts.items() if k in podcast_filter}

        for name, show_id in podcasts.items():
            episodes = self._extract_podcast(name, show_id)
            all_episodes.extend(episodes)

        self._end_extraction()
        self._log_stats()

        return all_episodes

    def _log_stats(self) -> None:
        """Log extraction statistics."""
        self.logger.info("=" * 60)
        self.logger.info("📊 SPOTIFY EXTRACTION STATS")
        self.logger.info("-" * 60)
        self.logger.info(f"Podcasts processed : {self.stats.podcasts_processed}")
        self.logger.info(f"Total episodes     : {self.stats.total_episodes}")
        self.logger.info(f"API calls          : {self.stats.api_calls}")
        self.logger.info(f"Errors             : {self.stats.errors}")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)

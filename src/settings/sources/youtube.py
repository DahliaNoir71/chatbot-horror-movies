"""YouTube Data API v3 configuration settings.

Source 3 (E1): REST API for video content and transcripts.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class YouTubeSettings(BaseSettings):
    """YouTube Data API v3 configuration.

    Supports channel handles and playlist IDs extraction.

    Attributes:
        api_key: YouTube API key.
        channel_handles: List of channel handles to extract from.
        playlist_ids: List of playlist IDs to extract from.
        max_videos: Maximum videos to extract per source.
    """

    api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    base_url: str = Field(
        default="https://www.googleapis.com/youtube/v3",
        alias="YOUTUBE_BASE_URL",
    )

    # Channels (comma-separated handles like @ChannelName)
    channel_handles_raw: str = Field(
        default="",
        alias="YOUTUBE_CHANNEL_HANDLES",
    )

    # Playlists (comma-separated playlist IDs)
    playlist_ids_raw: str = Field(
        default="",
        alias="YOUTUBE_PLAYLIST_IDS",
    )

    # Extraction parameters
    max_videos: int = Field(default=500, alias="YOUTUBE_MAX_VIDEOS")
    extract_transcripts: bool = Field(
        default=True,
        alias="YOUTUBE_EXTRACT_TRANSCRIPTS",
    )

    # Rate limiting
    request_delay: float = Field(default=0.5, alias="YOUTUBE_REQUEST_DELAY")
    daily_quota_limit: int = Field(default=10000, alias="YOUTUBE_DAILY_QUOTA")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Check if YouTube API key is configured."""
        return bool(self.api_key)

    @property
    def channel_handles(self) -> list[str]:
        """Parse channel handles from comma-separated string.

        Returns:
            List of channel handles (e.g., ["@AzzLepouvantail", "@jumpscarecast"]).
        """
        if not self.channel_handles_raw:
            return []
        return [ch.strip() for ch in self.channel_handles_raw.split(",") if ch.strip()]

    @property
    def playlist_ids(self) -> list[str]:
        """Parse playlist IDs from comma-separated string.

        Returns:
            List of playlist IDs.
        """
        if not self.playlist_ids_raw:
            return []
        return [pl.strip() for pl in self.playlist_ids_raw.split(",") if pl.strip()]

    @property
    def has_sources(self) -> bool:
        """Check if any sources (channels or playlists) are configured."""
        return bool(self.channel_handles or self.playlist_ids)

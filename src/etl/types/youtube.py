"""YouTube Data API types.

TypedDict definitions for data structures returned by
YouTube Data API v3 endpoints.
"""

from typing import NotRequired, TypedDict


class YouTubeVideoData(TypedDict):
    """Video data from YouTube Data API v3."""

    # Required fields
    youtube_id: str
    title: str

    # Content
    description: NotRequired[str | None]

    # Channel info
    channel_id: NotRequired[str | None]
    channel_title: NotRequired[str | None]

    # Metrics
    view_count: NotRequired[int]
    like_count: NotRequired[int]
    comment_count: NotRequired[int]

    # Metadata
    duration: NotRequired[str | None]
    published_at: NotRequired[str | None]
    thumbnail_url: NotRequired[str | None]

    # Classification
    video_type: NotRequired[str | None]
    tags: NotRequired[list[str]]


class YouTubeTranscriptData(TypedDict):
    """Transcript data from YouTube."""

    video_id: NotRequired[int]
    youtube_id: NotRequired[str]
    transcript: str
    language: NotRequired[str]
    is_generated: NotRequired[bool]
    word_count: NotRequired[int]


class YouTubeTranscriptSegment(TypedDict):
    """Single segment from YouTube transcript."""

    text: str
    start: float
    duration: float


class YouTubeChannelData(TypedDict):
    """Channel metadata from YouTube API."""

    channel_id: str
    title: str
    description: NotRequired[str | None]
    subscriber_count: NotRequired[int]
    video_count: NotRequired[int]
    thumbnail_url: NotRequired[str | None]


class YouTubePlaylistData(TypedDict):
    """Playlist metadata from YouTube API."""

    playlist_id: str
    title: str
    description: NotRequired[str | None]
    video_count: int
    channel_id: NotRequired[str]
    channel_title: NotRequired[str]


class YouTubePlaylistItemData(TypedDict):
    """Item in a YouTube playlist."""

    video_id: str
    title: str
    position: int
    published_at: NotRequired[str | None]


class YouTubeSearchResultData(TypedDict):
    """Search result from YouTube API."""

    video_id: str
    title: str
    description: str | None
    channel_id: str
    channel_title: str
    published_at: str | None
    thumbnail_url: str | None

"""YouTube extractor package.

Provides extraction from YouTube channels and playlists
using YouTube Data API v3 and youtube_transcript_api.

Classes:
    YouTubeExtractor: Main extractor orchestrating the process.
    YouTubeClient: API client with quota management.
    YouTubeNormalizer: Data transformation to normalized format.
    TranscriptExtractor: Video transcript extraction.

Exceptions:
    YouTubeClientError: Base API error.
    YouTubeQuotaError: API quota exceeded.
    YouTubeNotFoundError: Resource not found.

Example:
    >>> from src.etl.extractors.youtube import YouTubeExtractor
    >>>
    >>> extractor = YouTubeExtractor()
    >>>
    >>> # Full extraction from configured sources
    >>> videos = extractor.extract(include_transcripts=True)
    >>>
    >>> # Single video
    >>> video, transcript = extractor.extract_video("dQw4w9WgXcQ")
"""

from .client import (
    YouTubeClient,
    YouTubeClientError,
    YouTubeNotFoundError,
    YouTubeQuotaError,
)
from .normalizer import YouTubeNormalizer
from .transcript import TranscriptExtractor
from .youtube import YouTubeExtractor, YouTubeStats

__all__ = [
    # Main extractor
    "YouTubeExtractor",
    "YouTubeStats",
    # Client
    "YouTubeClient",
    "YouTubeClientError",
    "YouTubeQuotaError",
    "YouTubeNotFoundError",
    # Components
    "YouTubeNormalizer",
    "TranscriptExtractor",
]

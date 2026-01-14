"""YouTube extraction package.

Provides video extraction from YouTube channels and playlists
with transcript support and film matching capabilities.

Example:
    >>> from src.etl.extractors.youtube import YouTubeExtractor, YouTubeMatcher
    >>>
    >>> extractor = YouTubeExtractor()
    >>> result = extractor.extract(extract_transcripts=True)
    >>>
    >>> matcher = YouTubeMatcher(min_score=0.70)
    >>> match = matcher.match_video(title, candidates)
"""

from src.etl.extractors.youtube.client import (
    YouTubeAPIError,
    YouTubeClient,
    YouTubeNotFoundError,
    YouTubeQuotaExceededError,
)
from src.etl.extractors.youtube.extractor import VideoBundle, YouTubeExtractor
from src.etl.extractors.youtube.matcher import (
    MatchResult,
    ParsedVideoTitle,
    YouTubeMatcher,
)
from src.etl.extractors.youtube.normalizer import YouTubeNormalizer
from src.etl.extractors.youtube.transcript import TranscriptExtractor, TranscriptResult

__all__ = [
    # Main classes
    "YouTubeExtractor",
    "YouTubeClient",
    "YouTubeMatcher",
    "YouTubeNormalizer",
    "TranscriptExtractor",
    # Data classes
    "VideoBundle",
    "MatchResult",
    "ParsedVideoTitle",
    "TranscriptResult",
    # Exceptions
    "YouTubeAPIError",
    "YouTubeNotFoundError",
    "YouTubeQuotaExceededError",
]

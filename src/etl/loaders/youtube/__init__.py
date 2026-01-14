"""YouTube data loaders.

Provides loaders for YouTube videos, transcripts,
and film-video associations.
"""

from src.etl.loaders.youtube.film_video import FilmVideoLoader
from src.etl.loaders.youtube.transcript import TranscriptLoader
from src.etl.loaders.youtube.video import VideoLoader
from src.etl.loaders.youtube.youtube import YouTubeLoader

__all__ = [
    "FilmVideoLoader",
    "TranscriptLoader",
    "VideoLoader",
    "YouTubeLoader",
]

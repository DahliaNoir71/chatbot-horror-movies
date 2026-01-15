"""Data source settings for E1 extraction.

Exports configuration classes for all heterogeneous sources:
- TMDB API (REST)
- Rotten Tomatoes (Scraping)
- Kaggle (CSV + Spark)
"""

from src.settings.sources.kaggle import KaggleSettings
from src.settings.sources.rotten_tomatoes import RTSettings
from src.settings.sources.spark import SparkSettings
from src.settings.sources.tmdb import TMDBSettings

__all__ = [
    "TMDBSettings",
    "RTSettings",
    "KaggleSettings",
    "SparkSettings",
]

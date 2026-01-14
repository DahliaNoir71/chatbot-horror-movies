"""Rotten Tomatoes source repositories.

Repositories for data scraped from Rotten Tomatoes website.
"""

from src.database.repositories.rotten_tomatoes.rt_score import RTScoreRepository

__all__ = [
    "RTScoreRepository",
]

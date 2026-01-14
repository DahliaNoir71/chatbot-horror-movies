"""TMDB source repositories.

Repositories for data extracted from TMDB API.
"""

from src.database.repositories.tmdb.company import (
    ProductionCompanyData,
    ProductionCompanyRepository,
)
from src.database.repositories.tmdb.credit import CreditData, CreditRepository
from src.database.repositories.tmdb.film import FilmRepository
from src.database.repositories.tmdb.genre import GenreRepository
from src.database.repositories.tmdb.keyword import KeywordRepository
from src.database.repositories.tmdb.language import (
    SpokenLanguageData,
    SpokenLanguageRepository,
)

__all__ = [
    "FilmRepository",
    "GenreRepository",
    "KeywordRepository",
    "CreditRepository",
    "CreditData",
    "ProductionCompanyRepository",
    "ProductionCompanyData",
    "SpokenLanguageRepository",
    "SpokenLanguageData",
]

"""TMDB source models.

All models for data extracted from TMDB API:
films, genres, keywords, credits, companies, languages.
"""

from src.database.models.tmdb.company import ProductionCompany
from src.database.models.tmdb.credit import Credit
from src.database.models.tmdb.film import Film
from src.database.models.tmdb.film_company import FilmCompany
from src.database.models.tmdb.film_genre import FilmGenre
from src.database.models.tmdb.film_keyword import FilmKeyword
from src.database.models.tmdb.film_language import FilmLanguage
from src.database.models.tmdb.genre import Genre
from src.database.models.tmdb.keyword import Keyword
from src.database.models.tmdb.language import SpokenLanguage

__all__ = [
    "Film",
    "Genre",
    "Keyword",
    "Credit",
    "ProductionCompany",
    "SpokenLanguage",
    "FilmGenre",
    "FilmKeyword",
    "FilmCompany",
    "FilmLanguage",
]

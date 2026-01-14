"""TMDB loaders package.

Provides loaders for TMDB extraction data:
- TMDBLoader: Main orchestrator for bundles
- FilmLoader: Film data
- CreditLoader: Cast and crew
- AssociationLoader: Junction tables
- ReferenceLoader: Facade for reference data
- GenreLoader: Genre reference data
- KeywordLoader: Keyword reference data
- CompanyLoader: Production company reference data
- LanguageLoader: Spoken language reference data
"""

from src.etl.loaders.tmdb.association import AssociationLoader
from src.etl.loaders.tmdb.company import CompanyLoader
from src.etl.loaders.tmdb.credit import CreditLoader
from src.etl.loaders.tmdb.film import FilmLoader
from src.etl.loaders.tmdb.genre import GenreLoader
from src.etl.loaders.tmdb.keyword import KeywordLoader
from src.etl.loaders.tmdb.language import LanguageLoader
from src.etl.loaders.tmdb.reference import ReferenceLoader
from src.etl.loaders.tmdb.tmdb import TMDBLoader

__all__ = [
    "TMDBLoader",
    "FilmLoader",
    "CreditLoader",
    "AssociationLoader",
    "ReferenceLoader",
    "GenreLoader",
    "KeywordLoader",
    "CompanyLoader",
    "LanguageLoader",
]

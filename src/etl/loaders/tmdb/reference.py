"""TMDB reference data loader facade.

Coordinates all reference data loaders: genres, keywords,
production companies, and spoken languages.
"""

from sqlalchemy.orm import Session

from src.etl.loaders.base import LoaderStats
from src.etl.loaders.tmdb.company import CompanyLoader
from src.etl.loaders.tmdb.genre import GenreLoader
from src.etl.loaders.tmdb.keyword import KeywordLoader
from src.etl.loaders.tmdb.language import LanguageLoader
from src.etl.types import (
    NormalizedCompanyData,
    NormalizedGenreData,
    NormalizedKeywordData,
    NormalizedLanguageData,
)


class ReferenceLoader:
    """Facade for loading all TMDB reference data.

    Coordinates genres, keywords, companies, and languages loaders
    to simplify bulk loading operations.
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._genre = GenreLoader(session)
        self._keyword = KeywordLoader(session)
        self._company = CompanyLoader(session)
        self._language = LanguageLoader(session)

    @property
    def genre(self) -> GenreLoader:
        """Get genre loader.

        Returns:
            GenreLoader instance.
        """
        return self._genre

    @property
    def keyword(self) -> KeywordLoader:
        """Get keyword loader.

        Returns:
            KeywordLoader instance.
        """
        return self._keyword

    @property
    def company(self) -> CompanyLoader:
        """Get company loader.

        Returns:
            CompanyLoader instance.
        """
        return self._company

    @property
    def language(self) -> LanguageLoader:
        """Get language loader.

        Returns:
            LanguageLoader instance.
        """
        return self._language

    def load_all(
        self,
        genres: list[NormalizedGenreData] | None = None,
        keywords: list[NormalizedKeywordData] | None = None,
        companies: list[NormalizedCompanyData] | None = None,
        languages: list[NormalizedLanguageData] | None = None,
    ) -> LoaderStats:
        """Load all reference data types.

        Args:
            genres: Optional list of genres.
            keywords: Optional list of keywords.
            companies: Optional list of companies.
            languages: Optional list of languages.

        Returns:
            Combined LoaderStats from all loaders.
        """
        combined = LoaderStats()

        if genres:
            combined = combined.merge(self._genre.load(genres))
        if keywords:
            combined = combined.merge(self._keyword.load(keywords))
        if companies:
            combined = combined.merge(self._company.load(companies))
        if languages:
            combined = combined.merge(self._language.load(languages))

        return combined

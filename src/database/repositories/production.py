"""Production company and language repositories.

Provides CRUD and lookup operations for production
companies and spoken languages from Kaggle/Spark data.
"""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.production import (
    FilmCompany,
    FilmLanguage,
    ProductionCompany,
    SpokenLanguage,
)
from src.database.repositories.base import BaseRepository


class ProductionCompanyData(TypedDict, total=False):
    """Typed dictionary for production company input data."""

    name: str
    tmdb_company_id: int | None
    origin_country: str | None


class SpokenLanguageData(TypedDict):
    """Typed dictionary for spoken language input data."""

    iso_639_1: str
    name: str


class ProductionCompanyRepository(BaseRepository[ProductionCompany]):
    """Repository for ProductionCompany entity operations.

    Production companies are studios like Blumhouse, A24, etc.
    """

    model = ProductionCompany

    def __init__(self, session: Session) -> None:
        """Initialize production company repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_tmdb_id(self, tmdb_company_id: int) -> ProductionCompany | None:
        """Retrieve company by TMDB identifier.

        Args:
            tmdb_company_id: TMDB company ID.

        Returns:
            ProductionCompany instance or None.
        """
        return self.get_by_field("tmdb_company_id", tmdb_company_id)

    def get_by_name(self, name: str) -> ProductionCompany | None:
        """Retrieve company by name.

        Args:
            name: Company name.

        Returns:
            ProductionCompany instance or None.
        """
        return self.get_by_field("name", name)

    def get_or_create(
        self,
        name: str,
        tmdb_company_id: int | None = None,
        origin_country: str | None = None,
    ) -> ProductionCompany:
        """Get existing company or create new one.

        Args:
            name: Company name.
            tmdb_company_id: Optional TMDB company ID.
            origin_country: Optional ISO country code.

        Returns:
            ProductionCompany instance.
        """
        if tmdb_company_id:
            existing = self.get_by_tmdb_id(tmdb_company_id)
            if existing:
                return existing

        existing = self.get_by_name(name)
        if existing:
            return existing

        company = ProductionCompany(
            name=name,
            tmdb_company_id=tmdb_company_id,
            origin_country=origin_country,
        )
        return self.create(company)

    def get_id_map(self) -> dict[int, int]:
        """Get mapping of TMDB company IDs to internal IDs.

        Returns:
            Dictionary mapping tmdb_company_id to id.
        """
        stmt = select(ProductionCompany.tmdb_company_id, ProductionCompany.id).where(
            ProductionCompany.tmdb_company_id != None  # noqa: E711
        )
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def get_name_map(self) -> dict[str, int]:
        """Get mapping of company names to internal IDs.

        Returns:
            Dictionary mapping name to id.
        """
        stmt = select(ProductionCompany.name, ProductionCompany.id)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def bulk_upsert(self, companies_data: list[ProductionCompanyData]) -> int:
        """Bulk insert or update companies.

        Args:
            companies_data: List of company dictionaries.

        Returns:
            Number of companies processed.
        """
        if not companies_data:
            return 0

        stmt = insert(ProductionCompany).values(companies_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        self._session.execute(stmt)
        self._session.flush()
        return len(companies_data)

    def add_to_film(self, film_id: int, company_id: int) -> None:
        """Associate company with a film.

        Args:
            film_id: Film primary key.
            company_id: Company primary key.
        """
        stmt = (
            insert(FilmCompany)
            .values(film_id=film_id, company_id=company_id)
            .on_conflict_do_nothing()
        )
        self._session.execute(stmt)


class SpokenLanguageRepository(BaseRepository[SpokenLanguage]):
    """Repository for SpokenLanguage entity operations.

    Spoken languages are ISO 639-1 language codes.
    """

    model = SpokenLanguage

    def __init__(self, session: Session) -> None:
        """Initialize spoken language repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_iso(self, iso_639_1: str) -> SpokenLanguage | None:
        """Retrieve language by ISO code.

        Args:
            iso_639_1: ISO 639-1 language code.

        Returns:
            SpokenLanguage instance or None.
        """
        return self.get_by_field("iso_639_1", iso_639_1)

    def get_or_create(self, iso_639_1: str, name: str) -> SpokenLanguage:
        """Get existing language or create new one.

        Args:
            iso_639_1: ISO 639-1 code.
            name: Language name in English.

        Returns:
            SpokenLanguage instance.
        """
        existing = self.get_by_iso(iso_639_1)
        if existing:
            return existing

        language = SpokenLanguage(iso_639_1=iso_639_1, name=name)
        return self.create(language)

    def get_id_map(self) -> dict[str, int]:
        """Get mapping of ISO codes to internal IDs.

        Returns:
            Dictionary mapping iso_639_1 to id.
        """
        stmt = select(SpokenLanguage.iso_639_1, SpokenLanguage.id)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def bulk_upsert(self, languages_data: list[SpokenLanguageData]) -> int:
        """Bulk insert or update languages.

        Args:
            languages_data: List of language dictionaries.

        Returns:
            Number of languages processed.
        """
        if not languages_data:
            return 0

        stmt = insert(SpokenLanguage).values(languages_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["iso_639_1"])
        self._session.execute(stmt)
        self._session.flush()
        return len(languages_data)

    def add_to_film(self, film_id: int, language_id: int) -> None:
        """Associate language with a film.

        Args:
            film_id: Film primary key.
            language_id: Language primary key.
        """
        stmt = (
            insert(FilmLanguage)
            .values(film_id=film_id, language_id=language_id)
            .on_conflict_do_nothing()
        )
        self._session.execute(stmt)

    def get_all_sorted(self) -> list[SpokenLanguage]:
        """Get all languages sorted by name.

        Returns:
            List of all languages.
        """
        stmt = select(SpokenLanguage).order_by(SpokenLanguage.name)
        return list(self._session.scalars(stmt).all())

"""Production company repository.

Provides CRUD and lookup operations for production
companies (studios like Blumhouse, A24, etc.).
"""

from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.tmdb import FilmCompany, ProductionCompany
from src.database.repositories.base import BaseRepository


class ProductionCompanyData(TypedDict, total=False):
    """Typed dictionary for production company input data."""

    name: str
    tmdb_company_id: int | None
    origin_country: str | None


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

        Uses tmdb_company_id as conflict target (unique identifier).

        Args:
            companies_data: List of company dictionaries.

        Returns:
            Number of companies processed.
        """
        if not companies_data:
            return 0

        stmt = insert(ProductionCompany).values(companies_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_company_id"],
            set_={
                "name": stmt.excluded.name,
                "origin_country": stmt.excluded.origin_country,
            },
        )
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

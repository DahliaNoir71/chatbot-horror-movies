"""TMDB production company reference data loader.

Handles company entity insertion with upsert on tmdb_company_id.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.database.models import ProductionCompany
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedCompanyData


class CompanyLoader(BaseLoader):
    """Loader for production company reference data.

    Uses tmdb_company_id as unique constraint for upsert.
    """

    name = "tmdb.company"

    def load(self, companies: list[NormalizedCompanyData]) -> LoaderStats:
        """Load production companies into database.

        Args:
            companies: List of normalized company data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not companies:
            return self.stats

        self._logger.info(f"Loading {len(companies)} companies")
        for company_data in companies:
            self._upsert_company(company_data)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_company(self, data: NormalizedCompanyData) -> None:
        """Upsert a single production company.

        Args:
            data: Normalized company data dictionary.
        """
        stmt = insert(ProductionCompany).values(
            tmdb_company_id=data["tmdb_company_id"],
            name=data["name"],
            origin_country=data.get("origin_country"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_company_id"],
            set_={
                "name": stmt.excluded.name,
                "origin_country": stmt.excluded.origin_country,
            },
        )
        result = self._session.execute(stmt)
        self._record_insert() if result.rowcount > 0 else self._record_skip()

    def get_id_map(self) -> dict[int, int]:
        """Get mapping of tmdb_company_id to internal id.

        Returns:
            Dictionary mapping TMDB company IDs to internal IDs.
        """
        stmt = select(ProductionCompany.tmdb_company_id, ProductionCompany.id)
        rows = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in rows if row[0] is not None}

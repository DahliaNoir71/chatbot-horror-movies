"""TMDB keyword reference data loader.

Handles keyword entity insertion with upsert on tmdb_keyword_id.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.database.models import Keyword
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedKeywordData


class KeywordLoader(BaseLoader):
    """Loader for keyword reference data.

    Uses tmdb_keyword_id as unique constraint for upsert.
    """

    name = "tmdb.keyword"

    def load(self, keywords: list[NormalizedKeywordData]) -> LoaderStats:
        """Load keywords into database.

        Args:
            keywords: List of normalized keyword data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not keywords:
            return self.stats

        self._logger.info(f"Loading {len(keywords)} keywords")
        for kw_data in keywords:
            self._upsert_keyword(kw_data)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_keyword(self, data: NormalizedKeywordData) -> None:
        """Upsert a single keyword.

        Args:
            data: Normalized keyword data dictionary.
        """
        stmt = insert(Keyword).values(
            tmdb_keyword_id=data["tmdb_keyword_id"],
            name=data["name"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_keyword_id"],
            set_={"name": stmt.excluded.name},
        )
        result = self._session.execute(stmt)
        self._record_insert() if result.rowcount > 0 else self._record_skip()

    def get_id_map(self) -> dict[int, int]:
        """Get mapping of tmdb_keyword_id to internal id.

        Returns:
            Dictionary mapping TMDB keyword IDs to internal IDs.
        """
        stmt = select(Keyword.tmdb_keyword_id, Keyword.id)
        rows = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in rows if row[0] is not None}

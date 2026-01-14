"""TMDB spoken language reference data loader.

Handles language entity insertion with upsert on iso_639_1.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.database.models import SpokenLanguage
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedLanguageData


class LanguageLoader(BaseLoader):
    """Loader for spoken language reference data.

    Uses iso_639_1 as unique constraint for upsert.
    """

    name = "tmdb.language"

    def load(self, languages: list[NormalizedLanguageData]) -> LoaderStats:
        """Load spoken languages into database.

        Args:
            languages: List of normalized language data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not languages:
            return self.stats

        self._logger.info(f"Loading {len(languages)} languages")
        for lang_data in languages:
            self._upsert_language(lang_data)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_language(self, data: NormalizedLanguageData) -> None:
        """Upsert a single spoken language.

        Args:
            data: Normalized language data dictionary.
        """
        stmt = insert(SpokenLanguage).values(
            iso_639_1=data["iso_639_1"],
            name=data["name"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["iso_639_1"],
            set_={"name": stmt.excluded.name},
        )
        result = self._session.execute(stmt)
        self._record_insert() if result.rowcount > 0 else self._record_skip()

    def get_id_map(self) -> dict[str, int]:
        """Get mapping of iso_639_1 to internal id.

        Returns:
            Dictionary mapping ISO language codes to internal IDs.
        """
        stmt = select(SpokenLanguage.iso_639_1, SpokenLanguage.id)
        rows = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in rows}

"""TMDB genre reference data loader.

Handles genre entity insertion with upsert on tmdb_genre_id.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.database.models import Genre
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedGenreData


class GenreLoader(BaseLoader):
    """Loader for genre reference data.

    Uses tmdb_genre_id as unique constraint for upsert.
    """

    name = "tmdb.genre"

    def load(self, genres: list[NormalizedGenreData]) -> LoaderStats:
        """Load genres into database.

        Args:
            genres: List of normalized genre data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not genres:
            return self.stats

        self._logger.info(f"Loading {len(genres)} genres")
        for genre_data in genres:
            self._upsert_genre(genre_data)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_genre(self, data: NormalizedGenreData) -> None:
        """Upsert a single genre.

        Args:
            data: Normalized genre data dictionary.
        """
        stmt = insert(Genre).values(
            tmdb_genre_id=data["tmdb_genre_id"],
            name=data["name"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_genre_id"],
            set_={"name": stmt.excluded.name},
        )
        result = self._session.execute(stmt)
        self._record_insert() if result.rowcount > 0 else self._record_skip()

    def get_id_map(self) -> dict[int, int]:
        """Get mapping of tmdb_genre_id to internal id.

        Returns:
            Dictionary mapping TMDB genre IDs to internal IDs.
        """
        stmt = select(Genre.tmdb_genre_id, Genre.id)
        rows = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in rows}

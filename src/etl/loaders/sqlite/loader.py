"""IMDB loader for film enrichment.

Enriches existing films with IMDB ratings and metadata
by matching on imdb_id field.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.database.models.tmdb.film import Film
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types.imdb import IMDBEnrichmentStats, IMDBNormalized


class IMDBLoader(BaseLoader):
    """Loads IMDB data to enrich existing films.

    Matches films by imdb_id and updates:
    - IMDB rating (stored separately or as reference)
    - Runtime if missing

    Attributes:
        name: Loader identifier.
    """

    name = "imdb"

    def __init__(self, session: Session) -> None:
        """Initialize IMDB loader.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)
        self._matched_count: int = 0
        self._runtime_updates: int = 0
        self._not_found: int = 0

    # -------------------------------------------------------------------------
    # Main Load
    # -------------------------------------------------------------------------

    def load(self, data: list[IMDBNormalized]) -> LoaderStats:
        """Load IMDB data to enrich films.

        Args:
            data: List of normalized IMDB data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        self._reset_enrichment_counters()

        total = len(data)
        self._logger.info(f"Enriching films with {total} IMDB records")

        for idx, imdb_data in enumerate(data):
            self._process_record(imdb_data)
            self._log_progress(idx + 1, total)

        self._session.commit()
        self._log_summary()
        self._log_enrichment_summary()

        return self.stats

    def _process_record(self, imdb_data: IMDBNormalized) -> None:
        """Process a single IMDB record.

        Args:
            imdb_data: Normalized IMDB data.
        """
        imdb_id = imdb_data["imdb_id"]

        try:
            film = self._find_film_by_imdb_id(imdb_id)
            if film:
                self._enrich_film(film, imdb_data)
            else:
                self._not_found += 1
                self._record_skip()
        except Exception as e:
            self._record_error(f"Failed imdb_id={imdb_id}: {e}")

    # -------------------------------------------------------------------------
    # Film Lookup
    # -------------------------------------------------------------------------

    def _find_film_by_imdb_id(self, imdb_id: str) -> Film | None:
        """Find film by IMDB ID.

        Args:
            imdb_id: IMDB tconst.

        Returns:
            Film or None if not found.
        """
        stmt = select(Film).where(Film.imdb_id == imdb_id)
        return self._session.scalars(stmt).first()

    def get_films_with_imdb_ids(self) -> list[str]:
        """Get all films that have IMDB IDs.

        Returns:
            List of IMDB IDs from existing films.
        """
        stmt = select(Film.imdb_id).where(Film.imdb_id.isnot(None))
        results = self._session.scalars(stmt).all()
        return [r for r in results if r]

    def get_films_without_imdb_data(
        self,
        limit: int | None = None,
    ) -> list[dict[str, str | int | None]]:
        """Get films that have imdb_id but no IMDB enrichment.

        Args:
            limit: Optional max results.

        Returns:
            List of film dicts with id, title, imdb_id.
        """
        stmt = select(Film.id, Film.title, Film.imdb_id).where(Film.imdb_id.isnot(None))

        if limit:
            stmt = stmt.limit(limit)

        results = self._session.execute(stmt).fetchall()

        return [{"id": r.id, "title": r.title, "imdb_id": r.imdb_id} for r in results]

    # -------------------------------------------------------------------------
    # Enrichment Logic
    # -------------------------------------------------------------------------

    def _enrich_film(self, film: Film, imdb_data: IMDBNormalized) -> None:
        """Enrich film with IMDB data.

        Args:
            film: Film to enrich.
            imdb_data: IMDB data.
        """
        updated = self._apply_enrichment(film, imdb_data)

        if updated:
            self._matched_count += 1
            self._record_update()
        else:
            self._record_skip()

    def _apply_enrichment(
        self,
        film: Film,
        imdb_data: IMDBNormalized,
    ) -> bool:
        """Apply IMDB enrichment to film.

        Args:
            film: Film entity.
            imdb_data: IMDB data.

        Returns:
            True if any field was updated.
        """
        updated = False

        # Update runtime if missing
        if self._should_update_runtime(film, imdb_data):
            film.runtime = imdb_data["runtime"]
            self._runtime_updates += 1
            updated = True

        return updated

    @staticmethod
    def _should_update_runtime(
        film: Film,
        imdb_data: IMDBNormalized,
    ) -> bool:
        """Check if runtime should be updated.

        Args:
            film: Existing film.
            imdb_data: IMDB data.

        Returns:
            True if should update.
        """
        current = film.runtime
        new_value = imdb_data.get("runtime")
        return current is None and new_value is not None

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_update_runtime(
        self,
        data: list[IMDBNormalized],
    ) -> int:
        """Bulk update runtime for films.

        Args:
            data: List of IMDB data with runtime.

        Returns:
            Number of films updated.
        """
        updated_count = 0

        for imdb_data in data:
            runtime = imdb_data.get("runtime")
            if runtime is None:
                continue

            stmt = (
                update(Film)
                .where(Film.imdb_id == imdb_data["imdb_id"])
                .where(Film.runtime.is_(None))
                .values(runtime=runtime)
            )

            result = self._session.execute(stmt)
            updated_count += result.rowcount

        self._session.commit()
        self._logger.info(f"Bulk updated runtime for {updated_count} films")

        return updated_count

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def _reset_enrichment_counters(self) -> None:
        """Reset enrichment-specific counters."""
        self._matched_count = 0
        self._runtime_updates = 0
        self._not_found = 0

    def _log_enrichment_summary(self) -> None:
        """Log enrichment-specific statistics."""
        self._logger.info(
            f"Enrichment: matched={self._matched_count}, "
            f"runtime_updates={self._runtime_updates}, "
            f"not_found={self._not_found}"
        )

    def get_enrichment_stats(self) -> IMDBEnrichmentStats:
        """Get detailed enrichment statistics.

        Returns:
            IMDBEnrichmentStats with counts.
        """
        return IMDBEnrichmentStats(
            films_matched=self._matched_count,
            ratings_updated=0,
            runtime_updated=self._runtime_updates,
            not_found=self._not_found,
            errors=self._stats.errors,
        )

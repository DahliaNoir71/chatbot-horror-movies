"""Kaggle CSV loader.

Inserts or updates films from Kaggle horror movies dataset.
Enriches existing TMDB films with budget/revenue data.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.models.tmdb.film import Film
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types.kaggle import KaggleEnrichmentStats, KaggleHorrorMovieNormalized


class KaggleLoader(BaseLoader):
    """Loads Kaggle horror movies into database.

    Performs upsert operations:
    - Existing films (by tmdb_id): enriches budget/revenue
    - New films: inserts complete record

    Attributes:
        name: Loader identifier.
    """

    name = "kaggle"

    def __init__(self, session: Session) -> None:
        """Initialize Kaggle loader.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)
        self._enriched_count: int = 0
        self._budget_updates: int = 0
        self._revenue_updates: int = 0

    # -------------------------------------------------------------------------
    # Main Load
    # -------------------------------------------------------------------------

    def load(self, data: list[KaggleHorrorMovieNormalized]) -> LoaderStats:
        """Load Kaggle movies into database.

        Args:
            data: List of normalized movie data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        self._reset_enrichment_counters()

        total = len(data)
        self._logger.info(f"Loading {total} Kaggle movies")

        existing_ids = self._get_existing_tmdb_ids()

        for idx, movie_data in enumerate(data):
            self._process_movie(movie_data, existing_ids)
            self._log_progress(idx + 1, total)

        self._session.commit()
        self._log_summary()
        self._log_enrichment_summary()

        return self.stats

    def _process_movie(
        self,
        movie_data: KaggleHorrorMovieNormalized,
        existing_ids: set[int],
    ) -> None:
        """Process a single movie record.

        Args:
            movie_data: Normalized movie data.
            existing_ids: Set of existing TMDB IDs.
        """
        tmdb_id = movie_data["tmdb_id"]

        try:
            if tmdb_id in existing_ids:
                self._enrich_existing(movie_data)
            else:
                self._insert_new(movie_data)
        except Exception as e:
            self._record_error(f"Failed tmdb_id={tmdb_id}: {e}")

    # -------------------------------------------------------------------------
    # Database Operations
    # -------------------------------------------------------------------------

    def _get_existing_tmdb_ids(self) -> set[int]:
        """Get all existing TMDB IDs from database.

        Returns:
            Set of TMDB IDs.
        """
        stmt = select(Film.tmdb_id)
        return set(self._session.scalars(stmt).all())

    def _enrich_existing(self, movie_data: KaggleHorrorMovieNormalized) -> None:
        """Enrich existing film with Kaggle data.

        Updates budget/revenue if currently zero.

        Args:
            movie_data: Normalized movie data.
        """
        tmdb_id = movie_data["tmdb_id"]
        stmt = select(Film).where(Film.tmdb_id == tmdb_id)
        film = self._session.scalars(stmt).first()

        if film is None:
            self._record_skip()
            return

        updated = self._apply_enrichment(film, movie_data)

        if updated:
            self._record_update()
            self._enriched_count += 1
        else:
            self._record_skip()

    def _apply_enrichment(
        self,
        film: Film,
        movie_data: KaggleHorrorMovieNormalized,
    ) -> bool:
        """Apply enrichment data to existing film.

        Args:
            film: Existing film record.
            movie_data: Kaggle data with budget/revenue.

        Returns:
            True if any field was updated.
        """
        updated = False

        # Enrich budget if missing
        if self._should_update_budget(film, movie_data):
            film.budget = movie_data["budget"]
            self._budget_updates += 1
            updated = True

        # Enrich revenue if missing
        if self._should_update_revenue(film, movie_data):
            film.revenue = movie_data["revenue"]
            self._revenue_updates += 1
            updated = True

        return updated

    @staticmethod
    def _should_update_budget(
        film: Film,
        movie_data: KaggleHorrorMovieNormalized,
    ) -> bool:
        """Check if budget should be updated.

        Args:
            film: Existing film.
            movie_data: Kaggle data.

        Returns:
            True if should update.
        """
        current = film.budget or 0
        new_value = movie_data.get("budget", 0)
        return current == 0 and new_value > 0

    @staticmethod
    def _should_update_revenue(
        film: Film,
        movie_data: KaggleHorrorMovieNormalized,
    ) -> bool:
        """Check if revenue should be updated.

        Args:
            film: Existing film.
            movie_data: Kaggle data.

        Returns:
            True if should update.
        """
        current = film.revenue or 0
        new_value = movie_data.get("revenue", 0)
        return current == 0 and new_value > 0

    def _insert_new(self, movie_data: KaggleHorrorMovieNormalized) -> None:
        """Insert new film from Kaggle data.

        Args:
            movie_data: Normalized movie data.
        """
        film = self._build_film_entity(movie_data)
        self._session.add(film)
        self._session.flush()
        self._record_insert()

    def _build_film_entity(self, movie_data: KaggleHorrorMovieNormalized) -> Film:
        """Build Film entity from normalized data.

        Args:
            movie_data: Normalized Kaggle data.

        Returns:
            Film entity ready for insertion.
        """
        return Film(
            tmdb_id=movie_data["tmdb_id"],
            title=movie_data["title"],
            original_title=movie_data.get("original_title"),
            original_language=movie_data.get("original_language"),
            overview=movie_data.get("overview"),
            tagline=movie_data.get("tagline"),
            release_date=self._parse_release_date(movie_data.get("release_date")),
            poster_path=movie_data.get("poster_path"),
            backdrop_path=movie_data.get("backdrop_path"),
            popularity=movie_data.get("popularity", 0.0),
            vote_average=movie_data.get("vote_average", 0.0),
            vote_count=movie_data.get("vote_count", 0),
            budget=movie_data.get("budget", 0),
            revenue=movie_data.get("revenue", 0),
            runtime=movie_data.get("runtime"),
            status=movie_data.get("status", "Released"),
            adult=movie_data.get("adult", False),
            source="kaggle",
        )

    @staticmethod
    def _parse_release_date(date_str: str | None) -> date | None:
        """Parse release date string.

        Args:
            date_str: ISO format date string.

        Returns:
            Date object or None.
        """
        if not date_str:
            return None
        from datetime import date

        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_upsert(self, data: list[KaggleHorrorMovieNormalized]) -> LoaderStats:
        """Bulk upsert using PostgreSQL ON CONFLICT.

        More efficient for large datasets.

        Args:
            data: List of normalized movie data.

        Returns:
            LoaderStats with results.
        """
        self.reset_stats()
        self._logger.info(f"Bulk upserting {len(data)} movies")

        for movie_data in data:
            self._upsert_single(movie_data)

        self._session.commit()
        self._log_summary()

        return self.stats

    def _upsert_single(self, movie_data: KaggleHorrorMovieNormalized) -> None:
        """Upsert a single movie using ON CONFLICT.

        Args:
            movie_data: Normalized movie data.
        """
        values = self._prepare_upsert_values(movie_data)
        stmt = self._build_upsert_statement(values)

        try:
            self._session.execute(stmt)
            self._record_insert()
        except Exception as e:
            self._record_error(f"Upsert failed: {e}")

    def _prepare_upsert_values(
        self,
        movie_data: KaggleHorrorMovieNormalized,
    ) -> dict[str, str | int | float | bool | date | None]:
        """Prepare values dict for upsert.

        Args:
            movie_data: Normalized data.

        Returns:
            Dict of column values.
        """
        return {
            "tmdb_id": movie_data["tmdb_id"],
            "title": movie_data["title"],
            "original_title": movie_data.get("original_title"),
            "original_language": movie_data.get("original_language"),
            "overview": movie_data.get("overview"),
            "tagline": movie_data.get("tagline"),
            "release_date": self._parse_release_date(movie_data.get("release_date")),
            "poster_path": movie_data.get("poster_path"),
            "backdrop_path": movie_data.get("backdrop_path"),
            "popularity": movie_data.get("popularity", 0.0),
            "vote_average": movie_data.get("vote_average", 0.0),
            "vote_count": movie_data.get("vote_count", 0),
            "budget": movie_data.get("budget", 0),
            "revenue": movie_data.get("revenue", 0),
            "runtime": movie_data.get("runtime"),
            "status": movie_data.get("status", "Released"),
            "adult": movie_data.get("adult", False),
            "source": "kaggle",
        }

    def _build_upsert_statement(
        self, values: dict[str, str | int | float | bool | date | None]
    ) -> Insert:
        """Build PostgreSQL upsert statement.

        Args:
            values: Column values.

        Returns:
            SQLAlchemy insert statement.
        """
        stmt = pg_insert(Film).values(**values)
        return stmt.on_conflict_do_update(
            index_elements=["tmdb_id"],
            set_={
                "budget": stmt.excluded.budget,
                "revenue": stmt.excluded.revenue,
            },
        )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def _reset_enrichment_counters(self) -> None:
        """Reset enrichment-specific counters."""
        self._enriched_count = 0
        self._budget_updates = 0
        self._revenue_updates = 0

    def _log_enrichment_summary(self) -> None:
        """Log enrichment-specific statistics."""
        self._logger.info(
            f"Enrichment: {self._enriched_count} films, "
            f"budget={self._budget_updates}, revenue={self._revenue_updates}"
        )

    def get_enrichment_stats(self) -> KaggleEnrichmentStats:
        """Get detailed enrichment statistics.

        Returns:
            KaggleEnrichmentStats with counts.
        """
        return KaggleEnrichmentStats(
            films_enriched=self._enriched_count,
            films_inserted=self._stats.inserted,
            budget_updates=self._budget_updates,
            revenue_updates=self._revenue_updates,
            skipped=self._stats.skipped,
            errors=self._stats.errors,
        )

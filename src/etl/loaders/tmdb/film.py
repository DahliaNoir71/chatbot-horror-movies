"""TMDB film data loader.

Handles film entity insertion with upsert on tmdb_id.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert, insert

from src.database.models import Film
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedFilmData


class FilmLoader(BaseLoader):
    """Loader for film data.

    Uses tmdb_id as unique constraint for upsert operations.
    """

    name = "tmdb.film"

    def load(self, data: object) -> LoaderStats:
        """Load films into database.

        Args:
            data: List of NormalizedFilmData dictionaries.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        films = self._validate_input(data)
        if not films:
            return self.stats

        self._logger.info(f"Loading {len(films)} films")
        for idx, film_data in enumerate(films, 1):
            self._upsert_film(film_data)
            self._log_progress(idx, len(films))

        self._session.flush()
        self._log_summary()
        return self.stats

    def _validate_input(self, data: object) -> list[NormalizedFilmData]:
        """Validate and cast input data.

        Args:
            data: Raw input data.

        Returns:
            Validated list of film data.
        """
        if not isinstance(data, list):
            self._record_error("Input must be a list")
            return []
        return data  # type: ignore[return-value]

    def _upsert_film(self, data: NormalizedFilmData) -> None:
        """Upsert a single film record.

        Args:
            data: Normalized film data dictionary.
        """
        try:
            stmt = insert(Film).values(**self._build_values(data))
            stmt = stmt.on_conflict_do_update(
                index_elements=["tmdb_id"],
                set_=self._build_update_set(stmt),
            )
            self._session.execute(stmt)
            self._record_insert()
        except Exception as e:
            self._record_error(f"Film {data['tmdb_id']} failed: {e}")

    def get_id_by_tmdb_id(self, tmdb_id: int) -> int | None:
        """Get internal film ID by TMDB ID.

        Args:
            tmdb_id: TMDB unique identifier.

        Returns:
            Internal database ID or None if not found.
        """
        stmt = select(Film.id).where(Film.tmdb_id == tmdb_id)
        return self._session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _build_values(data: NormalizedFilmData) -> dict[str, object]:
        """Build INSERT values from normalized data.

        Args:
            data: Normalized film data dictionary.

        Returns:
            Dictionary of column-value pairs for INSERT.
        """
        return {
            "tmdb_id": data["tmdb_id"],
            "imdb_id": data.get("imdb_id"),
            "title": data["title"],
            "original_title": data.get("original_title"),
            "release_date": data.get("release_date"),
            "tagline": data.get("tagline"),
            "overview": data.get("overview"),
            "popularity": data.get("popularity", 0.0),
            "vote_average": data.get("vote_average", 0.0),
            "vote_count": data.get("vote_count", 0),
            "runtime": data.get("runtime"),
            "original_language": data.get("original_language"),
            "status": data.get("status", "Unknown"),
            "adult": data.get("adult", False),
            "poster_path": data.get("poster_path"),
            "backdrop_path": data.get("backdrop_path"),
            "homepage": data.get("homepage"),
            "budget": data.get("budget", 0),
            "revenue": data.get("revenue", 0),
            "source": data.get("source", "tmdb"),
        }

    @staticmethod
    def _build_update_set(stmt: Insert) -> dict[str, object]:
        """Build SET clause for upsert conflict resolution.

        Args:
            stmt: PostgreSQL INSERT statement with excluded pseudo-table.

        Returns:
            Dictionary mapping column names to excluded values.
        """
        excluded = stmt.excluded
        return {
            "imdb_id": excluded.imdb_id,
            "title": excluded.title,
            "original_title": excluded.original_title,
            "release_date": excluded.release_date,
            "tagline": excluded.tagline,
            "overview": excluded.overview,
            "popularity": excluded.popularity,
            "vote_average": excluded.vote_average,
            "vote_count": excluded.vote_count,
            "runtime": excluded.runtime,
            "original_language": excluded.original_language,
            "status": excluded.status,
            "adult": excluded.adult,
            "poster_path": excluded.poster_path,
            "backdrop_path": excluded.backdrop_path,
            "homepage": excluded.homepage,
            "budget": excluded.budget,
            "revenue": excluded.revenue,
            "source": excluded.source,
        }

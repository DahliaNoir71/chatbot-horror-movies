"""Rotten Tomatoes score loader.

Inserts normalized RT scores into PostgreSQL.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult

from src.database.models.rotten_tomatoes import RTScore
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import NormalizedRTScoreData


class RTScoreLoader(BaseLoader):
    """Loads RT scores into database.

    Performs upsert operations on rt_scores table,
    linking scores to existing films.
    """

    name = "rt_score"

    def load(self, data: list[NormalizedRTScoreData]) -> LoaderStats:
        """Load RT scores into database.

        Args:
            data: List of normalized RT score data.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        total = len(data)

        self._logger.info(f"Loading {total} RT scores")

        for idx, score_data in enumerate(data):
            self._load_single_score(score_data)
            self._log_progress(idx + 1, total)

        self._session.commit()
        self._log_summary()

        return self.stats

    def _load_single_score(self, score_data: NormalizedRTScoreData) -> None:
        """Load a single RT score.

        Args:
            score_data: Normalized RT score data.
        """
        film_id = score_data.get("film_id")
        if not film_id:
            self._record_error("Missing film_id in RT score data")
            return

        try:
            self._upsert_score(score_data)
        except Exception as e:
            self._record_error(f"Failed to load RT score for film {film_id}: {e}")

    def _upsert_score(self, score_data: NormalizedRTScoreData) -> None:
        """Upsert RT score using PostgreSQL ON CONFLICT.

        Args:
            score_data: Normalized RT score data.
        """
        stmt = pg_insert(RTScore).values(
            film_id=score_data["film_id"],
            tomatometer_score=score_data.get("tomatometer_score"),
            tomatometer_state=score_data.get("tomatometer_state"),
            critics_count=score_data.get("critics_count", 0),
            critics_average_rating=score_data.get("critics_average_rating"),
            audience_score=score_data.get("audience_score"),
            audience_state=score_data.get("audience_state"),
            audience_count=score_data.get("audience_count", 0),
            audience_average_rating=score_data.get("audience_average_rating"),
            critics_consensus=score_data.get("critics_consensus"),
            rt_url=score_data.get("rt_url"),
            rt_rating=score_data.get("rt_rating"),
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["film_id"],
            set_={
                "tomatometer_score": stmt.excluded.tomatometer_score,
                "tomatometer_state": stmt.excluded.tomatometer_state,
                "critics_count": stmt.excluded.critics_count,
                "critics_average_rating": stmt.excluded.critics_average_rating,
                "audience_score": stmt.excluded.audience_score,
                "audience_state": stmt.excluded.audience_state,
                "audience_count": stmt.excluded.audience_count,
                "audience_average_rating": stmt.excluded.audience_average_rating,
                "critics_consensus": stmt.excluded.critics_consensus,
                "rt_url": stmt.excluded.rt_url,
                "rt_rating": stmt.excluded.rt_rating,
            },
        )

        result = self._session.execute(stmt)

        if self._is_insert(result):
            self._record_insert()
        else:
            self._record_update()

    @staticmethod
    def _is_insert(result: CursorResult) -> bool:
        """Check if result was an insert vs update.

        Args:
            result: SQLAlchemy execution result.

        Returns:
            True if insert, False if update.
        """
        return result.rowcount > 0

    def get_films_without_rt(self, limit: int | None = None) -> list[dict[str, int | str | None]]:
        """Get films that don't have RT scores.

        Args:
            limit: Optional max films to return.

        Returns:
            List of film dicts with id, title, year.
        """
        from src.database.models.tmdb.film import Film

        subquery = select(RTScore.film_id)

        query = (
            select(Film.id, Film.title, Film.original_title, Film.release_date)
            .where(Film.id.notin_(subquery))
            .order_by(Film.popularity.desc())
        )

        if limit:
            query = query.limit(limit)

        results = self._session.execute(query).fetchall()

        return [
            {
                "id": r.id,
                "title": r.title,
                "original_title": r.original_title,
                "year": r.release_date.year if r.release_date else None,
            }
            for r in results
        ]

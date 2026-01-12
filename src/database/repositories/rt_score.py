"""Rotten Tomatoes score repository.

Provides CRUD and query operations for RT scores
scraped from Rotten Tomatoes website.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.rotten_tomatoes import RTScore
from src.database.repositories.base import BaseRepository


class RTScoreRepository(BaseRepository[RTScore]):
    """Repository for RTScore entity operations.

    RT scores are scraped data with tomatometer and
    audience scores plus critics consensus text.
    """

    model = RTScore

    def __init__(self, session: Session) -> None:
        """Initialize RT score repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_film_id(self, film_id: int) -> RTScore | None:
        """Retrieve RT score by film ID.

        Args:
            film_id: Film primary key.

        Returns:
            RTScore instance or None.
        """
        return self.get_by_field("film_id", film_id)

    def get_film_ids_with_scores(self) -> set[int]:
        """Get all film IDs that have RT scores.

        Returns:
            Set of film IDs.
        """
        stmt = select(RTScore.film_id)
        return set(self._session.scalars(stmt).all())

    def get_certified_fresh(self, limit: int = 50) -> list[RTScore]:
        """Get films with Certified Fresh status.

        Args:
            limit: Maximum results.

        Returns:
            List of RT scores with certified fresh status.
        """
        stmt = (
            select(RTScore)
            .where(RTScore.tomatometer_state == "certified_fresh")
            .order_by(RTScore.tomatometer_score.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_fresh(self, min_score: int = 60, limit: int = 100) -> list[RTScore]:
        """Get films with Fresh status.

        Args:
            min_score: Minimum tomatometer score.
            limit: Maximum results.

        Returns:
            List of RT scores above threshold.
        """
        stmt = (
            select(RTScore)
            .where(RTScore.tomatometer_score >= min_score)
            .order_by(RTScore.tomatometer_score.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_rotten(self, max_score: int = 59, limit: int = 100) -> list[RTScore]:
        """Get films with Rotten status.

        Args:
            max_score: Maximum tomatometer score.
            limit: Maximum results.

        Returns:
            List of RT scores below threshold.
        """
        stmt = (
            select(RTScore)
            .where(RTScore.tomatometer_score <= max_score)
            .order_by(RTScore.tomatometer_score.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_with_consensus(self, limit: int = 100) -> list[RTScore]:
        """Get scores that have critics consensus text.

        Args:
            limit: Maximum results.

        Returns:
            List of RT scores with consensus.
        """
        stmt = (
            select(RTScore)
            .where(RTScore.critics_consensus != None)  # noqa: E711
            .order_by(RTScore.tomatometer_score.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def upsert(self, data: dict[str, Any]) -> RTScore:
        """Insert or update RT score.

        Args:
            data: RT score data with film_id.

        Returns:
            Upserted RTScore instance.
        """
        stmt = (
            insert(RTScore)
            .values(**data)
            .on_conflict_do_update(
                index_elements=["film_id"],
                set_={k: v for k, v in data.items() if k != "film_id"},
            )
            .returning(RTScore)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.scalar_one()

    def bulk_upsert(self, scores_data: list[dict[str, Any]]) -> int:
        """Bulk insert or update RT scores.

        Args:
            scores_data: List of RT score dictionaries.

        Returns:
            Number of scores processed.
        """
        if not scores_data:
            return 0

        stmt = insert(RTScore).values(scores_data)
        update_cols = {col.name: col for col in stmt.excluded if col.name not in ("id", "film_id")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["film_id"],
            set_=update_cols,
        )
        self._session.execute(stmt)
        self._session.flush()
        return len(scores_data)

    def get_stats(self) -> dict[str, Any]:
        """Get RT score statistics.

        Returns:
            Dictionary with various stats.
        """
        total = self.count()

        avg_tomatometer = self._session.scalar(select(func.avg(RTScore.tomatometer_score)))
        avg_audience = self._session.scalar(select(func.avg(RTScore.audience_score)))
        with_consensus = self._session.scalar(
            select(func.count(RTScore.id)).where(
                RTScore.critics_consensus != None  # noqa: E711
            )
        )
        certified_fresh = self._session.scalar(
            select(func.count(RTScore.id)).where(RTScore.tomatometer_state == "certified_fresh")
        )

        return {
            "total": total,
            "avg_tomatometer": round(float(avg_tomatometer or 0), 1),
            "avg_audience": round(float(avg_audience or 0), 1),
            "with_consensus": with_consensus or 0,
            "certified_fresh": certified_fresh or 0,
        }

    def get_score_distribution(self) -> dict[str, int]:
        """Get distribution of tomatometer scores by range.

        Returns:
            Dictionary with score ranges and counts.
        """
        ranges = [
            ("0-19", 0, 19),
            ("20-39", 20, 39),
            ("40-59", 40, 59),
            ("60-79", 60, 79),
            ("80-100", 80, 100),
        ]

        distribution = {}
        for label, min_score, max_score in ranges:
            count = self._session.scalar(
                select(func.count(RTScore.id)).where(
                    RTScore.tomatometer_score.between(min_score, max_score)
                )
            )
            distribution[label] = count or 0

        return distribution

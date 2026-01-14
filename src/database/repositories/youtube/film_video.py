"""Film-Video association repository.

Manages the many-to-many relationship between films
and YouTube videos with match scoring.
"""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models.youtube import FilmVideo
from src.database.repositories.base import BaseRepository


class FilmVideoRepository(BaseRepository[FilmVideo]):
    """Repository for Film-Video association operations.

    Manages the many-to-many relationship between films
    and YouTube videos with match scoring.
    """

    model = FilmVideo

    def __init__(self, session: Session) -> None:
        """Initialize film-video repository.

        Args:
            session: SQLAlchemy session instance.
        """
        super().__init__(session)

    def get_by_film(self, film_id: int) -> list[FilmVideo]:
        """Get all video associations for a film.

        Args:
            film_id: Film primary key.

        Returns:
            List of associations ordered by match score.
        """
        stmt = (
            select(FilmVideo)
            .where(FilmVideo.film_id == film_id)
            .order_by(FilmVideo.match_score.desc())
        )
        return list(self._session.scalars(stmt).all())

    def get_by_video(self, video_id: int) -> list[FilmVideo]:
        """Get all film associations for a video.

        Args:
            video_id: Video primary key.

        Returns:
            List of associations ordered by match score.
        """
        stmt = (
            select(FilmVideo)
            .where(FilmVideo.video_id == video_id)
            .order_by(FilmVideo.match_score.desc())
        )
        return list(self._session.scalars(stmt).all())

    def get_by_film_and_video(
        self,
        film_id: int,
        video_id: int,
    ) -> FilmVideo | None:
        """Get specific film-video association.

        Args:
            film_id: Film primary key.
            video_id: Video primary key.

        Returns:
            FilmVideo instance or None.
        """
        stmt = select(FilmVideo).where(
            FilmVideo.film_id == film_id,
            FilmVideo.video_id == video_id,
        )
        return self._session.scalars(stmt).first()

    def link(
        self,
        film_id: int,
        video_id: int,
        match_score: float,
        match_method: str,
    ) -> FilmVideo:
        """Create association between film and video.

        Args:
            film_id: Film primary key.
            video_id: Video primary key.
            match_score: Confidence score (0-1).
            match_method: Method used for matching.

        Returns:
            Created FilmVideo association.
        """
        association = FilmVideo(
            film_id=film_id,
            video_id=video_id,
            match_score=match_score,
            match_method=match_method,
        )
        return self.create(association)

    def upsert(
        self,
        film_id: int,
        video_id: int,
        match_score: float,
        match_method: str,
    ) -> FilmVideo:
        """Insert or update film-video association.

        Args:
            film_id: Film primary key.
            video_id: Video primary key.
            match_score: Confidence score (0-1).
            match_method: Method used for matching.

        Returns:
            Upserted FilmVideo instance.
        """
        stmt = (
            insert(FilmVideo)
            .values(
                film_id=film_id,
                video_id=video_id,
                match_score=match_score,
                match_method=match_method,
            )
            .on_conflict_do_update(
                index_elements=["film_id", "video_id"],
                set_={
                    "match_score": match_score,
                    "match_method": match_method,
                },
            )
            .returning(FilmVideo)
        )
        result = self._session.execute(stmt)
        self._session.flush()
        return result.scalar_one()

    def get_high_confidence(
        self,
        min_score: float = 0.8,
        limit: int = 100,
    ) -> list[FilmVideo]:
        """Get high confidence matches.

        Args:
            min_score: Minimum match score threshold.
            limit: Maximum results.

        Returns:
            List of high confidence associations.
        """
        stmt = (
            select(FilmVideo)
            .where(FilmVideo.match_score >= min_score)
            .order_by(FilmVideo.match_score.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def count_by_method(self) -> dict[str, int]:
        """Count associations by match method.

        Returns:
            Dictionary mapping match_method to count.
        """
        stmt = select(FilmVideo.match_method, func.count()).group_by(FilmVideo.match_method)
        result = self._session.execute(stmt).all()
        return {row[0]: row[1] for row in result}

    def get_avg_score_by_method(self) -> dict[str, float]:
        """Get average match score by method.

        Returns:
            Dictionary mapping match_method to average score.
        """
        stmt = select(FilmVideo.match_method, func.avg(FilmVideo.match_score)).group_by(
            FilmVideo.match_method
        )
        result = self._session.execute(stmt).all()
        return {row[0]: round(float(row[1]), 3) for row in result}

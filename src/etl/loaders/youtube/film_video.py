"""Film-video association loader.

Handles film-video linking with match metadata.
"""

from sqlalchemy.dialects.postgresql import insert

from src.database.models.youtube.film_video import FilmVideo
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import FilmMatchResult


class FilmVideoLoader(BaseLoader):
    """Loader for film-video associations.

    Uses (film_id, video_id) as composite primary key for upsert.
    """

    name = "youtube.film_video"

    def load(self, data: list[FilmMatchResult]) -> LoaderStats:
        """Load film-video associations into database.

        Args:
            data: List of film match results.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        if not data:
            return self.stats

        total = len(data)
        self._logger.info(f"Loading {total} film-video associations")

        for idx, match_data in enumerate(data, 1):
            self._upsert_association(match_data)
            self._log_progress(idx, total)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _upsert_association(self, data: FilmMatchResult) -> None:
        """Upsert a single film-video association.

        Args:
            data: Film match result dictionary.
        """
        film_id = data.get("film_id")
        video_id = data.get("video_id")

        if not film_id or not video_id:
            self._record_error("Missing film_id or video_id in match data")
            return

        try:
            stmt = insert(FilmVideo).values(
                film_id=film_id,
                video_id=video_id,
                match_score=data.get("match_score", 1.0),
                match_method=data.get("match_method", "title_similarity"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["film_id", "video_id"],
                set_={
                    "match_score": stmt.excluded.match_score,
                    "match_method": stmt.excluded.match_method,
                },
            )
            self._session.execute(stmt)
            self._record_insert()
        except Exception as e:
            self._record_error(f"Association film={film_id}, video={video_id} failed: {e}")

    def load_single(
        self,
        film_id: int,
        video_id: int,
        match_score: float = 1.0,
        match_method: str = "title_similarity",
    ) -> bool:
        """Load a single film-video association.

        Args:
            film_id: Internal database film ID.
            video_id: Internal database video ID.
            match_score: Similarity score (0.0-1.0).
            match_method: Algorithm used for matching.

        Returns:
            True if successful, False otherwise.
        """
        match_data: FilmMatchResult = {
            "film_id": film_id,
            "video_id": video_id,
            "match_score": match_score,
            "match_method": match_method,
            "matched_title": "",
        }
        self._upsert_association(match_data)
        return self.stats.errors == 0

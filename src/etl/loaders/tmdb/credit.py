"""TMDB credit data loader.

Handles film credits (cast and crew) with replace strategy.
"""

from sqlalchemy import delete

from src.database.models import Credit
from src.etl.loaders.base import BaseLoader, LoaderStats
from src.etl.types import CreditLoadInput, NormalizedCreditData


class CreditLoader(BaseLoader):
    """Loader for film credits (cast and crew).

    Credits are replaced on each load (delete + insert strategy).
    """

    name = "tmdb.credit"

    def load(self, data: object) -> LoaderStats:
        """Load credits for a film (replaces existing).

        Args:
            data: CreditLoadInput with 'credits' list and 'film_id'.

        Returns:
            LoaderStats with operation results.
        """
        self.reset_stats()
        validated = self._validate_input(data)
        if validated is None:
            return self.stats

        credits_data, film_id = validated
        if not credits_data:
            return self.stats

        self._logger.info(f"Loading {len(credits_data)} credits for film_id={film_id}")
        self._delete_existing(film_id)
        for credit in credits_data:
            self._insert_credit(credit, film_id)

        self._session.flush()
        self._log_summary()
        return self.stats

    def _validate_input(self, data: object) -> tuple[list[NormalizedCreditData], int] | None:
        """Validate and extract input data.

        Args:
            data: Raw input data.

        Returns:
            Tuple of (credits_list, film_id) or None if invalid.
        """
        if not isinstance(data, dict):
            self._record_error("Input must be a CreditLoadInput dict")
            return None

        input_data: CreditLoadInput = data  # type: ignore[assignment]
        credits_list = input_data.get("credits", [])
        film_id = input_data.get("film_id")

        if film_id is None:
            self._record_error("film_id is required")
            return None

        return credits_list, film_id

    def _delete_existing(self, film_id: int) -> None:
        """Delete existing credits for a film.

        Args:
            film_id: Internal database film ID.
        """
        stmt = delete(Credit).where(Credit.film_id == film_id)
        self._session.execute(stmt)

    def _insert_credit(self, data: NormalizedCreditData, film_id: int) -> None:
        """Insert a single credit record.

        Args:
            data: Normalized credit data.
            film_id: Internal database film ID.
        """
        try:
            credit = Credit(
                film_id=film_id,
                tmdb_person_id=data.get("tmdb_person_id"),
                person_name=data["person_name"],
                role_type=data["role_type"],
                character_name=data.get("character_name"),
                department=data.get("department"),
                job=data.get("job"),
                display_order=data.get("display_order", 0),
                profile_path=data.get("profile_path"),
            )
            self._session.add(credit)
            self._record_insert()
        except Exception as e:
            self._record_error(f"Credit insert failed: {e}")

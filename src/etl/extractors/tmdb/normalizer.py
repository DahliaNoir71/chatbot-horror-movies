"""TMDB data normalizer.

Transforms raw TMDB API responses into normalized
data structures ready for database insertion.
"""

import logging
from datetime import date

from src.etl.types import (
    NormalizedCompanyData,
    NormalizedCreditData,
    NormalizedFilmData,
    NormalizedGenreData,
    NormalizedKeywordData,
    NormalizedLanguageData,
    TMDBCastData,
    TMDBCrewData,
    TMDBFilmData,
    TMDBGenreData,
    TMDBKeywordData,
    TMDBProductionCompanyData,
    TMDBSpokenLanguageData,
)

logger = logging.getLogger(__name__)


class TMDBNormalizer:
    """Normalizes TMDB API data for database insertion.

    Handles parsing, validation, and transformation of
    raw API responses into consistent data structures.
    """

    # Role types for credits
    DIRECTOR_JOBS = {"Director"}
    WRITER_JOBS = {"Writer", "Screenplay", "Story"}
    PRODUCER_JOBS = {"Producer", "Executive Producer"}

    # Maximum actors to keep per film
    MAX_ACTORS = 10

    # -------------------------------------------------------------------------
    # Film Normalization
    # -------------------------------------------------------------------------

    def normalize_film(
        self,
        raw: TMDBFilmData,
        source: str = "tmdb_discover",
    ) -> NormalizedFilmData:
        """Normalize a TMDB film to database format.

        Args:
            raw: Raw TMDB film data.
            source: Data source identifier.

        Returns:
            Normalized film data.
        """
        return NormalizedFilmData(
            tmdb_id=raw["id"],
            imdb_id=raw.get("imdb_id"),
            title=self._clean_string(raw["title"]),
            original_title=raw.get("original_title"),
            release_date=self._parse_date(raw.get("release_date")),
            tagline=raw.get("tagline"),
            overview=self._clean_string(raw.get("overview")),
            popularity=raw.get("popularity", 0.0),
            vote_average=raw.get("vote_average", 0.0),
            vote_count=raw.get("vote_count", 0),
            runtime=self._validate_runtime(raw.get("runtime")),
            original_language=raw.get("original_language"),
            status=raw.get("status", "Unknown"),
            adult=raw.get("adult", False),
            poster_path=raw.get("poster_path"),
            backdrop_path=raw.get("backdrop_path"),
            homepage=raw.get("homepage"),
            budget=raw.get("budget", 0),
            revenue=raw.get("revenue", 0),
            source=source,
        )

    def normalize_films(
        self,
        raw_films: list[TMDBFilmData],
        source: str = "tmdb_discover",
    ) -> list[NormalizedFilmData]:
        """Normalize multiple films.

        Args:
            raw_films: List of raw TMDB films.
            source: Data source identifier.

        Returns:
            List of normalized films.
        """
        normalized = []
        for raw in raw_films:
            try:
                normalized.append(self.normalize_film(raw, source))
            except (KeyError, TypeError) as e:
                logger.warning(f"Failed to normalize film {raw.get('id')}: {e}")
        return normalized

    # -------------------------------------------------------------------------
    # Credits Normalization
    # -------------------------------------------------------------------------

    def normalize_credits(
        self,
        cast: list[TMDBCastData],
        crew: list[TMDBCrewData],
    ) -> list[NormalizedCreditData]:
        """Normalize cast and crew to credits.

        Args:
            cast: Raw cast data.
            crew: Raw crew data.

        Returns:
            Combined list of normalized credits.
        """
        film_credits: list[NormalizedCreditData] = []

        # Process directors first
        film_credits.extend(self._extract_crew_by_role(crew, "director"))

        # Process writers
        film_credits.extend(self._extract_crew_by_role(crew, "writer"))

        # Process producers
        film_credits.extend(self._extract_crew_by_role(crew, "producer"))

        # Process top actors
        film_credits.extend(self._extract_actors(cast))

        return film_credits

    def _extract_crew_by_role(
        self,
        crew: list[TMDBCrewData],
        role_type: str,
    ) -> list[NormalizedCreditData]:
        """Extract crew members by role type.

        Args:
            crew: Raw crew data.
            role_type: Target role type.

        Returns:
            List of normalized credits for role.
        """
        job_filter = self._get_job_filter(role_type)
        film_credits = []
        order = 0

        for member in crew:
            if member.get("job") in job_filter:
                film_credits.append(
                    NormalizedCreditData(
                        tmdb_person_id=member.get("id"),
                        person_name=self._clean_string(member["name"]),
                        role_type=role_type,
                        character_name=None,
                        department=member.get("department"),
                        job=member.get("job"),
                        display_order=order,
                        profile_path=member.get("profile_path"),
                    )
                )
                order += 1

        return film_credits

    def _extract_actors(
        self,
        cast: list[TMDBCastData],
    ) -> list[NormalizedCreditData]:
        """Extract top actors from cast.

        Args:
            cast: Raw cast data.

        Returns:
            List of normalized actor credits.
        """
        # Sort by order and take top N
        sorted_cast = sorted(cast, key=lambda x: x.get("order", 999))
        top_cast = sorted_cast[: self.MAX_ACTORS]

        return [
            NormalizedCreditData(
                tmdb_person_id=member.get("id"),
                person_name=self._clean_string(member["name"]),
                role_type="actor",
                character_name=member.get("character"),
                department="Acting",
                job="Actor",
                display_order=member.get("order", idx),
                profile_path=member.get("profile_path"),
            )
            for idx, member in enumerate(top_cast)
        ]

    def _get_job_filter(self, role_type: str) -> set[str]:
        """Get job titles for role type.

        Args:
            role_type: Role type identifier.

        Returns:
            Set of job titles.
        """
        filters = {
            "director": self.DIRECTOR_JOBS,
            "writer": self.WRITER_JOBS,
            "producer": self.PRODUCER_JOBS,
        }
        return filters.get(role_type, set())

    # -------------------------------------------------------------------------
    # Reference Data Normalization
    # -------------------------------------------------------------------------

    def normalize_genre(self, raw: TMDBGenreData) -> NormalizedGenreData:
        """Normalize a genre.

        Args:
            raw: Raw genre data.

        Returns:
            Normalized genre data.
        """
        return NormalizedGenreData(
            tmdb_genre_id=raw["id"],
            name=self._clean_string(raw["name"]),
        )

    def normalize_genres(
        self,
        raw_genres: list[TMDBGenreData],
    ) -> list[NormalizedGenreData]:
        """Normalize multiple genres.

        Args:
            raw_genres: List of raw genres.

        Returns:
            List of normalized genres.
        """
        return [self.normalize_genre(g) for g in raw_genres]

    def normalize_keyword(self, raw: TMDBKeywordData) -> NormalizedKeywordData:
        """Normalize a keyword.

        Args:
            raw: Raw keyword data.

        Returns:
            Normalized keyword data.
        """
        return NormalizedKeywordData(
            tmdb_keyword_id=raw["id"],
            name=self._clean_string(raw["name"]),
        )

    def normalize_keywords(
        self,
        raw_keywords: list[TMDBKeywordData],
    ) -> list[NormalizedKeywordData]:
        """Normalize multiple keywords.

        Args:
            raw_keywords: List of raw keywords.

        Returns:
            List of normalized keywords.
        """
        return [self.normalize_keyword(k) for k in raw_keywords]

    def normalize_company(
        self,
        raw: TMDBProductionCompanyData,
    ) -> NormalizedCompanyData:
        """Normalize a production company.

        Args:
            raw: Raw company data.

        Returns:
            Normalized company data.
        """
        return NormalizedCompanyData(
            tmdb_company_id=raw["id"],
            name=self._clean_string(raw["name"]),
            origin_country=raw.get("origin_country"),
        )

    def normalize_companies(
        self,
        raw_companies: list[TMDBProductionCompanyData],
    ) -> list[NormalizedCompanyData]:
        """Normalize multiple companies.

        Args:
            raw_companies: List of raw companies.

        Returns:
            List of normalized companies.
        """
        return [self.normalize_company(c) for c in raw_companies]

    @staticmethod
    def normalize_language(
        raw: TMDBSpokenLanguageData,
    ) -> NormalizedLanguageData:
        """Normalize a spoken language.

        Args:
            raw: Raw language data.

        Returns:
            Normalized language data.
        """
        return NormalizedLanguageData(
            iso_639_1=raw["iso_639_1"],
            name=raw.get("english_name") or raw["name"],
        )

    def normalize_languages(
        self,
        raw_languages: list[TMDBSpokenLanguageData],
    ) -> list[NormalizedLanguageData]:
        """Normalize multiple languages.

        Args:
            raw_languages: List of raw languages.

        Returns:
            List of normalized languages.
        """
        return [self.normalize_language(lang) for lang in raw_languages]

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_string(value: str | None) -> str | None:
        """Clean and normalize a string value.

        Args:
            value: String to clean.

        Returns:
            Cleaned string or None.
        """
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse a date string to date object.

        Args:
            date_str: Date string in YYYY-MM-DD format.

        Returns:
            Parsed date or None.
        """
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            logger.debug(f"Invalid date format: {date_str}")
            return None

    @staticmethod
    def _validate_runtime(runtime: int | None) -> int | None:
        """Validate runtime value.

        Args:
            runtime: Runtime in minutes.

        Returns:
            Valid runtime or None.
        """
        if runtime is None or runtime <= 0:
            return None
        if runtime > 1000:
            logger.debug(f"Suspicious runtime: {runtime}")
            return None
        return runtime

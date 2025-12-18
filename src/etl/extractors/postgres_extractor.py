"""PostgreSQL external database extractor for IMDB data.

Source 5 (E1): External PostgreSQL database on port 5433.
Database: horror_imdb with IMDB movie data.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings


@dataclass
class PostgresStats:
    """Extraction statistics."""

    tables_queried: int = 0
    total_rows: int = 0
    films_extracted: int = 0
    reviews_extracted: int = 0
    ratings_extracted: int = 0
    errors: int = 0


class PostgresExtractor(BaseExtractor):
    """Extract horror movie data from external PostgreSQL database.

    Connects to IMDB database on port 5433.
    Extracts films with SQL queries.
    """

    def __init__(self) -> None:
        """Initialize PostgreSQL extractor."""
        super().__init__("PostgresExtractor")
        self.logger = setup_logger("etl.postgres")
        self.cfg = settings.imdb_db
        self.engine: Engine | None = None
        self.stats = PostgresStats()

    def validate_config(self) -> None:
        """Validate database credentials are configured.

        Raises:
            ValueError: If credentials are missing.
        """
        if not self.cfg.is_configured:
            raise ValueError("IMDB DB credentials missing. Set IMDB_DB_PASSWORD in .env")

    # =========================================================================
    # CONNECTION
    # =========================================================================

    def _connect(self) -> Engine:
        """Create database connection.

        Returns:
            SQLAlchemy Engine instance.

        Raises:
            SQLAlchemyError: If connection fails.
        """
        self.logger.info(f"connecting_to_db: {self.cfg.host}:{self.cfg.port}/{self.cfg.database}")

        engine = create_engine(
            self.cfg.connection_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )

        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        self.logger.info("db_connection_established")
        return engine

    def _disconnect(self) -> None:
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            self.logger.info("db_connection_closed")

    # =========================================================================
    # SCHEMA DISCOVERY
    # =========================================================================

    def _get_tables(self) -> list[str]:
        """Get list of tables in database.

        Returns:
            List of table names.
        """
        query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            tables = [row[0] for row in result]

        self.logger.info(f"tables_found: {tables}")
        return tables

    def _get_columns(self, table: str) -> list[dict[str, str]]:
        """Get column information for a table.

        Args:
            table: Table name.

        Returns:
            List of column info dictionaries.
        """
        query = text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table
            ORDER BY ordinal_position
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"table": table})
            return [{"name": row[0], "type": row[1], "nullable": row[2]} for row in result]

    # =========================================================================
    # DATA EXTRACTION
    # =========================================================================

    def _extract_films(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Extract films from database.

        Args:
            limit: Maximum rows to extract.

        Returns:
            List of film dictionaries.
        """
        self.logger.info("extracting_films")

        # Dynamic query based on available columns
        query_str = self._build_films_query(limit)
        query = text(query_str)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                columns = result.keys()
                films = [dict(zip(columns, row, strict=True)) for row in result]

            self.stats.tables_queried += 1
            self.stats.films_extracted = len(films)
            self.logger.info(f"films_extracted: {len(films)}")

            return films

        except SQLAlchemyError as e:
            self.stats.errors += 1
            self.logger.error(f"films_extraction_failed: {e}")
            return []

    def _build_films_query(self, limit: int | None) -> str:
        """Build SQL query for films table.

        Args:
            limit: Row limit.

        Returns:
            SQL query string.
        """
        # Base query - adapt to actual schema
        query = """
            SELECT *
            FROM films
            WHERE 1=1
        """

        # Add horror filter if genre column exists
        columns = self._get_columns("films")
        col_names = [c["name"] for c in columns]

        if "genre" in col_names:
            query += " AND LOWER(genre) LIKE '%horror%'"
        elif "genres" in col_names:
            query += " AND LOWER(genres) LIKE '%horror%'"

        # Add ordering
        if "year" in col_names:
            query += " ORDER BY year DESC"
        elif "release_date" in col_names:
            query += " ORDER BY release_date DESC"

        # Add limit
        if limit:
            query += f" LIMIT {limit}"

        return query

    def _extract_reviews(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Extract reviews from database.

        Args:
            limit: Maximum rows to extract.

        Returns:
            List of review dictionaries.
        """
        self.logger.info("extracting_reviews")

        query_str = """
            SELECT *
            FROM reviews
        """
        if limit:
            query_str += f" LIMIT {limit}"

        query = text(query_str)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                columns = result.keys()
                reviews = [dict(zip(columns, row, strict=True)) for row in result]

            self.stats.tables_queried += 1
            self.stats.reviews_extracted = len(reviews)
            self.logger.info(f"reviews_extracted: {len(reviews)}")

            return reviews

        except SQLAlchemyError as e:
            self.stats.errors += 1
            self.logger.warning(f"reviews_extraction_failed: {e}")
            return []

    def _extract_ratings(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Extract ratings from database.

        Args:
            limit: Maximum rows to extract.

        Returns:
            List of rating dictionaries.
        """
        self.logger.info("extracting_ratings")

        query_str = """
            SELECT *
            FROM ratings
        """
        if limit:
            query_str += f" LIMIT {limit}"

        query = text(query_str)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query)
                columns = result.keys()
                ratings = [dict(zip(columns, row, strict=True)) for row in result]

            self.stats.tables_queried += 1
            self.stats.ratings_extracted = len(ratings)
            self.logger.info(f"ratings_extracted: {len(ratings)}")

            return ratings

        except SQLAlchemyError as e:
            self.stats.errors += 1
            self.logger.warning(f"ratings_extraction_failed: {e}")
            return []

    # =========================================================================
    # CUSTOM QUERIES
    # =========================================================================

    def execute_query(self, query: str, params: dict | None = None) -> list[dict[str, Any]]:
        """Execute custom SQL query.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            List of row dictionaries.
        """
        self.logger.info(f"executing_custom_query: {query[:100]}...")

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                columns = result.keys()
                rows = [dict(zip(columns, row, strict=True)) for row in result]

            self.stats.tables_queried += 1
            return rows

        except SQLAlchemyError as e:
            self.stats.errors += 1
            self.logger.error(f"custom_query_failed: {e}")
            return []

    # =========================================================================
    # NORMALIZATION
    # =========================================================================

    def _normalize_film(self, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize film row to standard schema.

        Args:
            row: Raw database row.

        Returns:
            Normalized dictionary.
        """
        return {
            # Identifiers
            "letterboxd_id": row.get("id") or row.get("film_id"),
            "imdb_id": row.get("imdb_id"),
            "tmdb_id": row.get("tmdb_id"),
            "source": "imdb",
            # Content
            "title": row.get("title") or row.get("name"),
            "original_title": row.get("original_title"),
            "overview": row.get("overview") or row.get("description"),
            "tagline": row.get("tagline"),
            # Dates
            "release_date": self._format_date(row.get("release_date")),
            "year": row.get("year") or self._extract_year(row.get("release_date")),
            # Scores
            "letterboxd_rating": row.get("rating") or row.get("average_rating"),
            "letterboxd_votes": row.get("votes") or row.get("rating_count"),
            # Metadata
            "runtime": row.get("runtime"),
            "genres": self._parse_genres(row.get("genres") or row.get("genre")),
            "directors": self._parse_list(row.get("directors") or row.get("director")),
            "cast": self._parse_list(row.get("cast") or row.get("actors")),
            "original_language": row.get("original_language") or row.get("language"),
            "countries": self._parse_list(row.get("countries") or row.get("country")),
            # URLs
            "letterboxd_url": row.get("letterboxd_url") or row.get("url"),
            "poster_url": row.get("poster_url") or row.get("poster"),
            # Extraction timestamp
            "extracted_at": datetime.now().isoformat(),
        }

    def _normalize_review(self, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize review row to standard schema.

        Args:
            row: Raw database row.

        Returns:
            Normalized dictionary.
        """
        return {
            "review_id": row.get("id") or row.get("review_id"),
            "film_id": row.get("film_id"),
            "source": "imdb",
            "user_id": row.get("user_id"),
            "username": row.get("username") or row.get("user"),
            "rating": row.get("rating"),
            "review_text": row.get("review") or row.get("text") or row.get("content"),
            "likes": row.get("likes") or row.get("like_count"),
            "created_at": self._format_date(row.get("created_at") or row.get("date")),
            "extracted_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _format_date(value: datetime | date | str | None) -> str | None:
        """Format date value to ISO string.

        Args:
            value: Date value (datetime, date, or string).

        Returns:
            ISO date string or None.
        """
        if value is None:
            return None

        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    @staticmethod
    def _extract_year(date_value: datetime | date | str | int | None) -> int | None:
        """Extract year from date value.

        Args:
            date_value: Date value (datetime, date, string, or int).

        Returns:
            Year as integer or None.
        """
        if date_value is None:
            return None

        if hasattr(date_value, "year"):
            result = date_value.year
        else:
            result = PostgresExtractor._parse_year_from_string(date_value)

        return result

    @staticmethod
    def _parse_year_from_string(value: str | int) -> int | None:
        """Parse year from string representation.

        Args:
            value: Value to parse (first 4 characters as year).

        Returns:
            Year as integer or None if parsing fails.
        """
        try:
            return int(str(value)[:4])
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_genres(value: list[str] | str | None) -> list[str]:
        """Parse genres from various formats.

        Args:
            value: Genres value (string, list, or JSON).

        Returns:
            List of genre names.
        """
        if not value:
            return []

        if isinstance(value, list):
            result = [str(g).strip() for g in value if g]
        elif isinstance(value, str):
            result = PostgresExtractor._parse_genres_from_string(value)
        else:
            result = []

        return result

    @staticmethod
    def _parse_genres_from_string(value: str) -> list[str]:
        """Parse genres from string format (comma-separated or JSON).

        Args:
            value: String containing genres.

        Returns:
            List of genre names.
        """
        # Handle comma-separated
        if "," in value:
            return [g.strip() for g in value.split(",") if g.strip()]

        # Handle JSON array
        if value.startswith("["):
            parsed = PostgresExtractor._try_parse_json_array(value)
            if parsed is not None:
                return parsed

        return [value.strip()]

    @staticmethod
    def _try_parse_json_array(value: str) -> list[str] | None:
        """Try to parse a JSON array string.

        Args:
            value: JSON array string.

        Returns:
            Parsed list or None if parsing fails.
        """
        import json

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _parse_list(value: list[str] | str | None) -> list[str]:
        """Parse list from various formats.

        Args:
            value: List value (string, list, or None).

        Returns:
            List of strings.
        """
        if not value:
            return []

        if isinstance(value, list):
            result = [str(v).strip() for v in value if v]
        elif isinstance(value, str):
            parts = value.split(",") if "," in value else [value]
            result = [v.strip() for v in parts if v.strip()]
        else:
            result = []

        return result

    # =========================================================================
    # MAIN EXTRACTION
    # =========================================================================

    def extract(
        self,
        tables: list[str] | None = None,
        limit: int | None = None,
        **_kwargs: Any,
    ) -> dict[str, list[dict[str, Any]]]:
        """Extract data from IMDB database.

        Args:
            tables: Tables to extract ("films", "reviews", "ratings").
                   If None, extracts all available.
            limit: Maximum rows per table.

        Returns:
            Dictionary with table names as keys and row lists as values.
        """
        self._start_extraction()
        self.validate_config()
        self._log_extraction_header()

        result: dict[str, list[dict[str, Any]]] = {}

        try:
            self.engine = self._connect()
            available_tables = self._get_tables()
            actual_tables = self._resolve_table_mapping(available_tables)
            tables_to_extract = tables or ["films", "reviews", "ratings"]
            result = self._extract_requested_tables(
                tables_to_extract, actual_tables, available_tables, limit
            )
            self.stats.total_rows = sum(len(v) for v in result.values())

        except SQLAlchemyError as e:
            self.stats.errors += 1
            self.logger.error(f"extraction_failed: {e}")

        finally:
            self._disconnect()

        self._end_extraction()
        self._log_stats()
        return result

    def _log_extraction_header(self) -> None:
        """Log extraction start header."""
        self.logger.info("=" * 60)
        self.logger.info("🗄️ POSTGRESQL EXTRACTION STARTED")
        self.logger.info(f"Database: {self.cfg.database}@{self.cfg.host}:{self.cfg.port}")
        self.logger.info("=" * 60)

    def _resolve_table_mapping(self, available_tables: list[str]) -> dict[str, str]:
        """Resolve expected table names to actual database table names.

        Args:
            available_tables: List of tables present in database.

        Returns:
            Mapping from expected names to actual table names.
        """
        table_mapping = {
            "films": ["films", "movies", "imdb_movies", "v_horror_movies"],
            "reviews": ["reviews", "imdb_reviews", "user_reviews"],
            "ratings": ["ratings", "imdb_ratings", "user_ratings"],
        }

        actual_tables: dict[str, str] = {}
        self.logger.info(f"searching_tables_in: {available_tables}")

        for expected, candidates in table_mapping.items():
            resolved = self._find_matching_table(expected, candidates, available_tables)
            if resolved:
                actual_tables[expected] = resolved

        self.logger.info(f"actual_tables_resolved: {actual_tables}")
        return actual_tables

    def _find_matching_table(
        self, expected: str, candidates: list[str], available_tables: list[str]
    ) -> str | None:
        """Find first matching table from candidates.

        Args:
            expected: Expected table name for logging.
            candidates: List of candidate table names.
            available_tables: List of available tables in database.

        Returns:
            Matched table name or None.
        """
        self.logger.info(f"mapping_{expected}: checking {candidates}")
        for candidate in candidates:
            if candidate in available_tables:
                self.logger.info(f"table_mapped: {expected} -> {candidate}")
                return candidate

        self.logger.warning(f"no_table_found_for: {expected}")
        return None

    def _extract_requested_tables(
        self,
        tables: list[str],
        actual_tables: dict[str, str],
        available_tables: list[str],
        limit: int | None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Extract data from requested tables.

        Args:
            tables: List of tables to extract.
            actual_tables: Mapping of expected to actual table names.
            available_tables: All available tables in database.
            limit: Maximum rows per table.

        Returns:
            Dictionary with extracted data per table.
        """
        result: dict[str, list[dict[str, Any]]] = {}

        if "films" in tables and "films" in actual_tables:
            result["films"] = self._extract_films_with_fallback(
                actual_tables["films"], available_tables, limit
            )
            self.stats.films_extracted = len(result["films"])

        if "reviews" in tables and "reviews" in actual_tables:
            reviews = self._extract_table(actual_tables["reviews"], limit)
            result["reviews"] = [self._normalize_review(r) for r in reviews]
            self.stats.reviews_extracted = len(result["reviews"])

        if "ratings" in tables and "ratings" in actual_tables:
            ratings = self._extract_table(actual_tables["ratings"], limit)
            result["ratings"] = ratings
            self.stats.ratings_extracted = len(ratings)

        return result

    def _extract_films_with_fallback(
        self,
        primary_table: str,
        available_tables: list[str],
        limit: int | None,
    ) -> list[dict[str, Any]]:
        """Extract films with fallback to alternative tables if primary is empty.

        Args:
            primary_table: Primary table name to extract from.
            available_tables: All available tables for fallback.
            limit: Maximum rows to extract.

        Returns:
            List of normalized film dictionaries.
        """
        films = self._extract_table(primary_table, limit)

        if not films:
            films = self._try_alternative_film_tables(primary_table, available_tables, limit)

        return [self._normalize_film(f) for f in films]

    def _try_alternative_film_tables(
        self,
        primary_table: str,
        available_tables: list[str],
        limit: int | None,
    ) -> list[dict[str, Any]]:
        """Try extracting films from alternative tables.

        Args:
            primary_table: Primary table that was empty.
            available_tables: All available tables.
            limit: Maximum rows to extract.

        Returns:
            List of film dictionaries from first successful alternative.
        """
        self.logger.warning(f"table_empty: {primary_table}, trying alternatives")
        alternatives = ["movies", "imdb_movies", "v_horror_movies"]

        for alt in alternatives:
            if alt not in available_tables or alt == primary_table:
                continue

            self.logger.info(f"trying_alternative: {alt}")
            films = self._extract_table(alt, limit)

            if films:
                self.logger.info(f"alternative_success: {alt}")
                return films

        return []

    def _extract_table(self, table_name: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Extract data from a specific table.

        Args:
            table_name: Name of the table to extract.
            limit: Maximum rows to extract.

        Returns:
            List of row dictionaries.
        """
        self.logger.info(f"extracting_table: {table_name}")

        # Build query with horror filter for films/movies table
        query_str = f"SELECT * FROM {table_name}"

        if table_name in ("films", "movies", "v_horror_movies"):
            # Get columns to check for genre field
            columns = self._get_columns(table_name)
            col_names = [c["name"] for c in columns]

            if "genres" in col_names:
                query_str += " WHERE LOWER(genres) LIKE '%horror%'"
            elif "genre" in col_names:
                query_str += " WHERE LOWER(genre) LIKE '%horror%'"

        if limit:
            query_str += f" LIMIT {limit}"

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query_str))
                columns = result.keys()
                rows = [dict(zip(columns, row, strict=True)) for row in result]

            self.stats.tables_queried += 1
            self.logger.info(f"table_extracted: {table_name} ({len(rows)} rows)")
            return rows

        except SQLAlchemyError as e:
            self.stats.errors += 1
            self.logger.warning(f"table_extraction_failed: {table_name} - {e}")
            return []

    def _log_stats(self) -> None:
        """Log extraction statistics."""
        self.logger.info("=" * 60)
        self.logger.info("📊 POSTGRESQL EXTRACTION STATS")
        self.logger.info("-" * 60)
        self.logger.info(f"Tables queried     : {self.stats.tables_queried}")
        self.logger.info(f"Total rows         : {self.stats.total_rows}")
        self.logger.info(f"Films extracted    : {self.stats.films_extracted}")
        self.logger.info(f"Reviews extracted  : {self.stats.reviews_extracted}")
        self.logger.info(f"Ratings extracted  : {self.stats.ratings_extracted}")
        self.logger.info(f"Errors             : {self.stats.errors}")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)

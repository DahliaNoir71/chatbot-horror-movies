"""CSV file reader for horror movies dataset (C1 - File source)."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings


@dataclass
class CSVExtractionStats:
    """Statistics for CSV extraction."""

    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    horror_movies: int = 0

    @property
    def validity_rate(self) -> float:
        """Calculate percentage of valid rows."""
        if self.total_rows == 0:
            return 0.0
        return (self.valid_rows / self.total_rows) * 100


class CSVReader(BaseExtractor):
    """
    Read and parse CSV files containing movie data.

    Implements C1 requirement: extraction from file source.
    Filters for horror genre and validates data integrity.
    """

    # Required columns for valid movie record
    REQUIRED_COLUMNS = {"id", "title", "release_date"}

    # Columns to extract
    EXTRACT_COLUMNS = [
        "id",
        "original_title",
        "title",
        "original_language",
        "overview",
        "tagline",
        "release_date",
        "popularity",
        "vote_count",
        "vote_average",
        "budget",
        "revenue",
        "runtime",
        "genre_names",
        "poster_path",
        "backdrop_path",
    ]

    def __init__(self, csv_path: Path | None = None) -> None:
        """
        Initialize the CSV reader.

        Args:
            csv_path: Path to CSV file (default: settings.paths.raw_dir)
        """
        super().__init__("CSVReader")
        self.logger = setup_logger("etl.csv")
        self.csv_path = csv_path
        self.stats = CSVExtractionStats()

    def validate_config(self) -> None:
        """Validate that CSV file exists."""
        if self.csv_path and not self.csv_path.exists():
            raise ValueError(f"CSV file not found: {self.csv_path}")

    def extract(
        self,
        *,
        file_path: str | None = None,
        limit: int | None = None,
        **kwargs: str | int | float | bool | None,
    ) -> list[dict[str, str | int | float | bool | list[str] | None]]:
        """
        Extract horror movies from CSV file.

        Args:
            **kwargs: Optional parameters
                - csv_path: Override CSV file path
                - limit: Maximum rows to process
                - filter_horror: Filter only horror movies (default: True)

        Returns:
            List of movie dictionaries
        """
        self._start_extraction()

        csv_path = kwargs.get("csv_path") or self.csv_path
        # Utiliser la valeur de 'limit' du paramètre directement
        # sans la réaffecter depuis kwargs
        filter_horror = kwargs.get("filter_horror", True)

        if not csv_path:
            csv_path = self._find_csv_file()

        self.logger.info(f"📄 Reading CSV: {csv_path}")

        movies = self._read_csv_file(csv_path, limit, filter_horror)

        self._end_extraction()
        self._log_stats()

        return movies

    def _find_csv_file(self) -> Path:
        """Find CSV file in raw data directory."""
        raw_dir = settings.paths.raw_dir
        csv_files = list(raw_dir.glob("*.csv"))

        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {raw_dir}")

        # Prefer horror_movies.csv
        for csv_file in csv_files:
            if "horror" in csv_file.name.lower():
                return csv_file

        return csv_files[0]

    def _read_csv_file(
        self,
        csv_path: Path,
        limit: int | None,
        filter_horror: bool,
    ) -> list[dict[str, Any]]:
        """
        Read and parse CSV file.

        Args:
            csv_path: Path to CSV file
            limit: Maximum rows to process
            filter_horror: Filter only horror movies

        Returns:
            List of parsed movie dictionaries
        """
        movies: list[dict[str, Any]] = []

        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                self.stats.total_rows += 1

                # Apply limit
                if limit and len(movies) >= limit:
                    break

                # Validate row
                if not self._is_valid_row(row):
                    self.stats.invalid_rows += 1
                    continue

                self.stats.valid_rows += 1

                # Filter horror
                if filter_horror and not self._is_horror(row):
                    continue

                self.stats.horror_movies += 1

                # Parse and add movie
                movie = self._parse_row(row)
                movies.append(movie)

        return movies

    def _is_valid_row(self, row: dict[str, str]) -> bool:
        """Check if row has required columns with values."""
        return all(not (col not in row or not row[col].strip()) for col in self.REQUIRED_COLUMNS)

    def _is_horror(self, row: dict[str, str]) -> bool:
        """Check if movie is horror genre."""
        genres = row.get("genre_names", "").lower()
        return "horror" in genres

    def _parse_row(self, row: dict[str, str]) -> dict[str, Any]:
        """
        Parse CSV row into movie dictionary.

        Args:
            row: Raw CSV row

        Returns:
            Parsed movie dictionary
        """
        movie: dict[str, Any] = {
            "source": "csv_kaggle",
            "csv_id": self._safe_int(row.get("id")),
        }

        # String fields
        for field in [
            "title",
            "original_title",
            "overview",
            "tagline",
            "original_language",
            "poster_path",
            "backdrop_path",
        ]:
            movie[field] = row.get(field, "").strip() or None

        # Numeric fields
        movie["vote_average"] = self._safe_float(row.get("vote_average"))
        movie["vote_count"] = self._safe_int(row.get("vote_count"))
        movie["popularity"] = self._safe_float(row.get("popularity"))
        movie["budget"] = self._safe_int(row.get("budget"))
        movie["revenue"] = self._safe_int(row.get("revenue"))
        movie["runtime"] = self._safe_int(row.get("runtime"))

        # Date field
        movie["release_date"] = row.get("release_date", "").strip() or None
        movie["year"] = self._extract_year(movie["release_date"])

        # Genres
        movie["genres"] = self._parse_genres(row.get("genre_names", ""))

        return movie

    @staticmethod
    def _safe_int(value: str | None) -> int | None:
        """Safely convert string to int."""
        if not value:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(value: str | None) -> float | None:
        """Safely convert string to float."""
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_year(date_str: str | None) -> int | None:
        """Extract year from date string."""
        if not date_str:
            return None
        try:
            return int(date_str[:4])
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_genres(genres_str: str) -> list[str]:
        """Parse genre string into list."""
        if not genres_str:
            return []
        # Handle both comma-separated and pipe-separated
        separator = "|" if "|" in genres_str else ","
        return [g.strip() for g in genres_str.split(separator) if g.strip()]

    def _log_stats(self) -> None:
        """Log extraction statistics."""
        self.logger.info("=" * 60)
        self.logger.info("📊 CSV EXTRACTION STATISTICS")
        self.logger.info("-" * 60)
        self.logger.info(f"Total rows read    : {self.stats.total_rows:,}")
        self.logger.info(f"Valid rows         : {self.stats.valid_rows:,}")
        self.logger.info(f"Invalid rows       : {self.stats.invalid_rows:,}")
        self.logger.info(f"Horror movies      : {self.stats.horror_movies:,}")
        self.logger.info(f"Validity rate      : {self.stats.validity_rate:.1f}%")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)

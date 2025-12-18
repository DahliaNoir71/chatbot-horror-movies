"""Kaggle dataset extractor for horror movies CSV.

Source 4 (E1): CSV file download via Kaggle API.
Dataset: evangower/horror-movies
"""

import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger
from src.settings import settings


@dataclass
class KaggleStats:
    """Extraction statistics."""

    files_downloaded: int = 0
    total_rows: int = 0
    filtered_rows: int = 0
    invalid_rows: int = 0


class KaggleExtractor(BaseExtractor):
    """Extract horror movies dataset from Kaggle.

    Downloads CSV file using Kaggle API and normalizes data.
    Requires KAGGLE_USERNAME and KAGGLE_KEY in environment.
    """

    def __init__(self) -> None:
        """Initialize Kaggle extractor."""
        super().__init__("KaggleExtractor")
        self.logger = setup_logger("etl.kaggle")
        self.cfg = settings.kaggle
        self.paths = settings.paths
        self.stats = KaggleStats()

    def validate_config(self) -> None:
        """Validate Kaggle credentials are configured.

        Raises:
            ValueError: If credentials are missing.
        """
        if not self.cfg.is_configured:
            raise ValueError(
                "Kaggle credentials missing. Set KAGGLE_USERNAME and KAGGLE_KEY in .env"
            )

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    def _setup_kaggle_auth(self) -> None:
        """Configure Kaggle API authentication via environment variables."""
        os.environ["KAGGLE_USERNAME"] = self.cfg.username
        os.environ["KAGGLE_KEY"] = self.cfg.key
        self.logger.info("kaggle_auth_configured")

    # =========================================================================
    # DOWNLOAD
    # =========================================================================

    def _download_dataset(self) -> Path:
        """Download dataset from Kaggle.

        Returns:
            Path to downloaded/extracted directory.

        Raises:
            RuntimeError: If download fails.
        """
        # Import kaggle here to avoid import errors if not installed
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
        except ImportError as e:
            raise RuntimeError("kaggle package not installed. Run: pip install kaggle") from e

        download_dir = self.paths.raw_dir / "kaggle"
        download_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"downloading_dataset: {self.cfg.dataset_slug}")

        try:
            api = KaggleApi()
            api.authenticate()

            api.dataset_download_files(
                self.cfg.dataset_slug,
                path=str(download_dir),
                unzip=False,
            )

            self.stats.files_downloaded += 1
            self.logger.info(f"dataset_downloaded: {download_dir}")

            # Extract zip file
            extracted_path = self._extract_zip(download_dir)
            return extracted_path

        except Exception as e:
            self.logger.error(f"download_failed: {e}")
            raise RuntimeError(f"Kaggle download failed: {e}") from e

    def _extract_zip(self, download_dir: Path) -> Path:
        """Extract downloaded zip file.

        Args:
            download_dir: Directory containing zip file.

        Returns:
            Path to extracted directory.
        """
        # Find zip file
        zip_files = list(download_dir.glob("*.zip"))
        if not zip_files:
            raise RuntimeError(f"No zip file found in {download_dir}")

        zip_path = zip_files[0]
        extract_dir = download_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        self.logger.info(f"extracting_zip: {zip_path.name}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        return extract_dir

    # =========================================================================
    # CSV PROCESSING
    # =========================================================================

    def _find_csv_file(self, directory: Path) -> Path:
        """Find CSV file in directory.

        Args:
            directory: Directory to search.

        Returns:
            Path to CSV file.

        Raises:
            FileNotFoundError: If no CSV found.
        """
        csv_files = list(directory.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV file found in {directory}")

        # Prefer file with "horror" in name
        for csv_file in csv_files:
            if "horror" in csv_file.name.lower():
                return csv_file

        return csv_files[0]

    def _read_csv(self, csv_path: Path) -> pd.DataFrame:
        """Read CSV file into DataFrame.

        Args:
            csv_path: Path to CSV file.

        Returns:
            DataFrame with raw data.
        """
        self.logger.info(f"reading_csv: {csv_path.name}")

        # Définition des types de colonnes pour une lecture plus efficace
        dtype = {
            "id": "string",
            "title": "string",
            "release_date": "string",
            "genres": "string",
            "overview": "string",
            "popularity": "float64",
            "vote_average": "float64",
            "vote_count": "Int64",
            "original_language": "category",
            "original_title": "string",
            "poster_path": "string",
            "backdrop_path": "string",
            "adult": "boolean",
            "video": "boolean",
            "budget": "float64",
            "revenue": "float64",
            "runtime": "float64",
            "status": "category",
            "tagline": "string",
            "imdb_id": "string",
            "homepage": "string",
            "production_companies": "string",
            "production_countries": "string",
            "spoken_languages": "string",
            "Keywords": "string",
        }

        df = pd.read_csv(
            csv_path, encoding="utf-8", on_bad_lines="warn", low_memory=False, dtype=dtype
        )

        self.stats.total_rows = len(df)
        self.logger.info(f"csv_loaded: {len(df)} rows, {len(df.columns)} columns")

        return df

    def _filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply filtering rules to DataFrame.

        Args:
            df: Raw DataFrame.

        Returns:
            Filtered DataFrame.
        """
        initial_count = len(df)

        # Debug: log available columns
        self.logger.info(f"columns_available: {list(df.columns)}")

        # Filter by vote count if column exists
        vote_col = self._find_vote_column(df)
        if vote_col:
            df[vote_col] = pd.to_numeric(df[vote_col], errors="coerce")
            before = len(df)
            df = df[df[vote_col] >= self.cfg.min_vote_count]
            self.logger.info(
                f"filter_vote_count: {before} -> {len(df)} "
                f"(min={self.cfg.min_vote_count}, col={vote_col})"
            )

        # Filter by year if column exists
        year_col = self._find_year_column(df)
        if year_col:
            self.logger.info(f"year_column_found: {year_col}")

            # Extract year from release_date if needed
            if year_col == "release_date":
                df["_year"] = pd.to_datetime(df[year_col], errors="coerce").dt.year
                year_col = "_year"
            else:
                df[year_col] = pd.to_numeric(df[year_col], errors="coerce")

            before = len(df)
            df = df[df[year_col] >= self.cfg.min_year]
            df = df.dropna(subset=[year_col])
            self.logger.info(f"filter_year: {before} -> {len(df)} (min={self.cfg.min_year})")
        else:
            self.logger.warning("no_year_column_found")

        filtered_count = initial_count - len(df)
        self.stats.filtered_rows = filtered_count

        self.logger.info(f"data_filtered: {filtered_count} rows removed, {len(df)} remaining")

        return df

    @staticmethod
    def _find_vote_column(df: pd.DataFrame) -> str | None:
        """Find vote count column in DataFrame.

        Args:
            df: DataFrame to search.

        Returns:
            Column name or None.
        """
        candidates = ["vote_count", "votes", "rating_count", "Vote_Count"]
        for col in candidates:
            if col in df.columns:
                return col
        return None

    @staticmethod
    def _find_year_column(df: pd.DataFrame) -> str | None:
        """Find year column in DataFrame.

        Args:
            df: DataFrame to search.

        Returns:
            Column name or None.
        """
        candidates = ["year", "release_year", "release_date", "Year"]
        for col in candidates:
            if col in df.columns:
                return col
        return None

    # =========================================================================
    # NORMALIZATION
    # =========================================================================

    def _normalize_row(self, row: pd.Series) -> dict[str, Any]:
        """Normalize a single row to standard schema.

        Args:
            row: DataFrame row.

        Returns:
            Normalized dictionary.
        """
        return {
            # Identifiers
            "kaggle_id": self._safe_get(row, "id"),
            "imdb_id": self._safe_get(row, "imdb_id"),
            "source": "kaggle",
            # Content
            "title": self._safe_get(row, "title", "original_title", "name"),
            "original_title": self._safe_get(row, "original_title"),
            "overview": self._safe_get(row, "overview", "description"),
            "tagline": self._safe_get(row, "tagline"),
            # Dates
            "release_date": self._safe_get(row, "release_date"),
            "year": self._extract_year(row),
            # Scores
            "vote_average": self._safe_float(row, "vote_average", "rating"),
            "vote_count": self._safe_int(row, "vote_count"),
            "popularity": self._safe_float(row, "popularity"),
            # Metadata
            "runtime": self._safe_int(row, "runtime"),
            "budget": self._safe_int(row, "budget"),
            "revenue": self._safe_int(row, "revenue"),
            "original_language": self._safe_get(row, "original_language", "language"),
            "genres": self._parse_genres(row),
            # Media
            "poster_path": self._safe_get(row, "poster_path"),
            "backdrop_path": self._safe_get(row, "backdrop_path"),
            # Extraction timestamp
            "extracted_at": datetime.now().isoformat(),
        }

    def _safe_get(self, row: pd.Series, *keys: str) -> str | None:
        """Safely get string value from row, trying multiple keys.

        Args:
            row: DataFrame row.
            *keys: Column names to try in order.

        Returns:
            String value or None.
        """
        for key in keys:
            if key in row.index:
                value = row[key]
                if pd.notna(value):
                    return str(value).strip()
        return None

    def _safe_int(self, row: pd.Series, *keys: str) -> int | None:
        """Safely get integer value from row.

        Args:
            row: DataFrame row.
            *keys: Column names to try.

        Returns:
            Integer value or None.
        """
        for key in keys:
            if key in row.index:
                value = row[key]
                if pd.notna(value):
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        pass
        return None

    def _safe_float(self, row: pd.Series, *keys: str) -> float | None:
        """Safely get float value from row.

        Args:
            row: DataFrame row.
            *keys: Column names to try.

        Returns:
            Float value or None.
        """
        for key in keys:
            if key in row.index:
                value = row[key]
                if pd.notna(value):
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        pass
        return None

    def _extract_year(self, row: pd.Series) -> int | None:
        """Extract year from row.

        Args:
            row: DataFrame row.

        Returns:
            Year as integer or None.
        """
        # Try direct year column
        year = self._safe_int(row, "year", "release_year")
        if year:
            return year

        # Try to extract from release_date
        date_str = self._safe_get(row, "release_date")
        if date_str:
            try:
                return int(date_str[:4])
            except (ValueError, TypeError):
                pass

        return None

    def _parse_genres(self, row: pd.Series) -> list[str]:
        """Parse genres from row.

        Args:
            row: DataFrame row.

        Returns:
            List of genre names.
        """
        genres_raw = self._safe_get(row, "genres", "genre")
        if not genres_raw:
            return []

        # Handle JSON-like format: [{"id": 27, "name": "Horror"}]
        if genres_raw.startswith("["):
            try:
                import json

                genres_data = json.loads(genres_raw.replace("'", '"'))
                return [g.get("name", str(g)) for g in genres_data if g]
            except (json.JSONDecodeError, AttributeError):
                pass

        # Handle comma-separated format
        return [g.strip() for g in genres_raw.split(",") if g.strip()]

    # =========================================================================
    # MAIN EXTRACTION
    # =========================================================================

    def extract(
        self,
        use_cache: bool = True,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Extract horror movies from Kaggle dataset.

        Args:
            use_cache: If True, use cached CSV if available.

        Returns:
            List of normalized movie dictionaries.
        """
        self._start_extraction()
        self.validate_config()

        self.logger.info("=" * 60)
        self.logger.info("📊 KAGGLE EXTRACTION STARTED")
        self.logger.info(f"Dataset: {self.cfg.dataset_slug}")
        self.logger.info("=" * 60)

        # Setup authentication
        self._setup_kaggle_auth()

        # Check for cached data
        cached_dir = self.paths.raw_dir / "kaggle" / "extracted"
        if use_cache and cached_dir.exists():
            self.logger.info("using_cached_data")
            extract_dir = cached_dir
        else:
            extract_dir = self._download_dataset()

        # Find and read CSV
        csv_path = self._find_csv_file(extract_dir)
        df = self._read_csv(csv_path)

        # Filter data
        df = self._filter_data(df)

        # Normalize rows
        movies: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            try:
                normalized = self._normalize_row(row)
                if normalized.get("title"):
                    movies.append(normalized)
            except Exception as e:
                self.stats.invalid_rows += 1
                self.logger.warning(f"row_normalization_failed: {e}")

        self._end_extraction()
        self._log_stats(len(movies))

        return movies

    def _log_stats(self, final_count: int) -> None:
        """Log extraction statistics.

        Args:
            final_count: Number of movies extracted.
        """
        self.logger.info("=" * 60)
        self.logger.info("📊 KAGGLE EXTRACTION STATS")
        self.logger.info("-" * 60)
        self.logger.info(f"Files downloaded   : {self.stats.files_downloaded}")
        self.logger.info(f"Total rows         : {self.stats.total_rows}")
        self.logger.info(f"Filtered rows      : {self.stats.filtered_rows}")
        self.logger.info(f"Invalid rows       : {self.stats.invalid_rows}")
        self.logger.info(f"Final movies       : {final_count}")
        self.logger.info(f"Duration           : {self.metrics.duration_seconds:.2f}s")
        self.logger.info("=" * 60)

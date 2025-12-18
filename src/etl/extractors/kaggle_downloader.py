"""Kaggle dataset downloader for horror movies CSV (C1 - File source)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.etl.utils import setup_logger
from src.settings import settings


@dataclass
class DownloadResult:
    """Result of download operation."""

    success: bool
    message: str
    csv_path: Path | None = None
    rows_count: int = 0


class KaggleDownloader:
    """
    Download and extract Kaggle/public datasets.

    Uses direct HTTP download for public datasets (no API auth required).
    Target: Horror movies dataset for E1 validation (5 heterogeneous sources).
    """

    # TidyTuesday Horror Movies dataset (public, no auth)
    DEFAULT_DATASET_URL = (
        "https://raw.githubusercontent.com/rfordatascience/tidytuesday/"
        "master/data/2022/2022-11-01/horror_movies.csv"
    )

    DEFAULT_FILENAME = "horror_movies_kaggle.csv"

    def __init__(self, output_dir: Path | None = None) -> None:
        """
        Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded files
        """
        self.logger = setup_logger("etl.kaggle")
        self.output_dir = output_dir or settings.paths.raw_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        force: bool = False,
        url: str | None = None,
        filename: str | None = None,
    ) -> DownloadResult:
        """
        Download CSV dataset.

        Args:
            force: Force re-download even if file exists
            url: Dataset URL (default: TidyTuesday horror movies)
            filename: Output filename

        Returns:
            DownloadResult with success status and file path
        """
        url = url or self.DEFAULT_DATASET_URL
        filename = filename or self.DEFAULT_FILENAME
        output_path = self.output_dir / filename

        # Skip if already downloaded (unless forced)
        if output_path.exists() and not force:
            rows = self._count_csv_rows(output_path)
            self.logger.info(f"✅ Dataset exists: {output_path.name} ({rows} rows)")
            return DownloadResult(
                success=True,
                message=f"Dataset already downloaded: {filename}",
                csv_path=output_path,
                rows_count=rows,
            )

        self.logger.info(f"📥 Downloading dataset from {url[:50]}...")

        try:
            response = requests.get(url, timeout=120, stream=True)
            response.raise_for_status()

            # Write content
            with output_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            rows = self._count_csv_rows(output_path)
            file_size = output_path.stat().st_size / 1024

            self.logger.info(f"✅ Downloaded: {filename} ({file_size:.1f} KB, {rows} rows)")

            return DownloadResult(
                success=True,
                message=f"Successfully downloaded {filename}",
                csv_path=output_path,
                rows_count=rows,
            )

        except requests.RequestException as e:
            self.logger.error(f"❌ Download failed: {e}")
            return DownloadResult(
                success=False,
                message=f"Download failed: {e}",
            )

    @staticmethod
    def _count_csv_rows(csv_path: Path) -> int:
        """Count rows in CSV file (excluding header)."""
        try:
            with csv_path.open("r", encoding="utf-8") as f:
                return sum(1 for _ in f) - 1
        except Exception:
            return 0

    def get_dataset_info(self) -> dict[str, Any]:
        """Return metadata about the default dataset."""
        return {
            "name": "TidyTuesday Horror Movies",
            "source": "GitHub/TidyTuesday",
            "url": self.DEFAULT_DATASET_URL,
            "description": "Horror movies dataset with ratings, budget, revenue",
            "format": "CSV",
        }

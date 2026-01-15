"""CSV extractors package.

Provides extractors for CSV file sources including
Kaggle datasets.
"""

from src.etl.extractors.csv.extractor import CSVExtractor
from src.etl.extractors.csv.normalizer import KaggleNormalizer

__all__ = ["CSVExtractor", "KaggleNormalizer"]

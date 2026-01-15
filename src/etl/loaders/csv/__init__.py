"""CSV loaders package.

Provides loaders for CSV data sources including
Kaggle datasets.
"""

from src.etl.loaders.csv.loader import KaggleLoader

__all__ = ["KaggleLoader"]

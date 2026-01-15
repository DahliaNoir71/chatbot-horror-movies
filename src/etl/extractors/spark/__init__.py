"""Spark extractor package for Big Data processing.

Validates C1 (Big Data extraction) and C2 (SparkSQL queries)
using PySpark in local mode.
"""

from src.etl.extractors.spark.extractor import SparkExtractor
from src.etl.extractors.spark.normalizer import SparkNormalizer
from src.etl.extractors.spark.queries import SparkQueries

__all__ = ["SparkExtractor", "SparkNormalizer", "SparkQueries"]

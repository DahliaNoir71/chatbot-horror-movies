"""Pipeline ETL HorrorBot - Wrapper for backward compatibility.

This file maintains backward compatibility with the original single-file
pipeline. All logic has been refactored into src/etl/pipeline/ package.

Usage:
    python pipeline.py --max-pages 5
    python pipeline.py --source tmdb
    python pipeline.py --resume-from 3
"""

from src.etl.pipeline import main

if __name__ == "__main__":
    main()

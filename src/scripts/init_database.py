"""Initialize HorrorBot database schema.

Creates all tables defined in SQLAlchemy models and seeds
reference data (genres, languages).

Usage:
    python -m src.scripts.init_database
    python -m src.scripts.init_database --drop  # Drop and recreate
    python -m src.scripts.init_database --seed  # Include seed data
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.connection import DatabaseConnection, get_database
from src.database.models import Base
from src.settings import settings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Initialize HorrorBot database schema",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing tables before creating",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed reference data after creation",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check connection, don't modify schema",
    )
    return parser.parse_args()


def check_extensions(db: DatabaseConnection) -> bool:
    """Verify required PostgreSQL extensions are installed.

    Args:
        db: DatabaseConnection instance.

    Returns:
        True if all extensions are present.
    """
    required = ["vector", "pg_trgm", "uuid-ossp"]
    missing = []

    with db.session() as session:
        result = session.execute(text("SELECT extname FROM pg_extension"))
        installed = {row[0] for row in result}

    for ext in required:
        if ext not in installed:
            missing.append(ext)

    if missing:
        print(f"❌ Missing extensions: {', '.join(missing)}")
        print("   Run: docker-compose down && docker-compose up -d db")
        return False

    print("✅ All required extensions installed")
    return True


def drop_tables(db: DatabaseConnection) -> None:
    """Drop all tables in the schema.

    Args:
        db: DatabaseConnection instance.
    """
    print("🗑️  Dropping existing tables...")
    Base.metadata.drop_all(bind=db.sync_engine)
    print("✅ Tables dropped")


def create_tables(db: DatabaseConnection) -> None:
    """Create all tables from SQLAlchemy models.

    Args:
        db: DatabaseConnection instance.
    """
    print("📋 Creating tables...")
    Base.metadata.create_all(bind=db.sync_engine)
    print("✅ Tables created")


def create_indexes(db: DatabaseConnection) -> None:
    """Create additional indexes not defined in models.

    Args:
        db: DatabaseConnection instance.
    """
    print("📇 Creating additional indexes...")

    indexes = [
        # GIN index for trigram search on film titles
        """
        CREATE INDEX IF NOT EXISTS idx_films_title_gin
            ON films USING gin (title gin_trgm_ops)
        """,
    ]

    with db.session() as session:
        for idx_sql in indexes:
            try:
                session.execute(text(idx_sql))
            except Exception as e:  # noqa: BLE001
                print(f"   ⚠️  Index warning: {e}")

    print("✅ Indexes created")


def seed_genres(db: DatabaseConnection) -> None:
    """Seed TMDB horror-related genres.

    Args:
        db: DatabaseConnection instance.
    """
    from src.database.models import Genre

    genres = [
        (27, "Horror"),
        (53, "Thriller"),
        (9648, "Mystery"),
        (878, "Science Fiction"),
        (14, "Fantasy"),
        (28, "Action"),
        (12, "Adventure"),
        (35, "Comedy"),
        (80, "Crime"),
        (18, "Drama"),
        (10751, "Family"),
        (36, "History"),
        (10402, "Music"),
        (10749, "Romance"),
        (10752, "War"),
        (37, "Western"),
        (99, "Documentary"),
        (16, "Animation"),
        (10770, "TV Movie"),
    ]

    with db.session() as session:
        for tmdb_id, name in genres:
            existing = session.query(Genre).filter_by(tmdb_genre_id=tmdb_id).first()
            if not existing:
                session.add(Genre(tmdb_genre_id=tmdb_id, name=name))

    print(f"✅ Seeded {len(genres)} genres")


def seed_languages(db: DatabaseConnection) -> None:
    """Seed common spoken languages.

    Args:
        db: DatabaseConnection instance.
    """
    from src.database.models import SpokenLanguage

    languages = [
        ("en", "English"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("de", "German"),
        ("it", "Italian"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("zh", "Chinese"),
        ("pt", "Portuguese"),
        ("ru", "Russian"),
        ("hi", "Hindi"),
        ("ar", "Arabic"),
        ("th", "Thai"),
        ("sv", "Swedish"),
        ("no", "Norwegian"),
        ("da", "Danish"),
        ("fi", "Finnish"),
        ("nl", "Dutch"),
        ("pl", "Polish"),
        ("tr", "Turkish"),
    ]

    with db.session() as session:
        for iso_code, name in languages:
            existing = session.query(SpokenLanguage).filter_by(iso_639_1=iso_code).first()
            if not existing:
                session.add(SpokenLanguage(iso_639_1=iso_code, name=name))

    print(f"✅ Seeded {len(languages)} languages")


def seed_rgpd_registry(db: DatabaseConnection) -> None:
    """Seed RGPD processing registry entries.

    Args:
        db: DatabaseConnection instance.
    """
    from src.database.models import RGPDProcessingRegistry

    # Constants for RGPD registry
    INDEFINITE_RETENTION = "Indefinite (public data)"

    entries = [
        {
            "processing_name": "Film Metadata Collection",
            "processing_purpose": "Collect film metadata from TMDB API for horror movie recommendations",
            "data_categories": ["film_titles", "release_dates", "synopses", "ratings"],
            "data_subjects": ["public_film_data"],
            "recipients": ["horrorbot_application"],
            "retention_period": INDEFINITE_RETENTION,
            "legal_basis": "legitimate_interests",
            "security_measures": "Database encryption, access control, regular backups",
        },
        {
            "processing_name": "Critics Scores Scraping",
            "processing_purpose": "Collect critic and audience scores from Rotten Tomatoes",
            "data_categories": ["tomatometer_scores", "audience_scores", "critics_consensus"],
            "data_subjects": ["aggregated_critic_data"],
            "recipients": ["horrorbot_application"],
            "retention_period": INDEFINITE_RETENTION,
            "legal_basis": "legitimate_interests",
            "security_measures": "Rate limiting, respectful scraping practices",
        },
    ]

    with db.session() as session:
        for entry in entries:
            existing = (
                session.query(RGPDProcessingRegistry)
                .filter_by(processing_name=entry["processing_name"])
                .first()
            )
            if not existing:
                session.add(RGPDProcessingRegistry(**entry))

    print(f"✅ Seeded {len(entries)} RGPD registry entries")


def print_table_summary(db: DatabaseConnection) -> None:
    """Print summary of created tables.

    Args:
        db: DatabaseConnection instance.
    """
    query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name \
            """

    with db.session() as session:
        result = session.execute(text(query))
        tables = [row[0] for row in result]

    print("\n📊 Database Tables:")
    print("-" * 40)
    for table in tables:
        print(f"   • {table}")
    print("-" * 40)
    print(f"   Total: {len(tables)} tables")


def _print_banner() -> None:
    """Print the application banner with database connection info."""
    print("=" * 50)
    print("🎬 HorrorBot Database Initialization")
    print("=" * 50)
    print(f"   Host: {settings.database.host}")
    print(f"   Port: {settings.database.port}")
    print(f"   Database: {settings.database.database}")
    print("=" * 50)


def _check_database_connection(db: DatabaseConnection) -> tuple[bool, int]:
    """Check database connection and return status.

    Args:
        db: DatabaseConnection instance.

    Returns:
        Tuple of (connection_success, status_code).
    """
    if not db.check_connection():
        print("❌ Cannot connect to database")
        print("   Make sure PostgreSQL is running:")
        print("   docker-compose up -d db")
        return False, 1
    print("✅ Database connection successful")
    return True, 0


def _perform_database_operations(db: DatabaseConnection, args: argparse.Namespace) -> int:
    """Perform the main database operations based on arguments.

    Args:
        db: DatabaseConnection instance.
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    if args.check:
        check_extensions(db)
        print_table_summary(db)
        return 0

    if not check_extensions(db):
        return 1

    if args.drop:
        drop_tables(db)

    create_tables(db)
    create_indexes(db)

    if args.seed:
        print("\n🌱 Seeding reference data...")
        seed_genres(db)
        seed_languages(db)
        seed_rgpd_registry(db)

    print_table_summary(db)
    print("\n✅ Database initialization complete!")
    return 0


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()
    _print_banner()

    db = get_database()

    # Check connection
    connection_ok, status = _check_database_connection(db)
    if not connection_ok:
        return status

    # Perform main operations
    return _perform_database_operations(db, args)


if __name__ == "__main__":
    sys.exit(main())

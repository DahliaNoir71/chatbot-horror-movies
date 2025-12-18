"""Import IMDB dataset from Kaggle into PostgreSQL.

Downloads carolzhangdc/imdb-5000-movie-dataset and imports horror movies
into the external PostgreSQL database (port 5433).

Usage:
    python -m src.scripts.import_imdb
    python -m src.scripts.import_imdb --limit 1000
    python -m src.scripts.import_imdb --replace
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Setup Kaggle credentials BEFORE importing KaggleApi
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)

    # Set Kaggle env vars if present in .env
    kaggle_user = os.getenv("KAGGLE_USERNAME")
    kaggle_key = os.getenv("KAGGLE_KEY")
    if kaggle_user and kaggle_key:
        os.environ["KAGGLE_USERNAME"] = kaggle_user
        os.environ["KAGGLE_KEY"] = kaggle_key


DATASET_SLUG = "carolzhangdc/imdb-5000-movie-dataset"
DATASET_FILE = "movie_metadata.csv"
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "imdb"


def download_dataset() -> Path:
    """Download IMDB dataset from Kaggle.

    Returns:
        Path to downloaded CSV file.
    """
    from kaggle.api.kaggle_api_extended import KaggleApi

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / DATASET_FILE

    if csv_path.exists():
        print(f"✅ Dataset déjà présent : {csv_path}")
        return csv_path

    print(f"📥 Téléchargement du dataset {DATASET_SLUG}...")
    api = KaggleApi()
    api.authenticate()

    api.dataset_download_files(
        DATASET_SLUG,
        path=str(DATA_DIR),
        unzip=True,
        quiet=False,
    )

    if csv_path.exists():
        print(f"✅ Dataset téléchargé : {csv_path}")
        return csv_path

    # Chercher le fichier téléchargé
    csv_files = list(DATA_DIR.glob("*.csv"))
    if csv_files:
        print(f"✅ Fichiers trouvés : {[f.name for f in csv_files]}")
        return csv_files[0]

    raise FileNotFoundError(f"Aucun CSV trouvé dans {DATA_DIR}")


def load_dataset(csv_path: Path, limit: int | None = None) -> pd.DataFrame:
    """Load CSV dataset.

    Args:
        csv_path: Path to IMDB CSV file.
        limit: Maximum number of rows to import.

    Returns:
        DataFrame with all movies.
    """
    print(f"📖 Lecture du fichier {csv_path.name}...")

    # Définition des types de colonnes pour une lecture plus efficace
    dtype = {
        "color": "category",
        "director_name": "string",
        "num_critic_for_reviews": "Int64",
        "duration": "float64",
        "director_facebook_likes": "Int64",
        "actor_3_facebook_likes": "Int64",
        "actor_2_name": "string",
        "actor_1_facebook_likes": "Int64",
        "gross": "float64",
        "genres": "string",
        "actor_1_name": "string",
        "movie_title": "string",
        "num_voted_users": "Int64",
        "cast_total_facebook_likes": "Int64",
        "actor_3_name": "string",
        "facenumber_in_poster": "Int64",
        "plot_keywords": "string",
        "movie_imdb_link": "string",
        "num_user_for_reviews": "Int64",
        "language": "category",
        "country": "category",
        "content_rating": "category",
        "budget": "float64",
        "title_year": "Int64",
        "actor_2_facebook_likes": "Int64",
        "imdb_score": "float64",
        "aspect_ratio": "float64",
        "movie_facebook_likes": "Int64",
    }

    df = pd.read_csv(csv_path, low_memory=False, dtype=dtype)

    print(f"   Colonnes disponibles : {list(df.columns)}")
    print(f"   Total lignes : {len(df):,}")

    # Appliquer la limite
    if limit and len(df) > limit:
        df = df.head(limit)
        print(f"   Limite appliquée : {limit:,} films")

    return df


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names for PostgreSQL.

    Args:
        df: Raw DataFrame.

    Returns:
        DataFrame with normalized column names.
    """
    # Mapping des colonnes carolzhangdc/imdb-5000-movie-dataset
    column_mapping = {
        "movie_title": "title",
        "title_year": "year",
        "genres": "genres",
        "duration": "runtime",
        "director_name": "director",
        "country": "country",
        "language": "language",
        "plot_keywords": "overview",
        "imdb_score": "vote_average",
        "num_voted_users": "vote_count",
        "budget": "budget",
        "gross": "revenue_worldwide",
        "num_critic_for_reviews": "critic_reviews",
        "num_user_for_reviews": "user_reviews",
        "content_rating": "content_rating",
        "movie_imdb_link": "imdb_link",
    }

    # Renommer les colonnes existantes
    rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Combiner acteurs si présents
    actor_cols = ["actor_1_name", "actor_2_name", "actor_3_name"]
    if all(col in df.columns for col in actor_cols):
        df["actors"] = df[actor_cols].fillna("").agg(", ".join, axis=1)
        df["actors"] = df["actors"].str.strip(", ")

    # Extraire IMDB ID depuis le lien
    if "imdb_link" in df.columns:
        df["imdb_id"] = df["imdb_link"].str.extract(r"(tt\d+)")
        df = df.drop(columns=["imdb_link"])

    # Nettoyer le titre (enlever espaces trailing)
    if "title" in df.columns:
        df["title"] = df["title"].str.strip()

    # Convertir colonnes numériques (peuvent contenir NaN)
    numeric_cols = ["budget", "revenue_worldwide", "vote_count", "critic_reviews", "user_reviews"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convertir year en int (supprimer NaN d'abord)
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df = df.dropna(subset=["year"])
        df["year"] = df["year"].astype(int)

    # Garder seulement les colonnes utiles
    keep_cols = [
        "imdb_id",
        "title",
        "year",
        "genres",
        "runtime",
        "director",
        "actors",
        "country",
        "language",
        "overview",
        "vote_average",
        "vote_count",
        "budget",
        "revenue_worldwide",
        "critic_reviews",
        "user_reviews",
        "content_rating",
    ]
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].copy()

    # Ajouter source
    df["source"] = "imdb"

    print(f"   Colonnes normalisées : {list(df.columns)}")

    return df


def get_connection_url() -> str:
    """Get PostgreSQL connection URL from environment.

    Returns:
        Connection URL string.
    """
    host = os.getenv("IMDB_DB_HOST", "localhost")
    port = os.getenv("IMDB_DB_PORT", "5433")
    database = os.getenv("IMDB_DB_NAME", "horror_imdb")
    user = os.getenv("IMDB_DB_USER", "imdb_user")
    password = os.getenv("IMDB_DB_PASSWORD", "")

    if not password:
        raise ValueError(
            "IMDB_DB_PASSWORD non défini. Ajouter dans .env:\nIMDB_DB_PASSWORD=your_password"
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def create_table(engine: Engine) -> None:
    """Create movies table if not exists.

    Args:
        engine: SQLAlchemy engine.
    """
    # noinspection SqlDialectInspection,SqlNoDataSourceInspection
    create_sql = """
    CREATE TABLE IF NOT EXISTS movies (
        id SERIAL PRIMARY KEY,
        imdb_id VARCHAR(20) UNIQUE,
        title VARCHAR(500),
        year INTEGER,
        genres TEXT,
        runtime INTEGER,
        director TEXT,
        actors TEXT,
        country TEXT,
        language TEXT,
        overview TEXT,
        vote_average FLOAT,
        vote_count INTEGER,
        budget BIGINT,
        revenue_worldwide BIGINT,
        critic_reviews INTEGER,
        user_reviews INTEGER,
        content_rating VARCHAR(20),
        source VARCHAR(50) DEFAULT 'imdb',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies(imdb_id);
    CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);
    CREATE INDEX IF NOT EXISTS idx_movies_vote_avg ON movies(vote_average);
    """

    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()

    print("✅ Table 'movies' créée/vérifiée")


def import_to_postgres(
    df: pd.DataFrame,
    connection_url: str,
    replace: bool = False,
) -> int:
    """Import DataFrame into PostgreSQL."""
    engine = create_engine(connection_url)

    # Créer la table
    create_table(engine)

    # Si replace, on TRUNCATE au lieu de DROP (préserve les vues)
    if replace:
        print("🗑️ Remplacement des données existantes...")
        with engine.connect() as conn:
            # noinspection SqlDialectInspection,SqlNoDataSourceInspection
            conn.execute(text("TRUNCATE TABLE movies RESTART IDENTITY"))
            conn.commit()

    print(f"📤 Import de {len(df):,} films dans PostgreSQL...")

    df.to_sql(
        "movies",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )

    # Vérifier le count
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM movies"))
        count = result.scalar()

    print(f"✅ Import terminé : {count:,} films dans la base")

    return count


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import IMDB dataset into PostgreSQL")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of films to import (default: all)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing data instead of appending",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download, use existing CSV",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🎬 IMPORT IMDB DATASET")
    print("=" * 60)

    try:
        # Download
        csv_path = download_dataset()

        # Load and filter
        df = load_dataset(csv_path, limit=args.limit)

        if df.empty:
            print("❌ Aucun film à importer")
            sys.exit(1)

        # Normalize
        df = normalize_columns(df)
        df = df.drop_duplicates(subset=["imdb_id"], keep="first").dropna(subset=["imdb_id"])

        # Import
        connection_url = get_connection_url()
        count = import_to_postgres(df, connection_url, replace=args.replace)

        print("=" * 60)
        print(f"✅ SUCCÈS : {count:,} films IMDB importés")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

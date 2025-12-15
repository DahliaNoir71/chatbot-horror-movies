"""Importateur de données agrégées vers PostgreSQL."""

from datetime import datetime
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from src.database.models import Base, Film
from src.etl.utils import setup_logger
from src.settings import settings


class DatabaseImporter:
    """Importe les films agrégés dans PostgreSQL avec embeddings."""

    def __init__(self) -> None:
        self.logger = setup_logger("database.importer")

        # SQLAlchemy
        self.engine = create_engine(
            settings.database.connection_url, pool_pre_ping=True, echo=settings.debug
        )
        self.session = sessionmaker(bind=self.engine)

        # Modèle embeddings
        self.logger.info("Chargement modèle embeddings...")
        self.embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def init_database(self) -> None:
        """Crée les tables si elles n'existent pas."""
        self.logger.info("Initialisation schéma PostgreSQL...")
        Base.metadata.create_all(self.engine)
        self.logger.info("✅ Schéma créé")

    def generate_embedding(self, film: dict[str, Any]) -> np.ndarray:
        """Génère l'embedding d'un film."""
        # Priorité: critics_consensus > overview
        text = film.get("critics_consensus") or film.get("overview") or film["title"]

        # Texte complet pour contexte RAG
        full_text = f"{film['title']} ({film['year']}). {text}"

        return self.embedding_model.encode(full_text, normalize_embeddings=True)

    def import_films(self, films: list[dict[str, Any]]) -> int:
        """Importe les films avec embeddings."""
        self.logger.info(f"Import de {len(films)} films...")

        session = self.session()
        imported = 0

        try:
            for film_data in tqdm(films, desc="Import PostgreSQL"):
                # Vérifier si existe déjà
                existing = session.query(Film).filter_by(tmdb_id=film_data["tmdb_id"]).first()

                if existing:
                    continue

                # Générer embedding
                embedding = self.generate_embedding(film_data)

                # Créer objet Film
                film = Film(
                    tmdb_id=film_data["tmdb_id"],
                    imdb_id=film_data.get("imdb_id"),
                    title=film_data["title"],
                    original_title=film_data.get("original_title"),
                    year=film_data["year"],
                    release_date=datetime.strptime(film_data["release_date"], "%Y-%m-%d").date()
                    if film_data.get("release_date")
                    else None,
                    vote_average=film_data.get("vote_average"),
                    vote_count=film_data.get("vote_count", 0),
                    popularity=film_data.get("popularity", 0.0),
                    tomatometer_score=film_data.get("tomatometer_score"),
                    audience_score=film_data.get("audience_score"),
                    certified_fresh=film_data.get("certified_fresh", False),
                    critics_consensus=film_data.get("critics_consensus"),
                    overview=film_data.get("overview"),
                    tagline=film_data.get("tagline"),
                    runtime=film_data.get("runtime"),
                    original_language=film_data.get("original_language"),
                    genres=film_data.get("genres"),
                    rotten_tomatoes_url=film_data.get("rotten_tomatoes_url"),
                    poster_path=film_data.get("poster_path"),
                    backdrop_path=film_data.get("backdrop_path"),
                    embedding=embedding.tolist(),
                )

                session.add(film)
                imported += 1

                # Commit par batch de 50
                if imported % 50 == 0:
                    session.commit()

            session.commit()
            self.logger.info(f"✅ {imported} films importés")
            return imported

        except Exception as e:
            session.rollback()
            self.logger.error(f"❌ Erreur import: {e}")
            raise
        finally:
            session.close()

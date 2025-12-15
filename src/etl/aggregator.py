"""Module d'agrégation et de normalisation des données films."""

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger

# === Schémas de validation Pydantic ===


class MovieSchema(BaseModel):
    """Schéma validé pour un film agrégé."""

    # Identifiants (TMDB source de vérité)
    tmdb_id: int = Field(gt=0)
    imdb_id: str | None = Field(default=None, pattern=r"^tt\d{7,8}$")

    # Informations de base
    title: str = Field(min_length=1, max_length=500)
    original_title: str | None = None
    # Premier film : 1888
    year: int = Field(ge=1888, le=2030)
    release_date: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    # Scores TMDB
    vote_average: float = Field(ge=0.0, le=10.0)
    vote_count: int = Field(ge=0)
    popularity: float = Field(ge=0.0)

    # Scores Rotten Tomatoes (optionnels)
    tomatometer_score: int | None = Field(default=None, ge=0, le=100)
    audience_score: int | None = Field(default=None, ge=0, le=100)
    certified_fresh: bool = Field(default=False)
    critics_count: int = Field(default=0, ge=0)
    audience_count: int = Field(default=0, ge=0)

    # Textes descriptifs (RT prioritaire)
    critics_consensus: str | None = Field(default=None, max_length=2000)
    overview: str | None = Field(default=None, max_length=2000)
    tagline: str | None = Field(default=None, max_length=500)

    # Métadonnées
    runtime: int | None = Field(default=None, ge=1, le=1000)
    genres: list[str] = Field(default_factory=list)
    original_language: str | None = Field(pattern=r"^[a-z]{2}$")

    # URLs et références
    rotten_tomatoes_url: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None

    # Flags
    incomplete: bool = Field(default=False)

    @field_validator("title", "original_title", "critics_consensus", "overview", "tagline")
    @classmethod
    def sanitize_text(cls, v: str | None) -> str | None:
        """Nettoie les champs texte."""
        if v is None:
            return None
        # Normalise les espaces multiples
        return " ".join(v.strip().split())

    @field_validator("release_date")
    @classmethod
    def validate_release_date(cls, v: str | None) -> str | None:
        """Valide le format de date."""
        if v is None:
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            return None


@dataclass
class AggregationStats:
    """Statistiques d'agrégation."""

    tmdb_movies: int = 0
    rt_enriched: int = 0
    duplicates_removed: int = 0
    validation_failed: int = 0
    final_count: int = 0

    @property
    def enrichment_rate(self) -> float:
        """Taux d'enrichissement RT en %."""
        if self.tmdb_movies == 0:
            return 0.0
        return (self.rt_enriched / self.tmdb_movies) * 100


# === Agrégateur principal ===


class DataAggregator(BaseExtractor):
    """Agrège et normalise les données de multiples sources."""

    def __init__(self) -> None:
        """Initialise l'agrégateur."""
        super().__init__("DataAggregator")
        self.logger = setup_logger("etl.aggregator")
        self.stats = AggregationStats()
        # tmdb_id -> movie
        self.seen_movies: dict[int, dict[str, Any]] = {}

    def validate_config(self) -> None:
        """Pas de configuration externe nécessaire."""
        pass

    # === Fusion des sources ===

    def merge_sources(
        self, tmdb_data: dict[str, Any], rt_data: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        Fusionne les données TMDB et RT selon les règles de priorité.

        Priorité :
        - Identifiants : TMDB
        - Scores : RT si disponible
        - Texte descriptif : Critics Consensus > Overview
        """
        merged: dict[str, Any] = {
            # TMDB (source de vérité pour identifiants)
            "tmdb_id": tmdb_data["id"],
            "imdb_id": tmdb_data.get("imdb_id"),
            "title": tmdb_data["title"],
            "original_title": tmdb_data.get("original_title"),
            "year": self._extract_year(tmdb_data.get("release_date")),
            "release_date": tmdb_data.get("release_date"),
            # Scores TMDB
            "vote_average": tmdb_data.get("vote_average", 0.0),
            "vote_count": tmdb_data.get("vote_count", 0),
            "popularity": tmdb_data.get("popularity", 0.0),
            # Textes TMDB (fallback)
            "overview": tmdb_data.get("overview"),
            "tagline": tmdb_data.get("tagline"),
            # Métadonnées
            "runtime": tmdb_data.get("runtime"),
            "genres": self._extract_genres(tmdb_data),
            "original_language": tmdb_data.get("original_language"),
            # Chemins images
            "poster_path": tmdb_data.get("poster_path"),
            "backdrop_path": tmdb_data.get("backdrop_path"),
        }

        # Enrichissement RT si disponible
        if rt_data:
            self._merge_rt_data(merged, rt_data)

        return merged

    def _merge_rt_data(self, merged: dict[str, Any], rt_data: dict[str, Any]) -> None:
        """Fusionne les données RT dans le dictionnaire fusionné."""
        merged["tomatometer_score"] = rt_data.get("tomatometer_score")
        merged["audience_score"] = rt_data.get("audience_score")
        merged["certified_fresh"] = rt_data.get("certified_fresh", False)
        merged["critics_count"] = rt_data.get("critics_count", 0)
        merged["audience_count"] = rt_data.get("audience_count", 0)
        merged["rotten_tomatoes_url"] = rt_data.get("rotten_tomatoes_url")

        # Priorité Critics Consensus > Overview pour RAG
        if consensus := rt_data.get("critics_consensus"):
            merged["critics_consensus"] = consensus

    @staticmethod
    def _extract_year(release_date: str | None) -> int:
        """Extrait l'année depuis release_date."""
        if not release_date:
            # Valeur par défaut
            return 1900
        try:
            return int(release_date[:4])
        except (ValueError, TypeError):
            return 1900

    @staticmethod
    def _extract_genres(tmdb_data: dict[str, Any]) -> list[str]:
        """Extrait les noms de genres."""
        genres = tmdb_data.get("genres", [])
        if isinstance(genres, list):
            return [g["name"] for g in genres if isinstance(g, dict) and "name" in g]
        return []

    # === Normalisation ===

    def normalize_movie(self, movie: dict[str, Any]) -> dict[str, Any]:
        """Normalise les formats selon les standards."""
        normalized = movie.copy()

        # Normalisation des scores (0-10 pour uniformité)
        if "vote_average" in normalized:
            normalized["vote_average"] = self._normalize_score(normalized["vote_average"], 0, 10)

        # Nettoyage des textes
        for field in ["title", "overview", "critics_consensus", "tagline"]:
            if field in normalized and normalized[field]:
                normalized[field] = self._clean_text(normalized[field])

        return normalized

    @staticmethod
    def _normalize_score(score: float, min_val: float, max_val: float) -> float:
        """Normalise un score dans une plage."""
        return max(min_val, min(max_val, float(score)))

    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoie un texte (espaces, caractères spéciaux)."""
        # Remplace espaces multiples par un seul
        cleaned = " ".join(text.split())
        # Retire caractères de contrôle
        return "".join(char for char in cleaned if char.isprintable() or char.isspace())

    # === Validation ===

    def validate_movie(self, movie: dict[str, Any]) -> MovieSchema | None:
        """
        Valide un film avec Pydantic.

        Returns:
            MovieSchema validé ou None si échec
        """
        try:
            return MovieSchema(**movie)
        except Exception as e:
            self.logger.warning(f"Validation échouée pour {movie.get('title', 'Unknown')}: {e}")
            self.stats.validation_failed += 1
            return None

    # === Déduplication ===

    def is_duplicate(self, movie: dict[str, Any]) -> bool:
        """
        Vérifie si un film est un doublon.

        Critères :
        - IMDb ID identique (priorité absolue)
        - Titre similaire (Levenshtein < 3) + année ±1
        """
        tmdb_id = movie["tmdb_id"]

        # Déjà vu par tmdb_id
        if tmdb_id in self.seen_movies:
            return True

        # Vérifier IMDb ID ou similarité titre
        return self._check_duplicate_by_metadata(movie)

    def _check_duplicate_by_metadata(self, movie: dict[str, Any]) -> bool:
        """Vérifie les doublons par IMDb ID et similarité titre."""
        imdb_id = movie.get("imdb_id")
        title = movie["title"].lower()
        year = movie["year"]

        for seen in self.seen_movies.values():
            # Match IMDb ID
            if imdb_id and seen.get("imdb_id") == imdb_id:
                self.logger.warning(f"Doublon détecté (IMDb): {movie['title']} = {seen['title']}")
                return True

            # Match titre + année
            if self._are_movies_similar(title, year, seen):
                self.logger.warning(f"Doublon détecté (titre): {movie['title']} = {seen['title']}")
                return True

        return False

    def _are_movies_similar(self, title: str, year: int, seen: dict[str, Any]) -> bool:
        """Vérifie si deux films sont similaires."""
        seen_title = seen["title"].lower()
        seen_year = seen["year"]

        # Différence d'année > 1 : pas similaire
        if abs(year - seen_year) > 1:
            return False

        # Similarité titre (ratio > 0.9)
        similarity = SequenceMatcher(None, title, seen_title).ratio()
        return similarity > 0.9

    def add_to_seen(self, movie: dict[str, Any]) -> None:
        """Ajoute un film à la liste des films vus."""
        self.seen_movies[movie["tmdb_id"]] = movie

    # === Point d'entrée principal ===

    def extract(
        self,
        tmdb_movies: list[dict[str, Any]],
        rt_enriched: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Agrège les données de multiples sources.

        Args:
            tmdb_movies: Films depuis TMDB
            rt_enriched: Films enrichis RT (optionnel)

        Returns:
            Liste de films agrégés, validés, dédupliqués
        """
        self._start_extraction()

        self.stats.tmdb_movies = len(tmdb_movies)
        self.logger.info(f"Agrégation de {self.stats.tmdb_movies} films TMDB")

        # Créer index RT par tmdb_id pour fusion rapide
        rt_index = self._build_rt_index(rt_enriched or [])
        self.stats.rt_enriched = len(rt_index)

        aggregated: list[dict[str, Any]] = []

        for tmdb_movie in tmdb_movies:
            tmdb_id = tmdb_movie.get("id")
            if not tmdb_id:
                continue

            # Récupérer données RT si disponibles
            rt_data = rt_index.get(tmdb_id)

            # Fusionner
            merged = self.merge_sources(tmdb_movie, rt_data)

            # Normaliser
            normalized = self.normalize_movie(merged)

            # Valider
            validated = self.validate_movie(normalized)
            if not validated:
                continue

            # Dédupliquer
            validated_dict = validated.model_dump()
            if self.is_duplicate(validated_dict):
                self.stats.duplicates_removed += 1
                continue

            self.add_to_seen(validated_dict)
            aggregated.append(validated_dict)

        self.stats.final_count = len(aggregated)
        self.metrics.total_records = self.stats.final_count

        self._end_extraction()
        self._log_aggregation_stats()

        return aggregated

    def _build_rt_index(self, rt_enriched: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        """Construit un index RT (seulement films avec données RT)."""
        index: dict[int, dict[str, Any]] = {}

        for movie in rt_enriched:
            # ✅ Vérifier présence données RT
            if not movie.get("tomatometer_score"):
                continue

            if tmdb_id := movie.get("tmdb_id") or movie.get("id"):
                index[tmdb_id] = movie

        return index

    def _log_aggregation_stats(self) -> None:
        """Affiche les statistiques d'agrégation."""
        self.logger.info("=" * 80)
        self.logger.info("📊 STATISTIQUES AGRÉGATION")
        self.logger.info("-" * 80)
        self.logger.info(f"Films TMDB          : {self.stats.tmdb_movies:,}")
        self.logger.info(f"Films RT enrichis   : {self.stats.rt_enriched:,}")
        self.logger.info(f"Taux enrichissement : {self.stats.enrichment_rate:.1f}%")
        self.logger.info(f"Doublons supprimés  : {self.stats.duplicates_removed:,}")
        self.logger.info(f"Validation échouée  : {self.stats.validation_failed:,}")
        self.logger.info(f"Films finaux        : {self.stats.final_count:,}")
        self.logger.info("=" * 80)

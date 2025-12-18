"""Module d'agrégation et de normalisation des données films - 5 sources.

Valide C3 : Agrégation de données issues de différentes sources.
Sources supportées :
1. TMDB API (source principale)
2. Rotten Tomatoes (web scraping)
3. Kaggle CSV (fichier données)
4. Letterboxd PostgreSQL (base externe)
5. YouTube Spark (big data)
"""

from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.etl.extractors.base_extractor import BaseExtractor
from src.etl.utils import setup_logger

# === Schémas de validation Pydantic ===


class MovieSchema(BaseModel):
    """Schéma validé pour un film agrégé multi-sources."""

    # Identifiants (TMDB source de vérité)
    tmdb_id: int = Field(gt=0)
    imdb_id: str | None = Field(default=None, pattern=r"^tt\d{7,8}$")
    letterboxd_id: str | None = Field(default=None)

    # Informations de base
    title: str = Field(min_length=1, max_length=500)
    original_title: str | None = None
    year: int = Field(ge=1888, le=2030)
    release_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    # Scores TMDB (source 1)
    vote_average: float = Field(ge=0.0, le=10.0)
    vote_count: int = Field(ge=0)
    popularity: float = Field(ge=0.0)

    # Scores Rotten Tomatoes (source 2)
    tomatometer_score: int | None = Field(default=None, ge=0, le=100)
    audience_score: int | None = Field(default=None, ge=0, le=100)
    certified_fresh: bool = Field(default=False)
    critics_count: int = Field(default=0, ge=0)
    audience_count: int = Field(default=0, ge=0)
    critics_consensus: str | None = Field(default=None, max_length=2000)

    # Scores Kaggle (source 3)
    kaggle_rating: float | None = Field(default=None, ge=0.0, le=10.0)
    kaggle_votes: int | None = Field(default=None, ge=0)

    # Scores Letterboxd (source 4)
    letterboxd_score: float | None = Field(default=None, ge=0.0, le=10.0)
    letterboxd_votes: int | None = Field(default=None, ge=0)
    letterboxd_url: str | None = None

    # Stats YouTube (source 5)
    youtube_video_count: int | None = Field(default=None, ge=0)
    youtube_total_views: int | None = Field(default=None, ge=0)
    youtube_engagement: float | None = Field(default=None, ge=0.0)

    # Textes descriptifs
    overview: str | None = Field(default=None, max_length=2000)
    tagline: str | None = Field(default=None, max_length=500)

    # Métadonnées
    runtime: int | None = Field(default=None, ge=1, le=1000)
    genres: list[str] = Field(default_factory=list)
    original_language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")

    # URLs et références
    rotten_tomatoes_url: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None

    # Flags sources
    source_tmdb: bool = Field(default=False)
    source_rt: bool = Field(default=False)
    source_kaggle: bool = Field(default=False)
    source_letterboxd: bool = Field(default=False)
    source_youtube: bool = Field(default=False)

    # Score agrégé calculé
    aggregated_score: float | None = Field(default=None, ge=0.0, le=10.0)
    source_count: int = Field(default=0, ge=0, le=5)

    @field_validator("title", "original_title", "critics_consensus", "overview", "tagline")
    @classmethod
    def sanitize_text(cls, v: str | None) -> str | None:
        """Nettoie les champs texte."""
        if v is None:
            return None
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
    """Statistiques d'agrégation multi-sources."""

    # Compteurs par source
    tmdb_count: int = 0
    rt_enriched: int = 0
    kaggle_matched: int = 0
    letterboxd_matched: int = 0
    youtube_matched: int = 0

    # Qualité
    duplicates_removed: int = 0
    validation_failed: int = 0
    final_count: int = 0

    # Couverture
    multi_source_films: int = 0

    @property
    def enrichment_rates(self) -> dict[str, float]:
        """Taux d'enrichissement par source en %."""
        if self.tmdb_count == 0:
            return {}
        return {
            "rotten_tomatoes": (self.rt_enriched / self.tmdb_count) * 100,
            "kaggle": (self.kaggle_matched / self.tmdb_count) * 100,
            "imdb": (self.letterboxd_matched / self.tmdb_count) * 100,
            "youtube": (self.youtube_matched / self.tmdb_count) * 100,
        }


@dataclass
class SourceData:
    """Container pour données d'une source."""

    name: str
    data: list[dict[str, Any]] = field(default_factory=list)
    index_by_tmdb: dict[int, dict[str, Any]] = field(default_factory=dict)
    index_by_imdb: dict[str, dict[str, Any]] = field(default_factory=dict)


# === Agrégateur principal ===


class DataAggregator(BaseExtractor):
    """Agrège et normalise les données de 5 sources hétérogènes."""

    def __init__(self) -> None:
        """Initialise l'agrégateur."""
        super().__init__("DataAggregator")
        self.logger = setup_logger("etl.aggregator")
        self.stats = AggregationStats()
        self.seen_movies: dict[int, dict[str, Any]] = {}

    def validate_config(self) -> None:
        """Pas de configuration externe nécessaire."""
        pass

    # === Indexation des sources ===

    def _build_source_index(self, data: list[dict[str, Any]], source_name: str) -> SourceData:
        """Construit index par tmdb_id et imdb_id pour une source.

        Args:
            data: Données brutes de la source.
            source_name: Nom de la source.

        Returns:
            SourceData avec index.
        """
        source = SourceData(name=source_name, data=data)

        for item in data:
            # Index par tmdb_id
            if tmdb_id := item.get("tmdb_id") or item.get("id"):
                source.index_by_tmdb[int(tmdb_id)] = item

            # Index par imdb_id
            if imdb_id := item.get("imdb_id"):
                source.index_by_imdb[str(imdb_id)] = item

        self.logger.debug(
            f"Index {source_name}: {len(source.index_by_tmdb)} tmdb, "
            f"{len(source.index_by_imdb)} imdb"
        )
        return source

    def _find_match(
        self, tmdb_id: int, imdb_id: str | None, source: SourceData
    ) -> dict[str, Any] | None:
        """Cherche correspondance dans une source par ID.

        Args:
            tmdb_id: ID TMDB du film.
            imdb_id: ID IMDb optionnel.
            source: Source indexée.

        Returns:
            Données correspondantes ou None.
        """
        # Priorité tmdb_id
        if tmdb_id in source.index_by_tmdb:
            return source.index_by_tmdb[tmdb_id]

        # Fallback imdb_id
        if imdb_id and imdb_id in source.index_by_imdb:
            return source.index_by_imdb[imdb_id]

        return None

    # === Fusion multi-sources ===

    def merge_all_sources(
        self,
        tmdb_movie: dict[str, Any],
        rt_source: SourceData,
        kaggle_source: SourceData,
        letterboxd_source: SourceData,
        youtube_source: SourceData,
    ) -> dict[str, Any]:
        """Fusionne données de toutes les sources pour un film.

        Args:
            tmdb_movie: Données TMDB (source principale).
            rt_source: Index Rotten Tomatoes.
            kaggle_source: Index Kaggle.
            letterboxd_source: Index Letterboxd.
            youtube_source: Index YouTube.

        Returns:
            Film fusionné avec toutes les sources.
        """
        tmdb_id = tmdb_movie.get("id") or tmdb_movie.get("tmdb_id")
        imdb_id = tmdb_movie.get("imdb_id")

        # Base TMDB
        merged = self._merge_tmdb_base(tmdb_movie)

        # Enrichissement par source
        self._merge_rotten_tomatoes(merged, tmdb_id, imdb_id, rt_source)
        self._merge_kaggle(merged, tmdb_id, imdb_id, kaggle_source)
        self._merge_letterboxd(merged, tmdb_id, imdb_id, letterboxd_source)
        self._merge_youtube(merged, tmdb_id, youtube_source)

        # Calcul score agrégé
        self._calculate_aggregated_score(merged)

        return merged

    def _merge_tmdb_base(self, tmdb_movie: dict[str, Any]) -> dict[str, Any]:
        """Extrait données de base TMDB.

        Args:
            tmdb_movie: Données TMDB brutes.

        Returns:
            Dictionnaire base fusionné.
        """
        return {
            "tmdb_id": tmdb_movie.get("id") or tmdb_movie.get("tmdb_id"),
            "imdb_id": tmdb_movie.get("imdb_id"),
            "title": tmdb_movie.get("title", ""),
            "original_title": tmdb_movie.get("original_title"),
            "year": self._extract_year(tmdb_movie.get("release_date")),
            "release_date": tmdb_movie.get("release_date"),
            "vote_average": tmdb_movie.get("vote_average", 0.0),
            "vote_count": tmdb_movie.get("vote_count", 0),
            "popularity": tmdb_movie.get("popularity", 0.0),
            "overview": tmdb_movie.get("overview"),
            "tagline": tmdb_movie.get("tagline"),
            "runtime": tmdb_movie.get("runtime"),
            "genres": self._extract_genres(tmdb_movie),
            "original_language": tmdb_movie.get("original_language"),
            "poster_path": tmdb_movie.get("poster_path"),
            "backdrop_path": tmdb_movie.get("backdrop_path"),
            "source_tmdb": True,
            "source_rt": False,
            "source_kaggle": False,
            "source_letterboxd": False,
            "source_youtube": False,
        }

    def _merge_rotten_tomatoes(
        self,
        merged: dict[str, Any],
        tmdb_id: int,
        imdb_id: str | None,
        source: SourceData,
    ) -> None:
        """Fusionne données Rotten Tomatoes.

        Args:
            merged: Dictionnaire fusionné (modifié in-place).
            tmdb_id: ID TMDB.
            imdb_id: ID IMDb.
            source: Source RT indexée.
        """
        rt_data = self._find_match(tmdb_id, imdb_id, source)
        if not rt_data or not rt_data.get("tomatometer_score"):
            return

        merged["tomatometer_score"] = rt_data.get("tomatometer_score")
        merged["audience_score"] = rt_data.get("audience_score")
        merged["certified_fresh"] = rt_data.get("certified_fresh", False)
        merged["critics_count"] = rt_data.get("critics_count", 0)
        merged["audience_count"] = rt_data.get("audience_count", 0)
        merged["critics_consensus"] = rt_data.get("critics_consensus")
        merged["rotten_tomatoes_url"] = rt_data.get("rotten_tomatoes_url")
        merged["source_rt"] = True
        self.stats.rt_enriched += 1

    def _merge_kaggle(
        self,
        merged: dict[str, Any],
        tmdb_id: int,
        imdb_id: str | None,
        source: SourceData,
    ) -> None:
        """Fusionne données Kaggle CSV.

        Args:
            merged: Dictionnaire fusionné (modifié in-place).
            tmdb_id: ID TMDB.
            imdb_id: ID IMDb.
            source: Source Kaggle indexée.
        """
        kaggle_data = self._find_match(tmdb_id, imdb_id, source)
        if not kaggle_data:
            return

        merged["kaggle_rating"] = kaggle_data.get("rating") or kaggle_data.get("vote_average")
        merged["kaggle_votes"] = kaggle_data.get("votes") or kaggle_data.get("vote_count")
        merged["source_kaggle"] = True
        self.stats.kaggle_matched += 1

    def _merge_letterboxd(
        self,
        merged: dict[str, Any],
        tmdb_id: int,
        imdb_id: str | None,
        source: SourceData,
    ) -> None:
        """Fusionne données Letterboxd PostgreSQL.

        Args:
            merged: Dictionnaire fusionné (modifié in-place).
            tmdb_id: ID TMDB.
            imdb_id: ID IMDb.
            source: Source Letterboxd indexée.
        """
        lb_data = self._find_match(tmdb_id, imdb_id, source)
        if not lb_data:
            return

        # Score déjà converti en échelle 0-10 par l'extracteur
        merged["letterboxd_score"] = lb_data.get("vote_average")
        merged["letterboxd_votes"] = lb_data.get("vote_count")
        merged["letterboxd_id"] = lb_data.get("letterboxd_id")
        merged["letterboxd_url"] = lb_data.get("letterboxd_url")
        merged["source_letterboxd"] = True
        self.stats.letterboxd_matched += 1

    def _merge_youtube(self, merged: dict[str, Any], tmdb_id: int, source: SourceData) -> None:
        """Fusionne stats YouTube Spark.

        Args:
            merged: Dictionnaire fusionné (modifié in-place).
            tmdb_id: ID TMDB (= film_id dans youtube_stats).
            source: Source YouTube indexée.
        """
        # YouTube indexé par film_id (= tmdb_id après import)
        yt_data = source.index_by_tmdb.get(tmdb_id)
        if not yt_data:
            return

        merged["youtube_video_count"] = yt_data.get("video_count")
        merged["youtube_total_views"] = yt_data.get("total_views")
        merged["youtube_engagement"] = yt_data.get("engagement_score")
        merged["source_youtube"] = True
        self.stats.youtube_matched += 1

    def _calculate_aggregated_score(self, merged: dict[str, Any]) -> None:
        """Calcule score agrégé pondéré multi-sources.

        Pondération :
        - TMDB: 25%
        - Rotten Tomatoes: 30%
        - Kaggle: 15%
        - Letterboxd: 30%

        Args:
            merged: Film fusionné (modifié in-place).
        """
        scores: list[tuple[float, float]] = []

        # TMDB (échelle 0-10)
        if merged.get("vote_average"):
            scores.append((merged["vote_average"], 0.25))

        # RT Tomatometer (échelle 0-100 -> 0-10)
        if merged.get("tomatometer_score"):
            scores.append((merged["tomatometer_score"] / 10, 0.30))

        # Kaggle (échelle 0-10)
        if merged.get("kaggle_rating"):
            scores.append((merged["kaggle_rating"], 0.15))

        # Letterboxd (déjà échelle 0-10)
        if merged.get("letterboxd_score"):
            scores.append((merged["letterboxd_score"], 0.30))

        # Calcul moyenne pondérée
        if scores:
            total_weight = sum(w for _, w in scores)
            weighted_sum = sum(s * w for s, w in scores)
            merged["aggregated_score"] = round(weighted_sum / total_weight, 2)

        # Compteur sources
        merged["source_count"] = sum(
            [
                merged.get("source_tmdb", False),
                merged.get("source_rt", False),
                merged.get("source_kaggle", False),
                merged.get("source_letterboxd", False),
                merged.get("source_youtube", False),
            ]
        )

        if merged["source_count"] > 1:
            self.stats.multi_source_films += 1

    # === Utilitaires ===

    @staticmethod
    def _extract_year(release_date: str | None) -> int:
        """Extrait l'année depuis release_date."""
        if not release_date:
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

        if "vote_average" in normalized:
            normalized["vote_average"] = self._clamp(normalized["vote_average"], 0, 10)

        for field_name in ["title", "overview", "critics_consensus", "tagline"]:
            if field_name in normalized and normalized[field_name]:
                normalized[field_name] = self._clean_text(normalized[field_name])

        return normalized

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """Limite une valeur dans une plage."""
        return max(min_val, min(max_val, float(value)))

    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoie un texte."""
        cleaned = " ".join(text.split())
        return "".join(c for c in cleaned if c.isprintable() or c.isspace())

    # === Validation ===

    def validate_movie(self, movie: dict[str, Any]) -> MovieSchema | None:
        """Valide un film avec Pydantic."""
        try:
            return MovieSchema(**movie)
        except Exception as e:
            self.logger.warning(f"Validation échouée: {movie.get('title')}: {e}")
            self.stats.validation_failed += 1
            return None

    # === Déduplication ===

    def is_duplicate(self, movie: dict[str, Any]) -> bool:
        """Vérifie si un film est un doublon."""
        tmdb_id = movie["tmdb_id"]

        if tmdb_id in self.seen_movies:
            return True

        return self._check_similarity(movie)

    def _check_similarity(self, movie: dict[str, Any]) -> bool:
        """Vérifie doublons par IMDb ID ou similarité titre."""
        imdb_id = movie.get("imdb_id")
        title = movie["title"].lower()
        year = movie["year"]

        for seen in self.seen_movies.values():
            if imdb_id and seen.get("imdb_id") == imdb_id:
                return True

            if abs(year - seen["year"]) <= 1:
                similarity = SequenceMatcher(None, title, seen["title"].lower()).ratio()
                if similarity > 0.9:
                    return True

        return False

    # === Point d'entrée principal ===

    def extract(
        self,
        tmdb_movies: list[dict[str, Any]],
        rt_data: list[dict[str, Any]] | None = None,
        kaggle_data: list[dict[str, Any]] | None = None,
        letterboxd_data: list[dict[str, Any]] | None = None,
        youtube_data: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Agrège les données de 5 sources hétérogènes.

        Args:
            tmdb_movies: Films depuis TMDB (source principale).
            rt_data: Films enrichis Rotten Tomatoes.
            kaggle_data: Films depuis CSV Kaggle.
            letterboxd_data: Films depuis PostgreSQL Letterboxd.
            youtube_data: Stats depuis Spark YouTube.

        Returns:
            Liste de films agrégés, validés, dédupliqués.
        """
        self._start_extraction()
        self._reset_stats()

        self.stats.tmdb_count = len(tmdb_movies)
        self.logger.info(f"🎬 Agrégation de {self.stats.tmdb_count} films TMDB")

        # Construire index par source
        rt_source = self._build_source_index(rt_data or [], "RottenTomatoes")
        kaggle_source = self._build_source_index(kaggle_data or [], "Kaggle")
        letterboxd_source = self._build_source_index(letterboxd_data or [], "Letterboxd")
        youtube_source = self._build_source_index(youtube_data or [], "YouTube")

        aggregated: list[dict[str, Any]] = []

        for tmdb_movie in tmdb_movies:
            if not tmdb_movie.get("id") and not tmdb_movie.get("tmdb_id"):
                continue

            # Fusion multi-sources
            merged = self.merge_all_sources(
                tmdb_movie, rt_source, kaggle_source, letterboxd_source, youtube_source
            )

            # Normalisation
            normalized = self.normalize_movie(merged)

            # Validation
            validated = self.validate_movie(normalized)
            if not validated:
                continue

            # Déduplication
            validated_dict = validated.model_dump()
            if self.is_duplicate(validated_dict):
                self.stats.duplicates_removed += 1
                continue

            self.seen_movies[validated_dict["tmdb_id"]] = validated_dict
            aggregated.append(validated_dict)

        self.stats.final_count = len(aggregated)
        self.metrics.total_records = self.stats.final_count

        self._end_extraction()
        self._log_aggregation_stats()

        return aggregated

    def _reset_stats(self) -> None:
        """Réinitialise les statistiques."""
        self.stats = AggregationStats()
        self.seen_movies.clear()

    def _log_aggregation_stats(self) -> None:
        """Affiche les statistiques d'agrégation."""
        self.logger.info("=" * 80)
        self.logger.info("📊 STATISTIQUES AGRÉGATION 5 SOURCES")
        self.logger.info("-" * 80)
        self.logger.info(f"Films TMDB (base)     : {self.stats.tmdb_count:,}")
        self.logger.info(f"+ Rotten Tomatoes     : {self.stats.rt_enriched:,}")
        self.logger.info(f"+ Kaggle CSV          : {self.stats.kaggle_matched:,}")
        self.logger.info(f"+ Letterboxd DB       : {self.stats.letterboxd_matched:,}")
        self.logger.info(f"+ YouTube Spark       : {self.stats.youtube_matched:,}")
        self.logger.info("-" * 80)
        self.logger.info(f"Films multi-sources   : {self.stats.multi_source_films:,}")
        self.logger.info(f"Doublons supprimés    : {self.stats.duplicates_removed:,}")
        self.logger.info(f"Validation échouée    : {self.stats.validation_failed:,}")
        self.logger.info(f"Films finaux          : {self.stats.final_count:,}")
        self.logger.info("=" * 80)

        # Taux enrichissement
        rates = self.stats.enrichment_rates
        if rates:
            self.logger.info("📈 TAUX D'ENRICHISSEMENT")
            for source, rate in rates.items():
                self.logger.info(f"  {source:20s}: {rate:.1f}%")

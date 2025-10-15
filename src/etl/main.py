"""
Orchestrateur principal du pipeline ETL HorrorBot.
Lance l'extraction depuis les 5 sources requises pour le bloc E1.
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from src.etl.extractors.tmdb_extractor import TMDBExtractor
from src.etl.extractors.wikipedia_scraper import WikipediaExtractor
from src.etl.settings import settings
from src.etl.utils import CheckpointManager, ETLStats, setup_logger

# Constantes
LINE_WIDTH = 80


class Extractor(Protocol):
    """Protocol définissant l'interface d'un extracteur."""

    def extract(self, **_kwargs: object) -> list[dict[str, object]]:
        """
        Extrait les données de la source.

        Args:
            **_kwargs: Arguments supplémentaires spécifiques à l'extracteur.
                Les implémentations peuvent définir leurs propres paramètres.

        Returns:
            Liste de dictionnaires contenant les données extraites.
        """
        ...


@dataclass
class ExtractionConfig:
    """Configuration pour l'extraction d'une source."""

    name: str
    enabled: bool
    icon: str
    extractor_class: type[Extractor] | None = None
    extract_kwargs: dict[str, object] | None = None

    def __post_init__(self) -> None:
        """Initialise les kwargs par défaut si None."""
        if self.extract_kwargs is None:
            self.extract_kwargs = {}


@dataclass
class ExtractionResult:
    """Résultat d'une extraction."""

    source_name: str
    movies: list[dict[str, object]]
    duration: float
    success: bool
    error_message: str | None = None


class ETLOrchestrator:
    """Orchestrateur du pipeline ETL."""

    def __init__(self) -> None:
        """Initialise l'orchestrateur avec logger, stats et checkpoint manager."""
        self.logger = setup_logger("etl.main")
        self.stats = ETLStats()
        self.checkpoint_manager = CheckpointManager()
        self.all_movies: list[dict[str, object]] = []
        self.extraction_errors: list[tuple[str, str]] = []

    def _log_header(self) -> None:
        """Affiche l'en-tête du pipeline."""
        self.logger.info("=" * LINE_WIDTH)
        self.logger.info("🎬 DÉMARRAGE PIPELINE ETL HORRORBOT")
        self.logger.info("=" * LINE_WIDTH)
        self.logger.info(f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Environnement : {settings.environment}")
        self.logger.info(f"Working directory : {Path.cwd().absolute()}")
        self.logger.info("")

    def _log_enabled_sources(self, sources: list[ExtractionConfig]) -> None:
        """
        Affiche les sources activées.

        Args:
            sources: Liste des configurations d'extraction
        """
        enabled_names = [s.name for s in sources if s.enabled]
        self.logger.info(f"📊 Sources activées : {', '.join(enabled_names)}")
        self.logger.info("")

    def _extract_from_source(
        self, extraction_config: ExtractionConfig
    ) -> ExtractionResult:
        """
        Extrait les données d'une source donnée.

        Args:
            extraction_config: Configuration de l'extraction

        Returns:
            Résultat de l'extraction
        """
        self.logger.info("-" * LINE_WIDTH)
        self.logger.info(f"{extraction_config.icon} SOURCE : {extraction_config.name}")
        self.logger.info("-" * LINE_WIDTH)

        # Vérifier si l'extracteur est implémenté
        if extraction_config.extractor_class is None:
            self.logger.warning(f"⚠️ {extraction_config.name} pas encore implémenté")
            return ExtractionResult(
                source_name=extraction_config.name,
                movies=[],
                duration=0.0,
                success=True,
                error_message="Non implémenté",
            )

        try:
            start_time = datetime.now()
            extractor = extraction_config.extractor_class()
            movies = extractor.extract(**extraction_config.extract_kwargs)
            duration = (datetime.now() - start_time).total_seconds()

            self.logger.info(
                f"✅ {extraction_config.name} : {len(movies):,} films extraits"
            )
            self.logger.info("")

            return ExtractionResult(
                source_name=extraction_config.name,
                movies=movies,
                duration=duration,
                success=True,
            )

        except Exception as e:
            self.logger.error(f"❌ Erreur extraction {extraction_config.name} : {e}")
            self.logger.info("")

            return ExtractionResult(
                source_name=extraction_config.name,
                movies=[],
                duration=0.0,
                success=False,
                error_message=str(e),
            )

    def _process_results(self, results: list[ExtractionResult]) -> None:
        """
        Traite les résultats des extractions.

        Args:
            results: Liste des résultats d'extraction
        """
        for result in results:
            if result.success and result.movies:
                self.all_movies.extend(result.movies)
                self.stats.add_source_stats(
                    result.source_name, len(result.movies), result.duration
                )
            elif not result.success and result.error_message:
                self.extraction_errors.append(
                    (result.source_name, result.error_message)
                )

    def _save_results(self) -> None:
        """Sauvegarde les résultats de l'extraction."""
        self.logger.info("=" * LINE_WIDTH)
        self.logger.info("💾 SAUVEGARDE DES RÉSULTATS")
        self.logger.info("=" * LINE_WIDTH)

        if self.all_movies:
            self.checkpoint_manager.save("etl_all_movies", self.all_movies)
            self.logger.info(
                f"✅ {len(self.all_movies):,} films sauvegardés dans "
                "etl_all_movies.json"
            )
        else:
            self.logger.warning("⚠️ Aucun film extrait !")

        stats_file = settings.paths.processed_dir / "etl_stats.json"
        self.stats.save_to_json(stats_file)
        self.logger.info(f"✅ Statistiques sauvegardées : {stats_file}")
        self.logger.info("")

    def _print_final_summary(self) -> int:
        """
        Affiche le résumé final et retourne le code de sortie.

        Returns:
            Code de sortie (0 = succès, 1 = erreur)
        """
        self.stats.print_summary()

        if self.extraction_errors:
            self.logger.warning("=" * LINE_WIDTH)
            self.logger.warning("⚠️ ERREURS RENCONTRÉES")
            self.logger.warning("=" * LINE_WIDTH)
            for source, error in self.extraction_errors:
                self.logger.warning(f"- {source} : {error}")
            self.logger.warning("")

        if self.extraction_errors and not self.all_movies:
            self.logger.error("❌ ÉCHEC : Aucune source n'a fonctionné")
            return 1
        if self.extraction_errors:
            self.logger.warning("⚠️ SUCCÈS PARTIEL : Certaines sources ont échoué")
            return 0

        self.logger.info("✅ SUCCÈS COMPLET : Toutes les sources ont fonctionné")
        return 0

    def run(self, sources: list[ExtractionConfig]) -> int:
        """
        Exécute le pipeline ETL complet.

        Args:
            sources: Liste des configurations d'extraction

        Returns:
            Code de sortie (0 = succès, 1 = erreur)
        """
        self._log_header()
        self._log_enabled_sources(sources)

        # Extraire depuis toutes les sources activées
        enabled_sources = [s for s in sources if s.enabled]
        results = [self._extract_from_source(source) for source in enabled_sources]

        # Traiter les résultats
        self._process_results(results)

        # Sauvegarder
        self._save_results()

        # Afficher le résumé et retourner le code de sortie
        return self._print_final_summary()


def create_extraction_configs(
    max_pages_tmdb: int | None = None,
    start_year_wikipedia: int | None = None,
    end_year_wikipedia: int | None = None,
    max_films_wikipedia: int | None = None,
    enable_tmdb: bool = True,
    enable_wikipedia: bool = False,
    enable_csv: bool = False,
    enable_postgres: bool = False,
    enable_spark: bool = False,
) -> list[ExtractionConfig]:
    """
    Crée la configuration des sources d'extraction.

    Args:
        max_pages_tmdb: Nombre max de pages TMDB (None = toutes)
        start_year_wikipedia: Année de début Wikipedia (None = config par défaut)
        end_year_wikipedia: Année de fin Wikipedia (None = config par défaut)
        max_films_wikipedia: Nombre max films Wikipedia (None = config par défaut)
        enable_tmdb: Activer extraction TMDB
        enable_wikipedia: Activer scraping Wikipedia
        enable_csv: Activer lecture CSV
        enable_postgres: Activer extraction PostgreSQL
        enable_spark: Activer extraction Spark

    Returns:
        Liste des configurations d'extraction
    """
    return [
        ExtractionConfig(
            name="TMDB",
            enabled=enable_tmdb,
            icon="🔡",
            extractor_class=TMDBExtractor,
            extract_kwargs={
                "max_pages": max_pages_tmdb or settings.tmdb_default_max_pages,
                "enrich": settings.tmdb_enrich_movies,
                "save_checkpoint": settings.tmdb_save_checkpoints,
            },
        ),
        ExtractionConfig(
            name="Wikipedia",
            enabled=enable_wikipedia,
            icon="🌐",
            extractor_class=WikipediaExtractor,
            extract_kwargs={
                "start_year": start_year_wikipedia or settings.wikipedia_start_year,
                "end_year": end_year_wikipedia or settings.wikipedia_end_year,
                "max_films": max_films_wikipedia or settings.wikipedia_max_films,
                "save_checkpoint": settings.wikipedia_save_checkpoints,
            },
        ),
        ExtractionConfig(
            name="CSV",
            enabled=enable_csv,
            icon="📄",
            # À implémenter
            extractor_class=None,
            extract_kwargs={},
        ),
        ExtractionConfig(
            name="PostgreSQL",
            enabled=enable_postgres,
            icon="🗄️",
            # À implémenter
            extractor_class=None,
            extract_kwargs={},
        ),
        ExtractionConfig(
            name="Spark",
            enabled=enable_spark,
            icon="⚡",
            # À implémenter
            extractor_class=None,
            extract_kwargs={},
        ),
    ]


def main(
    max_pages_tmdb: int | None = None,
    start_year_wikipedia: int | None = None,
    end_year_wikipedia: int | None = None,
    max_films_wikipedia: int | None = None,
    enable_tmdb: bool = True,
    enable_wikipedia: bool = False,
    enable_csv: bool = False,
    enable_postgres: bool = False,
    enable_spark: bool = False,
) -> int:
    """
    Point d'entrée principal du pipeline ETL.

    Args:
        max_pages_tmdb: Nombre max de pages TMDB (None = toutes)
        start_year_wikipedia: Année de début Wikipedia (None = config par défaut)
        end_year_wikipedia: Année de fin Wikipedia (None = config par défaut)
        max_films_wikipedia: Nombre max films Wikipedia (None = config par défaut)
        enable_tmdb: Activer extraction TMDB
        enable_wikipedia: Activer scraping Wikipedia
        enable_csv: Activer lecture CSV
        enable_postgres: Activer extraction PostgreSQL
        enable_spark: Activer extraction Spark

    Returns:
        Code de sortie (0 = succès, 1 = erreur)
    """
    sources = create_extraction_configs(
        max_pages_tmdb=max_pages_tmdb,
        start_year_wikipedia=start_year_wikipedia,
        end_year_wikipedia=end_year_wikipedia,
        max_films_wikipedia=max_films_wikipedia,
        enable_tmdb=enable_tmdb,
        enable_wikipedia=enable_wikipedia,
        enable_csv=enable_csv,
        enable_postgres=enable_postgres,
        enable_spark=enable_spark,
    )

    orchestrator = ETLOrchestrator()
    return orchestrator.run(sources)


if __name__ == "__main__":
    """
    Test de l'orchestrateur ETL.
    Usage: python -m src.etl.main
    """
    print("\n🧪 TEST ORCHESTRATEUR ETL")
    print("=" * LINE_WIDTH)

    exit_code = main(
        max_pages_tmdb=5,
        enable_tmdb=True,
        start_year_wikipedia=2023,
        end_year_wikipedia=2024,
        max_films_wikipedia=30,
        enable_wikipedia=True,
        enable_csv=False,
        enable_postgres=False,
        enable_spark=False,
    )

    print("=" * LINE_WIDTH)
    if exit_code == 0:
        print("✅ Test réussi !")
    else:
        print("❌ Test échoué !")

    sys.exit(exit_code)

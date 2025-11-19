"""Point d'entrée principal du pipeline ETL HorrorBot."""

import asyncio
import sys
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from src.etl.aggregator import DataAggregator
from src.etl.extractors.rotten_tomatoes_enricher import RottenTomatoesEnricher
from src.etl.extractors.tmdb_extractor import TMDBExtractor
from src.etl.settings import settings
from src.etl.utils import CheckpointManager, setup_logger

# === Configuration ===

logger = setup_logger("etl.main")
checkpoint_manager = CheckpointManager()


# === Étapes du pipeline ===


def step_1_extract_tmdb(max_pages: int | None = None) -> list[dict[str, Any]]:
    """
    Étape 1 : Extraction des films depuis TMDB.

    Args:
        max_pages: Nombre maximum de pages (None = défaut config)

    Returns:
        Liste de films TMDB bruts
    """
    logger.info("=" * 80)
    logger.info("🎬 ÉTAPE 1/3 : EXTRACTION TMDB")
    logger.info("=" * 80)

    try:
        extractor = TMDBExtractor()
        movies = extractor.extract(
            max_pages=max_pages,
            # Pas d'enrichissement TMDB (trop lent)
            enrich=False,
            save_checkpoint=True,
        )

        logger.info(f"✅ Étape 1 terminée : {len(movies)} films extraits")
        return movies

    except Exception as e:
        logger.error(f"❌ Échec étape 1 (TMDB) : {e}", exc_info=True)
        raise


async def step_2_enrich_rt(tmdb_movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Étape 2 : Enrichissement avec Rotten Tomatoes.

    Args:
        tmdb_movies: Films depuis TMDB

    Returns:
        Liste de films enrichis RT
    """
    logger.info("=" * 80)
    logger.info("🍅 ÉTAPE 2/3 : ENRICHISSEMENT ROTTEN TOMATOES")
    logger.info("=" * 80)

    try:
        enricher = RottenTomatoesEnricher()
        enriched = await enricher.enrich_films_async(
            tmdb_movies,
            # Éviter rate limiting RT
            max_concurrent=3,
        )

        enriched_count = sum(1 for film in enriched if "tomatometer_score" in film)
        logger.info(
            f"✅ Étape 2 terminée : {enriched_count}/{len(tmdb_movies)} films enrichis"
        )

        return enriched

    except Exception as e:
        logger.error(f"❌ Échec étape 2 (RT) : {e}", exc_info=True)
        raise


def step_3_aggregate(
    tmdb_movies: list[dict[str, Any]], rt_enriched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Étape 3 : Agrégation et nettoyage.

    Args:
        tmdb_movies: Films TMDB bruts
        rt_enriched: Films enrichis RT

    Returns:
        Liste de films agrégés, validés, dédupliqués
    """
    logger.info("=" * 80)
    logger.info("🔄 ÉTAPE 3/3 : AGRÉGATION ET NETTOYAGE")
    logger.info("=" * 80)

    try:
        aggregator = DataAggregator()
        aggregated = aggregator.extract(
            tmdb_movies=tmdb_movies, rt_enriched=rt_enriched
        )

        logger.info(f"✅ Étape 3 terminée : {len(aggregated)} films finaux")
        return aggregated

    except Exception as e:
        logger.error(f"❌ Échec étape 3 (Agrégation) : {e}", exc_info=True)
        raise


# === Orchestration ===


async def run_full_pipeline(max_pages: int | None = None) -> list[dict[str, Any]]:
    """
    Exécute le pipeline ETL complet.

    Pipeline :
    1. Extraction TMDB (API REST)
    2. Enrichissement Rotten Tomatoes (Web scraping)
    3. Agrégation et nettoyage

    Args:
        max_pages: Nombre de pages TMDB à extraire (None = défaut)

    Returns:
        Dataset final agrégé
    """
    start_time = datetime.now()

    logger.info("🚀 DÉMARRAGE PIPELINE ETL HORRORBOT")
    logger.info(f"Timestamp : {start_time.isoformat()}")
    logger.info(f"Max pages : {max_pages or settings.tmdb.default_max_pages}")

    try:
        # Étape 1 : TMDB
        tmdb_movies = step_1_extract_tmdb(max_pages)

        # Checkpoint étape 1
        checkpoint_manager.save("pipeline_step1_tmdb", tmdb_movies)

        # Étape 2 : Rotten Tomatoes
        rt_enriched = await step_2_enrich_rt(tmdb_movies)

        # Checkpoint étape 2
        checkpoint_manager.save("pipeline_step2_rt", rt_enriched)

        # Étape 3 : Agrégation
        final_dataset = step_3_aggregate(tmdb_movies, rt_enriched)

        # Checkpoint final
        final_checkpoint_name = (
            f"pipeline_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        checkpoint_path = checkpoint_manager.save(final_checkpoint_name, final_dataset)

        # Statistiques finales
        duration = (datetime.now() - start_time).total_seconds()
        _log_pipeline_stats(final_dataset, duration, checkpoint_path)

        return final_dataset

    except Exception as e:
        logger.error(f"❌ ÉCHEC PIPELINE : {e}", exc_info=True)
        raise


def _log_pipeline_stats(
    dataset: list[dict[str, Any]], duration: float, checkpoint_path: Path
) -> None:
    """Affiche les statistiques finales du pipeline."""
    logger.info("=" * 80)
    logger.info("📊 STATISTIQUES PIPELINE COMPLET")
    logger.info("=" * 80)
    logger.info(f"Films finaux         : {len(dataset):,}")
    logger.info(f"Durée totale         : {duration:.2f}s ({duration / 60:.1f} min)")
    logger.info(f"Débit                : {len(dataset) / duration:.2f} films/s")
    logger.info(f"Checkpoint           : {checkpoint_path.name}")
    logger.info(
        f"Taille fichier       : {checkpoint_path.stat().st_size / 1024:.1f} KB"
    )

    # Statistiques enrichissement RT
    rt_enriched_count = sum(1 for film in dataset if film.get("tomatometer_score"))
    if rt_enriched_count > 0:
        enrichment_rate = (rt_enriched_count / len(dataset)) * 100
        logger.info(f"Taux enrichissement  : {enrichment_rate:.1f}%")

    logger.info("=" * 80)


# === Fonctions de reprise ===


async def resume_from_step(
    step: int, max_pages: int | None = None
) -> list[dict[str, Any]]:
    """
    Reprend le pipeline depuis une étape spécifique.

    Args:
        step: Numéro de l'étape (1, 2 ou 3)
        max_pages: Pages TMDB si step=1

    Returns:
        Dataset final
    """
    logger.info(f"🔄 Reprise pipeline depuis étape {step}")

    if step == 1:
        return await run_full_pipeline(max_pages)

    if step == 2:
        # Charger checkpoint TMDB
        tmdb_movies = checkpoint_manager.load("pipeline_step1_tmdb")
        if not tmdb_movies:
            raise ValueError("Checkpoint TMDB introuvable. Relancer depuis étape 1.")

        rt_enriched = await step_2_enrich_rt(tmdb_movies)
        checkpoint_manager.save("pipeline_step2_rt", rt_enriched)

        final_dataset = step_3_aggregate(tmdb_movies, rt_enriched)
        checkpoint_manager.save(
            f"pipeline_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}", final_dataset
        )
        return final_dataset

    if step == 3:
        # Charger checkpoints
        tmdb_movies = checkpoint_manager.load("pipeline_step1_tmdb")
        rt_enriched = checkpoint_manager.load("pipeline_step2_rt")

        if not tmdb_movies or not rt_enriched:
            raise ValueError("Checkpoints manquants. Relancer depuis étape 1 ou 2.")

        final_dataset = step_3_aggregate(tmdb_movies, rt_enriched)
        checkpoint_manager.save(
            f"pipeline_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}", final_dataset
        )
        return final_dataset

    raise ValueError(f"Étape invalide : {step}. Attendu : 1, 2 ou 3")


# === CLI ===


def main() -> None:
    """Point d'entrée CLI du pipeline ETL."""

    try:
        parser = argparse.ArgumentParser(
            description="Pipeline ETL HorrorBot - Extraction et enrichissement films d'horreur"
        )

        parser.add_argument(
            "--max-pages",
            type=int,
            default=None,
            help=f"Nombre de pages TMDB (défaut: {settings.tmdb.default_max_pages})",
        )

        parser.add_argument(
            "--resume-from",
            type=int,
            choices=[1, 2, 3],
            default=None,
            help="Reprendre depuis l'étape N (1=TMDB, 2=RT, 3=Agrégation)",
        )

        parser.add_argument(
            "--list-checkpoints",
            action="store_true",
            help="Liste les checkpoints disponibles",
        )

        args = parser.parse_args()

        # Liste checkpoints
        if args.list_checkpoints:
            checkpoints = checkpoint_manager.list_checkpoints()
            print("\n📂 Checkpoints disponibles :")
            for cp in checkpoints:
                print(f"  - {cp}")
            print(f"\nTotal : {len(checkpoints)} checkpoints")
            return

        # Exécution pipeline
        if args.resume_from:
            dataset = asyncio.run(resume_from_step(args.resume_from, args.max_pages))
        else:
            dataset = asyncio.run(run_full_pipeline(args.max_pages))

        logger.info(f"✅ Pipeline terminé avec succès : {len(dataset)} films")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("⚠️ Pipeline interrompu par l'utilisateur")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ ERREUR FATALE : {e}", file=sys.stderr)
        traceback.print_exc()
        logger.error(f"❌ Échec pipeline : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

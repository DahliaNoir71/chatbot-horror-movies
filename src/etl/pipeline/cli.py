"""Command Line Interface for ETL pipeline.

Provides CLI entry point with argument parsing and command handling
for pipeline execution, resume, and single source extraction.
"""

import argparse
import asyncio
import sys
import traceback

from src.etl.pipeline.helpers import checkpoint_manager
from src.etl.pipeline.orchestrator import (
    extract_single_source,
    resume_from_step,
    run_full_pipeline,
)
from src.etl.types import ExtractionParams
from src.etl.utils import setup_logger
from src.settings import settings

logger = setup_logger("etl.pipeline.cli")


# =============================================================================
# ARGUMENT PARSING
# =============================================================================


def _parse_cli_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Pipeline ETL HorrorBot - 7 sources hétérogènes (E1)"
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help=f"Pages TMDB (défaut: {settings.tmdb.default_max_pages})",
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=None,
        help="Vidéos YouTube par chaîne",
    )

    parser.add_argument(
        "--resume-from",
        type=int,
        choices=[1, 2, 3, 4, 5, 6, 7],
        default=None,
        help="Reprendre depuis l'étape N",
    )

    parser.add_argument(
        "--skip",
        nargs="+",
        choices=["spotify", "youtube", "kaggle", "postgres"],
        default=[],
        help="Sources à ignorer",
    )

    parser.add_argument(
        "--source",
        type=str,
        choices=["tmdb", "spotify", "youtube", "kaggle", "postgres"],
        default=None,
        help="Extraire une seule source",
    )

    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="Lister les checkpoints disponibles",
    )

    return parser.parse_args()


# =============================================================================
# COMMAND HANDLERS
# =============================================================================


def _handle_list_checkpoints() -> None:
    """Handle --list-checkpoints command."""
    checkpoints = checkpoint_manager.list_checkpoints()
    print("\n📂 Checkpoints disponibles :")
    for cp in checkpoints:
        print(f"  - {cp}")
    print(f"\nTotal : {len(checkpoints)} checkpoints")


def _handle_single_source(args: argparse.Namespace) -> None:
    """Handle --source command for single source extraction.

    Args:
        args: Parsed arguments with source and params.
    """
    params = ExtractionParams(
        max_pages=args.max_pages,
        max_videos=args.max_videos,
    )
    data = extract_single_source(args.source, params)
    logger.info(f"✅ {args.source}: {len(data)} éléments extraits")


def _handle_pipeline_execution(args: argparse.Namespace) -> None:
    """Handle full pipeline or resume execution.

    Args:
        args: Parsed arguments.
    """
    if args.resume_from:
        result = asyncio.run(resume_from_step(args.resume_from, args.max_pages))
    else:
        result = asyncio.run(
            run_full_pipeline(
                max_pages=args.max_pages,
                max_videos=args.max_videos,
                skip_sources=args.skip,
            )
        )

    logger.info(f"✅ Pipeline terminé : {len(result.films)} films")
    sys.exit(0)


def _handle_fatal_error(error: Exception) -> None:
    """Handle fatal pipeline error.

    Args:
        error: Exception that caused the failure.
    """
    print(f"\n❌ ERREUR FATALE : {error}", file=sys.stderr)
    traceback.print_exc()
    logger.error(f"❌ Échec pipeline : {error}")
    sys.exit(1)


# =============================================================================
# COMMAND DISPATCH
# =============================================================================


def _execute_cli_command(args: argparse.Namespace) -> None:
    """Execute CLI command based on arguments.

    Args:
        args: Parsed command line arguments.
    """
    if args.list_checkpoints:
        _handle_list_checkpoints()
        return

    if args.source:
        _handle_single_source(args)
        return

    _handle_pipeline_execution(args)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main() -> None:
    """CLI entry point for ETL pipeline."""
    try:
        args = _parse_cli_arguments()
        _execute_cli_command(args)
    except KeyboardInterrupt:
        logger.warning("⚠️ Pipeline interrompu par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        _handle_fatal_error(e)


if __name__ == "__main__":
    main()

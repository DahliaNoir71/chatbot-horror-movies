#!/usr/bin/env python3
"""Script de purge checkpoints obsolètes (RGPD P2)."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.etl.utils import setup_logger

logger = setup_logger("scripts.clean_checkpoints")


def find_checkpoints(checkpoint_dir: Path) -> list[Path]:
    """Liste tous les checkpoints JSON triés par date (plus récent d'abord)."""
    checkpoints = list(checkpoint_dir.glob("*.json"))
    checkpoints.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return checkpoints


def filter_by_age(checkpoints: list[Path], days: int) -> list[Path]:
    """Filtre checkpoints plus vieux que N jours."""
    cutoff = datetime.now() - timedelta(days=days)
    return [cp for cp in checkpoints if cp.stat().st_mtime < cutoff.timestamp()]


def filter_keep_last(checkpoints: list[Path], keep: int) -> list[Path]:
    """Garde les N derniers checkpoints, supprime le reste."""
    if len(checkpoints) <= keep:
        return []
    return checkpoints[keep:]


def delete_checkpoints(checkpoints: list[Path], dry_run: bool) -> tuple[int, int]:
    """Supprime les checkpoints (avec option dry-run)."""
    total_size = sum(cp.stat().st_size for cp in checkpoints)

    if dry_run:
        logger.info(
            f"dry_run: {len(checkpoints)} checkpoints à supprimer ({total_size / 1024 / 1024:.1f} MB)"
        )
        for cp in checkpoints:
            logger.info(f"  - {cp.name}")
        return len(checkpoints), total_size

    deleted = 0
    for cp in checkpoints:
        try:
            cp.unlink()
            deleted += 1
            logger.info(f"deleted: {cp.name}")
        except Exception as e:
            logger.error(f"delete_failed: {cp.name} - {e}")

    return deleted, total_size


def _validate_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Validate command line arguments.

    Raises:
        SystemExit: If arguments are invalid
    """
    if not args.keep_last and not args.older_than:
        parser.error("Spécifier --keep-last ou --older-than")
    if not args.checkpoint_dir.exists():
        logger.error(f"checkpoint_dir_not_found: {args.checkpoint_dir}")
        raise SystemExit(1)


def _process_checkpoints(args: argparse.Namespace) -> None:
    """Process checkpoints based on command line arguments."""
    logger.info(
        f"clean_checkpoints_started: keep_last={args.keep_last}, "
        f"older_than={args.older_than}, dry_run={args.dry_run}"
    )

    all_checkpoints = find_checkpoints(args.checkpoint_dir)
    if not all_checkpoints:
        logger.info("no_checkpoints_found")
        return

    to_delete = _get_checkpoints_to_delete(args, all_checkpoints)
    if not to_delete:
        logger.info("no_checkpoints_to_delete")
        return

    deleted, total_size = delete_checkpoints(to_delete, args.dry_run)
    logger.info(
        f"clean_checkpoints_completed: deleted={deleted}, "
        f"kept={len(all_checkpoints) - deleted}, size_mb={total_size / 1024 / 1024:.1f}"
    )


def _get_checkpoints_to_delete(args: argparse.Namespace, all_checkpoints: list[Path]) -> list[Path]:
    """Determine which checkpoints should be deleted based on criteria."""
    to_delete: list[Path] = []

    if args.keep_last:
        to_delete.extend(filter_keep_last(all_checkpoints, args.keep_last))

    if args.older_than:
        old_checkpoints = filter_by_age(all_checkpoints, args.older_than)
        to_delete.extend(cp for cp in old_checkpoints if cp not in to_delete)

    return list(set(to_delete))


def main() -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Purge checkpoints obsolètes (RGPD P2)")
    parser.add_argument("--keep-last", type=int, help="Garder N derniers checkpoints")
    parser.add_argument("--older-than", type=int, help="Supprimer checkpoints >N jours")
    parser.add_argument("--dry-run", action="store_true", help="Aperçu sans suppression")
    parser.add_argument(
        "--checkpoint-dir", type=Path, default=Path("data/checkpoints"), help="Répertoire"
    )

    args = parser.parse_args()

    # Validate arguments (will raise SystemExit on error)
    _validate_arguments(parser, args)

    # Process checkpoints if validation passes
    _process_checkpoints(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

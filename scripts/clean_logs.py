#!/usr/bin/env python3
"""Script de nettoyage automatique des logs anciens (RGPD P1)."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.etl.utils import setup_logger
from src.settings import settings

logger = setup_logger("scripts.clean_logs")


def find_old_logs(logs_dir: Path, days: int) -> list[Path]:
    """Trouve les logs plus vieux que N jours."""
    cutoff = datetime.now() - timedelta(days=days)
    old_logs: list[Path] = []

    for log_file in logs_dir.glob("*.log"):
        if log_file.stat().st_mtime < cutoff.timestamp():
            old_logs.append(log_file)

    return old_logs


def archive_critical_logs(log_file: Path, archive_dir: Path) -> None:
    """Archive les logs contenant des erreurs critiques."""
    try:
        with log_file.open("r", encoding="utf-8") as f:
            content = f.read()

        if "ERROR" in content or "CRITICAL" in content:
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / f"{log_file.stem}_archived.log"
            archive_path.write_text(content, encoding="utf-8")
            logger.info(f"archived_critical_log: {log_file.name} -> {archive_path.name}")
    except Exception as e:
        logger.error(f"archive_failed: {log_file.name} - {e}")


def delete_logs(logs: list[Path], dry_run: bool) -> tuple[int, int]:
    """Supprime les logs (avec option dry-run)."""
    total_size = sum(log.stat().st_size for log in logs)

    if dry_run:
        logger.info(f"dry_run: {len(logs)} logs à supprimer ({total_size / 1024 / 1024:.1f} MB)")
        return len(logs), total_size

    deleted = 0
    for log_file in logs:
        try:
            log_file.unlink()
            deleted += 1
            logger.info(f"deleted: {log_file.name}")
        except Exception as e:
            logger.error(f"delete_failed: {log_file.name} - {e}")

    return deleted, total_size


def main() -> int:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Nettoyage logs anciens (RGPD P1)")
    parser.add_argument("--days", type=int, default=30, help="Âge minimum logs (défaut: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Aperçu sans suppression")
    parser.add_argument("--logs-dir", type=Path, default=settings.paths.logs_dir, help="Répertoire logs")
    parser.add_argument("--archive", action="store_true", help="Archiver logs critiques")

    args = parser.parse_args()

    # Ensure logs directory exists
    try:
        args.logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"failed_to_create_logs_dir: {args.logs_dir} - {e}")
        return 1

    logger.info(f"clean_logs_started: days={args.days}, dry_run={args.dry_run}")

    # Trouver logs anciens
    old_logs = find_old_logs(args.logs_dir, args.days)

    if not old_logs:
        logger.info("no_old_logs_found")
        return 0

    # Archiver logs critiques
    if args.archive:
        archive_dir = args.logs_dir / "archives"
        for log_file in old_logs:
            archive_critical_logs(log_file, archive_dir)

    # Suppression
    deleted, total_size = delete_logs(old_logs, args.dry_run)

    logger.info(
        f"clean_logs_completed: deleted={deleted}, size_mb={total_size / 1024 / 1024:.1f}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

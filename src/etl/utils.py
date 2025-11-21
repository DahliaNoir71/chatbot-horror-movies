"""Utilitaires communs pour le pipeline ETL."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.settings import settings

# === Configuration Logging Centralisée avec Structlog ===

_LOGGING_CONFIGURED = False


def setup_logging() -> None:
    """Configure structlog de manière centralisée (appelé une seule fois)."""
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    # Créer le répertoire de logs
    log_dir = settings.paths.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    # Fichier de log unique avec timestamp
    log_file = log_dir / f"horrorbot_{datetime.now().strftime('%Y%m%d')}.log"

    # Configuration structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(
            file=open(log_file, "a", encoding="utf-8")
        ),
        cache_logger_on_first_use=True,
    )

    _LOGGING_CONFIGURED = True

    # Log de démarrage
    logger = structlog.get_logger()
    logger.info("logging_configured", log_file=str(log_file))


def setup_logger(name: str) -> logging.Logger:
    """Configure un logger avec sortie console (lisible) et fichier (JSON)."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Format console lisible
    console_formatter = logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
    )

    # Format fichier JSON
    file_formatter = logging.Formatter(
        '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", '
        '"message": "%(message)s"}',
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # ✅ CENTRALISATION : Tous les logs dans logs/{name}.log
    log_file = settings.paths.logs_dir / f"{name}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# === Gestion Checkpoints ===


class CheckpointManager:
    """Gère la sauvegarde et le chargement de checkpoints."""

    def __init__(self, checkpoint_dir: Path | None = None) -> None:
        """
        Initialise le gestionnaire de checkpoints.

        Args:
            checkpoint_dir: Répertoire des checkpoints (défaut: settings)
        """
        self.checkpoint_dir = checkpoint_dir or settings.paths.checkpoints_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.logger = setup_logger("etl.checkpoints")

    def save(self, name: str, data: dict[str, Any] | list[dict[str, Any]]) -> Path:
        """
        Sauvegarde un checkpoint.

        Args:
            name: Nom du checkpoint (sans extension)
            data: Données à sauvegarder (dict ou list de films)

        Returns:
            Chemin du fichier créé
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        try:
            with checkpoint_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {"timestamp": datetime.now().isoformat(), "data": data},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            self.logger.info(
                f"checkpoint_saved: {checkpoint_path.name} - {checkpoint_path.stat().st_size} bytes"
            )
            return checkpoint_path

        except Exception as e:
            self.logger.error(f"checkpoint_save_failed: {checkpoint_path.name}")
            self.logger.error(f"checkpoint_save_failed: {str(e)}")
            raise

    def load(self, name: str) -> dict[str, Any] | list[dict[str, Any]] | None:
        """
        Charge un checkpoint.

        Args:
            name: Nom du checkpoint (sans extension)

        Returns:
            Données chargées ou None si inexistant
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        if not checkpoint_path.exists():
            self.logger.error(f"checkpoint_not_found: {name}")
            return None

        try:
            with checkpoint_path.open("r", encoding="utf-8") as f:
                checkpoint = json.load(f)

            self.logger.info(
                f"checkpoint_loaded: {name} - {checkpoint.get('timestamp', 'unknown')}"
            )
            return checkpoint.get("data")

        except Exception as e:
            self.logger.error(f"checkpoint_load_failed: {name}")
            self.logger.error(f"checkpoint_load_failed: {str(e)}")
            return None

    def exists(self, name: str) -> bool:
        """Vérifie si un checkpoint existe."""
        return (self.checkpoint_dir / f"{name}.json").exists()

    def delete(self, name: str) -> bool:
        """
        Supprime un checkpoint.

        Args:
            name: Nom du checkpoint

        Returns:
            True si supprimé, False si inexistant
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        if checkpoint_path.exists():
            checkpoint_path.unlink()
            self.logger.info(f"checkpoint_deleted: {name}")
            return True

        return False

    def list_checkpoints(self) -> list[str]:
        """Liste tous les checkpoints disponibles."""
        return [f.stem for f in self.checkpoint_dir.glob("*.json")]


# === Utilitaires Texte ===


def clean_text(text: str) -> str:
    """
    Nettoie un texte (espaces, caractères spéciaux).

    Args:
        text: Texte à nettoyer

    Returns:
        Texte nettoyé
    """
    cleaned = " ".join(text.split())
    return "".join(char for char in cleaned if char.isprintable() or char.isspace())


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Tronque un texte avec ellipse.

    Args:
        text: Texte à tronquer
        max_length: Longueur maximale

    Returns:
        Texte tronqué
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."


# === Utilitaires Validation ===


def is_valid_year(year: int) -> bool:
    """Valide qu'une année est plausible pour un film."""
    current_year = datetime.now().year
    return 1888 <= year <= current_year + 5


def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier en retirant les caractères invalides.

    Args:
        filename: Nom de fichier à nettoyer

    Returns:
        Nom de fichier sécurisé
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    return filename[:255]

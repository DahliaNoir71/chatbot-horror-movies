"""
Utilitaires communs pour le projet HorrorBot.
Logging, retry, checkpoints, helpers, etc.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from pythonjsonlogger.json import JsonFormatter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.etl.settings import settings


# ============================================================================
# Logging configuration
# ============================================================================


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configure un logger avec sortie console + fichier JSON.

    Args:
        name: Nom du logger (ex: "etl.main")
        level: Niveau de log (default: INFO)

    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    # =========================================================================
    # HANDLER 1 : Console (lisible pour humain)
    # =========================================================================
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    console_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # =========================================================================
    # HANDLER 2 : Fichier JSON (parsable pour monitoring)
    # =========================================================================
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"{datetime.now().strftime('%Y%m%d')}_etl.json"

    # ✅ FIX : encoding='utf-8' pour Windows
    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # ✅ FIX : json_ensure_ascii=False pour emojis corrects
    json_formatter = JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        json_ensure_ascii=False,
        # Optionnel : renommer les champs pour plus de clarté
        # rename_fields={
        #     "asctime": "timestamp",
        #     "levelname": "level",
        #     "name": "logger",
        # }
    )
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger


# ============================================================================
# Retry decorator pour robustesse
# ============================================================================


def retry_on_error(
    max_attempts: int = 3,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    wait_min: int = 1,
    wait_max: int = 10,
) -> Callable:
    """
    Décorateur pour retry automatique avec backoff exponentiel.

    Args:
        max_attempts: Nombre maximum de tentatives
        exceptions: Tuple des exceptions à retry
        wait_min: Délai minimum entre tentatives (secondes)
        wait_max: Délai maximum entre tentatives (secondes)

    Returns:
        Décorateur configuré

    Exemple:
        @retry_on_error(max_attempts=5, exceptions=(requests.RequestException,))
        def fetch_data():
            response = requests.get("https://api.example.com")
            return response.json()
    """
    return retry(
        retry=retry_if_exception_type(exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        reraise=True,
    )


# Type pour les données JSON
JSONType = Union[Dict[str, "JSONType"], List["JSONType"], str, int, float, bool, None]

# ============================================================================
# Gestion des checkpoints
# ============================================================================


class CheckpointManager:
    """
    Gestionnaire de checkpoints pour sauvegardes intermédiaires ETL.
    Permet de reprendre l'extraction en cas d'échec.
    """

    def __init__(self, checkpoint_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Args:
            checkpoint_dir: Répertoire des checkpoints (défaut: data/checkpoints)
        """
        if checkpoint_dir is None:
            # Use the checkpoints directory from config if available, otherwise use default
            try:
                self.checkpoint_dir = settings.checkpoints_dir
            except AttributeError:
                # Fallback to default path if config doesn't have checkpoints_dir
                default_dir = Path("data/checkpoints")
                default_dir.mkdir(parents=True, exist_ok=True)
                self.checkpoint_dir = default_dir
        else:
            # Convert string to Path if needed
            self.checkpoint_dir = Path(checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.logger = setup_logger(f"{__name__}.CheckpointManager")
        self.logger.debug(
            f"Using checkpoint directory: {self.checkpoint_dir.absolute()}"
        )

    def save(self, name: str, data: "JSONType") -> None:
        """
        Sauvegarde un checkpoint.

        Args:
            name: Nom du checkpoint (ex: 'tmdb_extraction')
            data: Données à sauvegarder (doit être JSON-serializable)
        """
        # S'assurer que le répertoire existe
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_file = self.checkpoint_dir / f"{name}.json"

        try:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "data": data,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            # Afficher chemin ABSOLU pour debug
            self.logger.info(f"💾 Checkpoint sauvegardé : {checkpoint_file.absolute()}")
        except Exception as e:
            self.logger.error(f"❌ Erreur sauvegarde checkpoint {name} : {e}")
            raise

    def load(self, name: str) -> Optional[Any]:
        """
        Charge un checkpoint.

        Args:
            name: Nom du checkpoint

        Returns:
            Données chargées ou None si checkpoint inexistant
        """
        checkpoint_file = self.checkpoint_dir / f"{name}.json"

        if not checkpoint_file.exists():
            self.logger.warning(f"⚠️  Checkpoint {name} inexistant")
            return None

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
            self.logger.info(
                f"📂 Checkpoint chargé : {name} "
                f"(sauvegardé le {checkpoint['timestamp']})"
            )
            return checkpoint["data"]
        except Exception as e:
            self.logger.error(f"❌ Erreur chargement checkpoint {name} : {e}")
            return None

    def exists(self, name: str) -> bool:
        """Vérifie si un checkpoint existe."""
        return (self.checkpoint_dir / f"{name}.json").exists()

    def delete(self, name: str) -> None:
        """Supprime un checkpoint."""
        checkpoint_file = self.checkpoint_dir / f"{name}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            self.logger.info(f"🗑️  Checkpoint supprimé : {name}")


# ============================================================================
# Helpers divers
# ============================================================================


def normalize_title(title: str) -> str:
    """
    Normalise un titre de film pour comparaison fuzzy.

    Args:
        title: Titre original

    Returns:
        Titre normalisé (lowercase, sans accents, sans ponctuation)

    Exemple:
        >>> normalize_title("The Shining (1980)")
        'the shining 1980'
    """
    import re
    import unicodedata

    # Supprimer accents
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    title = title.lower()

    # Supprimer ponctuation (garder lettres, chiffres, espaces)
    title = re.sub(r"[^\w\s]", " ", title)

    # Normaliser espaces multiples
    title = re.sub(r"\s+", " ", title).strip()

    return title


def calculate_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calcule la distance de Levenshtein entre deux chaînes.

    Args:
        s1: Première chaîne
        s2: Deuxième chaîne

    Returns:
        Distance (nombre de modifications nécessaires)

    Exemple:
        >>> calculate_levenshtein_distance("kitten", "sitting")
        3
    """
    import jellyfish

    return jellyfish.levenshtein_distance(s1, s2)


def safe_dict_get(
    data: dict[str, object], *keys: str, default: object = None
) -> object:
    """
    Récupère une valeur imbriquée dans un dictionnaire de manière sécurisée.

    Args:
        data: Dictionnaire source
        *keys: Clés imbriquées (ex: 'user', 'profile', 'name')
        default: Valeur par défaut si clé inexistante

    Returns:
        Valeur trouvée ou default

    Exemple:
        >>> user_data = {'user': {'profile': {'name': 'John'}}}
        >>> safe_dict_get(user_data, 'user', 'profile', 'name')
        'John'
        >>> safe_dict_get(user_data, 'user', 'age', default=0)
        0
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
            if result is None:
                return default
        else:
            return default
    return result


def format_duration(seconds: float) -> str:
    """
    Formate une durée en secondes en format lisible.

    Args:
        seconds: Durée en secondes

    Returns:
        Chaîne formatée (ex: "2h 15m 30s")

    Exemple:
        >>> format_duration(8130)
        '2h 15m 30s'
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """
    Découpe une liste en chunks de taille fixe.

    Args:
        lst: Liste à découper
        chunk_size: Taille de chaque chunk

    Returns:
        Liste de chunks

    Exemple:
        >>> chunk_list([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


# ============================================================================
# Statistiques ETL
# ============================================================================


class ETLStats:
    """Classe pour collecter et afficher les statistiques ETL."""

    def __init__(self) -> None:
        self.stats: dict[str, Any] = {
            "start_time": datetime.now().isoformat(),
            "sources": {},
        }

    def add_source_stats(
        self, source_name: str, count: int, duration_seconds: float
    ) -> None:
        """
        Ajoute les statistiques d'une source.

        Args:
            source_name: Nom de la source (ex: 'TMDB')
            count: Nombre d'éléments extraits
            duration_seconds: Durée d'extraction en secondes
        """
        self.stats["sources"][source_name] = {
            "count": count,
            "duration_seconds": round(duration_seconds, 2),
            "duration_formatted": format_duration(duration_seconds),
        }

    def get_total_count(self) -> int:
        """Retourne le nombre total d'éléments extraits."""
        return sum(s["count"] for s in self.stats["sources"].values())

    def get_total_duration(self) -> float:
        """Retourne la durée totale d'extraction en secondes."""
        return sum(s["duration_seconds"] for s in self.stats["sources"].values())

    def save_to_json(self, filepath: Path) -> None:
        """Sauvegarde les statistiques en JSON."""
        self.stats["end_time"] = datetime.now().isoformat()
        self.stats["total_count"] = self.get_total_count()
        self.stats["total_duration_seconds"] = self.get_total_duration()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def print_summary(self) -> None:
        """Affiche un résumé des statistiques."""
        print("\n" + "=" * 80)
        print("📊 STATISTIQUES ETL")
        print("=" * 80)

        for source, stats in self.stats["sources"].items():
            print(
                f"✅ {source:<20} : {stats['count']:>10,} films "
                f"en {stats['duration_formatted']}"
            )

        print("-" * 80)
        total_count = self.get_total_count()
        total_duration = format_duration(self.get_total_duration())
        print(f"🎉 TOTAL{' ' * 15} : {total_count:>10,} films en {total_duration}")
        print("=" * 80 + "\n")

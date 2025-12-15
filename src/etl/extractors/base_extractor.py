"""Classe de base abstraite pour tous les extracteurs de données."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExtractionMetrics:
    """Métriques d'extraction standardisées."""

    source_name: str
    total_records: int = 0
    failed_records: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Durée d'extraction en secondes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """Taux de succès en pourcentage."""
        if self.total_records == 0:
            return 0.0
        return ((self.total_records - self.failed_records) / self.total_records) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convertit les métriques en dictionnaire."""
        return {
            "source_name": self.source_name,
            "total_records": self.total_records,
            "failed_records": self.failed_records,
            "success_rate": round(self.success_rate, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "errors_count": len(self.errors),
        }


class BaseExtractor(ABC):
    """Classe abstraite définissant le contrat pour tous les extracteurs."""

    def __init__(self, source_name: str) -> None:
        """Initialise l'extracteur avec logging et métriques."""
        self.source_name = source_name
        self.metrics = ExtractionMetrics(source_name=source_name)

    @abstractmethod
    def extract(self, **_kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        """Extrait les données depuis la source.

        Args:
            **_kwargs: Paramètres spécifiques à chaque extracteur

        Returns:
            Liste de dictionnaires représentant les films extraits

        Raises:
            Exception: En cas d'erreur d'extraction
        """

    @abstractmethod
    def validate_config(self) -> None:
        """Valide la configuration de l'extracteur.

        Raises:
            ValueError: Si la configuration est invalide
        """

    def _start_extraction(self) -> None:
        """Initialise les métriques au début de l'extraction."""
        self.metrics.start_time = datetime.now()

    def _end_extraction(self) -> None:
        """Finalise les métriques à la fin de l'extraction."""
        self.metrics.end_time = datetime.now()

    def _record_error(self, error_msg: str) -> None:
        """Enregistre une erreur dans les métriques."""
        self.metrics.errors.append(error_msg)
        self.metrics.failed_records += 1

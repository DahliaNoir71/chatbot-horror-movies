"""Intent classification service using DeBERTa-v3 zero-shot.

Classifies user queries into intents for routing
(recommendation, details, discussion, trivia, greeting, farewell, out-of-scope).
"""

from functools import lru_cache

from src.etl.utils.logger import setup_logger
from src.settings import settings

logger = setup_logger("services.intent.classifier")

# Intent labels for zero-shot classification
INTENT_LABELS = [
    "horror_recommendation",
    "film_details",
    "horror_discussion",
    "horror_trivia",
    "greeting",
    "farewell",
    "out_of_scope",
]

# Fallback intent when confidence is below threshold
FALLBACK_INTENT = "horror_discussion"


class IntentClassifier:
    """Zero-shot intent classifier using DeBERTa-v3.

    Uses HuggingFace transformers pipeline for zero-shot
    classification of user queries into predefined intents.

    Attributes:
        _model_name: HuggingFace model identifier.
        _confidence_threshold: Minimum confidence to accept a classification.
        _device: Inference device (cpu, cuda, auto).
        _pipeline: Lazy-loaded classification pipeline.
    """

    def __init__(
        self,
        model_name: str | None = None,
        confidence_threshold: float | None = None,
        device: str | None = None,
    ) -> None:
        """Initialize classifier from settings or explicit parameters.

        Args:
            model_name: Override model name from settings.
            confidence_threshold: Override threshold from settings.
            device: Override device from settings.
        """
        classifier_settings = settings.classifier
        self._model_name = model_name or classifier_settings.model_name
        self._confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else classifier_settings.confidence_threshold
        )
        self._device = device or classifier_settings.device
        self._pipeline = None
        self._logger = logger

    @property
    def pipeline(self):
        """Lazy-load and return the zero-shot classification pipeline."""
        if self._pipeline is None:
            from transformers import pipeline

            device = self._resolve_device()
            self._logger.info(f"Loading classifier: {self._model_name} on {device}")
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self._model_name,
                device=device,
            )
            self._logger.info("Classifier loaded successfully")
        return self._pipeline

    def _resolve_device(self) -> int | str:
        """Resolve device string to transformers-compatible value.

        Returns:
            0 for CUDA GPU, "cpu" for CPU.
        """
        if self._device == "auto":
            import torch

            return 0 if torch.cuda.is_available() else "cpu"
        if self._device == "cuda":
            return 0
        return "cpu"

    def classify(self, text: str) -> dict:
        """Classify a user query into an intent.

        Args:
            text: User query text.

        Returns:
            Dict with keys:
                - intent: Best matching intent label.
                - confidence: Score of the best match (0.0-1.0).
                - all_scores: Dict mapping each intent to its score.
        """
        if not text or not text.strip():
            return {
                "intent": FALLBACK_INTENT,
                "confidence": 0.0,
                "all_scores": {},
            }

        result = self.pipeline(text, candidate_labels=INTENT_LABELS)

        scores = dict(zip(result["labels"], result["scores"], strict=True))
        top_label = result["labels"][0]
        top_score = result["scores"][0]

        if top_score < self._confidence_threshold:
            self._logger.debug(
                "low_confidence_fallback",
                text=text[:80],
                top_label=top_label,
                top_score=top_score,
                threshold=self._confidence_threshold,
            )
            top_label = FALLBACK_INTENT

        return {
            "intent": top_label,
            "confidence": top_score,
            "all_scores": scores,
        }

    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model_name

    @property
    def confidence_threshold(self) -> float:
        """Return confidence threshold."""
        return self._confidence_threshold


@lru_cache(maxsize=1)
def get_intent_classifier() -> IntentClassifier:
    """Get singleton intent classifier instance.

    Returns:
        Cached IntentClassifier instance.
    """
    return IntentClassifier()

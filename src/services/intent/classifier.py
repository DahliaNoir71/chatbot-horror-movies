"""Intent classification service using DeBERTa-v3 zero-shot.

Classifies user queries into 3 intents for routing:
needs_database (RAG), conversational (template), off_topic (template).
"""

import re
from functools import lru_cache

from src.etl.utils.logger import setup_logger
from src.settings import settings

logger = setup_logger("services.intent.classifier")

# Intent labels for zero-shot classification (3 distinct categories).
INTENT_LABELS = [
    "needs_database",
    "conversational",
    "off_topic",
]

# Fallback intent when confidence is below threshold.
# CRITICAL: routes to RAG (not LLM-only) so the pipeline can
# gracefully handle poor matches instead of hallucinating.
FALLBACK_INTENT = "needs_database"

# Horror domain keywords — if query contains any of these and the
# classifier says off_topic/conversational, override to needs_database.
_HORROR_DOMAIN_KEYWORDS = {
    "horreur",
    "horror",
    "scary",
    "effrayant",
    "terrifiant",
    "zombie",
    "vampire",
    "ghost",
    "fantome",
    "fantôme",
    "slasher",
    "gore",
    "surnaturel",
    "supernatural",
    "demon",
    "démon",
    "exorcis",
    "hante",
    "hanté",
    "haunted",
    "creature",
    "créature",
    "monstre",
    "monster",
    "sang",
    "blood",
    "mort",
    "dead",
    "tueur",
    "killer",
    "psychopathe",
    "cauchemar",
    "nightmare",
    "possession",
    "maudit",
    "cursed",
    "film",
    "movie",
    "cinema",
    "cinéma",
    "réalisateur",
    "realisateur",
}

# Greeting/farewell keywords for conversational pre-check.
# Short messages containing these (without domain keywords) are routed
# directly to conversational, bypassing zero-shot which struggles with them.
_CONVERSATIONAL_KEYWORDS = {
    "bonjour",
    "salut",
    "hello",
    "hey",
    "coucou",
    "bonsoir",
    "hi",
    "au revoir",
    "bye",
    "goodbye",
    "adieu",
    "bonne nuit",
    "merci",
    "thanks",
    "thank you",
    "good morning",
    "good evening",
    "à bientôt",
    "bientot",
    "prochaine",
    "bye bye",
}

# Maximum word count for conversational keyword pre-check.
_CONVERSATIONAL_MAX_WORDS = 10

# Compiled pattern with word boundaries to avoid substring false positives
# (e.g., "hi" inside "something"). Sorted longest-first for multi-word match.
_CONVERSATIONAL_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(kw) for kw in sorted(_CONVERSATIONAL_KEYWORDS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

# Secondary confidence threshold — between this and the main threshold,
# always route to needs_database (benefit of the doubt).
_SECONDARY_THRESHOLD = 0.35

# Descriptive zero-shot labels for DeBERTa.
# DeBERTa builds hypotheses from label text, so semantic descriptions
# perform much better than code names like "needs_database".
# IMPORTANT: off_topic must be positively defined (examples of actual topics)
# to avoid it matching greetings/farewells which are also "not about horror".
# Mapped 1:1 with INTENT_LABELS.
CANDIDATE_LABEL_MAP: dict[str, str] = {
    "needs_database": "question about horror films or movie recommendations",
    "conversational": "social greeting or farewell",
    "off_topic": "question about science, math, cooking, or other non-movie topic",
}

_CANDIDATE_LABELS = list(CANDIDATE_LABEL_MAP.values())
_CANDIDATE_TO_INTENT = {v: k for k, v in CANDIDATE_LABEL_MAP.items()}


class IntentClassifier:
    """Zero-shot intent classifier using DeBERTa-v3.

    Uses HuggingFace transformers pipeline for zero-shot
    classification of user queries into predefined intents.

    Attributes:
        _model_name: HuggingFace model identifier.
        _confidence_threshold: Minimum confidence to accept a classification.
        _device: Inference device (cpu).
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

    def _resolve_device(self) -> str:
        """Resolve device string to transformers-compatible value.

        Returns:
            "cpu" for CPU inference.
        """
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

        # Pre-check: short greeting/farewell messages bypass zero-shot.
        # DeBERTa struggles with these because they're neither questions
        # nor topic-specific, but keyword detection is reliable.
        if self._is_simple_conversational(text):
            return {
                "intent": "conversational",
                "confidence": 1.0,
                "all_scores": dict.fromkeys(INTENT_LABELS, 0.0) | {"conversational": 1.0},
            }

        result = self.pipeline(
            text,
            candidate_labels=_CANDIDATE_LABELS,
            hypothesis_template="This message is a {}.",
        )

        # Map descriptive labels back to code labels
        mapped_labels = [_CANDIDATE_TO_INTENT[label] for label in result["labels"]]
        scores = dict(zip(mapped_labels, result["scores"], strict=True))
        top_label = mapped_labels[0]
        top_score = result["scores"][0]

        # Domain keyword override: if classified as off_topic/conversational
        # but query contains horror-related keywords, force needs_database.
        if top_label in {"off_topic", "conversational"} and self._has_domain_keyword(text):
            self._logger.debug(
                "domain_keyword_override: text=%s, original_label=%s, original_score=%s",
                text[:80],
                top_label,
                top_score,
            )
            top_label = "needs_database"

        # Low confidence handling: benefit of the doubt → RAG
        if top_score < self._confidence_threshold:
            if top_score >= _SECONDARY_THRESHOLD:
                self._logger.debug(
                    "secondary_threshold_fallback: text=%s, top_label=%s, top_score=%s",
                    text[:80],
                    top_label,
                    top_score,
                )
                top_label = FALLBACK_INTENT
            else:
                self._logger.debug(
                    "low_confidence_fallback: text=%s, top_label=%s, top_score=%s, threshold=%s",
                    text[:80],
                    top_label,
                    top_score,
                    self._confidence_threshold,
                )
                top_label = FALLBACK_INTENT

        return {
            "intent": top_label,
            "confidence": top_score,
            "all_scores": scores,
        }

    @staticmethod
    def _is_simple_conversational(text: str) -> bool:
        """Check if text is a simple greeting or farewell.

        Detects short messages containing greeting/farewell keywords
        that do NOT also contain horror domain keywords (which would
        indicate a real question).

        Args:
            text: User query text.

        Returns:
            True if the message is a simple greeting/farewell.
        """
        lower = text.lower()
        words = lower.split()
        if len(words) > _CONVERSATIONAL_MAX_WORDS:
            return False
        if any(kw in lower for kw in _HORROR_DOMAIN_KEYWORDS):
            return False
        return bool(_CONVERSATIONAL_PATTERN.search(lower))

    @staticmethod
    def _has_domain_keyword(text: str) -> bool:
        """Check if text contains any horror domain keyword.

        Args:
            text: User query text.

        Returns:
            True if a domain keyword is found.
        """
        lower = text.lower()
        return any(kw in lower for kw in _HORROR_DOMAIN_KEYWORDS)

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

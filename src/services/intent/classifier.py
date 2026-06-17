"""Intent classification service using DeBERTa-v3 zero-shot.

Classifies user queries into 3 intents for routing:
needs_database (RAG), conversational (template), off_topic (template).
"""

import re
from collections.abc import Callable
from functools import lru_cache

from src.etl.utils.logger import setup_logger
from src.settings import settings

logger = setup_logger("services.intent.classifier")

# Intent labels for zero-shot classification (3 distinct categories).
INTENT_LABELS = [
    "needs_database",
    "conversational",
    "thanks",
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
    # Small talk / "how are you" pleasantries — route to conversational, not RAG.
    "comment vas-tu",
    "comment ça va",
    "comment allez-vous",
    "comment tu vas",
    "ça va",
    "how are you",
    "quoi de neuf",
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

# Thanks/gratitude keywords for pre-check — detected before the generic
# conversational pre-check so "merci" routes to "thanks", not "farewell".
_THANKS_KEYWORDS = {"merci", "thanks", "thank you"}

_THANKS_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(kw) for kw in sorted(_THANKS_KEYWORDS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

# Meta / self-referential follow-ups about the bot's OWN previous answer
# (e.g. "sur quels critères les as-tu choisis ?"). These must NOT hit RAG —
# there is nothing to retrieve about the assistant's reasoning, so routing them
# to needs_database yields irrelevant docs or a confusing circuit-breaker refusal.
_META_PATTERN = re.compile(
    r"as-tu chois|tu as chois|as-tu s[eé]lectionn|pourquoi ces (?:films|choix)|"
    r"pourquoi avoir chois|comment as-tu chois|ta s[eé]lection|tes choix|"
    r"why did you (?:choose|pick|select)|how did you (?:choose|pick)",
    re.IGNORECASE,
)

# Director / actor filmography questions ("films réalisés par X", "filmographie
# de X", "joue X", "avec <Name>"). Served by a structured SQL lookup (not RAG),
# so a complete filmography is never truncated by the vector top_k cap.
# Split in two (kept under SonarQube regex-complexity limit): role/verb cues are
# case-insensitive; the "avec <Name>" cue requires a capitalised first letter to
# avoid matching thematic queries like "films avec des enfants possédés".
_FILMOGRAPHY_CUES = re.compile(
    r"r[eé]alis[eé]s?\s+par|r[eé]alisateur|filmographie|\bjoue\b",
    re.IGNORECASE,
)
_FILMOGRAPHY_ACTOR = re.compile(r"\bavec\s+[A-ZÀ-Ÿ]")

# Franchise/saga counting questions ("combien de films dans la saga X",
# "la franchise Saw"). Served by a structured SQL lookup (full count) instead
# of the top_k-capped RAG path which truncates a saga to 5 titles.
_FRANCHISE_PATTERN = re.compile(
    r"\b(?:saga|franchise|trilogie|quadrilogie)\b|"
    r"combien\s+(?:de|d')\s*(?:films?|[eé]pisodes?|opus|volets?)",
    re.IGNORECASE,
)

# Genre/concept definition questions ("qu'est-ce que la body horror",
# "c'est quoi le found footage"). The synopsis corpus has no definition docs,
# so these are answered from open knowledge with an explicit disclaimer rather
# than grounded on weakly-matched film synopses.
_DEFINITIONAL_PATTERN = re.compile(
    r"qu'est[- ]ce que|qu'est[- ]ce qu'|c'est quoi|je ne sais pas ce qu|"
    r"que (?:signifie|veut dire)|d[eé]finition d|what\s+(?:is|are|'s)",
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
    "conversational": "social greeting, small talk such as 'how are you', or farewell",
    "thanks": "expressing gratitude or saying thank you",
    "off_topic": "question about a non-film topic such as weather, sports, cooking, science or history",
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
                revision=settings.classifier.revision,
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

        # Deterministic pre-checks bypass the zero-shot model for messages whose
        # intent is reliably detectable by keyword/pattern (and which DeBERTa
        # handles poorly or routes to a structured path instead of RAG).
        precheck = self._precheck_intent(text)
        if precheck is not None:
            return {
                "intent": precheck,
                "confidence": 1.0,
                "all_scores": dict.fromkeys(INTENT_LABELS, 0.0) | {precheck: 1.0},
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

    def _precheck_intent(self, text: str) -> str | None:
        """Resolve a deterministic intent without the zero-shot model.

        Runs ordered pattern/keyword checks that bypass DeBERTa. Order is
        load-bearing: ``thanks`` before ``conversational`` ("merci" is in both
        keyword sets), and ``filmography`` before ``franchise`` ("combien de
        films a réalisé X" is a filmography, not a saga count).

        Args:
            text: User query text.

        Returns:
            The matched intent label, or None when no pre-check fires (the
            caller then falls back to the zero-shot model).
        """
        checks: tuple[tuple[Callable[[str], bool], str], ...] = (
            (self._is_thanks, "thanks"),
            (self._is_meta, "meta"),
            (self._is_filmography, "filmography"),
            (self._is_franchise, "franchise"),
            (self._is_definitional, "definitional"),
            (self._is_simple_conversational, "conversational"),
        )
        for predicate, intent in checks:
            if predicate(text):
                return intent
        return None

    @staticmethod
    def _is_franchise(text: str) -> bool:
        """Check if text asks how many films a franchise/saga contains.

        Such counting questions need the full saga, which the vector top_k cap
        truncates; they are served by a structured SQL lookup instead.

        Args:
            text: User query text.

        Returns:
            True if the message is a franchise/saga counting request.
        """
        return bool(_FRANCHISE_PATTERN.search(text))

    @staticmethod
    def _is_definitional(text: str) -> bool:
        """Check if text asks for a horror genre/concept definition.

        Definitions ("what is body horror") cannot be grounded on a synopsis
        corpus, so they are routed to the open-knowledge path. A horror domain
        keyword is required to avoid hijacking off-topic definitions.

        Args:
            text: User query text.

        Returns:
            True if the message is a horror-domain definitional question.
        """
        lower = text.lower()
        return bool(_DEFINITIONAL_PATTERN.search(lower)) and any(
            kw in lower for kw in _HORROR_DOMAIN_KEYWORDS
        )

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
    def _is_thanks(text: str) -> bool:
        """Check if text is a short gratitude expression.

        Args:
            text: User query text.

        Returns:
            True if the message expresses thanks without horror domain keywords.
        """
        lower = text.lower()
        if len(lower.split()) > _CONVERSATIONAL_MAX_WORDS:
            return False
        if any(kw in lower for kw in _HORROR_DOMAIN_KEYWORDS):
            return False
        return bool(_THANKS_PATTERN.search(lower))

    @staticmethod
    def _is_meta(text: str) -> bool:
        """Check if text is a self-referential question about the bot's answer.

        Detects follow-ups like "on what criteria did you choose these?" that ask
        about the assistant's own prior selection. They have no answer in the film
        corpus, so they are routed to a template instead of RAG.

        Args:
            text: User query text.

        Returns:
            True if the message is a meta-question about the bot's reasoning.
        """
        return bool(_META_PATTERN.search(text))

    @staticmethod
    def _is_filmography(text: str) -> bool:
        """Check if text asks for a director's or actor's filmography.

        Such questions need a complete list and are served by a structured SQL
        lookup rather than the vector RAG path (whose top_k truncates lists).

        Args:
            text: User query text.

        Returns:
            True if the message is a filmography request.
        """
        return bool(_FILMOGRAPHY_CUES.search(text) or _FILMOGRAPHY_ACTOR.search(text))

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

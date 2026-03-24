"""Tests for IntentClassifier service.

Uses mocks to avoid loading the actual DeBERTa-v3 model in CI.
"""

from unittest.mock import MagicMock

import pytest
from pytest import approx

from src.services.intent.classifier import (
    CANDIDATE_LABEL_MAP,
    FALLBACK_INTENT,
    INTENT_LABELS,
    IntentClassifier,
)

# Shorthand for building mock pipeline returns with descriptive labels.
CL = CANDIDATE_LABEL_MAP


@pytest.fixture
def mock_pipeline():
    """Create a mock transformers pipeline."""
    mock = MagicMock()
    return mock


@pytest.fixture
def classifier(mock_pipeline):
    """Create an IntentClassifier with a pre-injected mock pipeline."""
    clf = IntentClassifier(
        model_name="mock-model",
        confidence_threshold=0.4,
        device="cpu",
    )
    clf._pipeline = mock_pipeline
    return clf


class TestIntentClassifier:
    """Tests for IntentClassifier class."""

    @staticmethod
    def test_classify_empty_text_returns_fallback(classifier) -> None:
        """Empty text returns fallback intent with 0.0 confidence."""
        result = classifier.classify("")
        assert result["intent"] == FALLBACK_INTENT
        assert result["confidence"] == approx(0.0)
        assert result["all_scores"] == {}

    @staticmethod
    def test_classify_none_text_returns_fallback(classifier) -> None:
        """None text returns fallback intent."""
        result = classifier.classify(None)
        assert result["intent"] == FALLBACK_INTENT
        assert result["confidence"] == approx(0.0)

    @staticmethod
    def test_classify_whitespace_returns_fallback(classifier) -> None:
        """Whitespace-only text returns fallback intent."""
        result = classifier.classify("   ")
        assert result["intent"] == FALLBACK_INTENT

    @staticmethod
    def test_classify_high_confidence(classifier, mock_pipeline) -> None:
        """High-confidence result returns the top label."""
        mock_pipeline.return_value = {
            "labels": [CL["needs_database"], CL["conversational"], CL["off_topic"]],
            "scores": [0.85, 0.10, 0.05],
        }

        result = classifier.classify("Recommend me a movie like Hereditary")

        assert result["intent"] == "needs_database"
        assert result["confidence"] == pytest.approx(0.85)
        assert "needs_database" in result["all_scores"]

    @staticmethod
    def test_classify_low_confidence_falls_back(classifier, mock_pipeline) -> None:
        """Low-confidence result falls back to FALLBACK_INTENT."""
        mock_pipeline.return_value = {
            "labels": [CL["off_topic"], CL["conversational"], CL["needs_database"]],
            "scores": [0.3, 0.2, 0.15],
        }

        result = classifier.classify("tell me something interesting")

        assert result["intent"] == FALLBACK_INTENT
        assert result["confidence"] == pytest.approx(0.3)

    @staticmethod
    def test_classify_returns_all_scores(classifier, mock_pipeline) -> None:
        """all_scores dict maps labels to scores."""
        mock_pipeline.return_value = {
            "labels": [CL["needs_database"], CL["off_topic"]],
            "scores": [0.7, 0.3],
        }

        result = classifier.classify("What is the rating of The Shining?")

        assert result["all_scores"]["needs_database"] == pytest.approx(0.7)
        assert result["all_scores"]["off_topic"] == pytest.approx(0.3)

    @staticmethod
    def test_model_name_property() -> None:
        """model_name property returns the configured model."""
        clf = IntentClassifier(model_name="test-model")
        assert clf.model_name == "test-model"

    @staticmethod
    def test_confidence_threshold_property() -> None:
        """confidence_threshold property returns the configured value."""
        clf = IntentClassifier(confidence_threshold=0.6)
        assert clf.confidence_threshold == pytest.approx(0.6)

    @staticmethod
    def test_conversational_precheck_greeting(classifier) -> None:
        """Short greeting bypasses zero-shot and returns conversational."""
        result = classifier.classify("Bonjour")

        assert result["intent"] == "conversational"
        assert result["confidence"] == pytest.approx(1.0)

    @staticmethod
    def test_conversational_precheck_farewell(classifier) -> None:
        """Short farewell bypasses zero-shot and returns conversational."""
        result = classifier.classify("Au revoir, merci")

        assert result["intent"] == "conversational"

    @staticmethod
    def test_conversational_precheck_skipped_with_domain_keywords(
        classifier, mock_pipeline,
    ) -> None:
        """Conversational pre-check does not trigger when domain keywords present."""
        mock_pipeline.return_value = {
            "labels": [CL["needs_database"], CL["conversational"], CL["off_topic"]],
            "scores": [0.80, 0.15, 0.05],
        }

        result = classifier.classify("Merci, recommande-moi un film d'horreur")

        assert result["intent"] == "needs_database"

    @staticmethod
    def test_domain_keyword_override(classifier, mock_pipeline) -> None:
        """Query with horror keywords overrides off_topic to needs_database."""
        mock_pipeline.return_value = {
            "labels": [CL["off_topic"], CL["conversational"], CL["needs_database"]],
            "scores": [0.60, 0.25, 0.15],
        }

        result = classifier.classify("Est-ce que le gore est nécessaire dans un film d'horreur ?")

        assert result["intent"] == "needs_database"


class TestIntentLabels:
    """Tests for intent label constants."""

    @staticmethod
    def test_all_expected_labels_present() -> None:
        """All 3 expected intents are defined."""
        expected = {"needs_database", "conversational", "off_topic"}
        assert set(INTENT_LABELS) == expected

    @staticmethod
    def test_fallback_intent_is_in_labels() -> None:
        """Fallback intent is one of the defined labels."""
        assert FALLBACK_INTENT in INTENT_LABELS

    @staticmethod
    def test_fallback_intent_is_needs_database() -> None:
        """Fallback intent routes to RAG, not LLM-only."""
        assert FALLBACK_INTENT == "needs_database"

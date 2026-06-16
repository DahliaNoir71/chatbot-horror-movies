"""Tests for the rerank × retrieval-prior blend.

Guards against the cross-encoder's lexical bias: on thematic queries it ranks
title term-overlap matches (e.g. "Body Snatcher" for "body horror") above
on-theme classics ("The Thing"). Blending the rerank rank with the
RRF+popularity prior rank lets popular on-theme films survive the final cut.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.services.rag.pipeline import RAGPipeline
from src.services.rag.retriever import RetrievedDocument
from src.settings.retrieval import RetrievalSettings


def _doc(tag: str, rerank: float, prior: float, sid: int) -> RetrievedDocument:
    return RetrievedDocument(
        id=uuid4(),
        content=tag,
        source_type="film_overview",
        source_id=sid,
        metadata={"title": tag},
        similarity=0.8,
        rerank_score=rerank,
        final_score=prior,
    )


def _pipeline(weight: float) -> RAGPipeline:
    return RAGPipeline(
        retriever=MagicMock(),
        reranker=MagicMock(),
        llm_service=MagicMock(),
        retrieval_settings=RetrievalSettings(rerank_blend_weight=weight),
    )


class TestRerankPriorBlend:
    @pytest.mark.unit
    def test_blend_rescues_high_prior_low_rerank_classic(self) -> None:
        # lexical: best rerank, worst prior (title term-overlap false friend)
        # middle:  middling on both
        # classic: worst rerank, best prior (popular on-theme film)
        lexical = _doc("Body Snatcher", rerank=0.0, prior=0.01, sid=1)
        middle = _doc("Middle", rerank=-1.0, prior=0.03, sid=2)
        classic = _doc("The Thing", rerank=-3.0, prior=0.06, sid=3)

        blended = _pipeline(0.5)._blend_rerank_with_prior([lexical, middle, classic])

        # Pure rerank ranks the classic LAST (dropped by a top-2 cut); the blend
        # lifts it above the middle doc and into the top 2.
        assert classic in blended[:2]
        assert blended.index(classic) < blended.index(middle)

    @pytest.mark.unit
    def test_weight_one_is_pure_rerank(self) -> None:
        lexical = _doc("Body Snatcher", rerank=0.0, prior=0.01, sid=1)
        classic = _doc("The Thing", rerank=-3.0, prior=0.06, sid=2)

        blended = _pipeline(1.0)._blend_rerank_with_prior([classic, lexical])

        assert blended[0] is lexical  # highest rerank wins outright

    @pytest.mark.unit
    def test_weight_zero_is_pure_prior(self) -> None:
        lexical = _doc("Body Snatcher", rerank=0.0, prior=0.01, sid=1)
        classic = _doc("The Thing", rerank=-3.0, prior=0.06, sid=2)

        blended = _pipeline(0.0)._blend_rerank_with_prior([lexical, classic])

        assert blended[0] is classic  # highest prior wins outright

    @pytest.mark.unit
    def test_single_doc_is_returned_unchanged(self) -> None:
        only = _doc("Solo", rerank=-2.0, prior=0.02, sid=1)

        assert _pipeline(0.5)._blend_rerank_with_prior([only]) == [only]

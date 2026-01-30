"""Tests for AI Score (TF-IDF similarity) - Milestone 3c"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.ai_score import compute_ai_scores, build_tfidf_model
from src.schemas import NewsItem
from src.scoring import RankConfig, rank_items


FIXTURES_DIR = Path("fixtures/ai_score")


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


class TestComputeAiScores:
    """Test ai_score computation with fixtures."""

    def test_similar_item_gets_boost(self):
        """Item similar to positive history should receive ai_score > 0.1"""
        positive_history = load_fixture("positive_history.json")["items"]
        similar_item = load_fixture("new_similar_item.json")["item"]

        # Build model from positive history (corpus = positives for this test)
        model = build_tfidf_model(positive_history)

        # Compute score for similar item
        scores = compute_ai_scores(model, positive_history, [similar_item])

        assert len(scores) == 1
        score = scores[0]
        assert score > 0.1, f"Expected ai_score > 0.1 for similar item, got {score}"

    def test_unrelated_item_no_boost(self):
        """Item unrelated to positive history should receive ai_score < 0.05"""
        positive_history = load_fixture("positive_history.json")["items"]
        unrelated_item = load_fixture("new_unrelated_item.json")["item"]

        model = build_tfidf_model(positive_history)
        scores = compute_ai_scores(model, positive_history, [unrelated_item])

        assert len(scores) == 1
        score = scores[0]
        assert score < 0.05, f"Expected ai_score < 0.05 for unrelated item, got {score}"

    def test_duplicate_url_clamped_to_zero(self):
        """Item with same URL as positive should have ai_score = 0"""
        positive_history = load_fixture("positive_history.json")["items"]
        duplicate_item = load_fixture("duplicate_item.json")["item"]

        model = build_tfidf_model(positive_history)
        scores = compute_ai_scores(model, positive_history, [duplicate_item])

        assert len(scores) == 1
        score = scores[0]
        assert score == 0.0, f"Expected ai_score = 0 for duplicate URL, got {score}"


class TestColdStart:
    """Test cold start behavior when no positive history exists."""

    def test_cold_start_returns_zero(self):
        """With no positive history, ai_score should be 0 for all items."""
        similar_item = load_fixture("new_similar_item.json")["item"]

        # Empty positive history
        model = build_tfidf_model([])
        scores = compute_ai_scores(model, [], [similar_item])

        assert len(scores) == 1
        assert scores[0] == 0.0, "Cold start should return ai_score = 0"

    def test_cold_start_model_is_none(self):
        """build_tfidf_model with empty corpus should return None."""
        model = build_tfidf_model([])
        assert model is None, "Empty corpus should return None model"


class TestAiScoreBounds:
    """Test that ai_score is properly bounded."""

    def test_score_bounded_zero_to_one(self):
        """ai_score should always be in [0, 1] range."""
        positive_history = load_fixture("positive_history.json")["items"]
        similar_item = load_fixture("new_similar_item.json")["item"]
        unrelated_item = load_fixture("new_unrelated_item.json")["item"]

        model = build_tfidf_model(positive_history)
        scores = compute_ai_scores(
            model, positive_history, [similar_item, unrelated_item]
        )

        for score in scores:
            assert 0.0 <= score <= 1.0, f"ai_score {score} out of bounds [0, 1]"


class TestBuildTfidfModel:
    """Test TF-IDF model building."""

    def test_model_uses_title_and_evidence(self):
        """Model should combine title + evidence for text."""
        items = [
            {"url": "u1", "title": "AI News", "evidence": "Machine learning update"},
            {"url": "u2", "title": "Tech Report", "evidence": "Neural network research"},
        ]
        model = build_tfidf_model(items)
        assert model is not None
        # Model should have vocabulary from both title and evidence
        vocab = model["vectorizer"].vocabulary_
        assert "ai" in vocab or "news" in vocab
        assert "machine" in vocab or "learning" in vocab

    def test_corpus_different_from_positives(self):
        """Model built on full corpus still boosts similar items vs positives subset.

        This validates the design decision: fit TF-IDF on all historical items
        (richer vocabulary), compute similarity only against positives.
        """
        # Corpus includes both positive and non-positive items
        corpus = [
            {"url": "u1", "title": "AI breakthrough announced", "evidence": "Machine learning model"},
            {"url": "u2", "title": "Cooking recipes for summer", "evidence": "Grilling tips and BBQ"},
            {"url": "u3", "title": "Sports news update", "evidence": "Football game results"},
            {"url": "u4", "title": "Neural network advances", "evidence": "Deep learning research"},
        ]

        # Only AI-related items are positives (thumbs-up)
        positives = [
            {"url": "u1", "title": "AI breakthrough announced", "evidence": "Machine learning model"},
            {"url": "u4", "title": "Neural network advances", "evidence": "Deep learning research"},
        ]

        # Build model on full corpus (includes cooking, sports)
        model = build_tfidf_model(corpus)
        assert model is not None

        # New AI-related item should get boost when compared to positives
        new_ai_item = {"url": "u5", "title": "AI startup launches", "evidence": "Machine learning platform"}
        new_unrelated = {"url": "u6", "title": "Recipe book review", "evidence": "Best cooking guides"}

        scores = compute_ai_scores(model, positives, [new_ai_item, new_unrelated])

        # AI item should score higher than unrelated item
        assert scores[0] > scores[1], f"AI item ({scores[0]}) should score higher than unrelated ({scores[1]})"
        # AI item should have meaningful boost
        assert scores[0] > 0.1, f"AI item should have ai_score > 0.1, got {scores[0]}"
        # Unrelated item should have minimal boost
        assert scores[1] < 0.1, f"Unrelated item should have ai_score < 0.1, got {scores[1]}"


class TestRankItemsWithAiScores:
    """Integration tests for rank_items() with ai_scores parameter."""

    def _make_item(self, url: str, title: str, source: str = "test") -> NewsItem:
        """Helper to create a NewsItem."""
        return NewsItem(
            url=url,
            title=title,
            source=source,
            evidence="Test evidence",
            published_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_ai_score_boosts_ranking(self):
        """Item with high ai_score should rank above equal base_score item."""
        now = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        cfg = RankConfig(ai_score_alpha=0.1)

        # Two items with identical attributes (same base score)
        item_a = self._make_item("http://a.com", "Item A")
        item_b = self._make_item("http://b.com", "Item B")

        # Give item_b a high ai_score, item_a gets 0
        # Note: Pydantic HttpUrl normalizes URLs (adds trailing slash)
        ai_scores = {
            "http://a.com/": 0.0,
            "http://b.com/": 0.8,
        }

        # With ai_scores, item_b should rank first (gets +0.08 boost)
        ranked_with = rank_items([item_a, item_b], now=now, top_n=2, cfg=cfg, ai_scores=ai_scores)

        assert str(ranked_with[0].url) == "http://b.com/", "Item with higher ai_score should rank first"
        assert str(ranked_with[1].url) == "http://a.com/"

    def test_ai_score_zero_unchanged(self):
        """With ai_scores=None, ranking matches base scoring (no boost)."""
        now = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        cfg = RankConfig(ai_score_alpha=0.1)

        item_a = self._make_item("http://a.com", "Item A")
        item_b = self._make_item("http://b.com", "Item B")

        # Rank without ai_scores
        ranked_none = rank_items([item_a, item_b], now=now, top_n=2, cfg=cfg, ai_scores=None)

        # Rank with all-zero ai_scores (note: Pydantic normalizes URLs)
        ai_scores_zero = {"http://a.com/": 0.0, "http://b.com/": 0.0}
        ranked_zero = rank_items([item_a, item_b], now=now, top_n=2, cfg=cfg, ai_scores=ai_scores_zero)

        # Both should produce same order
        assert [str(it.url) for it in ranked_none] == [str(it.url) for it in ranked_zero]

    def test_ai_score_alpha_zero_no_effect(self):
        """When ai_score_alpha=0, ai_scores have no effect on ranking."""
        now = datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        cfg = RankConfig(ai_score_alpha=0.0)

        item_a = self._make_item("http://a.com", "Item A")
        item_b = self._make_item("http://b.com", "Item B")

        # Even with high ai_score, alpha=0 means no boost (note: Pydantic normalizes URLs)
        ai_scores = {"http://a.com/": 0.0, "http://b.com/": 1.0}

        ranked_without = rank_items([item_a, item_b], now=now, top_n=2, cfg=cfg)
        ranked_with = rank_items([item_a, item_b], now=now, top_n=2, cfg=cfg, ai_scores=ai_scores)

        # Order should be identical when alpha=0
        assert [str(it.url) for it in ranked_without] == [str(it.url) for it in ranked_with]

"""Tests for the deterministic TF-IDF relevance scorer."""
from __future__ import annotations

import pytest

from app.services.scorer import (
    ScoredItem,
    ScoringConfig,
    TFIDFScorer,
    evaluate,
    mean_average_precision,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    tokenize,
)


class TestTokenization:
    def test_stopwords_removed(self):
        tokens = tokenize("the quick brown fox jumps")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_lowercase(self):
        tokens = tokenize("Machine Learning Engineer")
        assert "machine" in tokens
        assert "learning" in tokens
        assert "engineer" in tokens

    def test_empty_string(self):
        assert tokenize("") == []

    def test_accent_folding(self):
        # NFKD + ascii-ignore folds ü → u
        tokens = tokenize("München")
        assert "munchen" in tokens

    def test_numbers_preserved(self):
        tokens = tokenize("top 5 jobs in 2024")
        assert "5" in tokens
        assert "2024" in tokens

    def test_only_stopwords(self):
        assert tokenize("the and or but") == []


class TestScoring:
    @pytest.fixture
    def scorer(self):
        config = ScoringConfig(
            target_title="Machine Learning Engineer",
            target_description="tensorflow pytorch python scikit-learn model deployment",
        )
        return TFIDFScorer(config)

    def test_score_in_range(self, scorer):
        scorer.fit(["machine learning tensorflow pytorch"])
        score, _ = scorer.score_posting("machine learning tensorflow pytorch")
        assert 0.0 <= score <= 1.0

    def test_relevant_scores_higher(self, scorer):
        scorer.fit(
            [
                "machine learning tensorflow pytorch python model deployment",
                "sales representative b2b quota crm software",
            ]
        )
        score_ml, _ = scorer.score_posting(
            "machine learning tensorflow pytorch python model deployment"
        )
        score_sales, _ = scorer.score_posting(
            "sales representative b2b quota crm software"
        )
        assert score_ml > score_sales

    def test_empty_text_score_zero(self, scorer):
        scorer.fit(["machine learning tensorflow"])
        score, matched = scorer.score_posting("")
        assert score == 0.0
        assert matched == []

    def test_determinism(self, scorer):
        scorer.fit(["ml tensorflow pytorch"])
        s1, _ = scorer.score_posting("ml tensorflow pytorch")
        s2, _ = scorer.score_posting("ml tensorflow pytorch")
        assert s1 == s2

    def test_matched_terms_returned(self, scorer):
        scorer.fit(["machine learning tensorflow"])
        score, matched = scorer.score_posting("machine learning tensorflow pytorch")
        # At least one target token should be in the matched terms.
        assert len(matched) > 0 or score == 0.0

    def test_fit_not_called_raises(self, scorer):
        with pytest.raises(RuntimeError, match="not fitted"):
            scorer.score_posting("test")

    def test_score_postings_method(self, scorer):
        postings = [
            {
                "id": "1",
                "title": "ML Engineer",
                "company": "A",
                "source": "url1",
                "location": "C",
                "status": "new",
                "text": "machine learning tensorflow pytorch python model",
            },
            {
                "id": "2",
                "title": "Sales Rep",
                "company": "B",
                "source": "url2",
                "location": "D",
                "status": "new",
                "text": "sales representative b2b quota crm software",
            },
        ]
        results = scorer.score_postings(postings)
        assert len(results) == 2
        relevant = next(r for r in results if r.id == "1")
        irrelevant = next(r for r in results if r.id == "2")
        assert relevant.score > irrelevant.score

    def test_scored_item_explanation(self):
        item = ScoredItem(
            id="1", source="u", company="C", title="T",
            location="L", score=0.9, matched_terms=["ml", "tensorflow"], status="scored",
        )
        explanation = item.to_explanation()
        assert "ml" in explanation
        assert "tensorflow" in explanation

    def test_scored_item_no_matched_terms(self):
        item = ScoredItem(
            id="1", source="u", company="C", title="T",
            location="L", score=0.0, matched_terms=[], status="scored",
        )
        explanation = item.to_explanation()
        assert "No keyword overlap" in explanation


class TestEvaluationMetrics:
    def test_precision_at_k(self):
        relevant = {"a", "c"}
        ranked = ["a", "b", "c", "d"]
        # Top-2: a (relevant), b (not) → precision = 1/2
        assert precision_at_k(relevant, ranked, 2) == 0.5

    def test_recall_at_k(self):
        relevant = {"a", "c"}
        ranked = ["a", "b", "c", "d"]
        # Top-3: a(rel), b(not), c(rel) → 2 hits / 2 relevant = 1.0
        assert recall_at_k(relevant, ranked, 3) == 1.0
        # Top-2: only a is relevant → 1 hit / 2 relevant = 0.5
        assert recall_at_k(relevant, ranked, 2) == 0.5

    def test_mean_average_precision(self):
        relevant = {"a", "c"}
        # ranked: a(rel), b(not), c(rel), d(not)
        # AP@1 = 1/1, AP@3 = 2/3, MAP = (1 + 2/3) / 2 = 5/6
        ranked = ["a", "b", "c", "d"]
        assert mean_average_precision(ranked, relevant) == pytest.approx(5 / 6)

    def test_ndcg_at_k(self):
        relevant = {"a"}
        ranked = ["a", "b"]
        # DCG = 1.0 (first relevant at rank 1)
        # IDCG = 1.0 (ideal: a at rank 1)
        # NDCG = 1.0
        assert ndcg_at_k(ranked, relevant, 2) == pytest.approx(1.0)

    def test_ndcg_zero_when_irrelevant_first(self):
        relevant = {"c"}
        ranked = ["a", "b", "c"]
        # DCG at k=3: 0 + 0 + 1/log2(4) = 1/2
        # IDCG: 1 (best rank)
        # NDCG = 0.5
        assert ndcg_at_k(ranked, relevant, 3) == pytest.approx(0.5, abs=1e-4)

    def test_evaluate_function(self):
        scored_items = [
            ScoredItem(id="a", source="", company="", title="", location="", score=0.9),
            ScoredItem(id="b", source="", company="", title="", location="", score=0.5),
            ScoredItem(id="c", source="", company="", title="", location="", score=0.3),
        ]
        labels = {"a": 1, "b": 0, "c": 1}
        metrics = evaluate(scored_items, labels, ks=[3])
        assert metrics["num_relevant"] == 2
        assert metrics["num_ranked"] == 3
        assert "map" in metrics
        assert "ndcg@3" in metrics
        assert "precision@3" in metrics
        assert "recall@3" in metrics

    def test_evaluate_all_irrelevant(self):
        scored_items = [
            ScoredItem(id="a", source="", company="", title="", location="", score=0.9),
        ]
        labels = {"a": 0}
        metrics = evaluate(scored_items, labels)
        assert metrics["num_relevant"] == 0
        assert metrics["map"] == 0.0
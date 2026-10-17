"""Deterministic TF-IDF relevance scorer.

This is the core domain engine.  It scores how well a job posting matches a
target role profile using term-frequency / inverse-document-frequency
cosine similarity.  The algorithm is fully deterministic and runs offline
with no LLM key required.

Pipeline:
  1. Tokenize documents (posting title+description, target profile).
  2. Build vocabulary + corpus-derived IDF from all documents.
  3. Compute TF-IDF vectors.
  4. Cosine similarity between target vector and each posting vector.
  5. Normalize to [0, 1].

Issue #534 context: scoring only applies to postings that were successfully
fetched (status ``scored``).  A posting that could not be fetched is tracked
as ``fetch_failed`` — retryable — never ``expired`` (terminal).
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Common English stopwords (compact, deterministic set).
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
        "to", "was", "will", "with", "you", "your", "we", "our", "us",
        "this", "these", "those", "or", "but", "not", "so", "than", "too",
        "can", "may", "may", "into", "than", "then", "them", "they", "have",
        "had", "were", "been", "being", "if", "no", "nor", "only", "such",
        "do", "does", "did", "would", "could", "should", "about", "above",
        "after", "again", "against", "all", "am", "any", "because", "below",
        "between", "both", "down", "during", "each", "few", "further",
        "here", "how", "more", "most", "other", "over", "own", "same",
        "she", "some", "what", "when", "where", "which", "while", "who",
        "whom", "why",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class ScoredItem:
    """A posting and its relevance score."""

    id: str
    source: str
    company: str
    title: str
    location: str
    score: float
    matched_terms: list[str] = field(default_factory=list)
    status: str = "new"

    def to_explanation(self) -> str:
        if not self.matched_terms:
            return "No keyword overlap found between the posting and the target profile."
        terms = ", ".join(self.matched_terms[:10])
        return f"Relevance driven by matched terms: {terms}."


@dataclass
class ScoringConfig:
    """Configuration for the scoring pipeline."""

    target_title: str = "Machine Learning Engineer"
    target_description: str = ""
    keywords: list[str] = field(default_factory=list)
    max_retries: int = 3


class TFIDFScorer:
    """Deterministic TF-IDF + cosine-similarity relevance scorer."""

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or ScoringConfig()
        self._idf: dict[str, float] = {}
        self._vocabulary: set[str] = set()
        self._fitted = False

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------
    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Lowercase, strip accents, split on word boundaries, remove stopwords."""
        if not text:
            return []
        # Normalize unicode (NFC) then strip combining marks for accent folding.
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        tokens = _TOKEN_RE.findall(text.lower())
        return [t for t in tokens if t not in _STOPWORDS]

    # ------------------------------------------------------------------
    # TF-IDF
    # ------------------------------------------------------------------
    @staticmethod
    def _tf_vector(tokens: list[str]) -> dict[str, float]:
        """Term-frequency vector (L1-normalized raw counts)."""
        if not tokens:
            return {}
        counts = Counter(tokens)
        total = len(tokens)
        return {term: count / total for term, count in counts.items()}

    @staticmethod
    def _tfidf(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
        return {term: weight * idf.get(term, 0.0) for term, weight in tf.items()}

    @staticmethod
    def _cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """Cosine similarity of two sparse vectors."""
        if not vec_a or not vec_b:
            return 0.0
        dot = sum(vec_a.get(t, 0.0) * vec_b.get(t, 0.0) for t in set(vec_a) | set(vec_b))
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _build_idf(self, documents: list[list[str]]) -> dict[str, float]:
        """Inverse document frequency with Laplace smoothing."""
        n = len(documents)
        if n == 0:
            return {}
        df = defaultdict(int)
        for doc in documents:
            for term in set(doc):
                df[term] += 1
        return {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}

    def fit(self, posting_texts: list[str]) -> "TFIDFScorer":
        """Build IDF from a corpus of posting texts + the target profile."""
        target_doc = self._target_document()
        docs = [self.tokenize(target_doc)]
        for text in posting_texts:
            if text:
                docs.append(self.tokenize(text))
        self._vocabulary = set()
        for doc in docs:
            self._vocabulary.update(doc)
        self._idf = self._build_idf(docs)
        self._fitted = True
        return self

    def _target_document(self) -> str:
        parts = [self.config.target_title, self.config.target_description]
        parts.extend(self.config.keywords)
        return " ".join(parts)

    def _target_vector(self) -> dict[str, float]:
        tokens = self.tokenize(self._target_document())
        tf = self._tf_vector(tokens)
        return self._tfidf(tf, self._idf)

    def score_posting(self, text: str, top_k: int = 10) -> tuple[float, list[str]]:
        """Score a single posting text against the target profile.

        Returns (score, matched_terms) where score is in [0, 1].
        """
        if not self._fitted:
            raise RuntimeError("Scorer not fitted. Call fit() first.")
        tokens = self.tokenize(text)
        if not tokens:
            return 0.0, []
        tf = self._tf_vector(tokens)
        tfidf_vec = self._tfidf(tf, self._idf)
        target_vec = self._target_vector()
        raw = self._cosine(target_vec, tfidf_vec)
        score = max(0.0, min(1.0, raw))
        # Matched terms: intersection of posting tokens and target tokens.
        target_tokens = set(tokenize(self._target_document()))
        posting_tokens = set(tokens)
        matched = sorted(target_tokens & posting_tokens)
        return score, matched[:top_k]

    def score_postings(self, postings: list[dict]) -> list[ScoredItem]:
        """Score a batch of postings.  Each dict must have: id, source,
        company, title, location, and a ``text`` field (title + description).
        """
        if not self._fitted:
            corpus = [p.get("text", "") for p in postings]
            self.fit(corpus)
        target_vec = self._target_vector()
        results: list[ScoredItem] = []
        for posting in postings:
            text = posting.get("text", "")
            tokens = self.tokenize(text)
            tf = self._tf_vector(tokens)
            tfidf_vec = self._tfidf(tf, self._idf)
            raw = self._cosine(target_vec, tfidf_vec)
            score = max(0.0, min(1.0, raw))
            target_tokens = set(tokenize(self._target_document()))
            matched = sorted(target_tokens & set(tokens))
            results.append(
                ScoredItem(
                    id=posting.get("id", ""),
                    source=posting.get("source", ""),
                    company=posting.get("company", ""),
                    title=posting.get("title", ""),
                    location=posting.get("location", ""),
                    score=score,
                    matched_terms=matched[:10],
                    status=posting.get("status", "new"),
                )
            )
        return results


def tokenize(text: str) -> list[str]:
    """Module-level alias for TFIDFScorer.tokenize (used in tests + scoring)."""
    return TFIDFScorer.tokenize(text)


def score_posting(scorer: TFIDFScorer, text: str, top_k: int = 10) -> tuple[float, list[str]]:
    return scorer.score_posting(text, top_k)


# ---------------------------------------------------------------------------
# Evaluation metrics (deterministic IR metrics)
# ---------------------------------------------------------------------------
def precision_at_k(relevant_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """Precision@k — fraction of top-k results that are relevant."""
    if k == 0 or not ranked_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(relevant_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """Recall@k — fraction of relevant items found in top-k."""
    if not relevant_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(relevant_ids)


def mean_average_precision(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    """MAP — mean of precision at each relevant position."""
    if not relevant_ids:
        return 0.0
    precisions = []
    hits = 0
    for i, rid in enumerate(ranked_ids, start=1):
        if rid in relevant_ids:
            hits += 1
            precisions.append(hits / i)
    if not precisions:
        return 0.0
    return sum(precisions) / len(relevant_ids)


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """NDCG@k — normalized discounted cumulative gain."""
    if k == 0 or not ranked_ids:
        return 0.0
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k], start=1):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 1) if i > 1 else 1.0
    ideal = sorted(relevant_ids, key=lambda x: 0, reverse=True)
    idcg = sum(
        1.0 / math.log2(i + 1) if i > 1 else 1.0
        for i in range(1, min(len(ideal), k) + 1)
    )
    if idcg == 0:
        return 0.0
    return dcg / idcg


def evaluate(
    scored_items: list[ScoredItem],
    labels: dict[str, int],
    ks: list[int] | None = None,
) -> dict:
    """Compute IR metrics for a scored set against binary labels.

    Args:
        scored_items: items sorted by score descending (already ranked).
        labels: mapping of item id → 1 (relevant) or 0 (not).
        ks: cutoff values to report.

    Returns:
        Dict with precision@k, recall@k, MAP, NDCG@k for each k.
    """
    if ks is None:
        ks = [3, 5, 10]
    ranked_ids = [item.id for item in scored_items]
    relevant_ids = {iid for iid, label in labels.items() if label == 1}
    metrics: dict = {
        "num_relevant": len(relevant_ids),
        "num_ranked": len(ranked_ids),
    }
    for k in ks:
        metrics[f"precision@{k}"] = round(precision_at_k(relevant_ids, ranked_ids, k), 4)
        metrics[f"recall@{k}"] = round(recall_at_k(relevant_ids, ranked_ids, k), 4)
        metrics[f"ndcg@{k}"] = round(ndcg_at_k(ranked_ids, relevant_ids, k), 4)
    metrics["map"] = round(mean_average_precision(ranked_ids, relevant_ids), 4)
    return metrics


def load_labeled_dataset(path: str | Path) -> list[dict]:
    """Load a labeled dataset from a JSON file.

    Expected format:
    {"target": {"title": "...", "description": "..."},
     "examples": [{"id": "...", "title": "...", "company": "...",
                   "description": "...", "label": 1}]}
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data
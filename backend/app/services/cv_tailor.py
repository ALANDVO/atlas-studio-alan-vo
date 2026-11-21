"""CV/resume tailoring: analyze a posting against a base CV and return keyword gaps.
...
"""
from __future__ import annotations

from pathlib import Path
import re

# Common English stopwords (compact, deterministic set).
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "while", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after", "above",
    "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "should", "now",
    "are", "was", "were", "been", "being",
    "you", "your", "yours", "he", "him", "his", "she", "her", "hers",
    "it", "its", "we", "us", "our", "they", "them", "their",
    "are", "am", "is", "was", "were", "be", "been", "being",
    "does", "do", "did", "doing",
    "just", "not", "no", "nor", "only",
    "such", "own", "same", "so", "too",
    "s", "t", "can", "will", "just", "should", "now",
    "y", "ll", "m", "re", "ve", "d",
    "ain", "aren", "don", "don't", "doesn", "don't", "hadn", "hadn't", "hasn", "hasn't",
    "haven", "haven't", "isn", "isn't", "ma", "mightn", "mightn't", "mustn", "mustn't",
    "needn", "needn't", "shan", "shan't", "shouldn", "shouldn't", "wasn", "wasn't",
    "weren", "weren't", "won", "won't", "wouldn", "wouldn't",
    "aren't", "couldn", "couldn't", "didn", "didn't", "doesn", "doesn't",
    "hadn", "hadn't", "hasn", "hasn't", "haven", "haven't", "isn", "isn't",
    "mightn", "mightn't", "mustn", "mustn't", "needn", "needn't", "shan", "shan't",
    "shouldn", "shouldn't", "wasn", "wasn't", "weren", "weren't", "won", "won't",
    "wouldn", "wouldn't",
    "looking", "look", "looks",
    "we", "us",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercased alphanumeric terms, filtering stopwords."""
    terms: list[str] = []
    for m in _TOKEN_RE.finditer(text.lower()):
        term = m.group(0)
        if term not in _STOPWORDS and len(term) >= 2:
            terms.append(term)
    return terms


def find_keyword_gaps(cv_text: str, posting_text: str) -> dict[str, list[str]]:
    """Find keyword gaps: terms from the posting that are missing from the CV.

    Returns a dict with:
      - "present": terms appearing in both CV and posting
      - "missing": terms appearing in the posting but not in the CV
      - "cv_terms": all unique terms from the CV
      - "posting_terms": all unique terms from the posting
    """
    cv_terms = set(tokenize(cv_text))
    posting_terms = set(tokenize(posting_text))

    present = sorted(cv_terms & posting_terms)
    missing = sorted(posting_terms - cv_terms)

    return {
        "cv_terms": cv_terms,
        "posting_terms": posting_terms,
        "present": present,
        "missing": missing,
    }


def summarize_gaps(gaps: dict[str, list[str]]) -> str:
    """Produce a human-readable summary of keyword gaps."""
    missing = gaps["missing"]
    present = gaps["present"]
    if not missing:
        return "No keyword gaps — your CV covers all posting terms."
    n_missing = len(missing)
    n_present = len(present)
    lines: list[str] = [
        f"Keyword gaps: {n_missing} posting term{s(n_missing)}, {n_present} term{s(n_present)} present.",
        f"Missing: {', '.join(missing) if missing else 'none'}.",
    ]
    return "\n".join(lines)


def s(count: int) -> str:
    return "" if count == 1 else "s"

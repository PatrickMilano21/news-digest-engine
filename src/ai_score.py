"""AI Score computation using TF-IDF similarity - Milestone 3c

Pure domain logic. No database access.
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


def _item_to_text(item: dict) -> str:
    """Convert item to text for TF-IDF: title + evidence."""
    title = item.get("title", "")
    evidence = item.get("evidence", "")
    return f"{title} {evidence}".strip()


def build_tfidf_model(corpus_items: list[dict]) -> dict | None:
    """
    Build TF-IDF model from corpus items.

    Args:
        corpus_items: List of {url, title, evidence} dicts

    Returns:
        Model dict with 'vectorizer' and 'matrix', or None if corpus empty
    """
    if not corpus_items:
        return None

    texts = [_item_to_text(item) for item in corpus_items]

    # Filter out empty texts
    non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
    if not non_empty:
        return None

    indices, filtered_texts = zip(*non_empty)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),
    )

    matrix = vectorizer.fit_transform(filtered_texts)

    return {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "indices": list(indices),  # Map back to original corpus_items
    }


def compute_ai_scores(
    model: dict | None,
    positive_items: list[dict],
    new_items: list[dict],
    *,
    aggregation: str = "max",
) -> list[float]:
    """
    Compute ai_score for new items based on similarity to positive history.

    Args:
        model: TF-IDF model from build_tfidf_model (or None for cold start)
        positive_items: Items with thumbs-up feedback
        new_items: Items to score
        aggregation: How to aggregate similarity scores ('max' or 'mean')

    Returns:
        List of ai_scores (0.0-1.0), one per new_item
    """
    # Cold start: no model or no positives
    if model is None or not positive_items:
        return [0.0] * len(new_items)

    if not new_items:
        return []

    # Build set of positive URLs for duplicate detection
    positive_urls = {item.get("url") for item in positive_items}

    # Vectorize positive items using fitted model
    positive_texts = [_item_to_text(item) for item in positive_items]
    positive_matrix = model["vectorizer"].transform(positive_texts)

    scores = []
    for item in new_items:
        item_url = item.get("url")

        # Duplicate check: if URL matches a positive, score = 0
        if item_url in positive_urls:
            scores.append(0.0)
            continue

        # Vectorize new item
        item_text = _item_to_text(item)
        if not item_text.strip():
            scores.append(0.0)
            continue

        item_vector = model["vectorizer"].transform([item_text])

        # Compute cosine similarity to all positives
        similarities = cosine_similarity(item_vector, positive_matrix).flatten()

        # Aggregate
        if len(similarities) == 0:
            score = 0.0
        elif aggregation == "max":
            score = float(np.max(similarities))
        else:  # mean
            score = float(np.mean(similarities))

        # Bound to [0, 1]
        score = max(0.0, min(1.0, score))
        scores.append(score)

    return scores


def compute_ai_score_for_item(
    model: dict | None,
    positive_items: list[dict],
    item: dict,
) -> float:
    """
    Convenience function to compute ai_score for a single item.

    Returns:
        ai_score (0.0-1.0)
    """
    scores = compute_ai_scores(model, positive_items, [item])
    return scores[0] if scores else 0.0

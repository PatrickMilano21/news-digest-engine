# src/weights.py
"""
Domain logic for source weight learning loop (Milestone 3b).

Pure functions with no database access. All persistence handled by repo.py.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeedbackStats:
    """Aggregated feedback statistics for a single source."""

    source: str
    total: int
    useful: int
    rate_7d: float
    rate_longterm: float
    effective_rate: float  # 0.7 * rate_7d + 0.3 * rate_longterm


def compute_effective_rate(rate_7d: float, rate_longterm: float) -> float:
    """
    Blend short-term and long-term rates.

    Formula: 0.7 * rate_7d + 0.3 * rate_longterm

    This weighting favors recent feedback (70%) while still considering
    historical patterns (30%) to prevent overreaction to short-term noise.

    Args:
        rate_7d: Useful rate over the last 7 days
        rate_longterm: Useful rate over all time

    Returns:
        Blended effective rate between 0.0 and 1.0
    """
    return 0.7 * rate_7d + 0.3 * rate_longterm


def compute_weight_adjustments(
    current_weights: dict[str, float],
    feedback_stats: dict[str, dict],
    *,
    adjustment: float = 0.1,
    min_weight: float = 0.5,
    max_weight: float = 2.0,
    high_threshold: float = 0.7,
    low_threshold: float = 0.3,
) -> dict[str, float]:
    """
    Compute new source weights based on feedback.

    Adjustment rules:
    - effective_rate > high_threshold (0.7): increase weight by adjustment
    - effective_rate < low_threshold (0.3): decrease weight by adjustment
    - Between thresholds: no change (neutral zone)

    All weights are clamped to [min_weight, max_weight].
    Sources not in feedback_stats keep their current weight.

    Args:
        current_weights: Current source weights {source: weight}
        feedback_stats: Feedback stats by source from aggregate_feedback_by_source()
        adjustment: Weight change per cycle (default 0.1)
        min_weight: Minimum allowed weight (default 0.5)
        max_weight: Maximum allowed weight (default 2.0)
        high_threshold: Rate above which to increase weight (default 0.7)
        low_threshold: Rate below which to decrease weight (default 0.3)

    Returns:
        New weights dict with adjustments applied
    """
    new_weights = current_weights.copy()

    for source, stats in feedback_stats.items():
        source_key = source.lower()
        current = new_weights.get(source_key, 1.0)
        effective_rate = stats.get("effective_rate", 0.5)

        if effective_rate > high_threshold:
            # Good feedback: increase weight
            new_weight = min(current + adjustment, max_weight)
        elif effective_rate < low_threshold:
            # Poor feedback: decrease weight
            new_weight = max(current - adjustment, min_weight)
        else:
            # Neutral zone: no change
            new_weight = current

        new_weights[source_key] = round(new_weight, 2)

    return new_weights


def compute_weight_changes(
    weights_before: dict[str, float],
    weights_after: dict[str, float],
    feedback_stats: dict[str, dict],
) -> list[dict]:
    """
    Compute a detailed list of weight changes for artifact reporting.

    Args:
        weights_before: Weights before update
        weights_after: Weights after update
        feedback_stats: Feedback stats by source

    Returns:
        List of dicts with: source, before, after, change, reason
    """
    changes = []

    # Get all sources from both dicts
    all_sources = set(weights_before.keys()) | set(weights_after.keys())

    for source in sorted(all_sources):
        before = weights_before.get(source, 1.0)
        after = weights_after.get(source, 1.0)
        delta = after - before

        # Determine reason
        stats = feedback_stats.get(source, {})
        effective_rate = stats.get("effective_rate")

        if effective_rate is None:
            reason = "no feedback data"
        elif delta > 0:
            reason = f"effective_rate {effective_rate:.2f} > 0.7"
        elif delta < 0:
            reason = f"effective_rate {effective_rate:.2f} < 0.3"
        else:
            reason = f"neutral zone ({effective_rate:.2f})"

        changes.append({
            "source": source,
            "before": before,
            "after": after,
            "change": delta,
            "reason": reason,
        })

    return changes

# src/advisor_tools.py
"""
Advisor tools for the Config Advisor Agent (Milestone 4.5).

This module implements the business logic layer between the OpenAI agent
and the repo layer. All validation happens here, server-side.

Architecture:
    advisor.py (orchestration) → advisor_tools.py (this) → repo.py (CRUD)
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from src.repo import (
    get_all_item_feedback_by_user,
    get_user_config,
    get_active_source_weights,
    get_user_profile as repo_get_user_profile,
    get_pending_suggestions,
    insert_suggestion,
    get_outcomes_by_user,
    get_outcomes_by_type,
    is_target_on_cooldown,
)


# --- Constants ---

MIN_FEEDBACK_ITEMS = 1   # TEMP: lowered for smoke test (production: 10)
MIN_DAYS_HISTORY = 1     # TEMP: lowered for smoke test (production: 7)
MAX_CURATED_ITEMS = 50
MAX_ITEMS_PER_SOURCE = 10
RECENT_DAYS = 14
RECENT_RATIO = 0.7  # 70% from recent, 30% from older


# --- query_user_feedback ---

def query_user_feedback(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    """
    Get curated feedback items with computed patterns for the agent.

    Applies stratified sampling to return a representative subset:
    - Max 50 items total
    - ~60% liked, ~40% disliked
    - Max 10 items per source
    - 70% from last 14 days, 30% older
    - Priority: items with reason_tag > bare thumbs

    Returns:
        {
            "curated_items": [...],
            "source_patterns": {source: {like_rate, sample_size, confidence}},
            "tag_patterns": {"values": {...}, "dislikes": {...}},
            "meta": {total_feedback_available, items_returned, date_range, days_of_history},
            "insufficient_data": bool
        }
    """
    # Get all feedback for user
    all_feedback = get_all_item_feedback_by_user(conn, user_id=user_id)

    if not all_feedback:
        return {
            "curated_items": [],
            "source_patterns": {},
            "tag_patterns": {"values": {}, "dislikes": {}},
            "meta": {
                "total_feedback_available": 0,
                "items_returned": 0,
                "date_range": None,
                "days_of_history": 0,
            },
            "insufficient_data": True,
            "insufficient_reason": "No feedback items found",
        }

    # Calculate days of history (span from oldest to newest feedback_date)
    dates = [_parse_date(f["feedback_date"]) for f in all_feedback if f["feedback_date"]]
    if not dates:
        days_of_history = 0
    else:
        days_of_history = (max(dates) - min(dates)).days + 1  # +1 to include both endpoints

    # Check thresholds
    if len(all_feedback) < MIN_FEEDBACK_ITEMS:
        return _build_insufficient_response(
            all_feedback,
            f"Need at least {MIN_FEEDBACK_ITEMS} feedback items (you have {len(all_feedback)})",
            days_of_history,
        )

    if days_of_history < MIN_DAYS_HISTORY:
        return _build_insufficient_response(
            all_feedback,
            f"Need at least {MIN_DAYS_HISTORY} days of history (you have {days_of_history})",
            days_of_history,
        )

    # Compute patterns from ALL feedback (before sampling)
    source_patterns = _compute_source_patterns(all_feedback)
    tag_patterns = _compute_tag_patterns(all_feedback)

    # Apply stratified sampling
    curated_items = _stratified_sample(all_feedback)

    # Build response
    date_range = None
    if dates:
        date_range = f"{min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}"

    return {
        "curated_items": curated_items,
        "source_patterns": source_patterns,
        "tag_patterns": tag_patterns,
        "meta": {
            "total_feedback_available": len(all_feedback),
            "items_returned": len(curated_items),
            "date_range": date_range,
            "days_of_history": days_of_history,
        },
        "insufficient_data": False,
    }


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        # Handle both full ISO and date-only formats
        if "T" in date_str:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _build_insufficient_response(
    all_feedback: list[dict], reason: str, days_of_history: int
) -> dict[str, Any]:
    """Build response for insufficient data case."""
    dates = [_parse_date(f["feedback_date"]) for f in all_feedback if f["feedback_date"]]
    date_range = None
    if dates:
        date_range = f"{min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}"

    return {
        "curated_items": [],
        "source_patterns": _compute_source_patterns(all_feedback),
        "tag_patterns": _compute_tag_patterns(all_feedback),
        "meta": {
            "total_feedback_available": len(all_feedback),
            "items_returned": 0,
            "date_range": date_range,
            "days_of_history": days_of_history,
        },
        "insufficient_data": True,
        "insufficient_reason": reason,
    }


def _compute_source_patterns(feedback: list[dict]) -> dict[str, dict]:
    """
    Compute like rate and confidence for each source.

    Confidence levels:
    - high: sample_size >= 20
    - medium: sample_size >= 10
    - low: sample_size < 10
    """
    source_stats: dict[str, dict] = defaultdict(lambda: {"liked": 0, "total": 0})

    for item in feedback:
        source = item.get("source", "unknown")
        source_stats[source]["total"] += 1
        if item.get("useful") == 1:
            source_stats[source]["liked"] += 1

    patterns = {}
    for source, stats in source_stats.items():
        total = stats["total"]
        liked = stats["liked"]
        like_rate = round(liked / total, 2) if total > 0 else 0.0

        if total >= 20:
            confidence = "high"
        elif total >= 10:
            confidence = "medium"
        else:
            confidence = "low"

        patterns[source] = {
            "like_rate": like_rate,
            "sample_size": total,
            "confidence": confidence,
        }

    return patterns


def _compute_tag_patterns(feedback: list[dict]) -> dict[str, dict]:
    """
    Compute reason_tag frequency by sentiment.

    Returns:
        {"values": {tag: count}, "dislikes": {tag: count}}
    """
    values: dict[str, int] = defaultdict(int)
    dislikes: dict[str, int] = defaultdict(int)

    for item in feedback:
        tag = item.get("reason_tag")
        if not tag:
            continue

        if item.get("useful") == 1:
            values[tag] += 1
        else:
            dislikes[tag] += 1

    return {
        "values": dict(values),
        "dislikes": dict(dislikes),
    }


def _stratified_sample(feedback: list[dict]) -> list[dict]:
    """
    Apply stratified sampling to get representative subset.

    Rules:
    - Max 50 items total
    - ~60% liked, ~40% disliked
    - Max 10 items per source
    - 70% from last 14 days, 30% from older
    - Priority: items with reason_tag > bare thumbs
    """
    from datetime import timezone as tz
    now = datetime.now(tz.utc)
    cutoff = now - timedelta(days=RECENT_DAYS)

    # Separate into buckets
    recent_liked_tagged: list[dict] = []
    recent_liked_bare: list[dict] = []
    recent_disliked_tagged: list[dict] = []
    recent_disliked_bare: list[dict] = []
    older_liked_tagged: list[dict] = []
    older_liked_bare: list[dict] = []
    older_disliked_tagged: list[dict] = []
    older_disliked_bare: list[dict] = []

    for item in feedback:
        item_date = _parse_date(item.get("feedback_date"))
        is_recent = item_date and item_date >= cutoff if item_date else True
        is_liked = item.get("useful") == 1
        has_tag = bool(item.get("reason_tag"))

        if is_recent:
            if is_liked:
                if has_tag:
                    recent_liked_tagged.append(item)
                else:
                    recent_liked_bare.append(item)
            else:
                if has_tag:
                    recent_disliked_tagged.append(item)
                else:
                    recent_disliked_bare.append(item)
        else:
            if is_liked:
                if has_tag:
                    older_liked_tagged.append(item)
                else:
                    older_liked_bare.append(item)
            else:
                if has_tag:
                    older_disliked_tagged.append(item)
                else:
                    older_disliked_bare.append(item)

    # Target counts
    total_target = MAX_CURATED_ITEMS
    recent_target = int(total_target * RECENT_RATIO)  # 35
    older_target = total_target - recent_target  # 15

    liked_ratio = 0.6
    recent_liked_target = int(recent_target * liked_ratio)  # 21
    recent_disliked_target = recent_target - recent_liked_target  # 14
    older_liked_target = int(older_target * liked_ratio)  # 9
    older_disliked_target = older_target - older_liked_target  # 6

    # Sample from each bucket (priority: tagged > bare)
    result: list[dict] = []
    source_counts: dict[str, int] = defaultdict(int)

    def add_items(items: list[dict], target: int) -> int:
        """Add items up to target, respecting per-source limit."""
        added = 0
        for item in items:
            if added >= target:
                break
            source = item.get("source", "unknown")
            if source_counts[source] >= MAX_ITEMS_PER_SOURCE:
                continue
            result.append(_format_curated_item(item))
            source_counts[source] += 1
            added += 1
        return added

    # Recent liked (tagged first, then bare)
    added = add_items(recent_liked_tagged, recent_liked_target)
    if added < recent_liked_target:
        add_items(recent_liked_bare, recent_liked_target - added)

    # Recent disliked (tagged first, then bare)
    added = add_items(recent_disliked_tagged, recent_disliked_target)
    if added < recent_disliked_target:
        add_items(recent_disliked_bare, recent_disliked_target - added)

    # Older liked (tagged first, then bare)
    added = add_items(older_liked_tagged, older_liked_target)
    if added < older_liked_target:
        add_items(older_liked_bare, older_liked_target - added)

    # Older disliked (tagged first, then bare)
    added = add_items(older_disliked_tagged, older_disliked_target)
    if added < older_disliked_target:
        add_items(older_disliked_bare, older_disliked_target - added)

    return result


def _format_curated_item(item: dict) -> dict:
    """Format feedback item for agent consumption."""
    from datetime import timezone as tz
    item_date = _parse_date(item.get("feedback_date"))
    days_ago = None
    if item_date:
        days_ago = (datetime.now(tz.utc) - item_date).days

    return {
        "url": item.get("url"),
        "title": item.get("title", "Unknown")[:100],  # Truncate for token budget
        "source": item.get("source", "unknown"),
        "useful": item.get("useful"),
        "reason_tag": item.get("reason_tag"),
        "feedback_date": item.get("feedback_date", "")[:10] if item.get("feedback_date") else None,
        "days_ago": days_ago,
    }


# --- query_user_config ---

def query_user_config(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    """
    Get merged config view for the agent.

    Returns:
        {
            "config": {topics, source_weights, keyword_boosts, ...},
            "active_weights": {source: weight after learning loop},
            "has_user_overrides": bool,
            "last_weight_update": date or None
        }
    """
    # Get user config (explicit overrides)
    user_config = get_user_config(conn, user_id=user_id)

    # Get active weights (from learning loop)
    active_weights = get_active_source_weights(conn, user_id=user_id)

    # Build merged config view
    config = {
        "topics": [],
        "source_weights": {},
        "keyword_boosts": {},
        "recency_half_life_hours": 24.0,
        "ai_score_alpha": 0.1,
    }

    if user_config:
        config.update({
            "topics": user_config.get("topics", []),
            "source_weights": user_config.get("source_weights", {}),
            "keyword_boosts": user_config.get("keyword_boosts", {}),
            "recency_half_life_hours": user_config.get("recency_half_life_hours", 24.0),
            "ai_score_alpha": user_config.get("ai_score_alpha", 0.1),
        })

    return {
        "config": config,
        "active_weights": active_weights,
        "has_user_overrides": user_config is not None,
        "last_weight_update": None,  # Could query weight_snapshots if needed
    }


# --- get_user_profile (tool wrapper) ---

def get_user_profile(conn: sqlite3.Connection, *, user_id: str) -> dict[str, Any]:
    """
    Get user preference profile for the agent.

    Returns profile or empty profile for first-run users.
    """
    profile = repo_get_user_profile(conn, user_id=user_id)

    if profile is None:
        # First-run user - return empty profile
        return {
            "acceptance_stats": {},
            "patterns": {},
            "trends": None,
            "total_outcomes": 0,
            "last_outcome_at": None,
            "is_new_user": True,
        }

    return {
        "acceptance_stats": profile.get("acceptance_stats", {}),
        "patterns": profile.get("patterns", {}),
        "trends": profile.get("trends"),
        "total_outcomes": profile.get("total_outcomes", 0),
        "last_outcome_at": profile.get("last_outcome_at"),
        "is_new_user": False,
    }


# --- write_suggestion (with validation) ---

# Validation error codes
UNGROUNDED_EVIDENCE = "UNGROUNDED_EVIDENCE"
WEIGHT_OUT_OF_BOUNDS = "WEIGHT_OUT_OF_BOUNDS"
DUPLICATE_SUGGESTION = "DUPLICATE_SUGGESTION"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
TARGET_ON_COOLDOWN = "TARGET_ON_COOLDOWN"

# Weight change limit
MAX_WEIGHT_CHANGE = 0.3

# Cooldown period (days) - targets can't be re-suggested within this window
COOLDOWN_DAYS = 10


def write_suggestion(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    suggestion_type: str,
    field: str,
    target_key: str | None = None,
    current_value: str | None,
    suggested_value: str,
    evidence_items: list[dict],
    reason: str,
) -> dict[str, Any]:
    """
    Validate and write a suggestion.

    Validation rules:
    1. Minimum evidence: at least 3 items
    2. Evidence grounding: all URLs must exist in user's item_feedback
    3. Weight bounds: source weights can only change ±0.3
    4. No duplicates: same suggestion_type + suggested_value cannot be pending
    5. Cooldown: target can't be re-suggested within 10 days

    Args:
        target_key: Source name for boost/reduce (e.g., "techcrunch"), None for topics

    Returns:
        {success: True, suggestion_id: int} or
        {success: False, error: str, details: str}
    """
    # Validation 1: Minimum evidence
    if len(evidence_items) < 3:
        return {
            "success": False,
            "error": INSUFFICIENT_EVIDENCE,
            "details": f"Need at least 3 evidence items (got {len(evidence_items)})",
        }

    # Validation 2: Evidence grounding
    user_feedback = get_all_item_feedback_by_user(conn, user_id=user_id)
    user_urls = {f["url"] for f in user_feedback}

    ungrounded = []
    for item in evidence_items:
        url = item.get("url")
        if url and url not in user_urls:
            ungrounded.append(url)

    if ungrounded:
        return {
            "success": False,
            "error": UNGROUNDED_EVIDENCE,
            "details": f"URLs not in user feedback: {ungrounded[:3]}{'...' if len(ungrounded) > 3 else ''}",
        }

    # Validation 3: Weight bounds (for source weight suggestions)
    if suggestion_type in ("boost_source", "reduce_source") and field == "source_weights":
        try:
            current = float(current_value) if current_value else 1.0
            suggested = float(suggested_value)
            change = abs(suggested - current)

            if change > MAX_WEIGHT_CHANGE:
                return {
                    "success": False,
                    "error": WEIGHT_OUT_OF_BOUNDS,
                    "details": f"Weight change {change:.2f} exceeds max {MAX_WEIGHT_CHANGE} (current={current}, suggested={suggested})",
                }
        except (ValueError, TypeError):
            pass  # Non-numeric values skip this check

    # Validation 4: No duplicates
    pending = get_pending_suggestions(conn, user_id=user_id, status="pending")
    for existing in pending:
        if (
            existing["suggestion_type"] == suggestion_type
            and existing["suggested_value"] == suggested_value
        ):
            return {
                "success": False,
                "error": DUPLICATE_SUGGESTION,
                "details": f"Pending suggestion already exists with type={suggestion_type}, value={suggested_value}",
            }

    # Validation 5: Cooldown check (10 days)
    # The target is target_key if set (sources), otherwise suggested_value (topics)
    cooldown_target = target_key if target_key else suggested_value
    if is_target_on_cooldown(conn, user_id=user_id, target_value=cooldown_target, cooldown_days=COOLDOWN_DAYS):
        return {
            "success": False,
            "error": TARGET_ON_COOLDOWN,
            "details": f"Target '{cooldown_target}' was suggested or resolved within the last {COOLDOWN_DAYS} days",
        }

    # All validations passed - insert
    suggestion_id = insert_suggestion(
        conn,
        user_id=user_id,
        suggestion_type=suggestion_type,
        field=field,
        target_key=target_key,
        current_value=current_value,
        suggested_value=suggested_value,
        evidence_items=evidence_items,
        reason=reason,
    )

    return {
        "success": True,
        "suggestion_id": suggestion_id,
    }


# --- get_suggestion_outcomes (3-layer retrieval) ---

def get_suggestion_outcomes(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    layer: str,
    query: dict[str, Any],
) -> dict[str, Any]:
    """
    3-layer retrieval for suggestion outcomes.

    Layers:
    - "search": Filter by suggestion_type/outcome, return compact snippets (~50 tokens/result)
    - "timeline": Get by outcome_ids or limit N, add context (~200 tokens/result)
    - "detail": Full records with evidence_summary (~500 tokens/result)

    Query params by layer:
    - search: {suggestion_type?, outcome?}
    - timeline: {outcome_ids: [int]} or {limit: int}
    - detail: {outcome_ids: [int]}
    """
    if layer == "search":
        return _outcomes_search(conn, user_id=user_id, query=query)
    elif layer == "timeline":
        return _outcomes_timeline(conn, user_id=user_id, query=query)
    elif layer == "detail":
        return _outcomes_detail(conn, user_id=user_id, query=query)
    else:
        return {"error": f"Unknown layer: {layer}", "valid_layers": ["search", "timeline", "detail"]}


def _outcomes_search(
    conn: sqlite3.Connection, *, user_id: str, query: dict[str, Any]
) -> dict[str, Any]:
    """Layer 1: Compact snippets (~50 tokens/result)."""
    suggestion_type = query.get("suggestion_type")
    # outcome_filter = query.get("outcome")  # Could add filtering by outcome

    if suggestion_type:
        outcomes = get_outcomes_by_type(conn, user_id=user_id, suggestion_type=suggestion_type)
    else:
        outcomes = get_outcomes_by_user(conn, user_id=user_id, limit=50)

    # Return compact format
    snippets = [
        {
            "outcome_id": o.get("outcome_id"),
            "suggestion_type": o.get("suggestion_type"),
            "value": o.get("suggestion_value"),
            "outcome": o.get("outcome"),
            "decided_at": o.get("decided_at"),
        }
        for o in outcomes
    ]

    return {
        "layer": "search",
        "count": len(snippets),
        "outcomes": snippets,
    }


def _outcomes_timeline(
    conn: sqlite3.Connection, *, user_id: str, query: dict[str, Any]
) -> dict[str, Any]:
    """Layer 2: Context around decisions (~200 tokens/result)."""
    outcome_ids = query.get("outcome_ids", [])
    limit = query.get("limit", 10)

    # Get outcomes
    all_outcomes = get_outcomes_by_user(conn, user_id=user_id, limit=100)

    # Filter by IDs if provided
    if outcome_ids:
        outcomes = [o for o in all_outcomes if o.get("outcome_id") in outcome_ids]
    else:
        outcomes = all_outcomes[:limit]

    # Return with context
    timeline = [
        {
            "outcome_id": o.get("outcome_id"),
            "suggestion_type": o.get("suggestion_type"),
            "value": o.get("suggestion_value"),
            "outcome": o.get("outcome"),
            "user_reason": o.get("user_reason"),
            "config_before": o.get("config_before"),
            "config_after": o.get("config_after"),
            "decided_at": o.get("decided_at"),
        }
        for o in outcomes
    ]

    return {
        "layer": "timeline",
        "count": len(timeline),
        "outcomes": timeline,
    }


def _outcomes_detail(
    conn: sqlite3.Connection, *, user_id: str, query: dict[str, Any]
) -> dict[str, Any]:
    """Layer 3: Full records with evidence (~500 tokens/result)."""
    outcome_ids = query.get("outcome_ids", [])

    if not outcome_ids:
        return {"layer": "detail", "count": 0, "outcomes": [], "error": "outcome_ids required"}

    # Get all outcomes and filter
    all_outcomes = get_outcomes_by_user(conn, user_id=user_id, limit=100)
    outcomes = [o for o in all_outcomes if o.get("outcome_id") in outcome_ids]

    # Return full records
    details = [
        {
            "outcome_id": o.get("outcome_id"),
            "suggestion_id": o.get("suggestion_id"),
            "suggestion_type": o.get("suggestion_type"),
            "value": o.get("suggestion_value"),
            "outcome": o.get("outcome"),
            "user_reason": o.get("user_reason"),
            "config_before": o.get("config_before"),
            "config_after": o.get("config_after"),
            "evidence_summary": o.get("evidence_summary"),
            "created_at": o.get("created_at"),
            "decided_at": o.get("decided_at"),
        }
        for o in outcomes
    ]

    return {
        "layer": "detail",
        "count": len(details),
        "outcomes": details,
    }

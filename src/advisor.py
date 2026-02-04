"""
Config Advisor Agent — OpenAI tool-calling orchestration (Milestone 4.5, Step 5).

Architecture:
    advisor.py (this) → advisor_tools.py (business logic) → repo.py (CRUD)

Entry point: run_advisor(user_id, conn) — called from generate endpoint and scheduled job.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.advisor_tools import (
    get_suggestion_outcomes,
    get_user_profile,
    query_user_config,
    query_user_feedback,
    write_suggestion,
)
from src.logging_utils import log_event
from src.repo import (
    finish_run_error,
    finish_run_ok,
    get_daily_spend_by_type,
    get_suggestions_for_today,
    start_run,
    update_run_llm_stats,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ADVISOR_MODEL = "gpt-4o"
ADVISOR_DAILY_CAP_USD = float(os.environ.get("ADVISOR_DAILY_CAP_USD", "1.00"))

# Cost estimates (per 1k tokens) — gpt-4o pricing for logging
COST_PER_1K_PROMPT = 0.0025
COST_PER_1K_COMPLETION = 0.01

# Guardrails (three separate caps)
MAX_API_TURNS = 50
MAX_TOOL_CALLS = 30
HISTORY_WINDOW = 15  # Keep system + user context + last N turns

# Prompt file path (relative to project root)
PROMPT_PATH = Path(".claude/agents/config-advisor.md")

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "query_user_feedback",
            "strict": True,
            "description": (
                "Get curated feedback items with pre-computed source and tag patterns. "
                "Call this first to understand what the user likes and dislikes. "
                "Returns up to 50 representative items with stratified sampling."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_user_config",
            "strict": True,
            "description": (
                "Get the user's current configuration (topics, source weights) "
                "merged with active learning-loop weights. "
                "Call this to know the starting point before suggesting changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "strict": True,
            "description": (
                "Get the user's acceptance history and preference patterns from past "
                "suggestions. Use this to avoid suggesting things they've already rejected."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_suggestion",
            "strict": True,
            "description": (
                "Validate and store a suggestion. Server-side validation checks evidence "
                "grounding, weight bounds, duplicates, cooldown, and minimum evidence (3+). "
                "Returns success with suggestion_id or error with details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "suggestion_type": {
                        "type": "string",
                        "enum": ["boost_source", "reduce_source", "add_topic", "remove_topic"],
                        "description": "Type of suggestion",
                    },
                    "field": {
                        "type": "string",
                        "enum": ["source_weights", "topics"],
                        "description": "Config field to change",
                    },
                    "target_key": {
                        "type": ["string", "null"],
                        "description": (
                            "Source name for boost/reduce suggestions. "
                            "null for topic suggestions."
                        ),
                    },
                    "current_value": {
                        "type": ["string", "null"],
                        "description": (
                            "Current weight as string for source changes. "
                            "null for add_topic."
                        ),
                    },
                    "suggested_value": {
                        "type": "string",
                        "description": (
                            "Proposed weight as string for sources, "
                            "or topic name for topic changes."
                        ),
                    },
                    "evidence_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "title": {"type": "string"},
                            },
                            "required": ["url", "title"],
                            "additionalProperties": False,
                        },
                        "description": "At least 3 items from the user's feedback as evidence",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "One sentence explaining why, written for the user to read"
                        ),
                    },
                },
                "required": [
                    "suggestion_type",
                    "field",
                    "target_key",
                    "current_value",
                    "suggested_value",
                    "evidence_items",
                    "reason",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_suggestion_outcomes",
            "strict": True,
            "description": (
                "Retrieve past suggestion outcomes. Use layer 'search' first to scan, "
                "'timeline' for context, 'detail' for full records."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "layer": {
                        "type": "string",
                        "enum": ["search", "timeline", "detail"],
                        "description": "Retrieval layer",
                    },
                    "query": {
                        "type": "object",
                        "description": (
                            "Query params. search: {suggestion_type?, outcome?}. "
                            "timeline: {outcome_ids: [int]} or {limit: int}. "
                            "detail: {outcome_ids: [int]}."
                        ),
                    },
                },
                "required": ["layer", "query"],
                "additionalProperties": False,
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def load_agent_prompt() -> str | None:
    """
    Load the agent prompt from the markdown file.

    Strips YAML frontmatter (between --- markers).
    Returns None if file is missing or malformed.
    """
    try:
        if not PROMPT_PATH.exists():
            log_event("advisor_prompt_missing", path=str(PROMPT_PATH))
            return None

        content = PROMPT_PATH.read_text(encoding="utf-8")

        # Strip YAML frontmatter: expect exactly 2 '---' markers
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) < 3:
                log_event(
                    "advisor_prompt_malformed",
                    path=str(PROMPT_PATH),
                    reason="Expected exactly 2 '---' markers for frontmatter",
                )
                return None
            return parts[2].strip()

        return content.strip()

    except Exception as exc:
        log_event("advisor_prompt_error", path=str(PROMPT_PATH), error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def _handle_tool_call(
    name: str,
    args: dict[str, Any],
    conn: sqlite3.Connection,
    user_id: str,
) -> dict[str, Any]:
    """Dispatch a tool call to the appropriate advisor_tools function."""
    if name == "query_user_feedback":
        return query_user_feedback(conn, user_id=user_id)

    if name == "query_user_config":
        return query_user_config(conn, user_id=user_id)

    if name == "get_user_profile":
        return get_user_profile(conn, user_id=user_id)

    if name == "write_suggestion":
        return write_suggestion(
            conn,
            user_id=user_id,
            suggestion_type=args.get("suggestion_type", ""),
            field=args.get("field", ""),
            target_key=args.get("target_key"),
            current_value=args.get("current_value"),
            suggested_value=args.get("suggested_value", ""),
            evidence_items=args.get("evidence_items", []),
            reason=args.get("reason", ""),
        )

    if name == "get_suggestion_outcomes":
        return get_suggestion_outcomes(
            conn,
            user_id=user_id,
            layer=args.get("layer", "search"),
            query=args.get("query", {}),
        )

    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Cost tracking helpers
# ---------------------------------------------------------------------------

def _estimate_cost(usage: dict) -> float:
    """Estimate cost from token usage."""
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    return round(
        prompt / 1000 * COST_PER_1K_PROMPT
        + completion / 1000 * COST_PER_1K_COMPLETION,
        6,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_advisor(user_id: str, conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Run the config advisor agent for a user.

    Returns a status dict:
        {status: 'completed', suggestions_created: N, suggestion_ids: [...]}
        {status: 'budget_exceeded', suggestions_created: N, ...}
        {status: 'agent_timeout', suggestions_created: N, ...}
        {status: 'agent_error', error: '...', suggestions_created: N}
    """
    try:
        import openai  # Lazy import — fail gracefully if not installed
    except ImportError:
        log_event("advisor_run_skipped", user_id=user_id, reason="openai_not_installed")
        return {"status": "agent_error", "error": "openai_not_installed", "suggestions_created": 0}

    today = date.today().isoformat()
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # --- Budget check (DB total for today) ---
    db_daily_cost = get_daily_spend_by_type(conn, day=today, run_type="advisor")
    if db_daily_cost >= ADVISOR_DAILY_CAP_USD:
        log_event(
            "advisor_run_skipped",
            user_id=user_id,
            reason="budget_exceeded",
            daily_cost=db_daily_cost,
            cap=ADVISOR_DAILY_CAP_USD,
        )
        return {"status": "budget_exceeded", "suggestions_created": 0}

    # --- Load prompt ---
    prompt_body = load_agent_prompt()
    if prompt_body is None:
        log_event("advisor_run_skipped", user_id=user_id, reason="prompt_load_failed")
        return {"status": "agent_error", "error": "prompt_load_failed", "suggestions_created": 0}

    # --- Build initial messages ---
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": prompt_body},
        {
            "role": "user",
            "content": (
                f"Analyze feedback for user_id: {user_id}\n\n"
                "Follow the reasoning steps in your instructions. "
                "Start by calling query_user_feedback."
            ),
        },
    ]

    # --- Start run record ---
    start_run(
        conn,
        run_id=run_id,
        started_at=started_at,
        received=0,
        run_type="advisor",
        user_id=user_id,
    )

    log_event("advisor_run_started", user_id=user_id, run_id=run_id)

    # --- Agent loop ---
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    accumulated_cost = 0.0
    total_latency_ms = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    api_turns = 0
    tool_call_count = 0
    suggestions_created: list[int] = []
    error_pairs: dict[tuple[str, str], int] = {}  # {(tool_name, error_code): count}

    try:
        while api_turns < MAX_API_TURNS:
            # --- Per-call budget check ---
            effective_daily = db_daily_cost + accumulated_cost
            if effective_daily >= ADVISOR_DAILY_CAP_USD:
                log_event(
                    "advisor_budget_exceeded_mid_run",
                    user_id=user_id,
                    run_id=run_id,
                    accumulated_cost=accumulated_cost,
                    suggestions_created=len(suggestions_created),
                )
                _finalize_run(
                    conn, run_id, started_at, accumulated_cost, total_latency_ms,
                    len(suggestions_created), "budget_exceeded",
                )
                return {
                    "status": "budget_exceeded",
                    "suggestions_created": len(suggestions_created),
                    "suggestion_ids": suggestions_created,
                }

            # --- Call OpenAI ---
            t0 = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=ADVISOR_MODEL,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    temperature=0.2,
                    timeout=30.0,
                )
            except openai.APITimeoutError:
                log_event(
                    "advisor_api_timeout",
                    user_id=user_id,
                    run_id=run_id,
                    turn=api_turns,
                )
                _finalize_run(
                    conn, run_id, started_at, accumulated_cost, total_latency_ms,
                    len(suggestions_created), "agent_timeout",
                )
                return {
                    "status": "agent_timeout",
                    "suggestions_created": len(suggestions_created),
                    "suggestion_ids": suggestions_created,
                }
            except Exception as exc:
                log_event(
                    "advisor_api_error",
                    user_id=user_id,
                    run_id=run_id,
                    turn=api_turns,
                    error=str(exc),
                )
                _finalize_run(
                    conn, run_id, started_at, accumulated_cost, total_latency_ms,
                    len(suggestions_created), "agent_error",
                    error_message=str(exc),
                )
                return {
                    "status": "agent_error",
                    "error": str(exc),
                    "suggestions_created": len(suggestions_created),
                    "suggestion_ids": suggestions_created,
                }

            latency_ms = int((time.perf_counter() - t0) * 1000)
            total_latency_ms += latency_ms
            api_turns += 1

            # --- Track cost ---
            usage = response.usage
            if usage:
                total_prompt_tokens += usage.prompt_tokens
                total_completion_tokens += usage.completion_tokens
                call_cost = _estimate_cost({
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                })
                accumulated_cost += call_cost

            # --- Process response ---
            choice = response.choices[0]
            assistant_message = choice.message

            # Add assistant message to history
            messages.append(_message_to_dict(assistant_message))

            # --- No tool calls → agent is done ---
            if not assistant_message.tool_calls:
                log_event(
                    "advisor_run_completed",
                    user_id=user_id,
                    run_id=run_id,
                    suggestions_count=len(suggestions_created),
                    turns=api_turns,
                    cost_usd=accumulated_cost,
                )
                _finalize_run(
                    conn, run_id, started_at, accumulated_cost, total_latency_ms,
                    len(suggestions_created), "ok",
                )
                return {
                    "status": "completed",
                    "suggestions_created": len(suggestions_created),
                    "suggestion_ids": suggestions_created,
                }

            # --- Process tool calls ---
            for tool_call in assistant_message.tool_calls:
                tool_call_count += 1

                # Tool call cap
                if tool_call_count > MAX_TOOL_CALLS:
                    log_event(
                        "advisor_tool_cap_hit",
                        user_id=user_id,
                        run_id=run_id,
                        tool_calls=tool_call_count,
                    )
                    _finalize_run(
                        conn, run_id, started_at, accumulated_cost, total_latency_ms,
                        len(suggestions_created), "agent_error",
                        error_message="max_tool_calls_exceeded",
                    )
                    return {
                        "status": "agent_error",
                        "error": "max_tool_calls_exceeded",
                        "suggestions_created": len(suggestions_created),
                        "suggestion_ids": suggestions_created,
                    }

                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                # --- Concurrency guard: re-check before first write ---
                if func_name == "write_suggestion" and not suggestions_created:
                    existing_today = get_suggestions_for_today(
                        conn, user_id=user_id, day=today,
                    )
                    if existing_today:
                        log_event(
                            "advisor_concurrency_guard",
                            user_id=user_id,
                            run_id=run_id,
                            existing_count=len(existing_today),
                        )
                        _finalize_run(
                            conn, run_id, started_at, accumulated_cost,
                            total_latency_ms, 0, "ok",
                        )
                        return {
                            "status": "already_generated",
                            "suggestions_created": 0,
                            "suggestion_ids": [],
                        }

                # --- Dispatch tool call ---
                tool_result = _handle_tool_call(func_name, func_args, conn, user_id)

                # --- Error retry guardrail ---
                error_code = tool_result.get("error")
                if error_code:
                    pair = (func_name, str(error_code))
                    error_pairs[pair] = error_pairs.get(pair, 0) + 1
                    if error_pairs[pair] >= 2:
                        log_event(
                            "advisor_error_retry_guard",
                            user_id=user_id,
                            run_id=run_id,
                            tool=func_name,
                            error=error_code,
                        )
                        _finalize_run(
                            conn, run_id, started_at, accumulated_cost,
                            total_latency_ms, len(suggestions_created),
                            "agent_error",
                            error_message=f"repeated_error:{func_name}:{error_code}",
                        )
                        return {
                            "status": "agent_error",
                            "error": f"repeated_error:{func_name}:{error_code}",
                            "suggestions_created": len(suggestions_created),
                            "suggestion_ids": suggestions_created,
                        }

                # --- Track successful writes ---
                if func_name == "write_suggestion" and tool_result.get("success"):
                    sid = tool_result.get("suggestion_id")
                    if sid is not None:
                        suggestions_created.append(sid)
                        log_event(
                            "suggestion_written",
                            user_id=user_id,
                            run_id=run_id,
                            suggestion_id=sid,
                            type=func_args.get("suggestion_type"),
                        )

                # --- Add tool result to messages ---
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str),
                })

            # --- Trim history (keep system + user context + last N turns) ---
            messages = _trim_history(messages)

        # --- Max API turns exhausted ---
        log_event(
            "advisor_max_turns_hit",
            user_id=user_id,
            run_id=run_id,
            turns=api_turns,
            suggestions_created=len(suggestions_created),
        )
        _finalize_run(
            conn, run_id, started_at, accumulated_cost, total_latency_ms,
            len(suggestions_created), "agent_error",
            error_message="max_api_turns_exceeded",
        )
        return {
            "status": "agent_error",
            "error": "max_api_turns_exceeded",
            "suggestions_created": len(suggestions_created),
            "suggestion_ids": suggestions_created,
        }

    except Exception as exc:
        # Catch-all for unexpected errors
        log_event(
            "advisor_unexpected_error",
            user_id=user_id,
            run_id=run_id,
            error=str(exc),
            suggestions_created=len(suggestions_created),
        )
        _finalize_run(
            conn, run_id, started_at, accumulated_cost, total_latency_ms,
            len(suggestions_created), "agent_error",
            error_message=f"unexpected:{str(exc)[:200]}",
        )
        return {
            "status": "agent_error",
            "error": str(exc),
            "suggestions_created": len(suggestions_created),
            "suggestion_ids": suggestions_created,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _message_to_dict(msg: Any) -> dict[str, Any]:
    """Convert an OpenAI ChatCompletionMessage to a dict for the messages list."""
    d: dict[str, Any] = {"role": msg.role}
    if msg.content:
        d["content"] = msg.content
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


def _trim_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Keep system message + user context message + last HISTORY_WINDOW turns.

    A 'turn' is an assistant message plus its subsequent tool response messages.
    """
    if len(messages) <= 2:
        return messages

    # Always keep first 2 messages (system + user context)
    prefix = messages[:2]
    rest = messages[2:]

    # Count turns: each assistant message starts a new turn
    turns: list[list[dict]] = []
    current_turn: list[dict] = []

    for msg in rest:
        if msg.get("role") == "assistant":
            if current_turn:
                turns.append(current_turn)
            current_turn = [msg]
        else:
            current_turn.append(msg)

    if current_turn:
        turns.append(current_turn)

    # Keep last HISTORY_WINDOW turns
    if len(turns) > HISTORY_WINDOW:
        turns = turns[-HISTORY_WINDOW:]

    # Flatten back
    trimmed = prefix
    for turn in turns:
        trimmed.extend(turn)

    return trimmed


def _finalize_run(
    conn: sqlite3.Connection,
    run_id: str,
    started_at: datetime,
    total_cost: float,
    total_latency_ms: int,
    suggestions_count: int,
    status: str,
    *,
    error_message: str | None = None,
) -> None:
    """Update the run record with final stats."""
    finished_at = datetime.now(timezone.utc)

    # Always update LLM stats
    update_run_llm_stats(
        conn,
        run_id=run_id,
        cache_hits=0,
        cache_misses=0,
        total_cost_usd=total_cost,
        saved_cost_usd=0.0,
        total_latency_ms=total_latency_ms,
    )

    if status == "ok":
        finish_run_ok(
            conn,
            run_id=run_id,
            finished_at=finished_at,
            after_dedupe=0,
            inserted=suggestions_count,
            duplicates=0,
        )
    else:
        finish_run_error(
            conn,
            run_id=run_id,
            finished_at=finished_at,
            error_type=status,
            error_message=error_message or status,
        )

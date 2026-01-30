# Load .env file BEFORE other imports (so env vars are available)
from dotenv import load_dotenv
load_dotenv()

import json
import uuid

from datetime import datetime, timezone, date

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError

from src.middleware import request_id_middleware
from src.logging_utils import log_event
from src.errors import problem

from src.schemas import IngestRequest, RunFeedbackRequest, ItemFeedbackRequest
from src.db import db_conn, get_conn, init_db
from src.repo import (
    insert_news_items, start_run, finish_run_ok, finish_run_error,
    get_latest_run, get_news_items_by_date, get_run_by_day, get_run_by_id,
    get_run_failures_with_sources, get_run_artifacts,
    get_news_item_by_id, get_news_items_by_date_with_ids, get_idempotency_response,
    store_idempotency_response, upsert_run_feedback, upsert_item_feedback,
    get_distinct_dates, get_daily_spend, get_daily_refusal_counts,
    get_all_item_feedback_for_run, get_active_source_weights,
    get_positive_feedback_items, get_all_historical_items,
    create_user, get_user_by_email, get_user_by_id,
    create_session, get_session, delete_session, update_user_last_login,
)
from src.auth import hash_password, verify_password
from src.ai_score import build_tfidf_model, compute_ai_scores
from src.normalize import normalize_and_dedupe
from src.scoring import RankConfig, rank_items
from src.artifacts import render_digest_html
from src.explain import explain_item
from src.views import build_ranked_display_items, build_homepage_data, build_debug_stats


app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/artifacts", StaticFiles(directory="artifacts"), name = "artifacts")

#Register middleware
app.middleware("http")(request_id_middleware)

def render_ui_error(request: Request, status: int, message: str) -> HTMLResponse:
    """Return HTML error for UI routes (not JSON)."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status": status, "message": message},
        status_code=status
    )


# --- Session Middleware (Milestone 4) ---

def get_current_user(request: Request, conn) -> dict | None:
    """
    Extract user from session cookie.

    Returns:
        User dict or None if not logged in or session expired.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    session = get_session(conn, session_id=session_id)
    if not session:
        return None

    return get_user_by_id(conn, user_id=session["user_id"])


def require_admin(request: Request, conn) -> dict:
    """
    Require admin role for access.

    Returns:
        User dict if admin.

    Raises:
        HTTPException 401 if not logged in.
        HTTPException 403 if not admin.
    """
    user = get_current_user(request, conn)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# --- Auth Endpoints (Milestone 4) ---

@app.post("/auth/register")
def auth_register(request: Request, email: str, password: str):
    """
    Register a new user (admin-only, invite-based system).

    Requires admin session to create new users.
    """
    with db_conn() as conn:
        # Require admin for user creation (invite-only system)
        require_admin(request, conn)

        # Check if email already exists
        existing = get_user_by_email(conn, email=email)
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        # Hash password and create user
        password_hash = hash_password(password)
        user_id = create_user(conn, email=email, password_hash=password_hash, role="user")

    return {"status": "created", "user_id": user_id, "email": email}


@app.post("/auth/login")
def auth_login(request: Request, email: str, password: str):
    """
    Log in with email and password.

    Sets session cookie on success.
    """
    with db_conn() as conn:
        user = get_user_by_email(conn, email=email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.get("password_hash"):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Create session and update last login
        session_id = create_session(conn, user_id=user["user_id"], expires_hours=24)
        update_user_last_login(conn, user_id=user["user_id"])

    # Set cookie and return success
    response = JSONResponse(content={
        "status": "logged_in",
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
    })
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=24 * 60 * 60,  # 24 hours
    )
    return response


@app.post("/auth/logout")
def auth_logout(request: Request):
    """
    Log out (invalidate session).

    Clears session cookie.
    """
    session_id = request.cookies.get("session_id")

    if session_id:
        with db_conn() as conn:
            delete_session(conn, session_id=session_id)

    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(key="session_id")
    return response


@app.get("/auth/me")
def auth_me(request: Request):
    """
    Get current user info.

    Returns user info if logged in, 401 if not.
    """
    with db_conn() as conn:
        user = get_current_user(request, conn)

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
    }


@app.get("/")
def root(request: Request):
    """Redirect to user's most recent digest (customer landing page)."""
    with db_conn() as conn:
        user = get_current_user(request, conn)
        user_id = user["user_id"] if user else None

        # Get latest run for this user
        latest_run = get_latest_run(conn, user_id=user_id)

    if latest_run and latest_run.get("started_at"):
        # Extract date from started_at (YYYY-MM-DD from ISO timestamp)
        latest_date = latest_run["started_at"][:10]
        return RedirectResponse(url=f"/ui/date/{latest_date}", status_code=302)

    # No runs yet for this user - show welcome page
    return templates.TemplateResponse(
        request,
        "welcome.html",
        {}
    )

@app.get("/api/history")
def api_history(request: Request, limit: int = 20):
    """Return recent dates with ratings for nav menu."""
    with db_conn() as conn:
        user = get_current_user(request, conn)
        user_id = user["user_id"] if user else None
        data = build_homepage_data(conn, page=1, per_page=limit, user_id=user_id)
    return {"dates": data["dates"]}


@app.get("/ui/history", response_class=HTMLResponse)
def ui_history(request: Request, page: int = 1):
    """History page showing all past digests."""
    with db_conn() as conn:
        user = get_current_user(request, conn)
        user_id = user["user_id"] if user else None
        data = build_homepage_data(conn, page=page, per_page=15, user_id=user_id)

    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "dates": data["dates"],
            "pagination": data["pagination"],
        }
    )


@app.get("/ui/config", response_class=HTMLResponse)
def ui_config(request: Request):
    """Config page (placeholder for future preferences)."""
    return templates.TemplateResponse(
        request,
        "config.html",
        {}
    )


@app.get("/ui/settings", response_class=HTMLResponse)
def ui_settings(request: Request):
    """Settings page (placeholder)."""
    return templates.TemplateResponse(
        request,
        "settings.html",
        {}
    )


@app.get("/health")
def health(request: Request):
    request_id = request.state.request_id
    log_event("health_check", request_id=request_id)
    return {"status": "ok"}

 

@app.post("/ingest/raw")
def ingest_raw(payload: IngestRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    run_id = uuid.uuid4().hex
    request.state.run_id = run_id
    
    received = len(payload.items)
    deduped = normalize_and_dedupe(payload.items)
    after_dedupe = len(deduped)
    python_dupes = received - after_dedupe

    log_event("ingest_started", request_id=request_id, run_id=run_id, count=received)
    started_at = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id, started_at, received=received)

        result = insert_news_items(conn, deduped)

        inserted = result["inserted"]
        db_ignored = result["duplicates"]
        duplicates = python_dupes + db_ignored

        finished_at = datetime.now(timezone.utc).isoformat()

        finish_run_ok(conn, run_id, finished_at, after_dedupe=after_dedupe, inserted=inserted, duplicates=duplicates,)

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        try:
            finish_run_error(conn, run_id, finished_at, error_type=type(exc).__name__, error_message=str(exc))

        finally:
            conn.close()
        raise
    else:
        conn.close()


    out = {"received": received, "after_dedupe": after_dedupe, "inserted": inserted, "duplicates": duplicates, "run_id": run_id,
    }

    log_event("ingest_finished", request_id=request_id, run_id=run_id, inserted=out["inserted"], duplicates=out["duplicates"],
    )
    return out


@app.get("/runs/latest")
def latest_run():
    with db_conn() as conn:
        latest = get_latest_run(conn)

    if latest is None:
        raise HTTPException(status_code=404, detail="No runs found")

    return latest


@app.post("/rank/{date_str}")
def rank_for_date(date_str: str, cfg: RankConfig, top_n: int =10):
    try:
        date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    if top_n < 1:
        raise HTTPException(status_code=400, detail="top_n must be >= 1")

    now = datetime.fromisoformat(f"{date_str}T23:59:59+00:00")

    with db_conn() as conn:
        items = get_news_items_by_date(conn, day=date_str)

        # Compute ai_scores (Milestone 3c)
        # Fit TF-IDF on all historical items (richer vocabulary), similarity against positives only
        corpus = get_all_historical_items(conn, as_of_date=date_str)
        positives = get_positive_feedback_items(conn, as_of_date=date_str)
        model = build_tfidf_model(corpus) if corpus else None
        item_dicts = [{"url": str(it.url), "title": it.title, "evidence": it.evidence} for it in items]
        scores = compute_ai_scores(model, positives, item_dicts)
        ai_scores = {item_dicts[i]["url"]: scores[i] for i in range(len(scores))}

    ranked = rank_items(items, now=now, top_n=top_n, cfg=cfg, ai_scores=ai_scores)
    return {
        "date": date_str,
        "top_n": top_n,
        "count": len(ranked),
        "items": [it.model_dump() for it in ranked],
    }


@app.get("/digest/{date_str}", response_class=HTMLResponse)
def get_digest(date_str: str, top_n: int = 10) -> HTMLResponse:
    # 1) validate date + deterministic now
    try:
        day = date.fromisoformat(date_str).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")
    except TypeError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

    if top_n < 1:
        raise HTTPException(status_code=400, detail="top_n must be >= 1")

    now = datetime.fromisoformat(f"{day}T23:59:59+00:00")

    # 2) DB reads
    with db_conn() as conn:
        run = get_run_by_day(conn, day=day)
        items = get_news_items_by_date(conn, day=day)

        # If literally nothing exists, return a 404 (ProblemDetails JSON handled by middleware)
        if run is None and not items:
            raise HTTPException(status_code=404, detail="No data found for this day")

        # 3) rank + explain with dynamic weights (Milestone 3b)
        source_weights = get_active_source_weights(conn)
        cfg = RankConfig(source_weights=source_weights)

        # Compute ai_scores (Milestone 3c)
        # Fit TF-IDF on all historical items (richer vocabulary), similarity against positives only
        corpus = get_all_historical_items(conn, as_of_date=day)
        positives = get_positive_feedback_items(conn, as_of_date=day)
        model = build_tfidf_model(corpus) if corpus else None
        item_dicts = [{"url": str(it.url), "title": it.title, "evidence": it.evidence} for it in items]
        scores = compute_ai_scores(model, positives, item_dicts)
        ai_scores = {item_dicts[i]["url"]: scores[i] for i in range(len(scores))}

    ranked = rank_items(items, now=now, top_n=top_n, cfg=cfg, ai_scores=ai_scores)
    explanations = [explain_item(it, now=now, cfg=cfg) for it in ranked]

    # 4) render
    html_text = render_digest_html(
        day=day,
        run=run,
        ranked_items=ranked,
        explanations=explanations,
        cfg=cfg,
        now=now,
        top_n=top_n,
    )
    return HTMLResponse(content=html_text, status_code=200)

@app.get("/ui/date/{date_str}", response_class=HTMLResponse)
def ui_date(request: Request, date_str: str, top_n: int = 10):
    # Validate date
    try:
        day = date.fromisoformat(date_str).isoformat()
    except ValueError:
        return render_ui_error(request, 400, "Invalid date format. Expected YYYY-MM-DD.")

    if top_n < 1:
        return render_ui_error(request, 400, "top_n must be >= 1")

    now = datetime.fromisoformat(f"{day}T23:59:59+00:00")

    with db_conn() as conn:
        # Get user for scoped queries (Milestone 4)
        user = get_current_user(request, conn)
        user_id = user["user_id"] if user else None

        # Load dynamic source weights (user-scoped, Milestone 3b + 4)
        source_weights = get_active_source_weights(conn, user_id=user_id)
        cfg = RankConfig(source_weights=source_weights)

        items_with_ids = get_news_items_by_date_with_ids(conn, day=day)
        run = get_run_by_day(conn, day=day, user_id=user_id)

        if not items_with_ids:
            return render_ui_error(request, 404, f"No items found for {day}.")

        # Compute ai_scores (user-scoped, Milestone 3c + 4)
        corpus = get_all_historical_items(conn, as_of_date=day)
        positives = get_positive_feedback_items(conn, as_of_date=day, user_id=user_id)
        model = build_tfidf_model(corpus) if corpus else None
        items_only = [item for _, item in items_with_ids]
        item_dicts = [{"url": str(it.url), "title": it.title, "evidence": it.evidence} for it in items_only]
        scores = compute_ai_scores(model, positives, item_dicts)
        ai_scores = {item_dicts[i]["url"]: scores[i] for i in range(len(scores))}

        display_items = build_ranked_display_items(conn, items_with_ids, now, cfg, top_n, ai_scores=ai_scores)

        # Get existing feedback for this run (user-scoped)
        run_id = run.get("run_id") if run else None
        item_feedback = {}
        if run_id:
            item_feedback = get_all_item_feedback_for_run(conn, run_id=run_id, user_id=user_id)

    # Format run timestamp for display (customer-safe)
    run_status = None
    if run:
        finished_at = run.get("finished_at")
        if finished_at:
            try:
                dt = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                run_status = {
                    "ok": run.get("status") == "ok",
                    "updated_at": dt.strftime("%b %d, %Y at %I:%M %p").replace(" 0", " "),
                }
            except (ValueError, AttributeError):
                pass

    return templates.TemplateResponse(
        request,
        "date.html",
        {"day": day, "items": display_items, "count": len(display_items), "run": run, "run_id": run_id, "run_status": run_status, "item_feedback": item_feedback}
    )

@app.get("/ui/item/{item_id}", response_class=HTMLResponse)
def ui_item(request: Request, item_id: int):
    if item_id < 1:
        return render_ui_error(request, 400, "item_id must be >= 1")

    with db_conn() as conn:
        # Get user for scoped queries (Milestone 4)
        user = get_current_user(request, conn)
        user_id = user["user_id"] if user else None

        result = get_news_item_by_id(conn, item_id=item_id)

        if result is None:
            return render_ui_error(request, 404, f"Item {item_id} not found.")

        item, day = result
        now = datetime.fromisoformat(f"{day}T23:59:59+00:00")

        # Load dynamic source weights (user-scoped, Milestone 3b + 4)
        source_weights = get_active_source_weights(conn, user_id=user_id)
        cfg = RankConfig(source_weights=source_weights)

    expl = explain_item(item, now=now, cfg=cfg)

    return templates.TemplateResponse(
        request,
        "item.html",
        {"item_id": item_id, "item": item, "expl": expl, "day": day}
    )

@app.get("/debug/run/{run_id}")
def debug_run(run_id: str, request: Request):
    request_id = request.state.request_id

    with db_conn() as conn:
        # Admin only (Milestone 4)
        require_admin(request, conn)

        run = get_run_by_id(conn, run_id=run_id)
        failures_data = get_run_failures_with_sources(conn, run_id=run_id)
        artifact_paths = get_run_artifacts(conn, run_id=run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    #Build counts dict
    counts = {
        "received": run.get("received"),
        "after_dedupe": run.get("after_dedupe"),
        "inserted": run.get("inserted"),
        "duplicates": run.get("duplicates"),
    }

    # Build LLM stats dict
    cache_hits = run.get("llm_cache_hits", 0) or 0
    cache_misses = run.get("llm_cache_misses", 0) or 0
    total_calls = cache_hits + cache_misses
    cache_hit_rate = round(cache_hits / total_calls * 100, 1) if total_calls > 0 else 0.0

    llm_stats = {
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": cache_hit_rate,
        "total_cost_usd": run.get("llm_total_cost_usd", 0.0) or 0.0,
        "saved_cost_usd": run.get("llm_saved_cost_usd", 0.0) or 0.0,
        "total_latency_ms": run.get("llm_total_latency_ms", 0) or 0,
    }

    return {
        "run_id": run.get("run_id"),
        "run_type": run.get("run_type"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "counts": counts,
        "llm_stats": llm_stats,
        "failures_by_code": failures_data["by_code"],
        "failed_sources": failures_data["failed_sources"],
        "artifact_paths": artifact_paths,
        "request_id": request_id,
    }


@app.get("/debug/http_error")
def debug_http_error(request: Request):
    with db_conn() as conn:
        require_admin(request, conn)
    raise HTTPException(status_code=400, detail="Bad request (debug)")


@app.get("/debug/crash")
def debug_crash(request: Request):
    with db_conn() as conn:
        require_admin(request, conn)
    raise RuntimeError("boom")


@app.get("/debug/stats")
def debug_stats(request: Request):
    """Database stats for operational debugging - scoped to last 10 dates."""
    import os
    request_id = request.state.request_id
    db_path = os.environ.get("NEWS_DB_PATH", "./data/news.db")

    with db_conn() as conn:
        # Admin only (Milestone 4)
        require_admin(request, conn)

        stats = build_debug_stats(conn, date_limit=10)

    return {
        "db_path": db_path,
        "items_last_10_dates": stats["items_count"],
        "runs_last_10_dates": stats["runs_count"],
        "items_by_date": stats["items_by_date"],
        "recent_runs": stats["recent_runs"],
        "request_id": request_id,
    }


@app.get("/debug/costs")
def debug_costs(request: Request, date: str | None = None):
    """LLM cost stats for operational debugging.

    Args:
        date: Optional YYYY-MM-DD date. Defaults to today.

    Returns:
        Daily spend, cap, remaining budget, and refusal counts.
    """
    import os
    from datetime import date as date_type

    request_id = request.state.request_id

    # Default to today if no date provided
    if date is None:
        date = date_type.today().isoformat()

    # Get cap from env var (same default as llm_openai.py)
    daily_cap = float(os.environ.get("LLM_DAILY_CAP_USD", "1.00"))

    with db_conn() as conn:
        # Admin only (Milestone 4)
        require_admin(request, conn)

        daily_spend = get_daily_spend(conn, day=date)
        refusal_counts = get_daily_refusal_counts(conn, day=date)

    remaining = max(0.0, daily_cap - daily_spend)

    return {
        "date": date,
        "daily_spend_usd": round(daily_spend, 6),
        "daily_cap_usd": daily_cap,
        "remaining_usd": round(remaining, 6),
        "budget_exceeded": daily_spend >= daily_cap,
        "refusal_counts": refusal_counts,
        "request_id": request_id,
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = request.state.request_id
    run_id = getattr(request.state, "run_id", None)
    payload = problem(
        status=exc.status_code,
        code="http_error",
        message=str(exc.detail),
        request_id=rid,
        run_id=run_id,
    )
    log_event("http_error", request_id=rid, run_id=run_id, status=exc.status_code, message=str(exc.detail))
    resp = JSONResponse(status_code=exc.status_code, content=payload.model_dump(exclude_none=True))
    resp.headers["X-Request-ID"] = rid
    return resp


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = request.state.request_id
    run_id = getattr(request.state, "run_id", None)
    payload = problem(
        status=500,
        code="internal_error",
        message="Internal server error",
        request_id=rid,
        run_id=run_id,
    )
    # Don't leak details to the client, but do log them
    log_event("internal_error", request_id=rid, run_id=run_id, error_type=type(exc).__name__)
    resp = JSONResponse(status_code=500, content=payload.model_dump(exclude_none=True))
    resp.headers["X-Request-ID"] = rid
    return resp

@app.post("/feedback/run")
async def submit_run_feedback(
    request: Request,
    body: RunFeedbackRequest,
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """
    Submit feedback for overall digest (1-5 star rating).
    Submitting again for the same run_id UPDATES the existing feedback.
    Supports idempotency: Include X-Idempotency-Key header for safe retries.
    """
    request_id = request.state.request_id
    with db_conn() as conn:
        # 1. Check idempotency key FIRST (prevents double-click duplicates)
        if idempotency_key:
            cached = get_idempotency_response(conn, key=idempotency_key)
            if cached:
                log_event("run_feedback_idempotency_hit",
                    request_id=request_id,
                    idempotency_key=idempotency_key
                )
                return JSONResponse(
                    status_code=200,
                    content=json.loads(cached["response_json"]),
                    headers={"X-Request-ID": request_id}
                )

        # 2. Process: Upsert feedback (only if not cached)
        now = datetime.now(timezone.utc).isoformat()
        feedback_id = upsert_run_feedback(
            conn,
            run_id=body.run_id,
            rating=body.rating,
            comment=body.comment,
            created_at=now,
            updated_at=now,
        )

        response_data = {
            "status": "saved",
            "feedback_id": feedback_id,
            "run_id": body.run_id,
            "rating": body.rating,
            "request_id": request_id,
        }

        # 3. Store idempotency key (after successful processing)
        if idempotency_key:
            store_idempotency_response(
                conn,
                key=idempotency_key,
                endpoint="/feedback/run",
                response_json=json.dumps(response_data),
                created_at=now,
            )

        log_event("run_feedback_saved",
            request_id=request_id,
            feedback_id=feedback_id,
            run_id=body.run_id,
            rating=body.rating,
        )

        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"X-Request-ID": request_id}
        )


@app.post("/feedback/item")
async def submit_item_feedback(
    request: Request,
    body: ItemFeedbackRequest,
    idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
):
    """
    Submit feedback for a specific item (thumbs up/down).
    Submitting again for the same (run_id, item_url) UPDATES the existing feedback.
    Supports idempotency: Include X-Idempotency-Key header for safe retries.
    """
    request_id = request.state.request_id
    with db_conn() as conn:
        # Check idempotency key
        if idempotency_key:
            cached = get_idempotency_response(conn, key=idempotency_key)
            if cached:
                log_event("item_feedback_idempotency_hit",
                    request_id=request_id,
                    idempotency_key=idempotency_key
                )
                return JSONResponse(
                    status_code=200,
                    content=json.loads(cached["response_json"]),
                    headers={"X-Request-ID": request_id}
                )

        # Upsert feedback (insert or update)
        now = datetime.now(timezone.utc).isoformat()
        useful_int = 1 if body.useful else 0
        feedback_id = upsert_item_feedback(
            conn,
            run_id=body.run_id,
            item_url=body.item_url,
            useful=useful_int,
            reason_tag=body.reason_tag,
            created_at=now,
            updated_at=now,
        )

        response_data = {
            "status": "saved",
            "feedback_id": feedback_id,
            "run_id": body.run_id,
            "item_url": body.item_url,
            "useful": body.useful,
            "reason_tag": body.reason_tag,
            "request_id": request_id,
        }

        # Store idempotency key
        if idempotency_key:
            store_idempotency_response(
                conn,
                key=idempotency_key,
                endpoint="/feedback/item",
                response_json=json.dumps(response_data),
                created_at=now,
            )

        log_event("item_feedback_saved",
            request_id=request_id,
            feedback_id=feedback_id,
            run_id=body.run_id,
            item_url=body.item_url,
            useful=body.useful,
        )

        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"X-Request-ID": request_id}
        )



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return ProblemDetails for Pydantic validation errors."""
    rid = request.state.request_id
    run_id = getattr(request.state, "run_id", None)

    # Extract first error for a clean message
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = ".".join(str(x) for x in first.get("loc", []))  #e.g., "body.rating"
        msg = first.get("msg", "Validation error")
        message = f"{loc}: {msg}"
    else:
        message = "Validation error"
    
    payload = problem(
        status=422,
        code="validation_error",
        message=message,
        request_id=rid,
        run_id=run_id,
    )

    log_event("validation_error", request_id=rid, message=message)
    resp = JSONResponse(status_code=422, content=payload.model_dump(exclude_none=True))
    resp.headers["X-Request-ID"] = rid
    return resp
    

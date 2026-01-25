# Load .env file BEFORE other imports (so env vars are available)
from dotenv import load_dotenv
load_dotenv()

import json
import uuid
import html as html_lib

from datetime import datetime, timezone, date

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError

from src.middleware import request_id_middleware
from src.logging_utils import log_event
from src.errors import problem

from src.schemas import IngestRequest, RunFeedbackRequest, ItemFeedbackRequest
from src.db import get_conn, init_db
from src.repo import (
    insert_news_items, start_run, finish_run_ok, finish_run_error,
    get_latest_run, get_news_items_by_date, get_run_by_day, get_run_by_id,
    get_run_failures_with_sources, get_run_artifacts,
    get_news_item_by_id, get_news_items_by_date_with_ids, get_idempotency_response,
    store_idempotency_response, upsert_run_feedback, upsert_item_feedback,
    get_run_feedback, get_item_feedback,
)
from src.normalize import normalize_and_dedupe
from src.scoring import RankConfig, rank_items
from src.artifacts import render_digest_html
from src.explain import explain_item
from src.views import build_ranked_display_items


app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.mount("/artifacts", StaticFiles(directory="artifacts"), name = "artifacts")

#Register middleware
app.middleware("http")(request_id_middleware)

def render_ui_error(request: Request, status: int, message: str) -> HTMLResponse:
    """Return HTML error for UI routes (not JSON)."""
    safe_msg = html_lib.escape(message)
    content = f"""<!DOCTYPE html>
<html><head><title>Error {status}</title></head>
<body style="font-family: sans-serif; margin: 24px;">
<h1>Error {status}</h1>
<p>{safe_msg}</p>
<p><a href="/">← Home</a></p>
</body></html>"""
    return HTMLResponse(content=content, status_code=status)

@app.get("/", response_class=HTMLResponse)
def root(request: Request, page: int = 1):
    """Home page with tabbed navigation."""
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_conn()
    try:
        init_db(conn)

        # Get total count of dates for pagination
        total_dates = conn.execute(
            "SELECT COUNT(DISTINCT substr(published_at, 1, 10)) FROM news_items"
        ).fetchone()[0]

        # Get dates with pagination
        dates_rows = conn.execute(
            "SELECT DISTINCT substr(published_at, 1, 10) as day FROM news_items ORDER BY day DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()
        dates = [row[0] for row in dates_rows]

        # Get run_id and saved rating for each date
        date_runs = {}
        date_ratings = {}
        for d in dates:
            run_row = conn.execute(
                "SELECT run_id FROM runs WHERE substr(started_at, 1, 10) = ? ORDER BY started_at DESC LIMIT 1",
                (d,)
            ).fetchone()
            run_id = run_row[0] if run_row else None
            date_runs[d] = run_id
            # Get saved rating
            if run_id:
                feedback = get_run_feedback(conn, run_id=run_id)
                date_ratings[d] = feedback["rating"] if feedback else 0
            else:
                date_ratings[d] = 0

        # Get recent runs
        runs_rows = conn.execute(
            "SELECT run_id, substr(started_at, 1, 10) as day, status, run_type, received, inserted FROM runs ORDER BY started_at DESC LIMIT 10"
        ).fetchall()
        runs = [{"run_id": r[0], "day": r[1], "status": r[2], "run_type": r[3], "received": r[4], "inserted": r[5]} for r in runs_rows]
    finally:
        conn.close()

    # Pagination
    total_pages = (total_dates + per_page - 1) // per_page if total_dates > 0 else 1
    has_prev = page > 1
    has_next = page < total_pages

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "dates": dates,
            "date_runs": date_runs,
            "date_ratings": date_ratings,
            "runs": runs,
            "page": page,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next,
        }
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
        finished_at = datetime.now(timezone.utc).isoformat
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
    conn = get_conn()
    try:
        init_db(conn)
        latest = get_latest_run(conn)
    finally:
        conn.close()

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

    conn = get_conn()
    try:
        init_db(conn)
        items = get_news_items_by_date(conn, day=date_str)

    finally:
        conn.close()
    
    ranked = rank_items(items, now=now, top_n=top_n, cfg=cfg)
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
    conn = get_conn()
    try:
        init_db(conn)

        run = get_run_by_day(conn, day=day)
        items = get_news_items_by_date(conn, day=day)

        # If literally nothing exists, return a 404 (ProblemDetails JSON handled by middleware)
        if run is None and not items:
            raise HTTPException(status_code=404, detail="No data found for this day")

        # 3) rank + explain (use default config for now)
        cfg = RankConfig()
        ranked = rank_items(items, now=now, top_n=top_n, cfg=cfg)
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

    finally:
        conn.close()

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
    cfg = RankConfig()

    conn = get_conn()
    try:
        init_db(conn)
        items_with_ids = get_news_items_by_date_with_ids(conn, day=day)
        run = get_run_by_day(conn, day=day)

        if not items_with_ids:
            return render_ui_error(request, 404, f"No items found for {day}.")

        display_items = build_ranked_display_items(conn, items_with_ids, now, cfg, top_n)
    finally:
        conn.close()

    run_id = run.get("run_id") if run else None

    return templates.TemplateResponse(
        request,
        "date.html",
        {"day": day, "items": display_items, "count": len(display_items), "run": run, "run_id": run_id}
    )

@app.get("/ui/item/{item_id}", response_class=HTMLResponse)
def ui_item(request: Request, item_id: int):
    if item_id < 1:
        return render_ui_error(request, 400, "item_id must be >= 1")

    conn = get_conn()
    try:
        init_db(conn)
        result = get_news_item_by_id(conn, item_id=item_id)
    finally:
        conn.close()

    if result is None:
        return render_ui_error(request, 404, f"Item {item_id} not found.")

    item, day = result
    now = datetime.fromisoformat(f"{day}T23:59:59+00:00")
    cfg = RankConfig()
    expl = explain_item(item, now=now, cfg=cfg)

    return templates.TemplateResponse(
        request,
        "item.html",
        {"item_id": item_id, "item": item, "expl": expl, "day": day}
    )

@app.get("/debug/run/{run_id}")
def debug_run(run_id: str, request: Request):
    request_id = request.state.request_id

    conn = get_conn()
    try:
        init_db(conn)
        run = get_run_by_id(conn, run_id=run_id)
        failures_data = get_run_failures_with_sources(conn, run_id=run_id)
        artifact_paths = get_run_artifacts(conn, run_id=run_id)
    finally:
        conn.close()

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    started_at = run.get("started_at", "") or ""
    day = started_at[:10] if len(started_at)>= 10 else ""
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
def debug_http_error():
    raise HTTPException(status_code=400, detail="Bad request (debug)")


@app.get("/debug/crash")
def debug_crash():
    raise RuntimeError("boom")


@app.get("/debug/stats")
def debug_stats(request: Request):
    """Database stats for operational debugging - scoped to last 10 dates."""
    import os
    request_id = request.state.request_id
    db_path = os.environ.get("NEWS_DB_PATH", "./data/news.db")

    conn = get_conn()
    try:
        init_db(conn)

        # Get last 10 dates with items
        dates_with_items = conn.execute(
            "SELECT DISTINCT substr(published_at, 1, 10) as day FROM news_items ORDER BY day DESC LIMIT 10"
        ).fetchall()
        dates_list = [row[0] for row in dates_with_items]

        # Items count - only from last 10 dates
        if dates_list:
            placeholders = ",".join("?" * len(dates_list))
            items_count = conn.execute(
                f"SELECT COUNT(*) FROM news_items WHERE substr(published_at, 1, 10) IN ({placeholders})",
                dates_list
            ).fetchone()[0]
        else:
            items_count = 0

        # Runs count - only from last 10 dates
        if dates_list:
            placeholders = ",".join("?" * len(dates_list))
            runs_count = conn.execute(
                f"SELECT COUNT(*) FROM runs WHERE substr(started_at, 1, 10) IN ({placeholders})",
                dates_list
            ).fetchone()[0]
        else:
            runs_count = 0

        # Items per date breakdown
        items_by_date = []
        for day in dates_list:
            count = conn.execute(
                "SELECT COUNT(*) FROM news_items WHERE substr(published_at, 1, 10) = ?",
                (day,)
            ).fetchone()[0]
            items_by_date.append({"date": day, "items": count})

        # Recent runs (last 10)
        recent_runs = conn.execute(
            "SELECT run_id, substr(started_at, 1, 10) as day, status, run_type FROM runs ORDER BY started_at DESC LIMIT 10"
        ).fetchall()
        runs_list = [{"run_id": r[0], "day": r[1], "status": r[2], "run_type": r[3]} for r in recent_runs]

    finally:
        conn.close()

    return {
        "db_path": db_path,
        "items_last_10_dates": items_count,
        "runs_last_10_dates": runs_count,
        "items_by_date": items_by_date,
        "recent_runs": runs_list,
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
    conn = get_conn()
    try:
        init_db(conn)

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
    finally:
        conn.close()


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
    conn = get_conn()
    try:
        init_db(conn)

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
            created_at=now,
            updated_at=now,
        )

        response_data = {
            "status": "saved",
            "feedback_id": feedback_id,
            "run_id": body.run_id,
            "item_url": body.item_url,
            "useful": body.useful,
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
    finally:
        conn.close()



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
    
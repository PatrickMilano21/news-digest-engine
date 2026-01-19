import uuid
from datetime import datetime, timezone, date

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.middleware import request_id_middleware
from src.logging_utils import log_event
from src.errors import problem

from src.schemas import IngestRequest
from src.db import get_conn, init_db
from src.repo import insert_news_items, start_run, finish_run_ok, finish_run_error, get_latest_run, get_news_items_by_date, get_run_by_day, get_run_by_id, get_run_failures_breakdown, get_run_artifacts
from src.normalize import normalize_and_dedupe
from src.scoring import RankConfig, rank_items
from src.artifacts import render_digest_html
from src.explain import explain_item


app = FastAPI()

app.mount("/artifacts", StaticFiles(directory="artifacts"), name = "artifacts")

#Register middleware
app.middleware("http")(request_id_middleware)

@app.get("/")
def root():
    return{"service": "news-digest-engine", "try": ["/health", "/docs"]}

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
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

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
def ui_for_date(date_str: str) -> HTMLResponse:
    try:
        day = date.fromisoformat(date_str).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

    conn = get_conn()
    try:
        init_db(conn)
        run = get_run_by_day(conn, day=day)
    finally:
        conn.close()

    digest_path = f"/artifacts/digest_{day}.html"
    latest_path = "/runs/latest"

    debug_link = ""
    if run is not None:
        rid = run.get("run_id", "")
        if rid:
            debug_link = f'<div><a href="/debug/run/{rid}">Debug run {rid}</a></div>'

    html_text = f"""
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>UI {day}</title></head>
      <body style="font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px;">
        <h2>UI for {day}</h2>
        <div><a href="{digest_path}">Open digest artifact</a></div>
        <div><a href="{latest_path}">View latest run (JSON)</a></div>
        {debug_link}
      </body>
    </html>
    """
    return HTMLResponse(content=html_text, status_code=200)


@app.get("/debug/run/{run_id}")
def debug_run(run_id: str, request: Request):
    request_id = request.state.request_id

    conn = get_conn()
    try:
        init_db(conn)
        run = get_run_by_id(conn, run_id=run_id)
        breakdown = get_run_failures_breakdown(conn, run_id=run_id)
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

    return {
        "run_id": run.get("run_id"),
        "run_type": run.get("run_type"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "counts": counts,
        "failures_by_code": breakdown,
        "artifact_paths": artifact_paths,
        "request_id": request_id,
    }


@app.get("/debug/http_error")
def debug_http_error():
    raise HTTPException(status_code=400, detail="Bad request (debug)")


@app.get("/debug/crash")
def debug_crash():
    raise RuntimeError("boom")



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

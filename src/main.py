import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from src.middleware import request_id_middleware
from src.logging_utils import log_event
from src.errors import problem

from src.schemas import IngestRequest
from src.db import get_conn, init_db
from src.repo import insert_news_items, start_run, finish_run_ok, finish_run_error, get_latest_run
from src.normalize import normalize_and_dedupe




app = FastAPI()

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

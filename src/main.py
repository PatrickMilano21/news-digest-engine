from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from src.middleware import request_id_middleware
from src.logging_utils import log_event
from src.errors import problem

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

@app.get("/debug/http_error")
def debug_http_error():
    raise HTTPException(status_code=400, detail="Bad request (debug)")


@app.get("/debug/crash")
def debug_crash():
    raise RuntimeError("boom")



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = request.state.request_id
    payload = problem(
        status=exc.status_code,
        code="http_error",
        message=str(exc.detail),
        request_id=rid,
    )
    log_event("http_error", request_id=rid, status=exc.status_code, message=str(exc.detail))
    resp = JSONResponse(status_code=exc.status_code, content=payload.model_dump())
    resp.headers["X-Request-ID"] = rid
    return resp


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = request.state.request_id
    payload = problem(
        status=500,
        code="internal_error",
        message="Internal server error",
        request_id=rid,
    )
    # Don't leak details to the client, but do log them
    log_event("internal_error", request_id=rid, error_type=type(exc).__name__)
    resp = JSONResponse(status_code=500, content=payload.model_dump())
    resp.headers["X-Request-ID"] = rid
    return resp

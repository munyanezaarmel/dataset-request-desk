import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .db import engine
from .logging_conf import setup_logging
from .routers import analytics, assignments, auth, episodes, imports, requests, users



setup_logging()
logger = logging.getLogger("app.request")

app = FastAPI(title="Dataset Request Desk")

ROUTERS = (
    auth.router,
    users.router,
    requests.router,
    assignments.router,
    episodes.router,
    imports.router,
    analytics.router,
)
for router in ROUTERS:
    app.include_router(router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Runs around EVERY request and writes exactly one log line."""
    start = time.perf_counter()
    status = 500  # if something crashes, this is what we log
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    # set by get_current_user() once the caller is authenticated
                    "user_id": getattr(request.state, "user_id", None),
                }
            },
        )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """Anything unexpected: log the full traceback, tell the client nothing internal."""
    logging.getLogger("app.error").exception("unhandled error")
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


@app.get("/health")
def health():
    """Liveness + database check. 200 = fine, 503 = database unreachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)
    return {"status": "ok"}

"""
Structured request/error logging for the AgriFlow API.

One JSON object per line, so the log is greppable by hand and parseable by any
log shipper without a custom regex. Emitted to stderr (which is what Hugging
Face Spaces and Docker capture) and, when AGRIFLOW_LOG_FILE is set, appended to
that file as well so a run can be archived as evidence.

PRIVACY: the WhatsApp webhook receives phone numbers. Nothing here ever writes a
raw sender. Request bodies are not logged at all, and the only user-linked value
that may appear is the salted hash the server already computes elsewhere.

Env:
    AGRIFLOW_LOG_FILE   optional path to append JSON lines to
    AGRIFLOW_LOG_LEVEL  default INFO
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
import uuid
from typing import Any, Dict

LOGGER_NAME = "agriflow.api"

# Query params that must never reach the log verbatim.
_REDACT_PARAMS = {"phone", "sender", "from", "token", "api_key", "key"}


class JsonLineFormatter(logging.Formatter):
    """Renders a record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "event": record.getMessage(),
        }
        # Anything attached via logger.info(..., extra={...}) rides along.
        for key, value in getattr(record, "context", {}).items():
            payload[key] = value
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            payload["error_type"] = exc_type.__name__ if exc_type else None
            payload["error"] = str(exc_value)
            payload["traceback"] = "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            ).strip().splitlines()[-12:]
        return json.dumps(payload, ensure_ascii=False)


def get_logger() -> logging.Logger:
    """Configure once, return the shared logger."""
    logger = logging.getLogger(LOGGER_NAME)
    if getattr(logger, "_agriflow_configured", False):
        return logger

    logger.setLevel(os.getenv("AGRIFLOW_LOG_LEVEL", "INFO").upper())
    logger.propagate = False

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(JsonLineFormatter())
    logger.addHandler(stream)

    log_file = os.getenv("AGRIFLOW_LOG_FILE")
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JsonLineFormatter())
        logger.addHandler(file_handler)

    logger._agriflow_configured = True  # type: ignore[attr-defined]
    return logger


def log(level: int, event: str, exc_info=None, **context: Any) -> None:
    """logger.log() with the context dict the formatter knows how to unpack."""
    get_logger().log(level, event, exc_info=exc_info, extra={"context": context})


def _safe_query(request) -> Dict[str, str]:
    return {
        k: ("<redacted>" if k.lower() in _REDACT_PARAMS else v)
        for k, v in request.query_params.items()
    }


def install(app) -> None:
    """
    Attach request logging and an unhandled-exception handler to a FastAPI app.

    Every request produces exactly one line. Requests that raise produce an
    ERROR line carrying the exception type and the tail of the traceback, then
    a 500 whose body contains the request_id so a user report can be tied back
    to the exact log line.
    """
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def _log_requests(request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            log(
                logging.ERROR,
                "request.failed",
                exc_info=sys.exc_info(),
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                query=_safe_query(request),
                duration_ms=duration_ms,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "request_id": request_id,
                    "detail": "Terjadi kesalahan di server. Sertakan request_id saat melapor.",
                },
            )

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        log(
            level,
            "request.completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=_safe_query(request),
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response

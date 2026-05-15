"""
FastAPI app — Twilio WhatsApp webhook + health endpoint.

Endpoints:
    GET  /health              — liveness check, returns engine + bot status
    POST /whatsapp            — Twilio webhook (form-encoded); returns TwiML XML
    POST /chat                — debug JSON endpoint (no Twilio); useful for curl

Run locally:
    uvicorn whatsapp_bot.server:app --reload --port 8000
"""

from __future__ import annotations
import sys
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

# Make project-root imports work when running `uvicorn whatsapp_bot.server:app`
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from fastapi import FastAPI, Form, Header, HTTPException, Request
    from fastapi.responses import JSONResponse, Response
except ImportError as e:
    raise RuntimeError(
        "fastapi not installed. Run: pip install -r requirements.txt"
    ) from e

from sample_data.loader import load_all_sample_data

from .config import settings
from .gemini_client import GeminiClient
from .handlers import EngineData, dispatch
from .intent import classify
from .twilio_client import make_twiml_response, validate_signature


# =============================================================================
# APP STATE — loaded once at startup
# =============================================================================

class AppState:
    data: EngineData | None = None
    gemini: GeminiClient | None = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.data = EngineData(load_all_sample_data())
    state.gemini = GeminiClient()
    yield
    # No teardown needed


app = FastAPI(
    title="AgriFlow WhatsApp Bot",
    version="0.1.0",
    description="Twilio webhook + Gemini RAG over the AgriFlow matching engine.",
    lifespan=lifespan,
)


# =============================================================================
# CORE — pure function (no Twilio coupling), reused by /whatsapp and /chat
# =============================================================================

def handle_message(message: str) -> str:
    """Pure pipeline: text in → text out. Easy to unit-test."""
    if state.data is None or state.gemini is None:
        # Eager init for non-FastAPI callers (CLI, tests not using TestClient)
        state.data = EngineData(load_all_sample_data())
        state.gemini = GeminiClient()
    intent = classify(
        message, state.gemini,
        state.data.kabupaten, state.data.komoditas,
    )
    return dispatch(intent, state.data, state.gemini)


# =============================================================================
# ROUTES
# =============================================================================

@app.get("/health")
async def health() -> Dict[str, Any]:
    data_loaded = state.data is not None
    return {
        "status": "ok",
        "version": "0.1.0",
        "mock_mode": settings.mock_mode,
        "data_loaded": data_loaded,
        "kabupaten_count": len(state.data.kabupaten) if data_loaded else 0,
        "komoditas_count": len(state.data.komoditas) if data_loaded else 0,
        "gemini_mock": state.gemini.mock if state.gemini else None,
    }


@app.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    x_twilio_signature: str | None = Header(default=None),
) -> Response:
    """
    Twilio WhatsApp webhook entrypoint.
    Body  — message text from user
    From  — 'whatsapp:+62xxx' sender
    Returns TwiML XML that Twilio will send back to the user.
    """
    # Optional signature validation — enable once webhook is reachable from Twilio
    if settings.twilio_validate_signature and not settings.mock_mode:
        form = await request.form()
        url = str(request.url)
        if not validate_signature(
            settings.twilio_auth_token, x_twilio_signature or "",
            url, form,
        ):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    reply = handle_message(Body)
    return Response(content=make_twiml_response(reply), media_type="application/xml")


@app.post("/chat")
async def chat_debug(payload: Dict[str, str]) -> JSONResponse:
    """
    Debug endpoint — bypasses Twilio. Useful for local curl testing:
        curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \\
             -d '{"message": "Harga cabai di Malang"}'
    """
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message field required")
    reply = handle_message(message)
    return JSONResponse({"reply": reply})


# =============================================================================
# CLI helper: python -m whatsapp_bot.server "Harga cabai di Malang"
# =============================================================================

def _cli_main() -> None:
    # Force UTF-8 stdout on Windows so emoji in replies don't crash cp1252 consoles
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    if len(sys.argv) < 2:
        print("Usage: python -m whatsapp_bot.server \"<your message>\"")
        sys.exit(1)
    msg = " ".join(sys.argv[1:])
    print(handle_message(msg))


if __name__ == "__main__":
    _cli_main()

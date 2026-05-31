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
    from fastapi import FastAPI, Form, Header, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response
except ImportError as e:
    raise RuntimeError(
        "fastapi not installed. Run: pip install -r requirements.txt"
    ) from e

from matching_engine import LogisticsContext, run_matching
from sample_data.loader import load_all_sample_data as _load_csv

# Precomputed data paths (resolved relative to project root so they work
# both locally and inside the Docker container)
_HERE_SERVER = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE_SERVER)
_ANOMALIES_PATH = os.path.join(_PROJECT_ROOT, "sample_data", "anomalies", "anomalies_all.json")
_FORECASTS_PATH = os.path.join(_PROJECT_ROOT, "sample_data", "forecasts", "forecast_all.json")


def _load_data_backend() -> dict:
    """
    Select the data backend via the DATA_BACKEND env var.

    DATA_BACKEND=csv      (default) — load from sample CSV files (offline-safe).
    DATA_BACKEND=postgres            — load from Supabase/Postgres via db.db_loader.

    The CSV path is always available; the Postgres path raises RuntimeError if
    SUPABASE_DB_URL is not set, so misconfiguration is loud rather than silent.
    """
    import os
    backend = os.environ.get("DATA_BACKEND", "csv").strip().lower()
    if backend == "postgres":
        from db.db_loader import load_all as _load_pg
        return _load_pg()
    # Default: csv (offline-safe, demo mode)
    return _load_csv()


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
    state.data = EngineData(_load_data_backend())
    state.gemini = GeminiClient()
    yield
    # No teardown needed


app = FastAPI(
    title="AgriFlow WhatsApp Bot",
    version="0.1.0",
    description="Twilio webhook + Gemini RAG over the AgriFlow matching engine.",
    lifespan=lifespan,
)

# CORS so the Next.js dashboard can hit /api/v1/* from dev (localhost)
# and from any *.vercel.app preview / production URL. Regex covers branch
# previews like agriflow-git-feature-x.vercel.app without re-deploys.
# Also allows *.hf.space (Hugging Face Spaces) for direct curl/browser testing
# against the API itself when it's hosted there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.(vercel\.app|hf\.space)",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# =============================================================================
# CORE — pure function (no Twilio coupling), reused by /whatsapp and /chat
# =============================================================================

def handle_message(message: str) -> str:
    """Pure pipeline: text in → text out. Easy to unit-test."""
    if state.data is None or state.gemini is None:
        # Eager init for non-FastAPI callers (CLI, tests not using TestClient)
        state.data = EngineData(_load_data_backend())
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
# DASHBOARD API — /api/v1/* (consumed by Next.js dashboard)
# =============================================================================

def _ensure_engine() -> EngineData:
    if state.data is None:
        state.data = EngineData(_load_data_backend())
    return state.data


@app.get("/api/v1/commodities")
async def api_commodities() -> JSONResponse:
    data = _ensure_engine()
    out = [
        {"code": c.code, "nama": c.nama}
        for c in sorted(data.komoditas.values(), key=lambda c: c.nama)
    ]
    return JSONResponse(out)


@app.get("/api/v1/kabupaten")
async def api_kabupaten() -> JSONResponse:
    data = _ensure_engine()
    out = [
        {
            "id": k.id, "nama": k.nama,
            "lat": k.latitude, "lng": k.longitude,
            "tier": k.tier.value, "ipm": k.ipm,
            "population": k.population,
        }
        for k in sorted(data.kabupaten.values(), key=lambda k: k.nama)
    ]
    return JSONResponse(out)


@app.get("/api/v1/surplus-deficit")
async def api_surplus_deficit(
    commodity: str = Query(..., description="Commodity code, e.g. cabai_merah"),
) -> JSONResponse:
    """Per-kab surplus/deficit volume for one commodity — powers the map bubbles."""
    data = _ensure_engine()
    if commodity not in data.komoditas:
        raise HTTPException(status_code=404, detail=f"unknown commodity: {commodity}")
    commo = data.komoditas[commodity]

    rows = []
    for s in data.surplus:
        if s.commodity.code != commodity:
            continue
        rows.append({
            "kab_id": s.kabupaten.id, "kab_nama": s.kabupaten.nama,
            "lat": s.kabupaten.latitude, "lng": s.kabupaten.longitude,
            "tier": s.kabupaten.tier.value,
            "role": "surplus",
            "volume_tons": s.volume_tons,
            "price_per_kg": s.price_per_kg,
        })
    for d in data.deficit:
        if d.commodity.code != commodity:
            continue
        rows.append({
            "kab_id": d.kabupaten.id, "kab_nama": d.kabupaten.nama,
            "lat": d.kabupaten.latitude, "lng": d.kabupaten.longitude,
            "tier": d.kabupaten.tier.value,
            "role": "deficit",
            "volume_tons": d.volume_tons,
            "price_per_kg": d.price_per_kg,
        })

    total_surplus = sum(r["volume_tons"] for r in rows if r["role"] == "surplus")
    total_deficit = sum(r["volume_tons"] for r in rows if r["role"] == "deficit")
    return JSONResponse({
        "commodity": {"code": commo.code, "nama": commo.nama},
        "rows": rows,
        "totals": {
            "surplus_tons": total_surplus,
            "deficit_tons": total_deficit,
            "balance_tons": total_surplus - total_deficit,
        },
    })


def _serialize_match(m) -> Dict[str, Any]:
    return {
        "surplus": {
            "kab_id": m.surplus.kabupaten.id,
            "kab_nama": m.surplus.kabupaten.nama,
            "lat": m.surplus.kabupaten.latitude,
            "lng": m.surplus.kabupaten.longitude,
            "price_per_kg": m.surplus.price_per_kg,
        },
        "deficit": {
            "kab_id": m.deficit.kabupaten.id,
            "kab_nama": m.deficit.kabupaten.nama,
            "lat": m.deficit.kabupaten.latitude,
            "lng": m.deficit.kabupaten.longitude,
            "price_per_kg": m.deficit.price_per_kg,
        },
        "commodity_code": m.surplus.commodity.code,
        "commodity_nama": m.surplus.commodity.nama,
        "matched_volume_tons": m.matched_volume_tons,
        "distance_km": m.distance_km,
        "final_score": m.final_score,
        "confidence": m.confidence.value,
        "flags": list(m.flags),
    }


@app.get("/api/v1/matches")
async def api_matches(
    commodity: str | None = Query(None, description="Filter by commodity code"),
    kab_id: str | None = Query(None, description="Filter where this kab is surplus OR deficit side"),
    limit: int = Query(50, ge=1, le=500),
) -> JSONResponse:
    """Run engine then filter. Returns scored matches for map flow lines + side panel."""
    data = _ensure_engine()
    report = run_matching(
        surplus_nodes=data.surplus,
        deficit_nodes=data.deficit,
        logistics=LogisticsContext(),
        weather_forecasts=data.weather,
        historical_prices=data.historical,
    )
    matches = report.matches
    if commodity:
        matches = [m for m in matches if m.surplus.commodity.code == commodity]
    if kab_id:
        matches = [
            m for m in matches
            if m.surplus.kabupaten.id == kab_id or m.deficit.kabupaten.id == kab_id
        ]
    matches.sort(key=lambda m: m.final_score, reverse=True)
    matches = matches[:limit]
    return JSONResponse({
        "count": len(matches),
        "matches": [_serialize_match(m) for m in matches],
    })


# =============================================================================
# FORECAST + ANOMALY API  --  /api/v1/forecast  and  /api/v1/anomalies
#
# Both endpoints serve precomputed JSON files that were generated offline by:
#   python analysis/precompute_anomalies.py
#   python analysis/forecast_timesfm.py
#
# The server NEVER imports timesfm at runtime (HF Space OOM guard).
# =============================================================================

import json as _json
import functools


@functools.lru_cache(maxsize=1)
def _load_forecasts() -> list:
    """Load forecast_all.json once and cache in-process."""
    if not os.path.exists(_FORECASTS_PATH):
        return []
    with open(_FORECASTS_PATH, encoding="utf-8") as fh:
        return _json.load(fh)


@functools.lru_cache(maxsize=1)
def _load_anomalies() -> list:
    """Load anomalies_all.json once and cache in-process."""
    if not os.path.exists(_ANOMALIES_PATH):
        return []
    with open(_ANOMALIES_PATH, encoding="utf-8") as fh:
        return _json.load(fh)


@app.get("/api/v1/forecast")
async def api_forecast(
    commodity: str = Query(..., description="Commodity code, e.g. cabai_rawit"),
    city: str = Query(..., description="IHK city_id, e.g. 3578 (Surabaya)"),
) -> JSONResponse:
    """
    30-day price forecast (point + P10/P90) for one commodity × city pair.

    Data is precomputed offline (seasonal-naive baseline unless TimesFM was
    available at precompute time).  The 'method' field in the response tells
    you which model was used.

    Query params:
        commodity  AgriFlow commodity code (e.g. cabai_rawit, bawang_merah)
        city       IHK city_id  (e.g. 3578 for Kota Surabaya)

    Response schema:
        commodity_code   str
        city_id          str
        city_name        str
        method           str  ("timesfm_2.0" | "seasonal_naive_baseline")
        generated_at     str  ISO 8601
        horizon_days     int
        history_end_date str  ISO 8601
        forecasts        list of {date, point, p10, p90}
    """
    records = _load_forecasts()
    if not records:
        raise HTTPException(
            status_code=503,
            detail=(
                "Forecast data not yet precomputed.  "
                "Run: python analysis/forecast_timesfm.py"
            ),
        )
    match = next(
        (r for r in records if r["commodity_code"] == commodity and r["city_id"] == city),
        None,
    )
    if match is None:
        # List available (commodity, city) pairs so caller can self-correct
        available = sorted({(r["commodity_code"], r["city_id"]) for r in records})
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"No forecast for commodity={commodity!r} city={city!r}",
                "available_pairs": [{"commodity": c, "city": ci} for c, ci in available[:20]],
            },
        )
    return JSONResponse(match)


@app.get("/api/v1/anomalies")
async def api_anomalies(
    commodity: str | None = Query(None, description="Filter by commodity code"),
    city: str | None = Query(None, description="Filter by IHK city_id"),
    limit: int = Query(50, ge=1, le=500, description="Max records returned (sorted by score desc)"),
    since: str | None = Query(None, description="ISO date lower-bound, e.g. 2024-01-01"),
) -> JSONResponse:
    """
    Detected price anomalies from the S-H-ESD scanner (precomputed offline).

    All filters are optional.  Without filters returns top-N anomalies by score.

    Query params:
        commodity  optional commodity code filter
        city       optional IHK city_id filter
        limit      max records (default 50, max 500)
        since      ISO date — only return anomalies on or after this date

    Response schema:
        count     int
        method    str  ("shesd_v2")
        anomalies list of {
            date           str  ISO 8601
            price          float  IDR/kg
            rolling_median float
            deviation_pct  float  (positive = spike, negative = drop)
            type           str    SPIKE | DROP
            score          float  (higher = more anomalous)
            commodity_code str
            city_id        str
            city_name      str
            persistent     bool
        }
    """
    records = _load_anomalies()
    if not records:
        raise HTTPException(
            status_code=503,
            detail=(
                "Anomaly data not yet precomputed.  "
                "Run: python analysis/precompute_anomalies.py"
            ),
        )

    filtered = records
    if commodity:
        filtered = [r for r in filtered if r["commodity_code"] == commodity]
    if city:
        filtered = [r for r in filtered if r["city_id"] == city]
    if since:
        filtered = [r for r in filtered if r["date"] >= since]

    # Already sorted by score desc in the precomputed file; slice to limit
    filtered = filtered[:limit]

    return JSONResponse({
        "count":     len(filtered),
        "method":    "shesd_v2",
        "anomalies": filtered,
    })


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

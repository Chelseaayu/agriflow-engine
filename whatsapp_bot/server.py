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
from sample_data.loader import load_real_data as _load_real
from whatsapp_bot import request_log

# Precomputed data paths (resolved relative to project root so they work
# both locally and inside the Docker container)
_HERE_SERVER = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE_SERVER)
_ANOMALIES_PATH = os.path.join(_PROJECT_ROOT, "sample_data", "anomalies", "anomalies_all.json")
_FORECASTS_PATH = os.path.join(_PROJECT_ROOT, "sample_data", "forecasts", "forecast_all.json")


def _load_data_backend() -> dict:
    """
    Select the data backend via the DATA_BACKEND env var.

    DATA_BACKEND=csv      (default) — REAL BPS Jawa Timur 2022 data from
                                      sample_data/surplus_deficit_real.csv.
                                      Offline-safe.
    DATA_BACKEND=demo                — the synthetic 19-commodity fixture. Test
                                      data only; never serve it to users.
    DATA_BACKEND=postgres            — load from Supabase/Postgres via db.db_loader.

    WHY THE DEFAULT IS REAL DATA
    ----------------------------
    This used to call load_all_sample_data(), whose default file is the
    synthetic surplus_deficit.csv. Every served response — dashboard map,
    WhatsApp reply, API — was therefore built on invented numbers while the
    real BPS-derived file sat unused beside it.

    That also caused a visible failure. The synthetic file prices rice demand
    in consumer cities at Rp16,400-17,000/kg against a 2022 farmgate-derived
    threshold whose 3-sigma ceiling is Rp15,100, so the D3 gate excluded EVERY
    rice deficit node and both beras commodities returned zero matches. On real
    data there are no anomaly exclusions at all, and matches go from 23 to 84.

    The synthetic fixture is still what 13 test files load directly, which is
    fine: it exercises engine logic across more commodities than the real data
    covers. It just must not be what users see.

    The Postgres path raises RuntimeError if SUPABASE_DB_URL is not set, so
    misconfiguration is loud rather than silent.
    """
    import os
    backend = os.environ.get("DATA_BACKEND", "csv").strip().lower()
    if backend == "postgres":
        from db.db_loader import load_all as _load_pg
        return _load_pg()
    if backend == "demo":
        return _load_csv()
    # Default: real BPS data (offline-safe)
    return _load_real()


from . import billing
from .auth import AuthUser, GatedUser, RequireUser, auth_configured, require_auth_enabled
from .config import settings
from .gemini_client import GeminiClient
from .handlers import (
    MISSING_SLOT_PREFIX, OUT_OF_COVERAGE_PREFIX, EngineData, dispatch,
)
from .intent import (
    INTENT_ANOMALI, INTENT_CARI_PEMBELI, INTENT_CARI_PENJUAL,
    INTENT_FORECAST, INTENT_HARGA_LOOKUP, classify,
)
from .subscription import SubscriptionService, hash_phone
from .twilio_client import make_twiml_response, validate_signature


# Intents that consume free-tier quota. The fallback intent is excluded on
# purpose: a Gemini chit-chat answer is not the product, and charging for it
# would let a vague question burn the user's daily allowance.
METERED_INTENTS = frozenset({
    INTENT_HARGA_LOOKUP, INTENT_CARI_PEMBELI, INTENT_CARI_PENJUAL,
    INTENT_FORECAST, INTENT_ANOMALI,
})


# =============================================================================
# APP STATE — loaded once at startup
# =============================================================================

class AppState:
    data: EngineData | None = None
    gemini: GeminiClient | None = None
    subs: SubscriptionService | None = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.data = EngineData(_load_data_backend())
    state.gemini = GeminiClient()
    state.subs = SubscriptionService()
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

# One JSON line per request on stderr, plus an X-Request-ID header so a user
# report ties back to an exact log line. Set AGRIFLOW_LOG_FILE to also archive
# the run to disk. Never logs phone numbers or request bodies.
request_log.install(app)


# =============================================================================
# CORE — pure function (no Twilio coupling), reused by /whatsapp and /chat
# =============================================================================

def _ensure_state() -> None:
    """Eager init for non-FastAPI callers (CLI, tests not using TestClient)."""
    if state.data is None:
        state.data = EngineData(_load_data_backend())
    if state.gemini is None:
        state.gemini = GeminiClient()
    if state.subs is None:
        state.subs = SubscriptionService()


def handle_message(message: str, sender: str | None = None) -> str:
    """
    Pure pipeline: text in → text out. Easy to unit-test.

    `sender` is the raw WhatsApp identifier ('whatsapp:+62...'). When it is
    absent the message is treated as anonymous and no quota is applied — that
    is the debug path (/chat, CLI). The Twilio webhook always passes a sender,
    so real users are always metered.

    Order of operations matters here:
      1. Billing/help commands run first and are never metered, so a user at
         their limit can still reach STATUS and UPGRADE.
      2. The quota check runs before dispatch, so an over-limit user gets the
         upgrade offer instead of an answer.
      3. Quota is consumed only *after* a metered intent produced a real
         answer, so incomplete questions cost nothing.
    """
    _ensure_state()
    assert state.data is not None and state.gemini is not None and state.subs is not None

    phone_hash = hash_phone(sender) if sender else ""

    # 1. Commands — free, and available even at zero remaining quota.
    #    Skipped entirely when the paywall is off: with no quota there is no
    #    billing surface, and a STATUS reply quoting a limit nobody enforces
    #    would be a lie.
    if settings.quota_enabled and phone_hash:
        command = billing.parse_command(message)
        if command is not None:
            return billing.handle_command(command, phone_hash, state.subs)

    intent = classify(
        message, state.gemini,
        state.data.kabupaten, state.data.komoditas,
    )
    metered = (
        settings.quota_enabled
        and bool(phone_hash)
        and intent.name in METERED_INTENTS
    )

    # 2. Paywall.
    if metered:
        decision = state.subs.check(phone_hash)
        if not decision.allowed:
            order = state.subs.start_upgrade(phone_hash)
            return billing.quota_exceeded(decision, order)

    reply = dispatch(intent, state.data, state.gemini)

    # 3. Bill only a query we actually answered. Asking the user to rephrase
    #    is free, and so is telling them a commodity is outside our data —
    #    neither delivered the thing they asked for.
    if metered and not reply.startswith((MISSING_SLOT_PREFIX, OUT_OF_COVERAGE_PREFIX)):
        state.subs.consume(phone_hash)

    return reply


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
        "auth_configured": auth_configured(),
        "require_auth": require_auth_enabled(),
        "quota_enabled": settings.quota_enabled,
        "free_daily_quota": settings.free_daily_quota,
        "quota_backend": settings.quota_backend,
        "billing_mock": settings.billing_mock,
        # Surfaced so a deployment check can catch an unsalted hash without
        # exposing the salt itself.
        "phone_hash_salted": bool(settings.phone_hash_salt),
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

    reply = handle_message(Body, sender=From)
    return Response(content=make_twiml_response(reply), media_type="application/xml")


@app.post("/chat")
async def chat_debug(payload: Dict[str, str]) -> JSONResponse:
    """
    Debug endpoint — bypasses Twilio. Useful for local curl testing:
        curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \\
             -d '{"message": "Harga cabai di Malang"}'

    Pass an optional "from" field to exercise the quota flow end to end:
             -d '{"message": "Harga cabai di Malang", "from": "whatsapp:+628123"}'

    WITHOUT "from" this endpoint is unmetered, so it bypasses the paywall by
    design. Set DEBUG_CHAT_ENABLED=false in any deployment where that matters —
    the Twilio webhook is the metered path, this one is a development tool.
    """
    if not settings.debug_chat_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message field required")
    reply = handle_message(message, sender=payload.get("from"))
    return JSONResponse({"reply": reply})


# =============================================================================
# BILLING — upgrade flow
#
# The payment page and confirm endpoint form the gateway seam. In mock mode
# they are self-contained; to go live, point PUBLIC_BASE_URL's payment link at
# Midtrans/Xendit and have their webhook POST /billing/confirm with the order id
# after verifying the provider signature.
# =============================================================================

def _ensure_subs() -> SubscriptionService:
    if state.subs is None:
        state.subs = SubscriptionService()
    return state.subs


@app.get("/billing/pay/{order_id}")
async def billing_pay_page(order_id: str) -> Response:
    """
    Minimal payment page the WhatsApp link opens.

    In mock mode this renders a confirm button that settles the order. With a
    real gateway this route would instead redirect to the provider's hosted
    checkout for this order.
    """
    subs = _ensure_subs()
    order = subs.store.get_order(order_id)
    if order is None:
        return Response(
            content="<h1>Pesanan tidak ditemukan</h1>"
                    "<p>Silakan balas UPGRADE di WhatsApp untuk membuat pesanan baru.</p>",
            media_type="text/html", status_code=404,
        )

    amount = f"Rp {order.amount_idr:,.0f}".replace(",", ".")
    if order.status == "PAID":
        body = "<p class=ok>Pesanan ini sudah dibayar. Akun Anda sudah PRO.</p>"
    elif billing.billing_mock_enabled():
        body = (
            f"<form method='post' action='/billing/confirm'>"
            f"<input type='hidden' name='order_id' value='{order.order_id}'>"
            f"<button type='submit'>Bayar {amount} (demo)</button></form>"
            f"<p class=note>Mode demo — tidak ada transaksi sungguhan.</p>"
        )
    else:
        body = "<p class=note>Menunggu pengalihan ke penyedia pembayaran.</p>"

    return Response(
        content=(
            "<!doctype html><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>AgriFlow PRO</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:26rem;margin:3rem auto;"
            "padding:0 1rem;line-height:1.6}button{background:#15803d;color:#fff;border:0;"
            "padding:.8rem 1.4rem;border-radius:.5rem;font-size:1rem;cursor:pointer;width:100%}"
            ".note{color:#666;font-size:.9rem}.ok{color:#15803d;font-weight:600}</style>"
            f"<h1>AgriFlow PRO</h1><p>Pesanan <b>{order.order_id}</b><br>"
            f"Jumlah <b>{amount}</b> untuk 30 hari</p>{body}"
        ),
        media_type="text/html",
    )


@app.post("/billing/confirm")
async def billing_confirm(request: Request) -> Response:
    """
    Settle an order and grant PRO — the gateway webhook seam.

    Accepts either form-encoded (the mock page) or JSON (a webhook). A real
    integration MUST verify the provider's signature here before trusting the
    order id; right now anyone who knows an order id can settle it, which is
    acceptable only because mock mode charges nothing.
    """
    subs = _ensure_subs()
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        payload = await request.json()
        order_id = str(payload.get("order_id", ""))
    else:
        form = await request.form()
        order_id = str(form.get("order_id", ""))

    if not order_id:
        raise HTTPException(status_code=400, detail="order_id required")

    if not billing.billing_mock_enabled():
        raise HTTPException(
            status_code=501,
            detail="Live payment confirmation is not wired yet. "
                   "Implement provider signature verification before enabling.",
        )

    account = subs.confirm_payment(order_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"unknown order: {order_id}")

    if "application/json" in ctype:
        return JSONResponse({
            "status": "ok",
            "plan": account.plan,
            "expires_at": account.expires_at.isoformat() if account.expires_at else None,
        })
    return Response(
        content="<!doctype html><meta charset='utf-8'>"
                "<style>body{font-family:system-ui,sans-serif;max-width:26rem;"
                "margin:3rem auto;padding:0 1rem;line-height:1.6}</style>"
                "<h1>Pembayaran berhasil</h1>"
                "<p>Akun WhatsApp Anda sekarang PRO selama 30 hari. "
                "Silakan kembali ke WhatsApp dan lanjutkan bertanya.</p>",
        media_type="text/html",
    )


@app.get("/billing/status")
async def billing_status(
    phone: str = Query(..., description="WhatsApp number, e.g. +628123456789"),
    user: AuthUser = RequireUser,
) -> JSONResponse:
    """
    Plan + remaining quota for one number. Powers the dashboard account panel.

    The number is hashed before lookup and never stored by this call.
    """
    subs = _ensure_subs()
    phone_hash = hash_phone(phone)
    if not phone_hash:
        raise HTTPException(status_code=400, detail="invalid phone number")
    decision = subs.check(phone_hash)
    return JSONResponse({
        "plan": decision.account.plan,
        "is_pro": decision.account.is_pro,
        "expires_at": (
            decision.account.expires_at.isoformat()
            if decision.account.expires_at else None
        ),
        "used_today": decision.used_today,
        "limit": decision.limit,
        "remaining": decision.remaining,
    })


# =============================================================================
# DASHBOARD API — /api/v1/* (consumed by Next.js dashboard)
# =============================================================================

def _ensure_engine() -> EngineData:
    if state.data is None:
        state.data = EngineData(_load_data_backend())
    return state.data


# Cached full engine run.
#
# run_matching() is a pure function of the data loaded at startup, so re-running
# it per request was burning ~1.5 ms of CPU to recompute a byte-identical
# answer — about 60x the cost of everything else in the request and the binding
# constraint on how many concurrent users one worker can serve.
#
# The cache is keyed on the EngineData object itself (not id(), which a garbage
# collector can recycle onto a different object). Reloading data rebinds
# state.data to a new instance, which misses the cache and recomputes.
_matching_cache: Dict[str, Any] = {"data": None, "report": None}


def _cached_report():
    data = _ensure_engine()
    if _matching_cache["data"] is not data:
        _matching_cache["report"] = run_matching(
            surplus_nodes=data.surplus,
            deficit_nodes=data.deficit,
            logistics=LogisticsContext(),
            weather_forecasts=data.weather,
            historical_prices=data.historical,
        )
        _matching_cache["data"] = data
    return _matching_cache["report"]


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
    user: AuthUser | None = GatedUser,
    commodity: str | None = Query(None, description="Filter by commodity code"),
    kab_id: str | None = Query(None, description="Filter where this kab is surplus OR deficit side"),
    limit: int = Query(50, ge=1, le=500),
) -> JSONResponse:
    """Serve scored matches for map flow lines + side panel, from a cached engine run."""
    report = _cached_report()

    # Copy before sorting. `report.matches` is the shared cached list, and an
    # unfiltered request would otherwise sort it in place under every other
    # concurrent caller.
    matches = list(report.matches)
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


_ANOMALY_SCHEMA_VERSION = "source-aware-anomaly/v1"
_ANOMALY_STATUSES = frozenset({
    "DETECTABLE", "INSUFFICIENT_HISTORY", "NO_ACTIVE_HISTORY",
})


def _validate_anomaly_artifact(artifact: Any) -> dict:
    """Return a strictly validated source-aware artifact or raise ValueError."""
    if not isinstance(artifact, dict):
        raise ValueError("artifact must be a JSON object")
    required = {
        "schema_version", "generated_at", "method", "active_source_policy",
        "series_statuses", "events",
    }
    missing = required - artifact.keys()
    if missing:
        raise ValueError("artifact missing required field(s): " + ", ".join(sorted(missing)))
    if artifact["schema_version"] != _ANOMALY_SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if not all(isinstance(artifact[key], str) and artifact[key] for key in (
        "generated_at", "method", "active_source_policy",
    )):
        raise ValueError("artifact generation metadata must be non-empty strings")
    if not isinstance(artifact["series_statuses"], list) or not isinstance(artifact["events"], list):
        raise ValueError("series_statuses and events must be lists")

    status_keys: set[tuple[str, str]] = set()
    for index, status in enumerate(artifact["series_statuses"]):
        if not isinstance(status, dict):
            raise ValueError(f"series_statuses[{index}] must be an object")
        fields = {
            "city_id", "city_name", "commodity_code", "series_status",
            "history_start_date", "latest_observation_date", "observation_count",
            "history_coverage_ratio", "history_confidence", "active_history_source_counts",
            "latest_observation_source", "observation_freshness_days", "market_quality",
            "market_quality_availability",
        }
        absent = fields - status.keys()
        if absent:
            raise ValueError(
                f"series_statuses[{index}] missing field(s): {', '.join(sorted(absent))}"
            )
        if status["series_status"] not in _ANOMALY_STATUSES:
            raise ValueError(f"series_statuses[{index}] has invalid series_status")
        key = (str(status["city_id"]), str(status["commodity_code"]))
        if key in status_keys:
            raise ValueError(f"duplicate series status for city={key[0]} commodity={key[1]}")
        status_keys.add(key)
    for index, event in enumerate(artifact["events"]):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] must be an object")
        absent = {
            "date", "price", "rolling_median", "deviation_pct", "type", "score",
            "persistent", "city_id", "city_name", "commodity_code",
            "observation_provenance",
        } - event.keys()
        if absent:
            raise ValueError(f"events[{index}] missing field(s): {', '.join(sorted(absent))}")
    return artifact


@functools.lru_cache(maxsize=1)
def _load_anomalies() -> dict:
    """Load and validate the completed offline anomaly artifact once per process."""
    if not os.path.exists(_ANOMALIES_PATH):
        raise ValueError(f"artifact not found: {_ANOMALIES_PATH}")
    try:
        with open(_ANOMALIES_PATH, encoding="utf-8") as fh:
            return _validate_anomaly_artifact(_json.load(fh))
    except (OSError, _json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid anomaly artifact at {_ANOMALIES_PATH}: {exc}") from exc


def reload_anomaly_artifact() -> None:
    """Clear the artifact reader cache after an atomic artifact replacement."""
    _load_anomalies.cache_clear()


def _status_summary(statuses: list[dict]) -> dict[str, int]:
    """Count supported status states without inferring availability from events."""
    return {state: sum(item["series_status"] == state for item in statuses)
            for state in sorted(_ANOMALY_STATUSES)}


def _out_of_coverage_status(city: str, commodity: str) -> dict:
    return {
        "city_id": city,
        "city_name": None,
        "commodity_code": commodity,
        "series_status": "OUT_OF_COVERAGE",
        "history_start_date": None,
        "latest_observation_date": None,
        "observation_count": 0,
        "history_coverage_ratio": None,
        "history_confidence": None,
        "active_history_source_counts": {"SISKAPERBAPO": 0, "PIHPS": 0},
        "latest_observation_source": None,
        "observation_freshness_days": None,
        "market_quality": None,
        "market_quality_availability": "OUT_OF_COVERAGE",
    }


@app.get("/api/v1/forecast")
async def api_forecast(
    user: AuthUser | None = GatedUser,
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
    user: AuthUser | None = GatedUser,
    commodity: str | None = Query(None, description="Filter by anomaly commodity code"),
    city: str | None = Query(None, description="Filter by Jawa Timur region ID"),
    limit: int = Query(50, ge=1, le=500, description="Max records returned (sorted by score desc)"),
    since: str | None = Query(None, description="ISO date lower-bound, e.g. 2024-01-01"),
) -> JSONResponse:
    """Serve the versioned, offline source-aware anomaly artifact only."""
    try:
        artifact = _load_anomalies()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    statuses = artifact["series_statuses"]
    events = artifact["events"]
    matching_statuses = [
        status for status in statuses
        if (commodity is None or status["commodity_code"] == commodity)
        and (city is None or str(status["city_id"]) == city)
    ]

    # A fully specified supported pair has exactly one status envelope. An
    # unsupported code is intentionally not substituted with a near commodity.
    if city is not None and commodity is not None:
        series = next(
            (status for status in matching_statuses
             if str(status["city_id"]) == city and status["commodity_code"] == commodity),
            None,
        )
        if series is None:
            supported_codes = {status["commodity_code"] for status in statuses}
            if commodity not in supported_codes:
                series = _out_of_coverage_status(city, commodity)
            else:
                raise HTTPException(
                    status_code=503,
                    detail=("invalid anomaly artifact: missing status for "
                            f"city={city} commodity={commodity}"),
                )
        filtered = [
            event for event in events
            if str(event["city_id"]) == city and event["commodity_code"] == commodity
        ]
        if since:
            filtered = [event for event in filtered if event["date"] >= since]
        filtered = filtered[:limit]
        return JSONResponse({
            "count": len(filtered),
            "method": artifact["method"],
            "anomalies": filtered,
            "schema_version": artifact["schema_version"],
            "artifact_generated_at": artifact["generated_at"],
            "active_source_policy": artifact["active_source_policy"],
            "series": series,
            "status_summary": _status_summary([series]) if series["series_status"] in _ANOMALY_STATUSES else {
                "DETECTABLE": 0, "INSUFFICIENT_HISTORY": 0, "NO_ACTIVE_HISTORY": 0,
            },
        })

    filtered = [
        event for event in events
        if (commodity is None or event["commodity_code"] == commodity)
        and (city is None or str(event["city_id"]) == city)
        and (since is None or event["date"] >= since)
    ][:limit]
    response: dict[str, Any] = {
        "count": len(filtered),
        "method": artifact["method"],
        "anomalies": filtered,
        "schema_version": artifact["schema_version"],
        "artifact_generated_at": artifact["generated_at"],
        "active_source_policy": artifact["active_source_policy"],
        "series": None,
        "status_summary": _status_summary(matching_statuses),
    }
    if commodity is not None or city is not None:
        response["matching_series_statuses"] = matching_statuses
    return JSONResponse(response)


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
        print("Usage: python -m whatsapp_bot.server \"<your message>\" [--from +628123]")
        sys.exit(1)
    argv = sys.argv[1:]
    sender = None
    if "--from" in argv:
        i = argv.index("--from")
        sender = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    msg = " ".join(argv)
    print(handle_message(msg, sender=sender))


if __name__ == "__main__":
    _cli_main()

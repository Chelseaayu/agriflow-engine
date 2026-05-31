"""
Intent handlers — translate Intent into engine queries and format reply text.

Each handler returns a plain-text WhatsApp-ready reply (string).
WhatsApp doesn't render markdown bold/italic the same way — keep plain text
plus simple bullet markers.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from matching_engine import (
    DemandNode, LogisticsContext, MatchingReport, MatchResult,
    SupplyNode, run_matching,
)

from .gemini_client import GeminiClient
from .intent import (
    INTENT_CARI_PEMBELI, INTENT_CARI_PENJUAL,
    INTENT_FALLBACK, INTENT_HARGA_LOOKUP,
    INTENT_FORECAST, INTENT_ANOMALI,
    Intent,
)

# Resolve precomputed data paths relative to project root
_HANDLERS_DIR   = Path(__file__).parent
_PROJECT_ROOT   = _HANDLERS_DIR.parent
_FORECASTS_PATH = _PROJECT_ROOT / "sample_data" / "forecasts" / "forecast_all.json"
_ANOMALIES_PATH = _PROJECT_ROOT / "sample_data" / "anomalies" / "anomalies_all.json"


def _load_json_file(path: Path) -> list:
    """Load a JSON file; return empty list if not found."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# =============================================================================
# FORMAT HELPERS
# =============================================================================

def _idr(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


def _missing_slot_reply(missing: List[str]) -> str:
    return (
        "Maaf, saya butuh info tambahan: " + ", ".join(missing) + ".\n"
        "Contoh format:\n"
        "• \"Harga cabai di Malang\"\n"
        "• \"Cari pembeli 50 ton cabai Kediri\""
    )


# =============================================================================
# DATA BUNDLE — passed in from server (loaded once at startup)
# =============================================================================

class EngineData:
    """Simple container so handlers don't reload sample data per request."""
    def __init__(self, sample_data: Dict[str, Any]):
        self.kabupaten = sample_data["kabupaten"]
        self.komoditas = sample_data["komoditas"]
        self.surplus: List[SupplyNode] = sample_data["surplus"]
        self.deficit: List[DemandNode] = sample_data["deficit"]
        self.weather = sample_data["weather"]
        self.historical = sample_data["historical_prices"]


# =============================================================================
# HANDLER: harga_lookup
# =============================================================================

def handle_harga_lookup(intent: Intent, data: EngineData) -> str:
    """Look up current price for a commodity in a specific kabupaten."""
    missing = []
    if not intent.commodity:
        missing.append("nama komoditas")
    if not intent.kabupaten_id:
        missing.append("nama kabupaten")
    if missing:
        return _missing_slot_reply(missing)

    kab_id = intent.kabupaten_id
    code = intent.commodity
    commodity = data.komoditas.get(code)
    kab = data.kabupaten.get(kab_id)
    if not commodity or not kab:
        return _missing_slot_reply(["nama komoditas atau kabupaten yang valid"])

    # Find price from supply OR deficit nodes
    surplus_match = next(
        (s for s in data.surplus
         if s.kabupaten.id == kab_id and s.commodity.code == code),
        None,
    )
    deficit_match = next(
        (d for d in data.deficit
         if d.kabupaten.id == kab_id and d.commodity.code == code),
        None,
    )

    if not surplus_match and not deficit_match:
        # No real-time data — fall back to historical median
        hist = data.historical.get(code)
        if hist:
            median, std = hist
            return (
                f"📊 {commodity.nama} di {kab.nama}\n"
                f"Tidak ada data real-time hari ini.\n"
                f"Median historis 30 hari: {_idr(median)}/kg "
                f"(std {_idr(std)}/kg).\n"
                "Saran: cek lagi besok atau hubungi Dinas setempat."
            )
        return (
            f"Belum ada data harga untuk {commodity.nama} di {kab.nama}.\n"
            "Coba kabupaten lain atau cek pekan depan."
        )

    lines = [f"📊 {commodity.nama} di {kab.nama} (Tier {kab.tier.value[-1]})"]
    if surplus_match:
        lines.append(
            f"• Surplus: {surplus_match.volume_tons:.0f} ton @ "
            f"{_idr(surplus_match.price_per_kg)}/kg "
            f"(panen {surplus_match.harvest_age_days} hari lalu)"
        )
    if deficit_match:
        lines.append(
            f"• Defisit: {deficit_match.volume_tons:.0f} ton @ "
            f"{_idr(deficit_match.price_per_kg)}/kg"
        )
    if surplus_match and deficit_match:
        spread = deficit_match.price_per_kg - surplus_match.price_per_kg
        lines.append(f"• Spread: {_idr(spread)}/kg")
    lines.append(f"\nSumber: {commodity.nama} ({code})")
    return "\n".join(lines)


# =============================================================================
# HANDLER: cari_pembeli / cari_penjual — both run engine, filter results
# =============================================================================

def _run_engine_filtered(
    data: EngineData,
    *,
    origin_kab_id: Optional[str] = None,
    dest_kab_id: Optional[str] = None,
    commodity_code: Optional[str] = None,
) -> tuple[MatchingReport, List[MatchResult]]:
    """Run engine against full sample, then filter matches to user's slot constraints."""
    report = run_matching(
        surplus_nodes=data.surplus,
        deficit_nodes=data.deficit,
        logistics=LogisticsContext(),
        weather_forecasts=data.weather,
        historical_prices=data.historical,
    )
    matches = report.matches
    if commodity_code:
        matches = [m for m in matches if m.surplus.commodity.code == commodity_code]
    if origin_kab_id:
        matches = [m for m in matches if m.surplus.kabupaten.id == origin_kab_id]
    if dest_kab_id:
        matches = [m for m in matches if m.deficit.kabupaten.id == dest_kab_id]
    matches.sort(key=lambda m: m.final_score, reverse=True)
    return report, matches


def handle_cari_pembeli(intent: Intent, data: EngineData) -> str:
    """User has supply — find best buyers."""
    missing = []
    if not intent.commodity:
        missing.append("nama komoditas")
    if not intent.kabupaten_id:
        missing.append("kabupaten asal")
    if missing:
        return _missing_slot_reply(missing)

    _, matches = _run_engine_filtered(
        data,
        origin_kab_id=intent.kabupaten_id,
        commodity_code=intent.commodity,
    )
    if not matches:
        return (
            f"Belum ada pembeli match untuk {intent.commodity} dari "
            f"{intent.kabupaten_name} hari ini.\n"
            "Saran: coba kabupaten lain atau cek pekan depan."
        )

    top3 = matches[:3]
    commodity = data.komoditas[intent.commodity]
    lines = [
        f"🚚 Top {len(top3)} pembeli {commodity.nama} dari {intent.kabupaten_name}:",
        "",
    ]
    for i, m in enumerate(top3, 1):
        lines.append(
            f"{i}. {m.deficit.kabupaten.nama} — "
            f"{m.matched_volume_tons:.0f} ton @ {_idr(m.deficit.price_per_kg)}/kg"
        )
        lines.append(
            f"   Jarak {m.distance_km:.0f} km · skor {m.final_score:.1f} · "
            f"confidence {m.confidence.value}"
        )
        if m.flags:
            lines.append(f"   Flags: {', '.join(m.flags[:3])}")
    if intent.volume_tons:
        lines.append(f"\nVolume Anda: {intent.volume_tons:.0f} ton (untuk perencanaan).")
    return "\n".join(lines)


def handle_cari_penjual(intent: Intent, data: EngineData) -> str:
    """User has demand — find best suppliers."""
    missing = []
    if not intent.commodity:
        missing.append("nama komoditas")
    if not intent.kabupaten_id:
        missing.append("kabupaten tujuan")
    if missing:
        return _missing_slot_reply(missing)

    _, matches = _run_engine_filtered(
        data,
        dest_kab_id=intent.kabupaten_id,
        commodity_code=intent.commodity,
    )
    if not matches:
        return (
            f"Belum ada supplier match untuk {intent.commodity} ke "
            f"{intent.kabupaten_name} hari ini.\n"
            "Saran: cek pekan depan atau pertimbangkan komoditas pengganti."
        )

    top3 = matches[:3]
    commodity = data.komoditas[intent.commodity]
    lines = [
        f"📦 Top {len(top3)} supplier {commodity.nama} untuk {intent.kabupaten_name}:",
        "",
    ]
    for i, m in enumerate(top3, 1):
        lines.append(
            f"{i}. {m.surplus.kabupaten.nama} — "
            f"{m.matched_volume_tons:.0f} ton @ {_idr(m.surplus.price_per_kg)}/kg"
        )
        lines.append(
            f"   Jarak {m.distance_km:.0f} km · skor {m.final_score:.1f} · "
            f"confidence {m.confidence.value}"
        )
        if m.flags:
            lines.append(f"   Flags: {', '.join(m.flags[:3])}")
    if intent.volume_tons:
        lines.append(f"\nKebutuhan Anda: {intent.volume_tons:.0f} ton (untuk perencanaan).")
    return "\n".join(lines)


# =============================================================================
# HANDLER: forecast — 30-day price forecast from precomputed file
# =============================================================================

# IHK city_id mapping — same as price_anomaly.CITY_NAMES
_CITY_ID_MAP: Dict[str, str] = {
    "jember":          "3509",
    "banyuwangi":      "3510",
    "sumenep":         "3529",
    "kediri":          "3571",
    "kota kediri":     "3571",
    "malang":          "3573",
    "kota malang":     "3573",
    "probolinggo":     "3574",
    "kota probolinggo":"3574",
    "madiun":          "3577",
    "kota madiun":     "3577",
    "surabaya":        "3578",
    "kota surabaya":   "3578",
}

# Canonical commodity codes available in price_history
_FORECAST_COMMODITIES = {
    "cabai_rawit", "bawang_merah", "bawang_putih",
    "beras_medium", "beras_premium", "daging_ayam", "telur_ayam",
}

# Human-readable commodity names
_COMMODITY_DISPLAY: Dict[str, str] = {
    "cabai_rawit":   "Cabai Rawit",
    "bawang_merah":  "Bawang Merah",
    "bawang_putih":  "Bawang Putih",
    "beras_medium":  "Beras Medium",
    "beras_premium": "Beras Premium",
    "daging_ayam":   "Daging Ayam",
    "telur_ayam":    "Telur Ayam",
}


def _resolve_city_id(kabupaten_id: Optional[str], kabupaten_name: Optional[str]) -> Optional[str]:
    """
    Return an IHK city_id that has price history.
    kabupaten_id from the engine may not be an IHK city; attempt name-based lookup.
    """
    if kabupaten_name:
        needle = kabupaten_name.strip().lower()
        # Strip prefixes
        for prefix in ("kabupaten ", "kab ", "kota "):
            if needle.startswith(prefix):
                needle = needle[len(prefix):]
        # Try exact then partial match
        for key, cid in _CITY_ID_MAP.items():
            k = key.replace("kota ", "").strip()
            if needle == k or needle in k or k in needle:
                return cid
    return None


def handle_forecast(intent: Intent, data: EngineData) -> str:
    """Return a 30-day price forecast summary from the precomputed file."""
    commodity = intent.commodity
    kab_name  = intent.kabupaten_name
    kab_id    = intent.kabupaten_id

    # Commodity must be present and in the forecast dataset
    if not commodity or commodity not in _FORECAST_COMMODITIES:
        available = ", ".join(sorted(_COMMODITY_DISPLAY.values()))
        return (
            "Prediksi harga tersedia untuk: " + available + ".\n"
            "Contoh: \"Prediksi harga cabai rawit Surabaya\""
        )

    # Resolve IHK city_id
    city_id = _resolve_city_id(kab_id, kab_name)
    if city_id is None:
        available_cities = "Jember, Banyuwangi, Sumenep, Kota Kediri, "
        available_cities += "Kota Malang, Kota Probolinggo, Kota Madiun, Kota Surabaya"
        return (
            "Data historis harga tersedia untuk 8 kota IHK Jawa Timur:\n"
            + available_cities + ".\n"
            "Contoh: \"Prediksi harga bawang merah Surabaya\""
        )

    records = _load_json_file(_FORECASTS_PATH)
    if not records:
        return (
            "Data forecast belum tersedia.  "
            "Silakan hubungi admin untuk menjalankan precompute."
        )

    match = next(
        (r for r in records if r["commodity_code"] == commodity and r["city_id"] == city_id),
        None,
    )
    if match is None:
        return (
            f"Belum ada forecast untuk {_COMMODITY_DISPLAY.get(commodity, commodity)} "
            f"di {kab_name or city_id}."
        )

    fc_list   = match["forecasts"]
    method    = match.get("method", "unknown")
    city_name = match.get("city_name", city_id)
    hist_end  = match.get("history_end_date", "?")
    com_name  = _COMMODITY_DISPLAY.get(commodity, commodity)

    # Summary: first, middle, last points
    first  = fc_list[0]
    mid    = fc_list[len(fc_list) // 2]
    last   = fc_list[-1]

    method_note = ""
    if method == "seasonal_naive_baseline":
        method_note = "\n[Baseline statistik — bukan TimesFM]"

    lines = [
        f"Prediksi {com_name} di {city_name} (30 hari):{method_note}",
        f"Data historis s.d. {hist_end}",
        "",
        f"Hari  1 ({first['date']}): {_idr(first['point'])}/kg",
        f"  P10: {_idr(first['p10'])} — P90: {_idr(first['p90'])}",
        f"Hari 15 ({mid['date']}): {_idr(mid['point'])}/kg",
        f"Hari 30 ({last['date']}): {_idr(last['point'])}/kg",
        f"  P10: {_idr(last['p10'])} — P90: {_idr(last['p90'])}",
    ]
    return "\n".join(lines)


# =============================================================================
# HANDLER: anomali — recent price anomalies from precomputed file
# =============================================================================

def handle_anomali(intent: Intent, data: EngineData) -> str:
    """Return a summary of the most recent detected price anomalies."""
    commodity = intent.commodity
    kab_name  = intent.kabupaten_name

    records = _load_json_file(_ANOMALIES_PATH)
    if not records:
        return (
            "Data anomali belum tersedia.  "
            "Silakan hubungi admin untuk menjalankan precompute."
        )

    # Filter
    filtered = records
    if commodity and commodity in _FORECAST_COMMODITIES:
        filtered = [r for r in filtered if r["commodity_code"] == commodity]
    if kab_name:
        city_id = _resolve_city_id(None, kab_name)
        if city_id:
            filtered = [r for r in filtered if r["city_id"] == city_id]

    if not filtered:
        com_label = _COMMODITY_DISPLAY.get(commodity or "", commodity or "")
        return (
            f"Tidak ada anomali terdeteksi untuk "
            f"{com_label or 'komoditas ini'}"
            f"{' di ' + kab_name if kab_name else ''}."
        )

    # Already sorted by score desc; take top 5 most recent by date in top 100
    top_pool = filtered[:100]
    top_pool.sort(key=lambda r: r["date"], reverse=True)
    top5 = top_pool[:5]

    com_label = (
        _COMMODITY_DISPLAY.get(commodity or "", commodity or "semua komoditas")
        if commodity
        else "semua komoditas"
    )
    city_label = kab_name or "semua kota"
    lines = [f"Anomali harga {com_label} di {city_label} (terbaru):"]
    for a in top5:
        sign   = "+" if a["deviation_pct"] >= 0 else ""
        badge  = "SPIKE" if a["type"] == "SPIKE" else "DROP"
        lines.append(
            f"• {a['date']} | {badge} | {_idr(a['price'])}/kg "
            f"| deviasi {sign}{a['deviation_pct']:.1f}% "
            f"| {a['city_name']} ({a['commodity_code']})"
        )
    lines.append(f"\nTotal anomali: {len(filtered)}")
    return "\n".join(lines)


# =============================================================================
# HANDLER: fallback — RAG via Gemini with engine context
# =============================================================================

def _build_rag_context(data: EngineData) -> str:
    kab_names = ", ".join(sorted(k.nama for k in data.kabupaten.values())[:10]) + ", ..."
    komo_names = ", ".join(sorted(c.nama for c in data.komoditas.values())[:10]) + ", ..."
    return (
        f"AgriFlow adalah platform matching surplus-defisit pangan untuk "
        f"{len(data.kabupaten)} kabupaten/kota Jawa Timur dan "
        f"{len(data.komoditas)} komoditas pangan utama.\n"
        f"Kabupaten contoh: {kab_names}\n"
        f"Komoditas contoh: {komo_names}\n"
        f"Bot ini dapat menjawab: harga komoditas per kabupaten, "
        f"mencari pembeli untuk surplus, mencari supplier untuk defisit."
    )


def handle_fallback(intent: Intent, data: EngineData, gemini: GeminiClient) -> str:
    context = _build_rag_context(data)
    return gemini.answer_with_context(intent.raw_message, context)


# =============================================================================
# DISPATCH
# =============================================================================

def dispatch(intent: Intent, data: EngineData, gemini: GeminiClient) -> str:
    if intent.name == INTENT_HARGA_LOOKUP:
        return handle_harga_lookup(intent, data)
    if intent.name == INTENT_CARI_PEMBELI:
        return handle_cari_pembeli(intent, data)
    if intent.name == INTENT_CARI_PENJUAL:
        return handle_cari_penjual(intent, data)
    if intent.name == INTENT_FORECAST:
        return handle_forecast(intent, data)
    if intent.name == INTENT_ANOMALI:
        return handle_anomali(intent, data)
    return handle_fallback(intent, data, gemini)

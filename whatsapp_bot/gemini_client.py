"""
Gemini LLM wrapper.

Two methods:
    classify_intent(message)       — structured intent + slots JSON
    answer_with_context(query, ctx) — RAG-style free-form answer

Mock mode (default): returns deterministic canned responses derived from
keyword matching on the message. Lets the rest of the pipeline run end-to-end
without any API key, so demos work from a fresh clone.
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, Optional

from .config import settings


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

INTENT_SYSTEM_PROMPT = """\
Anda adalah klasifikator intent untuk WhatsApp bot AgriFlow — platform
matching surplus-defisit pangan antar kabupaten Jawa Timur.

Klasifikasikan pesan pengguna ke salah satu intent:

1. harga_lookup — Tanya harga komoditas di kabupaten tertentu
   slots: {"commodity": str, "kabupaten": str}
   contoh: "Harga cabai di Malang?", "Berapa beras Kediri sekarang?"

2. cari_pembeli — User punya supply, ingin menjual
   slots: {"commodity": str, "kabupaten_origin": str, "volume_tons": float|null}
   contoh: "Saya punya 50 ton cabai di Kediri, cari pembeli"
           "Cari pasar untuk bawang Probolinggo"

3. cari_penjual — User butuh supply, ingin membeli
   slots: {"commodity": str, "kabupaten_dest": str, "volume_tons": float|null}
   contoh: "Butuh 100 ton beras untuk Surabaya"
           "Cari supplier cabai untuk Sidoarjo"

4. fallback — Pertanyaan umum, sapaan, atau tidak masuk kategori di atas
   slots: {}

Output HANYA JSON valid satu baris, tanpa markdown atau penjelasan:
{"intent": "...", "slots": {...}}
"""

ANSWER_SYSTEM_PROMPT = """\
Anda adalah asisten WhatsApp AgriFlow — platform Indonesia untuk
matching surplus-defisit pangan kabupaten Jawa Timur.

Jawab dalam Bahasa Indonesia yang ramah, ringkas (max 3 kalimat),
dan sertakan saran konkret bila memungkinkan. Jangan halusinasi data
harga/volume — kalau tidak yakin, sarankan pengguna gunakan format
spesifik: "Harga [komoditas] di [kabupaten]" atau
"Cari pembeli [komoditas] [kabupaten]".

Konteks AgriFlow:
{context}
"""


# =============================================================================
# CLIENT
# =============================================================================

class GeminiClient:
    """Wrapper for google-generativeai. Auto-falls back to mock if no API key."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 mock: Optional[bool] = None):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model_name = model or settings.gemini_model
        self.mock = mock if mock is not None else (
            settings.mock_mode or not self.api_key
        )
        self._model = None
        if not self.mock:
            self._init_real_client()

    def _init_real_client(self) -> None:
        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "google-genai not installed. "
                "Run: pip install google-genai"
            ) from e
        # Modern SDK: single Client, model picked per-call
        self._model = genai.Client(api_key=self.api_key)

    # -------------------------------------------------------------------------
    # Intent classification
    # -------------------------------------------------------------------------

    def classify_intent(self, message: str) -> Dict[str, Any]:
        """Return {"intent": str, "slots": dict}. Falls back to {"intent": "fallback"}."""
        if self.mock:
            return _mock_classify(message)

        prompt = f"{INTENT_SYSTEM_PROMPT}\n\nPesan pengguna: {message!r}\n\nOutput JSON:"
        try:
            resp = self._model.models.generate_content(
                model=self.model_name, contents=prompt,
            )
            text = (resp.text or "").strip()
            # Strip ```json fences if present
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
            parsed = json.loads(text)
            if "intent" not in parsed:
                return {"intent": "fallback", "slots": {}}
            parsed.setdefault("slots", {})
            return parsed
        except (json.JSONDecodeError, AttributeError, Exception):
            return {"intent": "fallback", "slots": {}}

    # -------------------------------------------------------------------------
    # Free-form answer with RAG context
    # -------------------------------------------------------------------------

    def answer_with_context(self, query: str, context: str) -> str:
        if self.mock:
            return _mock_answer(query, context)

        system = ANSWER_SYSTEM_PROMPT.format(context=context)
        prompt = f"{system}\n\nPertanyaan pengguna: {query}\n\nJawaban:"
        try:
            resp = self._model.models.generate_content(
                model=self.model_name, contents=prompt,
            )
            return (resp.text or "").strip() or _mock_answer(query, context)
        except Exception:
            return _mock_answer(query, context)


# =============================================================================
# MOCK FALLBACKS — lightweight keyword heuristics
# =============================================================================

_COMMODITY_KEYWORDS = {
    "cabai_merah": ["cabai merah", "cabe merah", "cabai", "cabe"],
    "cabai_rawit": ["cabai rawit", "cabe rawit", "rawit"],
    "bawang_merah": ["bawang merah", "bawang"],
    "bawang_putih": ["bawang putih"],
    "beras_premium": ["beras premium", "beras"],
    "beras_medium": ["beras medium"],
    "jagung": ["jagung"],
    "kedelai": ["kedelai", "kedele"],
    "tomat": ["tomat"],
    "kentang": ["kentang"],
    "telur_ayam": ["telur"],
    "daging_ayam": ["ayam"],
    "daging_sapi": ["daging sapi", "sapi"],
    "ikan_tongkol": ["tongkol"],
    "minyak_goreng": ["minyak goreng", "minyak"],
    "gula_pasir": ["gula"],
    "tepung_terigu": ["tepung", "terigu"],
}

_KABUPATEN_KEYWORDS = [
    "surabaya", "malang", "kediri", "blitar", "madiun", "mojokerto", "pasuruan",
    "probolinggo", "jember", "banyuwangi", "sidoarjo", "gresik", "lamongan",
    "tuban", "bojonegoro", "ngawi", "magetan", "ponorogo", "trenggalek",
    "tulungagung", "nganjuk", "jombang", "bangkalan", "sampang", "pamekasan",
    "sumenep", "lumajang", "bondowoso", "situbondo", "batu",
]

_VOLUME_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ton|kg|kuintal)", re.IGNORECASE)


def _detect_commodity(message: str) -> Optional[str]:
    msg = message.lower()
    # Sort by keyword length desc so "cabai merah" wins over "cabai"
    candidates = sorted(
        _COMMODITY_KEYWORDS.items(),
        key=lambda kv: -max(len(k) for k in kv[1]),
    )
    for code, keywords in candidates:
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in msg:
                return code
    return None


def _detect_kabupaten(message: str) -> Optional[str]:
    msg = message.lower()
    for kab in _KABUPATEN_KEYWORDS:
        if kab in msg:
            return kab.title()
    return None


def _detect_volume_tons(message: str) -> Optional[float]:
    m = _VOLUME_RE.search(message)
    if not m:
        return None
    num = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    if unit == "kg":
        return num / 1000.0
    if unit == "kuintal":
        return num / 10.0
    return num  # ton


def _mock_classify(message: str) -> Dict[str, Any]:
    """Keyword heuristic that mimics what a real LLM would extract."""
    msg = message.lower()
    commodity = _detect_commodity(message)
    kabupaten = _detect_kabupaten(message)
    volume = _detect_volume_tons(message)

    # Order matters: more specific patterns first
    if any(kw in msg for kw in ["harga", "berapa", "price"]):
        return {
            "intent": "harga_lookup",
            "slots": {"commodity": commodity, "kabupaten": kabupaten},
        }
    if any(kw in msg for kw in ["cari pembeli", "jual", "punya", "surplus", "pasar untuk"]):
        return {
            "intent": "cari_pembeli",
            "slots": {
                "commodity": commodity,
                "kabupaten_origin": kabupaten,
                "volume_tons": volume,
            },
        }
    if any(kw in msg for kw in ["butuh", "beli", "supplier", "cari penjual", "cari supplier"]):
        return {
            "intent": "cari_penjual",
            "slots": {
                "commodity": commodity,
                "kabupaten_dest": kabupaten,
                "volume_tons": volume,
            },
        }
    return {"intent": "fallback", "slots": {}}


def _mock_answer(query: str, context: str) -> str:
    """Generic helpful response when there is no LLM available."""
    return (
        "Halo! Saya asisten AgriFlow. Coba kirim pesan dengan format:\n"
        "• \"Harga cabai di Malang\"\n"
        "• \"Cari pembeli 50 ton cabai Kediri\"\n"
        "• \"Butuh 100 ton beras untuk Surabaya\"\n\n"
        "Saya akan bantu cari match terbaik dari engine AgriFlow."
    )

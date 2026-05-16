"""
Smoke tests for the WhatsApp bot — runs entirely in mock mode (no live Gemini/Twilio).
"""

from __future__ import annotations
import os
import sys

# Force MOCK_MODE before importing any whatsapp_bot module so settings load mocked
os.environ["MOCK_MODE"] = "true"

# Ensure project root importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest

from sample_data.loader import load_all_sample_data
from whatsapp_bot.gemini_client import GeminiClient
from whatsapp_bot.handlers import EngineData, dispatch
from whatsapp_bot.intent import (
    INTENT_CARI_PEMBELI, INTENT_CARI_PENJUAL,
    INTENT_FALLBACK, INTENT_HARGA_LOOKUP, classify,
)
from whatsapp_bot.twilio_client import make_twiml_response


@pytest.fixture(scope="module")
def data():
    return EngineData(load_all_sample_data())


@pytest.fixture(scope="module")
def gemini():
    return GeminiClient(mock=True)


# =============================================================================
# Intent classification — mock heuristic
# =============================================================================

class TestIntentClassification:
    def test_harga_lookup(self, gemini, data):
        intent = classify(
            "Harga cabai di Malang?", gemini, data.kabupaten, data.komoditas,
        )
        assert intent.name == INTENT_HARGA_LOOKUP
        assert intent.commodity == "cabai_merah"
        assert intent.kabupaten_id is not None
        assert "malang" in intent.kabupaten_name.lower()

    def test_cari_pembeli_with_volume(self, gemini, data):
        intent = classify(
            "Saya punya 50 ton cabai di Kediri, cari pembeli",
            gemini, data.kabupaten, data.komoditas,
        )
        assert intent.name == INTENT_CARI_PEMBELI
        assert intent.commodity == "cabai_merah"
        assert intent.volume_tons == 50.0

    def test_cari_penjual(self, gemini, data):
        intent = classify(
            "Butuh 100 ton beras untuk Surabaya",
            gemini, data.kabupaten, data.komoditas,
        )
        assert intent.name == INTENT_CARI_PENJUAL
        assert intent.commodity == "beras_premium"
        assert intent.volume_tons == 100.0

    def test_fallback_for_greeting(self, gemini, data):
        intent = classify("Halo, apa kabar?", gemini, data.kabupaten, data.komoditas)
        assert intent.name == INTENT_FALLBACK

    def test_kabupaten_normalization(self, gemini, data):
        # "Kota Malang" should resolve same as "Malang"
        intent = classify(
            "Harga beras Kota Malang", gemini, data.kabupaten, data.komoditas,
        )
        assert intent.kabupaten_id is not None


# =============================================================================
# Bahasa Jawa ngoko — keyword shim (pre-Sahabat-AI / M4)
# =============================================================================

class TestJavaneseShim:
    def test_jawa_harga_lookup(self, gemini, data):
        # "Pira regane lombok ing Malang?" = "Berapa harga cabai di Malang?"
        intent = classify(
            "Pira regane lombok ing Malang?",
            gemini, data.kabupaten, data.komoditas,
        )
        assert intent.name == INTENT_HARGA_LOOKUP
        assert intent.commodity == "cabai_merah"
        assert "malang" in intent.kabupaten_name.lower()

    def test_jawa_cari_pembeli(self, gemini, data):
        # "Aku duwe 50 ton brambang ing Probolinggo, golek pembeli"
        # = "Saya punya 50 ton bawang merah di Probolinggo, cari pembeli"
        intent = classify(
            "Aku duwe 50 ton brambang ing Probolinggo, golek pembeli",
            gemini, data.kabupaten, data.komoditas,
        )
        assert intent.name == INTENT_CARI_PEMBELI
        assert intent.commodity == "bawang_merah"
        assert intent.volume_tons == 50.0

    def test_jawa_cari_penjual(self, gemini, data):
        # "Butuh 100 ton sega kanggo Surabaya" = "...beras untuk Surabaya"
        intent = classify(
            "Butuh 100 ton sega kanggo Surabaya",
            gemini, data.kabupaten, data.komoditas,
        )
        assert intent.name == INTENT_CARI_PENJUAL
        assert intent.commodity == "beras_premium"
        assert intent.volume_tons == 100.0


# =============================================================================
# Handler dispatch — full pipeline
# =============================================================================

class TestHandlerDispatch:
    def test_harga_lookup_returns_text(self, gemini, data):
        intent = classify(
            "Harga cabai di Malang", gemini, data.kabupaten, data.komoditas,
        )
        reply = dispatch(intent, data, gemini)
        assert isinstance(reply, str)
        assert len(reply) > 0
        # Should mention either a price or "tidak ada data"
        assert any(token in reply.lower() for token in ["rp", "median", "tidak ada", "belum ada"])

    def test_cari_pembeli_runs_engine(self, gemini, data):
        intent = classify(
            "Cari pembeli cabai Kediri", gemini, data.kabupaten, data.komoditas,
        )
        reply = dispatch(intent, data, gemini)
        assert isinstance(reply, str)
        # Either some matches or a "no match" message
        assert any(token in reply.lower() for token in ["pembeli", "ton", "belum ada"])

    def test_cari_penjual_runs_engine(self, gemini, data):
        intent = classify(
            "Butuh 100 ton beras untuk Surabaya",
            gemini, data.kabupaten, data.komoditas,
        )
        reply = dispatch(intent, data, gemini)
        assert isinstance(reply, str)
        assert any(token in reply.lower() for token in ["supplier", "ton", "belum ada"])

    def test_missing_slot_returns_help(self, gemini, data):
        # No commodity, no kabupaten — should ask for more info
        intent = classify("Harga?", gemini, data.kabupaten, data.komoditas)
        reply = dispatch(intent, data, gemini)
        assert any(token in reply.lower() for token in ["maaf", "format", "contoh", "halo"])

    def test_fallback_returns_help_message(self, gemini, data):
        intent = classify("Halo", gemini, data.kabupaten, data.komoditas)
        reply = dispatch(intent, data, gemini)
        assert "agriflow" in reply.lower()


# =============================================================================
# TwiML response shape
# =============================================================================

class TestTwiMLResponse:
    def test_basic_response(self):
        xml = make_twiml_response("Hello world")
        assert xml.startswith('<?xml')
        assert "<Response>" in xml
        assert "<Message>Hello world</Message>" in xml

    def test_xml_escaping(self):
        # Critical — user input could contain XML control chars
        xml = make_twiml_response("Price < 5000 & quantity > 0")
        assert "&lt;" in xml
        assert "&amp;" in xml
        assert "&gt;" in xml

    def test_empty_message(self):
        xml = make_twiml_response("")
        assert "<Message></Message>" in xml


# =============================================================================
# FastAPI route smoke tests (TestClient)
# =============================================================================

class TestFastAPIRoutes:
    @pytest.fixture(scope="class")
    def client(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi not installed")
        from whatsapp_bot.server import app
        # Context manager triggers lifespan startup → engine data loaded
        with TestClient(app) as c:
            yield c

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["mock_mode"] is True
        assert body["data_loaded"] is True
        assert body["kabupaten_count"] > 0

    def test_chat_debug(self, client):
        r = client.post("/chat", json={"message": "Harga cabai di Malang"})
        assert r.status_code == 200
        body = r.json()
        assert "reply" in body
        assert len(body["reply"]) > 0

    def test_chat_empty_message_rejected(self, client):
        r = client.post("/chat", json={"message": ""})
        assert r.status_code == 400

    def test_whatsapp_webhook_returns_twiml(self, client):
        r = client.post(
            "/whatsapp",
            data={"Body": "Harga cabai di Malang", "From": "whatsapp:+6281234567890"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/xml")
        assert "<Response>" in r.text
        assert "<Message>" in r.text

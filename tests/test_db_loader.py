"""
Tests for db/db_loader.py and DATA_BACKEND env-switch in server.py.

These tests run fully offline — no Supabase/Postgres connection is made.

Coverage:
  (a) Import: db.db_loader is importable without any env vars set.
  (b) No-env error: load_all() raises RuntimeError with a clear message
      when SUPABASE_DB_URL is absent.
  (c) CSV default: server._load_data_backend() returns CSV data when
      DATA_BACKEND is not set (or is 'csv').
  (d) Backend dispatch: DATA_BACKEND=postgres routes to db_loader.load_all().
  (e) Return-key contract: both backends return the same 6 top-level keys.
"""

from __future__ import annotations

import os
import sys

# Ensure project root on path (same pattern as other tests)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest


# =============================================================================
# (a) Import succeeds without any env vars
# =============================================================================

class TestImport:
    def test_db_loader_importable(self):
        """db.db_loader must be importable regardless of env state."""
        import db.db_loader as m  # noqa: F401
        assert hasattr(m, "load_all"), "load_all function must exist"

    def test_db_package_importable(self):
        """db/__init__.py must be importable."""
        import db  # noqa: F401


# =============================================================================
# (b) load_all() raises RuntimeError when SUPABASE_DB_URL is absent
# =============================================================================

class TestNoEnvRaisesRuntimeError:
    def test_missing_env_raises(self, monkeypatch):
        """load_all() must raise RuntimeError with a descriptive message."""
        # Guarantee the env var is absent for this test
        monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

        from db.db_loader import load_all
        with pytest.raises(RuntimeError) as exc_info:
            load_all()

        msg = str(exc_info.value)
        assert "SUPABASE_DB_URL" in msg, (
            "RuntimeError should name the missing env var so the operator knows what to set"
        )

    def test_empty_string_env_raises(self, monkeypatch):
        """An empty SUPABASE_DB_URL must be treated the same as absent."""
        monkeypatch.setenv("SUPABASE_DB_URL", "")

        from db.db_loader import load_all
        with pytest.raises(RuntimeError) as exc_info:
            load_all()

        assert "SUPABASE_DB_URL" in str(exc_info.value)


# =============================================================================
# (c) CSV default path — server._load_data_backend() uses CSV when
#     DATA_BACKEND is unset or 'csv'
# =============================================================================

EXPECTED_KEYS = {"kabupaten", "komoditas", "surplus", "deficit", "weather", "historical_prices"}


class TestCsvDefaultPath:
    def test_unset_data_backend_uses_csv(self, monkeypatch):
        """Without DATA_BACKEND env, _load_data_backend() returns CSV data."""
        monkeypatch.delenv("DATA_BACKEND", raising=False)

        # Re-import so the function picks up clean env
        import importlib
        import whatsapp_bot.server as srv
        importlib.reload(srv)

        data = srv._load_data_backend()
        assert isinstance(data, dict)
        assert set(data.keys()) == EXPECTED_KEYS

    def test_explicit_csv_data_backend(self, monkeypatch):
        """DATA_BACKEND=csv must use CSV loader."""
        monkeypatch.setenv("DATA_BACKEND", "csv")

        import importlib
        import whatsapp_bot.server as srv
        importlib.reload(srv)

        data = srv._load_data_backend()
        assert isinstance(data, dict)
        assert set(data.keys()) == EXPECTED_KEYS

    def test_csv_data_has_content(self, monkeypatch):
        """CSV path must load at least one kabupaten and one komoditas."""
        monkeypatch.delenv("DATA_BACKEND", raising=False)

        import importlib
        import whatsapp_bot.server as srv
        importlib.reload(srv)

        data = srv._load_data_backend()
        assert len(data["kabupaten"]) > 0, "Expected kabupaten rows from CSV"
        assert len(data["komoditas"]) > 0, "Expected komoditas rows from CSV"
        assert len(data["surplus"]) > 0, "Expected surplus nodes from CSV"
        assert len(data["deficit"]) > 0, "Expected deficit nodes from CSV"


# =============================================================================
# (d) Postgres backend routes to db_loader.load_all (verified via mock)
# =============================================================================

class TestPostgresBackendDispatch:
    def test_postgres_backend_calls_db_loader(self, monkeypatch):
        """DATA_BACKEND=postgres must call db.db_loader.load_all, not CSV loader."""
        monkeypatch.setenv("DATA_BACKEND", "postgres")
        monkeypatch.setenv("SUPABASE_DB_URL", "postgresql+psycopg2://fake:fake@localhost:5432/fake")

        call_log: list[str] = []

        def fake_load_all():
            call_log.append("db_loader.load_all called")
            # Return the same shape as the real loader so downstream code is happy
            from sample_data.loader import load_all_sample_data
            return load_all_sample_data()

        import importlib
        import db.db_loader
        monkeypatch.setattr(db.db_loader, "load_all", fake_load_all)

        import whatsapp_bot.server as srv
        importlib.reload(srv)

        # Now call the dispatch function — it should route to our mock
        data = srv._load_data_backend()
        assert "db_loader.load_all called" in call_log, (
            "DATA_BACKEND=postgres did not call db.db_loader.load_all"
        )
        assert set(data.keys()) == EXPECTED_KEYS

    def test_postgres_backend_without_url_raises(self, monkeypatch):
        """DATA_BACKEND=postgres + missing SUPABASE_DB_URL => RuntimeError."""
        monkeypatch.setenv("DATA_BACKEND", "postgres")
        monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

        import importlib
        import whatsapp_bot.server as srv
        importlib.reload(srv)

        with pytest.raises(RuntimeError) as exc_info:
            srv._load_data_backend()

        assert "SUPABASE_DB_URL" in str(exc_info.value)


# =============================================================================
# (e) Return-key contract — both backends expose identical top-level keys
# =============================================================================

class TestReturnKeyContract:
    def test_csv_keys_match_contract(self, monkeypatch):
        monkeypatch.delenv("DATA_BACKEND", raising=False)

        import importlib
        import whatsapp_bot.server as srv
        importlib.reload(srv)

        data = srv._load_data_backend()
        assert set(data.keys()) == EXPECTED_KEYS

    def test_db_loader_signature_documented(self):
        """db_loader.load_all docstring must reference all 6 keys."""
        from db.db_loader import load_all
        doc = load_all.__doc__ or ""
        for key in EXPECTED_KEYS:
            assert key in doc, (
                f"Key '{key}' missing from db_loader.load_all docstring — "
                "keep docs aligned with the return contract"
            )

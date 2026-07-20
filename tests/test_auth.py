"""
Supabase JWT verification and endpoint gating.

The point of these tests is that the login actually protects something. Each
rejection case below is a way an attacker would try to get past it:
forged signature, no signature at all ("alg": "none"), expired token, wrong
audience, another project's secret, and simply omitting the header.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SECRET = "unit-test-jwt-secret"
OTHER_SECRET = "some-other-projects-secret"
SUB = "11111111-2222-3333-4444-555555555555"


def make_token(
    *, secret=SECRET, sub=SUB, aud="authenticated", expires_in=3600,
    algorithm="HS256", email="dinas@example.go.id",
):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub, "email": email, "role": "authenticated",
        "iat": now, "exp": now + timedelta(seconds=expires_in),
    }
    if aud is not None:
        payload["aud"] = aud
    return jwt.encode(payload, secret, algorithm=algorithm)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("PHONE_HASH_SALT", "t")
    from whatsapp_bot import server
    with TestClient(server.app) as c:
        yield c


@pytest.fixture
def strict_client(monkeypatch):
    """A client with REQUIRE_AUTH on — the production posture."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("PHONE_HASH_SALT", "t")
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    from whatsapp_bot import server
    with TestClient(server.app) as c:
        yield c


# =============================================================================
# A. TOKEN VERIFICATION
# =============================================================================

class TestA_Verification:

    def test_valid_token_is_accepted(self, client):
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=bearer(make_token()))
        assert r.status_code == 200

    def test_no_header_is_rejected(self, client):
        r = client.get("/billing/status", params={"phone": "+628111222333"})
        assert r.status_code == 401

    def test_forged_signature_is_rejected(self, client):
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=bearer(make_token(secret=OTHER_SECRET)))
        assert r.status_code == 401

    def test_alg_none_token_is_rejected(self, client):
        # The classic JWT bypass: strip the signature and claim it isn't needed.
        now = datetime.now(timezone.utc)
        unsigned = jwt.encode(
            {"sub": SUB, "aud": "authenticated", "exp": now + timedelta(hours=1)},
            key="", algorithm="none",
        )
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=bearer(unsigned))
        assert r.status_code == 401

    def test_expired_token_is_rejected(self, client):
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=bearer(make_token(expires_in=-60)))
        assert r.status_code == 401

    def test_wrong_audience_is_rejected(self, client):
        # A token minted for another Supabase surface must not open this door.
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=bearer(make_token(aud="some-other-service")))
        assert r.status_code == 401

    def test_token_without_subject_is_rejected(self, client):
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=bearer(make_token(sub=None)))
        assert r.status_code == 401

    @pytest.mark.parametrize("header", [
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic abc123"},
        {"Authorization": make_token()},          # missing the Bearer scheme
        {"Authorization": "Bearer not.a.token"},
    ])
    def test_malformed_headers_are_rejected(self, client, header):
        r = client.get("/billing/status", params={"phone": "+628111222333"},
                       headers=header)
        assert r.status_code == 401

    def test_rejection_does_not_leak_the_reason(self, client):
        # Expired vs forged must look identical, or a prober learns which
        # tokens are real.
        expired = client.get("/billing/status", params={"phone": "+628111222333"},
                             headers=bearer(make_token(expires_in=-60)))
        forged = client.get("/billing/status", params={"phone": "+628111222333"},
                            headers=bearer(make_token(secret=OTHER_SECRET)))
        assert expired.json() == forged.json()


# =============================================================================
# B. ENDPOINT GATING
# =============================================================================

class TestB_Gating:

    PREMIUM = [
        ("/api/v1/matches", {}),
        ("/api/v1/forecast", {"commodity": "cabai_rawit", "city": "3578"}),
        ("/api/v1/anomalies", {}),
    ]
    PUBLIC = ["/api/v1/commodities", "/api/v1/kabupaten"]

    @pytest.mark.parametrize("path,params", PREMIUM)
    def test_premium_open_when_require_auth_off(self, client, path, params):
        # Demo posture: judges can browse without an account.
        assert client.get(path, params=params).status_code != 401

    @pytest.mark.parametrize("path,params", PREMIUM)
    def test_premium_closed_when_require_auth_on(self, strict_client, path, params):
        assert strict_client.get(path, params=params).status_code == 401

    @pytest.mark.parametrize("path,params", PREMIUM)
    def test_premium_open_with_token_when_require_auth_on(self, strict_client, path, params):
        r = strict_client.get(path, params=params, headers=bearer(make_token()))
        assert r.status_code != 401

    @pytest.mark.parametrize("path", PUBLIC)
    def test_reference_data_stays_public(self, strict_client, path):
        # Commodity and kabupaten lists are public government reference data;
        # gating them would break the map for anonymous visitors.
        assert strict_client.get(path).status_code == 200

    def test_billing_status_ignores_require_auth_flag(self, client):
        # Per-person data is gated even in demo posture, because the endpoint
        # is an enumeration oracle for phone numbers.
        assert client.get("/billing/status",
                          params={"phone": "+628111222333"}).status_code == 401

    def test_health_is_always_public(self, strict_client):
        assert strict_client.get("/health").status_code == 200

    def test_health_reports_auth_posture(self, strict_client):
        body = strict_client.get("/health").json()
        assert body["auth_configured"] is True
        assert body["require_auth"] is True


# =============================================================================
# C. MISCONFIGURATION
# =============================================================================

class TestC_Misconfiguration:

    def test_unconfigured_auth_still_rejects_protected_routes(self, monkeypatch):
        # Fail closed: no secret and no URL must mean "nobody gets in",
        # never "everybody gets in".
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("PHONE_HASH_SALT", "t")
        from whatsapp_bot import server
        with TestClient(server.app) as c:
            r = c.get("/billing/status", params={"phone": "+628111222333"},
                      headers=bearer(make_token()))
            assert r.status_code == 401

    def test_health_flags_unconfigured_auth(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        from whatsapp_bot import server
        with TestClient(server.app) as c:
            assert c.get("/health").json()["auth_configured"] is False

"""
Free-tier quota, phone hashing, and the WhatsApp upgrade flow.

Covers:
    A. Identity  — normalization + salted hashing
    B. Store     — plan, usage counter, order lifecycle
    C. Service   — check/consume semantics, PRO bypass, expiry
    D. Commands  — parse_command precision
    E. Pipeline  — handle_message metering end to end
    F. HTTP      — /billing/* endpoints

Every test that touches state points QUOTA_STATE_PATH at a tmp_path file, so
the suite never reads or writes the developer's real .state/ directory.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whatsapp_bot import billing
from whatsapp_bot.subscription import (
    ORDER_PAID, ORDER_PENDING, PLAN_FREE, PLAN_PRO,
    Account, JsonStore, SubscriptionService,
    hash_phone, normalize_phone, now_wib, today_wib,
)


SALT = "test-salt"
ALICE = "whatsapp:+6281234567890"
BOB = "whatsapp:+6289876543210"
JWT_SECRET = "test-jwt-secret-not-a-real-one"


def make_token(*, sub="00000000-0000-0000-0000-000000000001",
               email="dinas@example.go.id", expires_in=3600, secret=JWT_SECRET):
    """Mint a Supabase-shaped HS256 access token."""
    import jwt as _jwt
    from datetime import datetime, timezone as _tz
    now = datetime.now(_tz.utc)
    return _jwt.encode(
        {
            "sub": sub, "email": email, "aud": "authenticated", "role": "authenticated",
            "iat": now, "exp": now + timedelta(seconds=expires_in),
        },
        secret, algorithm="HS256",
    )


def auth_header(**kw):
    return {"Authorization": f"Bearer {make_token(**kw)}"}


@pytest.fixture
def store(tmp_path):
    return JsonStore(path=tmp_path / "subs.json")


@pytest.fixture
def service(store):
    return SubscriptionService(store=store, free_daily_quota=2, pro_price_idr=25000)


@pytest.fixture
def alice(store):
    return hash_phone(ALICE, salt=SALT)


# =============================================================================
# A. IDENTITY
# =============================================================================

class TestA_Identity:

    def test_strips_whatsapp_prefix_and_separators(self):
        assert normalize_phone("whatsapp:+62812-3456-7890") == "6281234567890"

    def test_local_08_format_is_same_subscriber_as_62(self):
        # A farmer typing 08xx and Twilio reporting +628xx must be one account,
        # otherwise the quota is trivially reset by changing format.
        assert normalize_phone("081234567890") == normalize_phone("+6281234567890")

    def test_hash_is_stable_for_same_number(self):
        assert hash_phone(ALICE, salt=SALT) == hash_phone("+6281234567890", salt=SALT)

    def test_hash_differs_between_numbers(self):
        assert hash_phone(ALICE, salt=SALT) != hash_phone(BOB, salt=SALT)

    def test_salt_changes_the_digest(self):
        assert hash_phone(ALICE, salt="a") != hash_phone(ALICE, salt="b")

    def test_raw_number_is_not_recoverable_from_digest(self):
        digest = hash_phone(ALICE, salt=SALT)
        assert "6281234567890" not in digest
        assert len(digest) == 64

    def test_empty_sender_yields_empty_hash(self):
        assert hash_phone("", salt=SALT) == ""
        assert hash_phone("whatsapp:", salt=SALT) == ""

    def test_missing_salt_warns(self, monkeypatch):
        import whatsapp_bot.subscription as sub
        monkeypatch.setattr(sub, "_warned_about_salt", False)
        monkeypatch.delenv("PHONE_HASH_SALT", raising=False)
        with pytest.warns(RuntimeWarning, match="PHONE_HASH_SALT"):
            hash_phone(ALICE)


# =============================================================================
# B. STORE
# =============================================================================

class TestB_Store:

    def test_unknown_sender_defaults_to_free(self, store, alice):
        account = store.get_account(alice)
        assert account.plan == PLAN_FREE
        assert not account.is_pro

    def test_set_and_read_plan(self, store, alice):
        store.set_plan(alice, PLAN_PRO, now_wib() + timedelta(days=30))
        assert store.get_account(alice).is_pro

    def test_rejects_unknown_plan(self, store, alice):
        with pytest.raises(ValueError, match="unknown plan"):
            store.set_plan(alice, "ENTERPRISE")

    def test_usage_starts_at_zero_and_increments(self, store, alice):
        assert store.get_usage(alice) == 0
        assert store.increment_usage(alice) == 1
        assert store.increment_usage(alice) == 2
        assert store.get_usage(alice) == 2

    def test_usage_is_per_sender(self, store, alice):
        bob = hash_phone(BOB, salt=SALT)
        store.increment_usage(alice)
        assert store.get_usage(bob) == 0

    def test_usage_is_per_day(self, store, alice):
        store.increment_usage(alice)
        assert store.get_usage(alice, today_wib() - timedelta(days=1)) == 0

    def test_state_survives_a_new_store_instance(self, tmp_path, alice):
        path = tmp_path / "s.json"
        JsonStore(path=path).increment_usage(alice)
        assert JsonStore(path=path).get_usage(alice) == 1

    def test_corrupt_state_file_fails_open(self, tmp_path, alice):
        path = tmp_path / "s.json"
        path.write_text("{ not json", encoding="utf-8")
        # Losing counters must not take the bot down.
        assert JsonStore(path=path).get_usage(alice) == 0

    def test_old_usage_rows_are_pruned(self, store, alice):
        stale = today_wib() - timedelta(days=90)
        store.increment_usage(alice, stale)
        store.increment_usage(alice)  # triggers a write, and therefore a prune
        assert store.get_usage(alice, stale) == 0

    def test_order_lifecycle(self, service, alice):
        order = service.start_upgrade(alice)
        assert order.status == ORDER_PENDING
        assert order.amount_idr == 25000
        fetched = service.store.get_order(order.order_id)
        assert fetched is not None and fetched.phone_hash == alice
        assert service.store.mark_order_paid(order.order_id).status == ORDER_PAID

    def test_unknown_order_returns_none(self, store):
        assert store.get_order("AF-DEADBEEF") is None
        assert store.mark_order_paid("AF-DEADBEEF") is None

    def test_order_ids_are_unique(self, service, alice):
        ids = {service.start_upgrade(alice).order_id for _ in range(50)}
        assert len(ids) == 50


# =============================================================================
# C. SERVICE
# =============================================================================

class TestC_Service:

    def test_free_user_allowed_up_to_limit(self, service, alice):
        assert service.check(alice).allowed
        service.consume(alice)
        assert service.check(alice).allowed
        service.consume(alice)
        assert not service.check(alice).allowed

    def test_remaining_counts_down(self, service, alice):
        assert service.check(alice).remaining == 2
        service.consume(alice)
        assert service.check(alice).remaining == 1
        service.consume(alice)
        assert service.check(alice).remaining == 0

    def test_check_alone_does_not_consume(self, service, alice):
        for _ in range(10):
            service.check(alice)
        assert service.check(alice).used_today == 0

    def test_pro_is_never_blocked_or_counted(self, service, alice):
        service.store.set_plan(alice, PLAN_PRO, now_wib() + timedelta(days=30))
        for _ in range(20):
            assert service.check(alice).allowed
            service.consume(alice)
        assert service.store.get_usage(alice) == 0

    def test_pro_reports_unlimited_sentinel(self, service, alice):
        service.store.set_plan(alice, PLAN_PRO, now_wib() + timedelta(days=30))
        assert service.check(alice).remaining == -1

    def test_expired_pro_falls_back_to_free_limits(self, service, alice):
        service.store.set_plan(alice, PLAN_PRO, now_wib() - timedelta(days=1))
        assert not service.account(alice).is_pro
        service.consume(alice)
        service.consume(alice)
        assert not service.check(alice).allowed

    def test_pro_without_expiry_is_perpetual(self, alice):
        assert Account(alice, PLAN_PRO, None).is_pro

    def test_quota_resets_next_day(self, service, alice):
        service.consume(alice)
        service.consume(alice)
        assert not service.check(alice).allowed
        # A new day is a new counter row; yesterday's row does not carry over.
        assert service.store.get_usage(alice, today_wib() + timedelta(days=1)) == 0

    def test_confirm_payment_grants_pro(self, service, alice):
        order = service.start_upgrade(alice)
        account = service.confirm_payment(order.order_id)
        assert account is not None and account.is_pro
        assert service.check(alice).allowed

    def test_confirm_unknown_order_returns_none(self, service):
        assert service.confirm_payment("AF-DEADBEEF") is None

    def test_repeated_confirm_extends_rather_than_shortens(self, service, alice):
        order = service.start_upgrade(alice)
        first = service.confirm_payment(order.order_id)
        second = service.confirm_payment(order.order_id)
        assert first.expires_at is not None and second.expires_at is not None
        # A retried webhook must never leave the user with less time than before.
        assert second.expires_at >= first.expires_at

    def test_quota_limit_is_configurable(self, store, alice):
        svc = SubscriptionService(store=store, free_daily_quota=5)
        for _ in range(5):
            assert svc.check(alice).allowed
            svc.consume(alice)
        assert not svc.check(alice).allowed


# =============================================================================
# D. COMMAND PARSING
# =============================================================================

class TestD_Commands:

    @pytest.mark.parametrize("text", ["UPGRADE", "upgrade", " Upgrade ", "PRO", "langganan"])
    def test_upgrade_words(self, text):
        assert billing.parse_command(text).name == billing.CMD_UPGRADE

    @pytest.mark.parametrize("text", ["STATUS", "kuota", "sisa"])
    def test_status_words(self, text):
        assert billing.parse_command(text).name == billing.CMD_STATUS

    @pytest.mark.parametrize("text", ["help", "bantuan", "menu", "halo"])
    def test_help_words(self, text):
        assert billing.parse_command(text).name == billing.CMD_HELP

    def test_pay_command_extracts_order_id(self):
        cmd = billing.parse_command("BAYAR AF-1a2b3c4d")
        assert cmd.name == billing.CMD_PAY
        assert cmd.order_id == "AF-1A2B3C4D"

    @pytest.mark.parametrize("text", [
        "status harga cabai di Malang",   # 'status' as a sentence opener
        "Harga cabai di Malang",
        "berapa sisa stok beras Kediri",  # contains 'sisa'
        "",
    ])
    def test_real_questions_fall_through_to_nlu(self, text):
        assert billing.parse_command(text) is None

    def test_bare_pay_word_is_an_upgrade_request(self):
        # 'bayar' with no order id means "I want to pay", not "settle order X".
        assert billing.parse_command("bayar").name == billing.CMD_UPGRADE


# =============================================================================
# E. COMMAND HANDLING
# =============================================================================

class TestE_CommandHandling:

    def test_status_shows_free_quota(self, service, alice):
        reply = billing.handle_command(
            billing.Command(billing.CMD_STATUS), alice, service)
        assert "GRATIS" in reply and "2" in reply

    def test_status_shows_pro(self, service, alice):
        service.store.set_plan(alice, PLAN_PRO, now_wib() + timedelta(days=30))
        reply = billing.handle_command(
            billing.Command(billing.CMD_STATUS), alice, service)
        assert "PRO" in reply and "tanpa batas" in reply

    def test_upgrade_returns_order_and_link(self, service, alice):
        reply = billing.handle_command(
            billing.Command(billing.CMD_UPGRADE), alice, service)
        assert "AF-" in reply and "/billing/pay/" in reply
        assert "Rp 25.000" in reply

    def test_upgrade_when_already_pro_shows_status(self, service, alice):
        service.store.set_plan(alice, PLAN_PRO, now_wib() + timedelta(days=30))
        reply = billing.handle_command(
            billing.Command(billing.CMD_UPGRADE), alice, service)
        assert "Status akun: PRO" in reply

    def test_mock_pay_activates_pro(self, service, alice, monkeypatch):
        monkeypatch.setenv("BILLING_MOCK", "true")
        order = service.start_upgrade(alice)
        reply = billing.handle_command(
            billing.Command(billing.CMD_PAY, order.order_id), alice, service)
        assert "PRO" in reply
        assert service.account(alice).is_pro

    def test_mock_pay_refused_when_mock_disabled(self, service, alice, monkeypatch):
        monkeypatch.setenv("BILLING_MOCK", "false")
        order = service.start_upgrade(alice)
        reply = billing.handle_command(
            billing.Command(billing.CMD_PAY, order.order_id), alice, service)
        assert "tidak tersedia" in reply
        assert not service.account(alice).is_pro

    def test_cannot_settle_someone_elses_order(self, service, alice, monkeypatch):
        monkeypatch.setenv("BILLING_MOCK", "true")
        bob = hash_phone(BOB, salt=SALT)
        order = service.start_upgrade(alice)
        reply = billing.handle_command(
            billing.Command(billing.CMD_PAY, order.order_id), bob, service)
        assert "tidak ditemukan" in reply
        assert not service.account(bob).is_pro


# =============================================================================
# F. PIPELINE — handle_message metering
# =============================================================================

@pytest.fixture
def bot(tmp_path, monkeypatch):
    """A server module wired to an isolated quota store."""
    monkeypatch.setenv("PHONE_HASH_SALT", SALT)
    monkeypatch.setenv("BILLING_MOCK", "true")
    from whatsapp_bot import server
    # The paywall is off by default; these tests are specifically about it.
    # Settings is a frozen dataclass, so swap the whole object on the module.
    monkeypatch.setattr(server, "settings", replace(server.settings, quota_enabled=True))
    server.state.subs = SubscriptionService(
        store=JsonStore(path=tmp_path / "bot.json"), free_daily_quota=2)
    yield server
    server.state.subs = None


class TestF_Pipeline:

    QUESTION = "Harga cabai di Malang"

    def test_anonymous_caller_is_not_metered(self, bot):
        for _ in range(5):
            reply = bot.handle_message(self.QUESTION)
        assert "Kuota gratis" not in reply

    def test_third_query_hits_the_paywall(self, bot):
        bot.handle_message(self.QUESTION, sender=ALICE)
        bot.handle_message(self.QUESTION, sender=ALICE)
        reply = bot.handle_message(self.QUESTION, sender=ALICE)
        assert "Kuota gratis" in reply
        assert "AF-" in reply

    def test_quota_is_per_sender(self, bot):
        bot.handle_message(self.QUESTION, sender=ALICE)
        bot.handle_message(self.QUESTION, sender=ALICE)
        reply = bot.handle_message(self.QUESTION, sender=BOB)
        assert "Kuota gratis" not in reply

    def test_status_command_is_free(self, bot):
        for _ in range(10):
            bot.handle_message("STATUS", sender=ALICE)
        reply = bot.handle_message(self.QUESTION, sender=ALICE)
        assert "Kuota gratis" not in reply

    def test_paywalled_user_can_still_reach_status_and_upgrade(self, bot):
        bot.handle_message(self.QUESTION, sender=ALICE)
        bot.handle_message(self.QUESTION, sender=ALICE)
        assert "Status akun" in bot.handle_message("STATUS", sender=ALICE)
        assert "/billing/pay/" in bot.handle_message("UPGRADE", sender=ALICE)

    def test_incomplete_question_is_not_billed(self, bot):
        # Being asked to rephrase must be free, or typos burn the allowance.
        for _ in range(5):
            bot.handle_message("harga", sender=ALICE)
        reply = bot.handle_message(self.QUESTION, sender=ALICE)
        assert "Kuota gratis" not in reply

    def test_pay_flow_restores_access(self, bot):
        bot.handle_message(self.QUESTION, sender=ALICE)
        bot.handle_message(self.QUESTION, sender=ALICE)
        offer = bot.handle_message(self.QUESTION, sender=ALICE)
        order_id = [w for w in offer.replace("\n", " ").split() if w.startswith("AF-")][0]
        paid = bot.handle_message(f"BAYAR {order_id}", sender=ALICE)
        assert "PRO" in paid
        reply = bot.handle_message(self.QUESTION, sender=ALICE)
        assert "Kuota gratis" not in reply

    def test_pro_user_is_never_paywalled(self, bot):
        phone_hash = hash_phone(ALICE, salt=SALT)
        bot.state.subs.store.set_plan(phone_hash, PLAN_PRO, now_wib() + timedelta(days=30))
        for _ in range(10):
            reply = bot.handle_message(self.QUESTION, sender=ALICE)
        assert "Kuota gratis" not in reply


# =============================================================================
# G. HTTP ENDPOINTS
# =============================================================================

@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("PHONE_HASH_SALT", SALT)
    monkeypatch.setenv("BILLING_MOCK", "true")
    # HS256 shared-secret mode so tests can mint genuine tokens without a
    # network round trip to a JWKS endpoint.
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from whatsapp_bot import server
    monkeypatch.setattr(server, "settings", replace(server.settings, quota_enabled=True))
    with TestClient(server.app) as c:
        server.state.subs = SubscriptionService(
            store=JsonStore(path=tmp_path / "http.json"), free_daily_quota=2)
        yield c
    server.state.subs = None


class TestG_Http:

    def test_health_reports_billing_config(self, client):
        body = client.get("/health").json()
        assert body["free_daily_quota"] == 2
        assert body["billing_mock"] is True
        assert "phone_hash_salted" in body

    def test_billing_status_for_unknown_number(self, client):
        body = client.get("/billing/status", params={"phone": "+6281111111111"},
                          headers=auth_header()).json()
        assert body["plan"] == PLAN_FREE
        assert body["remaining"] == 2

    def test_billing_status_rejects_garbage(self, client):
        r = client.get("/billing/status", params={"phone": "abc"}, headers=auth_header())
        assert r.status_code == 400

    def test_pay_page_renders_for_real_order(self, client):
        from whatsapp_bot import server
        alice = hash_phone(ALICE, salt=SALT)
        order = server.state.subs.start_upgrade(alice)
        r = client.get(f"/billing/pay/{order.order_id}")
        assert r.status_code == 200
        assert order.order_id in r.text

    def test_pay_page_404s_for_unknown_order(self, client):
        assert client.get("/billing/pay/AF-DEADBEEF").status_code == 404

    def test_confirm_grants_pro_and_is_visible_in_status(self, client):
        from whatsapp_bot import server
        alice = hash_phone(ALICE, salt=SALT)
        order = server.state.subs.start_upgrade(alice)
        r = client.post("/billing/confirm", json={"order_id": order.order_id})
        assert r.status_code == 200 and r.json()["plan"] == PLAN_PRO
        body = client.get("/billing/status", params={"phone": ALICE},
                          headers=auth_header()).json()
        assert body["is_pro"] is True

    def test_confirm_unknown_order_404s(self, client):
        r = client.post("/billing/confirm", json={"order_id": "AF-DEADBEEF"})
        assert r.status_code == 404

    def test_confirm_requires_order_id(self, client):
        assert client.post("/billing/confirm", json={}).status_code == 400

    def test_whatsapp_webhook_meters_by_sender(self, client):
        def ask():
            return client.post("/whatsapp", data={
                "Body": "Harga cabai di Malang", "From": ALICE,
            }).text
        ask()
        ask()
        assert "Kuota gratis" in ask()

"""
Upgrade flow for WhatsApp — command parsing and Indonesian reply copy.

WHY THE PAYMENT PAGE IS A LINK
------------------------------
WhatsApp has no in-chat checkout available to a Twilio-hosted bot in Indonesia.
The flow therefore stays inside the conversation but the payment tap opens a
browser: bot replies with a link -> user pays -> the gateway calls our webhook
-> the bot confirms in-chat. Nothing about the user's journey leaves WhatsApp
except the payment page itself.

MOCK MODE
---------
BILLING_MOCK=true (default) skips the gateway entirely: the link points at our
own /billing/pay/{order_id} page and the WhatsApp command `BAYAR <order_id>`
settles the order directly. This keeps the demo runnable offline with no
merchant account. The mock settle path is refused when BILLING_MOCK=false so a
production deployment cannot be upgraded for free by typing a command.

Replies are plain text: WhatsApp does not render markdown the way the dashboard
does, so this module uses bullets and blank lines rather than bold/heading syntax.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from .subscription import (
    Account, AccessDecision, Order, SubscriptionService,
    PLAN_PRO, ORDER_PAID,
)

# Commands the user can send. All are free — a user who has exhausted their
# quota must always be able to check status and pay, or the paywall is a dead end.
CMD_UPGRADE = "upgrade"
CMD_STATUS = "status"
CMD_PAY = "pay"
CMD_HELP = "help"

_UPGRADE_WORDS = {"upgrade", "pro", "berlangganan", "langganan", "premium", "bayar"}
_STATUS_WORDS = {"status", "kuota", "quota", "sisa", "akun"}
_HELP_WORDS = {"help", "bantuan", "menu", "mulai", "start", "halo", "hai"}

# `BAYAR AF-1A2B3C4D` — the mock settle command.
_PAY_RE = re.compile(r"^\s*(?:bayar|pay|lunas)\s+(af-[0-9a-f]{8})\s*$", re.IGNORECASE)


def billing_mock_enabled() -> bool:
    return os.getenv("BILLING_MOCK", "true").strip().lower() in {"1", "true", "yes", "on"}


def _base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def _idr(amount: float) -> str:
    return f"Rp {amount:,.0f}".replace(",", ".")


# Month names are mapped explicitly rather than via locale: setlocale is
# process-global (it would leak into every other thread) and the id_ID locale
# is not installed on most Windows and slim Docker images.
_BULAN = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def _tanggal(dt) -> str:
    return f"{dt.day} {_BULAN[dt.month - 1]} {dt.year}"


# =============================================================================
# COMMAND PARSING
# =============================================================================

@dataclass(frozen=True)
class Command:
    name: str
    order_id: Optional[str] = None


def parse_command(message: str) -> Optional[Command]:
    """
    Recognize a billing/help command, or return None to let the NLU handle it.

    Matching is deliberately strict — only a bare keyword counts. 'status' alone
    is the status command, but 'status harga cabai di Malang' is a price
    question and must fall through to intent classification.
    """
    text = (message or "").strip().lower()
    if not text:
        return None

    pay = _PAY_RE.match(text)
    if pay:
        return Command(CMD_PAY, order_id=pay.group(1).upper())

    word = text.strip("!?.,")
    if word in _UPGRADE_WORDS:
        return Command(CMD_UPGRADE)
    if word in _STATUS_WORDS:
        return Command(CMD_STATUS)
    if word in _HELP_WORDS:
        return Command(CMD_HELP)
    return None


# =============================================================================
# REPLY COPY
# =============================================================================

def payment_url(order: Order) -> str:
    return f"{_base_url()}/billing/pay/{order.order_id}"


def upgrade_offer(order: Order, *, reason: str = "") -> str:
    """Reply shown when the user asks to upgrade, or hits the quota wall."""
    lines = []
    if reason:
        lines += [reason, ""]
    lines += [
        f"Paket AgriFlow PRO — {_idr(order.amount_idr)} / 30 hari",
        "",
        "Yang Anda dapat:",
        "• Tanya harga tanpa batas",
        "• Prediksi harga 30 hari ke depan",
        "• Peringatan harga tidak wajar",
        "• Rekomendasi pembeli dan supplier lengkap",
        "",
        f"Bayar di sini:\n{payment_url(order)}",
        "",
        f"Nomor pesanan: {order.order_id}",
    ]
    if billing_mock_enabled():
        lines += [
            "",
            f"[MODE DEMO] Balas \"BAYAR {order.order_id}\" untuk mengaktifkan "
            "tanpa pembayaran sungguhan.",
        ]
    return "\n".join(lines)


def quota_exceeded(decision: AccessDecision, order: Order) -> str:
    return upgrade_offer(
        order,
        reason=(
            f"Kuota gratis Anda hari ini sudah terpakai "
            f"({decision.used_today} dari {decision.limit} pertanyaan).\n"
            "Kuota diperbarui otomatis besok pukul 00.00 WIB."
        ),
    )


def status_reply(account: Account, decision: AccessDecision) -> str:
    if account.is_pro:
        exp = _tanggal(account.expires_at) if account.expires_at else "tanpa batas waktu"
        return (
            "Status akun: PRO\n"
            f"Aktif sampai: {exp}\n"
            "Pertanyaan: tanpa batas\n\n"
            "Terima kasih sudah berlangganan AgriFlow."
        )
    return (
        "Status akun: GRATIS\n"
        f"Terpakai hari ini: {decision.used_today} dari {decision.limit} pertanyaan\n"
        f"Sisa hari ini: {decision.remaining}\n"
        "Kuota diperbarui setiap pukul 00.00 WIB.\n\n"
        "Balas \"UPGRADE\" untuk pertanyaan tanpa batas."
    )


def payment_success(account: Account) -> str:
    exp = _tanggal(account.expires_at) if account.expires_at else "tanpa batas waktu"
    return (
        "Pembayaran diterima. Akun Anda sekarang PRO.\n"
        f"Aktif sampai: {exp}\n\n"
        "Silakan bertanya sepuasnya, misalnya:\n"
        "• \"Harga cabai di Malang\"\n"
        "• \"Prediksi harga bawang merah Surabaya\"\n"
        "• \"Cari pembeli 50 ton cabai Kediri\""
    )


def payment_not_found(order_id: str) -> str:
    return (
        f"Pesanan {order_id} tidak ditemukan atau sudah kedaluwarsa.\n"
        "Balas \"UPGRADE\" untuk membuat pesanan baru."
    )


def mock_disabled() -> str:
    return (
        "Aktivasi manual tidak tersedia di lingkungan ini.\n"
        "Silakan selesaikan pembayaran melalui tautan yang kami kirim."
    )


def help_reply(account: Account, decision: AccessDecision) -> str:
    if account.is_pro:
        quota_line = "Anda pengguna PRO — pertanyaan tanpa batas."
    else:
        quota_line = (
            f"Kuota gratis: {decision.remaining} dari {decision.limit} "
            "pertanyaan tersisa hari ini."
        )
    return (
        "AgriFlow — informasi pangan Jawa Timur lewat WhatsApp.\n\n"
        "Contoh pertanyaan:\n"
        "• \"Harga cabai di Malang\"\n"
        "• \"Prediksi harga bawang merah Surabaya\"\n"
        "• \"Anomali harga telur Surabaya\"\n"
        "• \"Cari pembeli 50 ton cabai Kediri\"\n\n"
        "Perintah:\n"
        "• STATUS — cek sisa kuota\n"
        "• UPGRADE — berlangganan PRO\n\n"
        + quota_line
    )


# =============================================================================
# FLOW ORCHESTRATION
# =============================================================================

def handle_command(
    command: Command, phone_hash: str, service: SubscriptionService
) -> str:
    """Execute a billing/help command. Never consumes quota."""
    account = service.account(phone_hash)
    decision = service.check(phone_hash)

    if command.name == CMD_STATUS:
        return status_reply(account, decision)

    if command.name == CMD_HELP:
        return help_reply(account, decision)

    if command.name == CMD_UPGRADE:
        if account.is_pro:
            return status_reply(account, decision)
        return upgrade_offer(service.start_upgrade(phone_hash))

    if command.name == CMD_PAY:
        if not billing_mock_enabled():
            return mock_disabled()
        order = service.store.get_order(command.order_id or "")
        if order is None:
            return payment_not_found(command.order_id or "")
        # Confirm against the order's own phone_hash, not the sender's, but
        # refuse if they differ — otherwise anyone who learns an order id could
        # settle someone else's subscription onto their own number.
        if order.phone_hash != phone_hash:
            return payment_not_found(command.order_id or "")
        updated = service.confirm_payment(order.order_id)
        if updated is None:
            return payment_not_found(command.order_id or "")
        return payment_success(updated)

    return help_reply(account, decision)

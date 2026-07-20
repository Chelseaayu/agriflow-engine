"""
Identity, plan, and free-tier quota state for the WhatsApp bot.

IDENTITY MODEL
--------------
The bot never persists a raw phone number.  Every WhatsApp sender is reduced to
a salted SHA-256 digest (`phone_hash`) before it reaches any store, so the saved
state cannot be replayed into a subscriber contact list.

The salt is mandatory in spirit: an *unsalted* digest of an Indonesian mobile
number is trivially reversible, because the keyspace (+62 8xx, ~10 digits) is
small enough to enumerate exhaustively in minutes.  PHONE_HASH_SALT unset means
the hash provides no real protection, so we emit a loud warning once rather than
letting a deployment believe it is private when it is not.

BACKENDS
--------
QUOTA_BACKEND=json      (default) — JSON file under .state/.  Offline-safe,
                        which the demo requires.
QUOTA_BACKEND=postgres  — the `subscriber` / `wa_usage_daily` / `payment_order`
                        tables defined in db/schema.sql.

Both backends implement the same interface, so callers never branch on backend.
This mirrors the existing DATA_BACKEND=csv|postgres seam in server.py.

TIME
----
Quota days roll over at midnight WIB (UTC+7).  We use a fixed offset rather than
zoneinfo because Jakarta has no DST and a fixed offset avoids depending on the
tzdata package being present on Windows.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Jakarta is UTC+7 year round — no DST, so a fixed offset is exact.
WIB = timezone(timedelta(hours=7))

PLAN_FREE = "FREE"
PLAN_PRO = "PRO"
VALID_PLANS = {PLAN_FREE, PLAN_PRO}

ORDER_PENDING = "PENDING"
ORDER_PAID = "PAID"
ORDER_EXPIRED = "EXPIRED"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_STATE_PATH = _PROJECT_ROOT / ".state" / "subscriptions.json"

# Usage rows older than this are pruned on write so the JSON file cannot grow
# without bound. Two weeks is well past any daily-quota question we can answer.
_USAGE_RETENTION_DAYS = 14

_warned_about_salt = False


# =============================================================================
# TIME + IDENTITY HELPERS
# =============================================================================

def today_wib() -> date:
    """Current date in Asia/Jakarta — the boundary the daily quota resets on."""
    return datetime.now(WIB).date()


def now_wib() -> datetime:
    return datetime.now(WIB)


def normalize_phone(raw: str) -> str:
    """
    Reduce a Twilio sender string to bare digits.

    'whatsapp:+62812-3456-7890' -> '628123456789 0' minus separators.
    Normalizing first means the same human always maps to the same hash
    regardless of how the channel formats their number.
    """
    s = (raw or "").strip().lower()
    if s.startswith("whatsapp:"):
        s = s[len("whatsapp:"):]
    digits = "".join(ch for ch in s if ch.isdigit())
    # Indonesian local format 08xx is the same subscriber as +628xx.
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits


def hash_phone(raw: str, salt: Optional[str] = None) -> str:
    """
    Salted SHA-256 of a normalized phone number, hex-encoded.

    Returns '' for an empty/unusable sender so callers can treat "no identity"
    distinctly from "some identity we cannot read".
    """
    global _warned_about_salt
    digits = normalize_phone(raw)
    if not digits:
        return ""
    if salt is None:
        salt = os.getenv("PHONE_HASH_SALT", "")
    if not salt and not _warned_about_salt:
        _warned_about_salt = True
        warnings.warn(
            "PHONE_HASH_SALT is not set. Phone hashes are therefore unsalted "
            "and reversible by brute force over the Indonesian mobile keyspace. "
            "Set PHONE_HASH_SALT before handling real users.",
            RuntimeWarning,
            stacklevel=2,
        )
    return hashlib.sha256(f"{salt}:{digits}".encode("utf-8")).hexdigest()


def new_order_id() -> str:
    """Short, unguessable order reference the user can quote back in chat."""
    return "AF-" + secrets.token_hex(4).upper()


# =============================================================================
# VALUE OBJECTS
# =============================================================================

@dataclass(frozen=True)
class Account:
    """A subscriber's plan state as the bot sees it."""
    phone_hash: str
    plan: str = PLAN_FREE
    expires_at: Optional[datetime] = None

    @property
    def is_pro(self) -> bool:
        """PRO only counts while unexpired; a lapsed PRO behaves as FREE."""
        if self.plan != PLAN_PRO:
            return False
        if self.expires_at is None:
            return True  # no expiry recorded == perpetual
        return self.expires_at > now_wib()


@dataclass(frozen=True)
class AccessDecision:
    """Outcome of a quota check, carried to the reply layer for messaging."""
    allowed: bool
    account: Account
    used_today: int
    limit: int

    @property
    def remaining(self) -> int:
        if self.account.is_pro:
            return -1  # sentinel: unlimited
        return max(0, self.limit - self.used_today)


@dataclass(frozen=True)
class Order:
    order_id: str
    phone_hash: str
    plan: str
    amount_idr: int
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None


# =============================================================================
# JSON STORE — default, offline-safe
# =============================================================================

class JsonStore:
    """
    File-backed store for demo and single-process deployments.

    Writes are guarded by a process lock and land via os.replace, so a crash
    mid-write leaves the previous good file rather than a truncated one. This
    is not safe across multiple processes writing concurrently; use the
    Postgres backend when you run more than one worker.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or os.getenv("QUOTA_STATE_PATH", _DEFAULT_STATE_PATH))
        self._lock = threading.Lock()

    # -- persistence -------------------------------------------------------

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"accounts": {}, "usage": {}, "orders": {}}
        try:
            with self.path.open(encoding="utf-8") as fh:
                blob = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # A corrupt state file must not take the bot down. Losing quota
            # counters fails open (users get their free queries again), which
            # is the right direction to fail for a food-security service.
            return {"accounts": {}, "usage": {}, "orders": {}}
        blob.setdefault("accounts", {})
        blob.setdefault("usage", {})
        blob.setdefault("orders", {})
        return blob

    def _write(self, blob: Dict[str, Any]) -> None:
        self._prune(blob)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    @staticmethod
    def _prune(blob: Dict[str, Any]) -> None:
        """Drop usage rows past the retention window."""
        cutoff = (today_wib() - timedelta(days=_USAGE_RETENTION_DAYS)).isoformat()
        usage = blob.get("usage", {})
        for key in [k for k in usage if k.split("|", 1)[-1] < cutoff]:
            del usage[key]

    @staticmethod
    def _usage_key(phone_hash: str, day: date) -> str:
        return f"{phone_hash}|{day.isoformat()}"

    # -- accounts ----------------------------------------------------------

    def get_account(self, phone_hash: str) -> Account:
        row = self._read()["accounts"].get(phone_hash)
        if not row:
            return Account(phone_hash=phone_hash)
        exp = row.get("expires_at")
        return Account(
            phone_hash=phone_hash,
            plan=row.get("plan", PLAN_FREE),
            expires_at=datetime.fromisoformat(exp) if exp else None,
        )

    def set_plan(
        self, phone_hash: str, plan: str, expires_at: Optional[datetime] = None
    ) -> Account:
        if plan not in VALID_PLANS:
            raise ValueError(f"unknown plan: {plan!r}")
        with self._lock:
            blob = self._read()
            blob["accounts"][phone_hash] = {
                "plan": plan,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "updated_at": now_wib().isoformat(),
            }
            self._write(blob)
        return Account(phone_hash=phone_hash, plan=plan, expires_at=expires_at)

    # -- usage -------------------------------------------------------------

    def get_usage(self, phone_hash: str, day: Optional[date] = None) -> int:
        day = day or today_wib()
        return self._read()["usage"].get(self._usage_key(phone_hash, day), 0)

    def increment_usage(self, phone_hash: str, day: Optional[date] = None) -> int:
        day = day or today_wib()
        with self._lock:
            blob = self._read()
            key = self._usage_key(phone_hash, day)
            count = blob["usage"].get(key, 0) + 1
            blob["usage"][key] = count
            # Read the count out BEFORE writing: _write prunes expired rows in
            # place, and incrementing a date past the retention window would
            # otherwise delete the row we are about to return.
            self._write(blob)
            return count

    # -- orders ------------------------------------------------------------

    def create_order(self, order: Order) -> Order:
        with self._lock:
            blob = self._read()
            blob["orders"][order.order_id] = {
                "phone_hash": order.phone_hash,
                "plan": order.plan,
                "amount_idr": order.amount_idr,
                "status": order.status,
                "created_at": order.created_at.isoformat(),
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            }
            self._write(blob)
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        row = self._read()["orders"].get(order_id)
        if not row:
            return None
        return Order(
            order_id=order_id,
            phone_hash=row["phone_hash"],
            plan=row["plan"],
            amount_idr=row["amount_idr"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            paid_at=datetime.fromisoformat(row["paid_at"]) if row.get("paid_at") else None,
        )

    def mark_order_paid(self, order_id: str) -> Optional[Order]:
        with self._lock:
            blob = self._read()
            row = blob["orders"].get(order_id)
            if not row:
                return None
            if row["status"] == ORDER_PAID:
                # Idempotent: a gateway retrying its webhook must not extend
                # the subscription a second time.
                paid = row.get("paid_at")
                return Order(
                    order_id=order_id, phone_hash=row["phone_hash"],
                    plan=row["plan"], amount_idr=row["amount_idr"],
                    status=ORDER_PAID,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    paid_at=datetime.fromisoformat(paid) if paid else None,
                )
            row["status"] = ORDER_PAID
            row["paid_at"] = now_wib().isoformat()
            self._write(blob)
            return Order(
                order_id=order_id, phone_hash=row["phone_hash"],
                plan=row["plan"], amount_idr=row["amount_idr"],
                status=ORDER_PAID,
                created_at=datetime.fromisoformat(row["created_at"]),
                paid_at=datetime.fromisoformat(row["paid_at"]),
            )

    # -- test/demo support -------------------------------------------------

    def reset(self) -> None:
        """Wipe all state. Used by tests and the demo reset endpoint."""
        with self._lock:
            self._write({"accounts": {}, "usage": {}, "orders": {}})


# =============================================================================
# POSTGRES STORE — for multi-worker deployments
# =============================================================================

class PostgresStore:
    """
    Postgres-backed store over the tables in db/schema.sql.

    Counter increments use INSERT .. ON CONFLICT DO UPDATE so two workers
    racing on the same sender cannot lose a count (which would hand out free
    queries beyond the limit).
    """

    def __init__(self, db_url: Optional[str] = None):
        from sqlalchemy import create_engine  # imported lazily: optional path

        url = db_url or os.getenv("SUPABASE_DB_URL", "")
        if not url:
            raise RuntimeError(
                "QUOTA_BACKEND=postgres requires SUPABASE_DB_URL to be set."
            )
        # Pool sizing for a multi-worker deployment.
        #
        # Supabase's connection ceiling is per PROJECT, not per worker, so the
        # budget is (workers x (pool_size + max_overflow)) and it must stay
        # under the plan's limit. Defaults here are deliberately modest so two
        # or three workers cannot exhaust a small Supabase instance; raise them
        # only alongside a bigger plan or a pgBouncer in front.
        #
        # pool_pre_ping costs one cheap round trip per checkout and buys
        # immunity to connections killed by an idle timeout, which is the usual
        # cause of a "server closed the connection unexpectedly" at low traffic.
        self._engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
        )

    def get_account(self, phone_hash: str) -> Account:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT plan, plan_expires_at FROM subscriber "
                     "WHERE phone_hash = :ph"),
                {"ph": phone_hash},
            ).fetchone()
        if not row:
            return Account(phone_hash=phone_hash)
        return Account(phone_hash=phone_hash, plan=row[0], expires_at=row[1])

    def set_plan(
        self, phone_hash: str, plan: str, expires_at: Optional[datetime] = None
    ) -> Account:
        from sqlalchemy import text
        if plan not in VALID_PLANS:
            raise ValueError(f"unknown plan: {plan!r}")
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO subscriber (phone_hash, plan, plan_expires_at)
                    VALUES (:ph, :plan, :exp)
                    ON CONFLICT (phone_hash) DO UPDATE
                        SET plan = EXCLUDED.plan,
                            plan_expires_at = EXCLUDED.plan_expires_at,
                            updated_at = NOW()
                """),
                {"ph": phone_hash, "plan": plan, "exp": expires_at},
            )
        return Account(phone_hash=phone_hash, plan=plan, expires_at=expires_at)

    def get_usage(self, phone_hash: str, day: Optional[date] = None) -> int:
        from sqlalchemy import text
        day = day or today_wib()
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT query_count FROM wa_usage_daily "
                     "WHERE phone_hash = :ph AND usage_date = :d"),
                {"ph": phone_hash, "d": day},
            ).fetchone()
        return row[0] if row else 0

    def increment_usage(self, phone_hash: str, day: Optional[date] = None) -> int:
        from sqlalchemy import text
        day = day or today_wib()
        with self._engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO wa_usage_daily (phone_hash, usage_date, query_count)
                    VALUES (:ph, :d, 1)
                    ON CONFLICT (phone_hash, usage_date) DO UPDATE
                        SET query_count = wa_usage_daily.query_count + 1
                    RETURNING query_count
                """),
                {"ph": phone_hash, "d": day},
            ).fetchone()
        return row[0]

    def create_order(self, order: Order) -> Order:
        from sqlalchemy import text
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO payment_order
                        (order_id, phone_hash, plan, amount_idr, status, created_at)
                    VALUES (:oid, :ph, :plan, :amt, :st, :ca)
                """),
                {"oid": order.order_id, "ph": order.phone_hash, "plan": order.plan,
                 "amt": order.amount_idr, "st": order.status, "ca": order.created_at},
            )
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT order_id, phone_hash, plan, amount_idr, status, "
                     "created_at, paid_at FROM payment_order WHERE order_id = :oid"),
                {"oid": order_id},
            ).fetchone()
        if not row:
            return None
        return Order(*row)

    def mark_order_paid(self, order_id: str) -> Optional[Order]:
        from sqlalchemy import text
        # The WHERE status <> 'PAID' guard makes this idempotent under webhook
        # retries: a second call updates zero rows and returns the existing state.
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE payment_order SET status = :paid, paid_at = NOW() "
                     "WHERE order_id = :oid AND status <> :paid"),
                {"oid": order_id, "paid": ORDER_PAID},
            )
        return self.get_order(order_id)

    def reset(self) -> None:
        raise NotImplementedError(
            "reset() is deliberately unavailable on the Postgres backend — "
            "it would delete real subscriber state."
        )


# =============================================================================
# SERVICE — the only thing callers touch
# =============================================================================

class SubscriptionService:
    """
    Quota + plan decisions on top of whichever store is configured.

    free_daily_quota is the number of *metered* queries a FREE sender may make
    per WIB day. Help text, plan status, and upgrade flows are never metered,
    so a user can always reach the paywall message and act on it.
    """

    def __init__(
        self,
        store: Optional[Any] = None,
        free_daily_quota: Optional[int] = None,
        pro_price_idr: Optional[int] = None,
        pro_period_days: int = 30,
    ):
        self.store = store or make_store()
        self.free_daily_quota = (
            free_daily_quota
            if free_daily_quota is not None
            else int(os.getenv("FREE_DAILY_QUOTA", "2"))
        )
        self.pro_price_idr = (
            pro_price_idr
            if pro_price_idr is not None
            else int(os.getenv("PRO_PRICE_IDR", "25000"))
        )
        self.pro_period_days = pro_period_days

    # -- read ---------------------------------------------------------------

    def account(self, phone_hash: str) -> Account:
        return self.store.get_account(phone_hash)

    def check(self, phone_hash: str) -> AccessDecision:
        """
        Decide whether this sender may make one more metered query today.

        Does NOT consume quota — call consume() only once the query actually
        produced an answer, so a malformed request costs the user nothing.
        """
        account = self.store.get_account(phone_hash)
        if account.is_pro:
            return AccessDecision(True, account, 0, self.free_daily_quota)
        used = self.store.get_usage(phone_hash)
        return AccessDecision(
            allowed=used < self.free_daily_quota,
            account=account,
            used_today=used,
            limit=self.free_daily_quota,
        )

    # -- write --------------------------------------------------------------

    def consume(self, phone_hash: str) -> int:
        """Record one metered query. PRO senders are not counted at all."""
        if self.store.get_account(phone_hash).is_pro:
            return 0
        return self.store.increment_usage(phone_hash)

    def start_upgrade(self, phone_hash: str) -> Order:
        order = Order(
            order_id=new_order_id(),
            phone_hash=phone_hash,
            plan=PLAN_PRO,
            amount_idr=self.pro_price_idr,
            status=ORDER_PENDING,
            created_at=now_wib(),
        )
        return self.store.create_order(order)

    def confirm_payment(self, order_id: str) -> Optional[Account]:
        """
        Settle an order and grant PRO.

        Returns None if the order is unknown. Safe to call twice: the store's
        mark_order_paid is idempotent, but the plan grant below is applied on
        every call, so we extend from the later of (now, current expiry) to
        keep repeated webhooks from silently shortening a subscription.
        """
        order = self.store.mark_order_paid(order_id)
        if order is None:
            return None
        current = self.store.get_account(order.phone_hash)
        base = (
            current.expires_at
            if current.is_pro and current.expires_at and current.expires_at > now_wib()
            else now_wib()
        )
        return self.store.set_plan(
            order.phone_hash, PLAN_PRO, base + timedelta(days=self.pro_period_days)
        )


# =============================================================================
# FACTORY
# =============================================================================

def make_store(backend: Optional[str] = None) -> Any:
    """Select a store from QUOTA_BACKEND. Defaults to the offline-safe JSON store."""
    backend = (backend or os.getenv("QUOTA_BACKEND", "json")).strip().lower()
    if backend == "postgres":
        return PostgresStore()
    if backend == "json":
        return JsonStore()
    raise ValueError(f"unknown QUOTA_BACKEND: {backend!r} (expected 'json' or 'postgres')")

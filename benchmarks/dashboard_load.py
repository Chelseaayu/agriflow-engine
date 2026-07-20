"""
Concurrency load test for the authenticated dashboard API.

Answers one question with numbers rather than adjectives: how many simultaneous
signed-in dashboard users can one API worker serve?

Simulates N distinct users, each with their own signed JWT, hitting the
endpoints the dashboard actually calls on page load. Reports throughput and
latency percentiles, and verifies every response was correct — a fast server
that returns 500s is not a passing result.

Run:
    python benchmarks/dashboard_load.py               # default 1000 users
    python benchmarks/dashboard_load.py --users 5000 --workers 64

Runs fully in-process against the ASGI app via TestClient, so it measures
application cost with no network or TLS in the way. Real-world numbers will be
lower; this isolates whether *our code* is the bottleneck.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SECRET = "load-test-secret-not-used-in-production"


def make_token(user_index: int) -> str:
    import jwt
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": f"00000000-0000-0000-0000-{user_index:012d}",
            "email": f"user{user_index}@dinas.example.go.id",
            "aud": "authenticated", "role": "authenticated",
            "iat": now, "exp": now + timedelta(hours=1),
        },
        SECRET, algorithm="HS256",
    )


# The requests a dashboard makes when a signed-in user opens it.
PAGE_LOAD = [
    ("/api/v1/commodities", {}),
    ("/api/v1/kabupaten", {}),
    ("/api/v1/surplus-deficit", {"commodity": "beras_premium"}),
    ("/api/v1/matches", {"commodity": "beras_premium", "limit": 50}),
    ("/api/v1/anomalies", {"limit": 20}),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args()

    os.environ["SUPABASE_JWT_SECRET"] = SECRET
    os.environ.pop("SUPABASE_URL", None)
    os.environ["REQUIRE_AUTH"] = "true"      # every request must verify a token
    os.environ["PHONE_HASH_SALT"] = "load-test"

    from fastapi.testclient import TestClient
    from whatsapp_bot import server

    print(f"Minting {args.users:,} distinct user tokens…")
    tokens = [make_token(i) for i in range(args.users)]

    latencies: list[float] = []
    failures: list[str] = []

    with TestClient(server.app) as client:
        # Warm the caches so we measure steady state, not cold start.
        for path, params in PAGE_LOAD:
            client.get(path, params=params, headers={"Authorization": f"Bearer {tokens[0]}"})

        def one_user(token: str) -> float:
            t0 = time.perf_counter()
            for path, params in PAGE_LOAD:
                r = client.get(path, params=params,
                               headers={"Authorization": f"Bearer {token}"})
                if r.status_code != 200:
                    failures.append(f"{path} -> {r.status_code}")
            return (time.perf_counter() - t0) * 1000

        print(f"Running {args.users:,} user sessions across {args.workers} workers…")
        t_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            latencies = list(pool.map(one_user, tokens))
        elapsed = time.perf_counter() - t_start

    latencies.sort()

    def pct(p: float) -> float:
        return latencies[min(int(len(latencies) * p), len(latencies) - 1)]

    requests = args.users * len(PAGE_LOAD)
    print()
    print("=" * 62)
    print(f"  users simulated      {args.users:,}")
    print(f"  requests issued      {requests:,}  ({len(PAGE_LOAD)} per user)")
    print(f"  wall clock           {elapsed:.2f} s")
    print(f"  throughput           {requests / elapsed:,.0f} req/s")
    print(f"  user sessions/sec    {args.users / elapsed:,.0f}")
    print("-" * 62)
    print(f"  full page load  mean {statistics.mean(latencies):7.1f} ms")
    print(f"                  p50  {pct(0.50):7.1f} ms")
    print(f"                  p95  {pct(0.95):7.1f} ms")
    print(f"                  p99  {pct(0.99):7.1f} ms")
    print(f"                  max  {latencies[-1]:7.1f} ms")
    print("-" * 62)
    print(f"  failed requests      {len(failures)}")
    if failures:
        for f in sorted(set(failures))[:5]:
            print(f"    {f}  (x{failures.count(f)})")
    print("=" * 62)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

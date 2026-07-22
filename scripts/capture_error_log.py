"""
scripts/capture_error_log.py — produce a real API request/error log as evidence.

Drives the actual FastAPI app in-process (no network) through a scripted mix of
healthy calls, client mistakes, and one forced server fault, so the resulting
log file shows what each class of failure looks like in production.

The forced fault is deliberate: it monkey-patches the surplus-deficit endpoint's
data accessor to raise, which is the only honest way to demonstrate the
unhandled-exception path without waiting for a real outage.

Run:
    python scripts/capture_error_log.py
    python scripts/capture_error_log.py --out docs/evidence/runs/api-request-log-sample.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "docs" / "evidence" / "runs" / "api-request-log-sample.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    # The logger reads this at import time of the app, so set it first.
    os.environ["AGRIFLOW_LOG_FILE"] = str(out_path)
    os.environ.setdefault("DATA_BACKEND", "csv")

    from fastapi.testclient import TestClient

    from whatsapp_bot import server

    with TestClient(server.app, raise_server_exceptions=False) as client:
        print("  [1/6] healthy: GET /health")
        client.get("/health")

        print("  [2/6] healthy: GET /api/v1/commodities")
        client.get("/api/v1/commodities")

        print("  [3/6] healthy: GET /api/v1/surplus-deficit")
        client.get("/api/v1/surplus-deficit?commodity=beras_medium")

        print("  [4/6] client error: unknown route -> 404")
        client.get("/api/v1/does-not-exist")

        print("  [5/6] client error: missing required param -> 422")
        client.get("/api/v1/forecast")

        print("  [6/6] server fault (forced): dependency raises -> 500")
        original = server.state.data

        class _BrokenData:
            def __getattr__(self, name):
                raise RuntimeError(
                    "simulated backend outage: price store unreachable"
                )

        server.state.data = _BrokenData()
        try:
            response = client.get("/api/v1/surplus-deficit?commodity=beras_medium")
            body = response.json()
            print(f"        -> status={response.status_code} "
                  f"request_id={body.get('request_id')}")
        finally:
            server.state.data = original

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    levels: dict[str, int] = {}
    for line in lines:
        levels[json.loads(line)["level"]] = levels.get(json.loads(line)["level"], 0) + 1

    print(f"\n  Wrote {len(lines)} log lines -> {out_path}")
    print(f"  Level breakdown: {levels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

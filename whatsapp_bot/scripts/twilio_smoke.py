"""
Twilio-shaped smoke test for the local /whatsapp webhook.

Mimics exactly what Twilio sends: form-encoded POST with Body + From fields.
Run AFTER starting `uvicorn whatsapp_bot.server:app --port 8000` in another
terminal. Verifies the bot returns valid TwiML XML.

Usage:
    python whatsapp_bot/scripts/twilio_smoke.py
    python whatsapp_bot/scripts/twilio_smoke.py "Cari pembeli cabai Kediri"
    python whatsapp_bot/scripts/twilio_smoke.py --base http://localhost:8000
"""

from __future__ import annotations
import argparse
import sys
from typing import List, Tuple

# Force UTF-8 stdout on Windows so the arrow + checkmarks don't crash cp1252
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


DEFAULT_TESTS = [
    "Harga cabai di Malang",
    "Cari pembeli 50 ton cabai di Kediri",
    "Butuh 100 ton beras untuk Surabaya",
    "Halo apa kabar",
]


def run(base_url: str, messages: List[str]) -> Tuple[int, int]:
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx not installed. Run: pip install httpx")
        return 0, 1

    passed = 0
    failed = 0
    for msg in messages:
        print(f"\n→ POST /whatsapp  Body={msg!r}")
        try:
            r = httpx.post(
                f"{base_url}/whatsapp",
                data={"Body": msg, "From": "whatsapp:+6281234567890"},
                timeout=10.0,
            )
        except Exception as e:
            print(f"  ✗ REQUEST FAILED: {e}")
            failed += 1
            continue

        if r.status_code != 200:
            print(f"  ✗ HTTP {r.status_code}: {r.text[:200]}")
            failed += 1
            continue

        body = r.text
        if not body.startswith("<?xml"):
            print(f"  ✗ NOT TwiML: {body[:200]}")
            failed += 1
            continue
        if "<Response>" not in body or "<Message>" not in body:
            print(f"  ✗ Missing TwiML elements: {body[:200]}")
            failed += 1
            continue

        # Pretty-print the inner message
        start = body.find("<Message>") + len("<Message>")
        end = body.find("</Message>")
        inner = body[start:end] if end > start else body
        # Unescape for readability
        inner = (inner.replace("&lt;", "<").replace("&gt;", ">")
                      .replace("&amp;", "&").replace("&quot;", '"'))
        print(f"  ✓ HTTP 200, valid TwiML")
        # Indent each reply line
        for line in inner.split("\n"):
            print(f"     {line}")
        passed += 1

    return passed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", nargs="*", help="Messages to send (default: 4 standard tests)")
    parser.add_argument("--base", default="http://localhost:8000", help="Base URL")
    args = parser.parse_args()

    messages = args.messages or DEFAULT_TESTS

    # First check the server is up
    try:
        import httpx
        h = httpx.get(f"{args.base}/health", timeout=5.0).json()
        print(f"Server health: {h}")
    except Exception as e:
        print(f"ERROR: server unreachable at {args.base} — start it first:")
        print("  uvicorn whatsapp_bot.server:app --port 8000")
        print(f"  ({e})")
        return 1

    passed, failed = run(args.base, messages)
    print(f"\n{'='*60}")
    print(f"Result: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

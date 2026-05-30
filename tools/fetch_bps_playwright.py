"""
Fetch produksi pertanian per-kabupaten Jatim dari BPS WebAPI — via BROWSER ASLI (Playwright).
==============================================================================================

Kenapa Playwright, bukan cloudscraper:
    BPS pakai Cloudflare managed-challenge (Turnstile) yang HARUS dieksekusi
    oleh JS engine browser sungguhan. cloudscraper (trik ringan) GAGAL — balas
    HTTP 200 body kosong. Playwright menjalankan Chromium asli → Cloudflare
    auto-lolos dalam beberapa detik → JSON muncul.

Cara pakai (di terminal mesin Anda, dari root repo):
    pip install playwright
    playwright install chromium
    python tools/fetch_bps_playwright.py

    Browser Chrome akan TERBUKA (headful) — biarkan, jangan ditutup. Kalau muncul
    "Just a moment..." / centang Cloudflare, TUNGGU (auto-lolos) atau klik centang
    sekali kalau diminta. Skrip menunggu sampai JSON keluar, lalu lanjut sendiri.

Output:
    sample_data/bps_real/_raw_<table_id>.json   (raw JSON dari BPS)
    sample_data/bps_real/_search_<kw>.json       (hasil pencarian tabel)

Setelah selesai: kabari Claude isi folder sample_data/bps_real/ → DEA decode jadi
surplus/deficit real. Skrip TIDAK mengarang angka — hanya menyimpan respons asli BPS.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit(
        "Butuh Playwright.\n  pip install playwright\n  playwright install chromium"
    )

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "sample_data" / "bps_real"
DOMAIN = "3500"  # Jawa Timur
BASE = "https://webapi.bps.go.id/v1/api"


def _load_key() -> str:
    key = os.getenv("BPS_API_KEY", "")
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("BPS_API_KEY"):
                    key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("BPS_API_KEY tidak ada (set di .env).")
    return key


def grab_json(page, url: str, label: str, max_wait: int = 40):
    """Buka URL di browser, tunggu Cloudflare lolos, kembalikan JSON (atau None)."""
    print(f"[goto] {label} ...")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        body = page.inner_text("body").strip()
        if body.startswith("{") or body.startswith("["):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                pass
        # masih di halaman challenge Cloudflare
        time.sleep(2)
    print(f"    !! timeout — masih ke-blok/kosong untuk {label}")
    return None


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key = _load_key()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headful: paling andal lawan Cloudflare
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="id-ID",
        )
        page = ctx.new_page()

        found = {"716": "Produksi Padi Menurut Kabupaten/Kota (Ton)"}

        # 1) cari tabel cabai & bawang per-kab
        for kw in ("cabai", "bawang", "sayuran"):
            url = f"{BASE}/list/model/statictable/domain/{DOMAIN}/keyword/{kw}/key/{key}/perpage/50/"
            b = grab_json(page, url, f"search '{kw}'")
            if b:
                (OUT_DIR / f"_search_{kw}.json").write_text(
                    json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                data = b.get("data")
                if isinstance(data, list) and len(data) > 1:
                    for r in data[1]:
                        title = r.get("title", "")
                        low = title.lower()
                        if "menurut kabupaten" in low and "produksi" in low and any(
                            w in low for w in ("cabai", "cabe", "bawang")
                        ):
                            found[str(r.get("table_id"))] = title
            time.sleep(2)

        print(f"\n[tables to fetch] {json.dumps(found, ensure_ascii=False)}\n")

        # 2) ambil tiap tabel
        ok, fail = [], []
        for tid, title in found.items():
            url = f"{BASE}/view/model/statictable/lang/ind/domain/{DOMAIN}/id/{tid}/key/{key}/"
            b = grab_json(page, url, f"table {tid} ({title[:40]})")
            if b and isinstance(b.get("data"), dict) and b["data"].get("datacontent"):
                (OUT_DIR / f"_raw_{tid}.json").write_text(
                    json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                n = len(b["data"]["datacontent"])
                print(f"    OK -> _raw_{tid}.json ({n} datacontent entries)")
                ok.append((tid, title))
            else:
                fail.append((tid, title))
            time.sleep(2)

        browser.close()

    print("\n=== SELESAI ===")
    print(f"Output: {OUT_DIR}")
    print(f"Berhasil: {[t for t,_ in ok]}")
    if fail:
        print(f"Gagal (coba ulang / Excel manual): {[(t,ti[:40]) for t,ti in fail]}")
    print("\nKabari Claude isi sample_data/bps_real/ -> DEA decode jadi data real.")


if __name__ == "__main__":
    main()

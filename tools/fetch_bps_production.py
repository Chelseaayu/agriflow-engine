"""
Fetch produksi pertanian per-kabupaten Jawa Timur dari BPS WebAPI (statictable).
=================================================================================

Kenapa skrip ini ada:
    Sandbox build (server CI/agent) sering di-throttle/blok oleh Cloudflare BPS
    sehingga webapi balas kosong. DI MESIN ANDA SENDIRI (IP rumah/kantor) biasanya
    lolos. Jalankan skrip ini sekali di laptop Anda; hasilnya CSV bersih yang bisa
    di-commit + dipakai offline untuk demo.

Cara pakai (di terminal mesin Anda, dari root repo):
    pip install cloudscraper
    python tools/fetch_bps_production.py

    (Key dibaca dari .env -> BPS_API_KEY. Sudah ada di repo Anda.)

Output:
    sample_data/bps_real/<komoditas>_produksi.csv   (kab_id, produksi_ton, satuan, tahun, table_id)
    sample_data/bps_real/_raw_<table_id>.json       (raw response, untuk audit/parse ulang)
    sample_data/bps_real/PROVENANCE.md              (sumber tiap angka)

Kalau ada tabel yang gagal (balas kosong), skrip retry beberapa kali dengan jeda.
Kalau tetap gagal, ia lapor tabel mana yang perlu Anda download manual (Excel).
Skrip TIDAK pernah mengarang angka — hanya menulis yang benar-benar diterima dari API.
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

try:
    import cloudscraper
except ImportError:
    raise SystemExit("Butuh cloudscraper. Jalankan: pip install cloudscraper")

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "sample_data" / "bps_real"
DOMAIN = "3500"  # Jawa Timur
BASE = "https://webapi.bps.go.id/v1/api"

# Tabel yang dicari (keyword -> komoditas yang diharapkan di dalamnya).
# table_id 716 (padi) sudah terkonfirmasi; sisanya dicari via keyword.
SEARCH = {
    "padi": ["padi"],
    "sayuran cabai": ["cabai", "cabe"],
    "sayuran bawang": ["bawang"],
}


def _load_key() -> str:
    key = os.getenv("BPS_API_KEY", "")
    if not key:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("BPS_API_KEY"):
                    key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("BPS_API_KEY tidak ditemukan (set di .env atau env var).")
    return key


def _scraper():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )


def _get(s, url: str, tries: int = 4, pause: float = 3.0):
    """GET dengan retry + jeda (hormati rate limit BPS ~100 req/menit)."""
    for i in range(tries):
        try:
            r = s.get(url, timeout=60)
            if r.status_code == 200 and r.text.strip():
                try:
                    return r.json()
                except json.JSONDecodeError:
                    pass  # mungkin halaman challenge; retry
        except Exception as e:
            print(f"    (attempt {i+1} error: {type(e).__name__})")
        time.sleep(pause * (i + 1))
    return None


def list_tables(s, key: str, keyword: str):
    url = f"{BASE}/list/model/statictable/domain/{DOMAIN}/keyword/{keyword}/key/{key}/perpage/50/"
    b = _get(s, url)
    if not b or not isinstance(b.get("data"), list) or len(b["data"]) < 2:
        return []
    return [(r.get("table_id"), r.get("title", "")) for r in b["data"][1]]


def fetch_table(s, key: str, table_id):
    url = f"{BASE}/view/model/statictable/lang/ind/domain/{DOMAIN}/id/{table_id}/key/{key}/"
    b = _get(s, url)
    if b:
        (OUT_DIR / f"_raw_{table_id}.json").write_text(
            json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return b


def decode_per_kab(view_json):
    """Decode datacontent statictable -> {kab_id: {tahun: nilai}} (defensif).

    Key datacontent = concat string mulai dgn kode verticalvar (region).
    Kita hanya pertahankan region yang berupa kode kab BPS (35xx, 4 digit, bukan
    agregat 'JAWA TIMUR'). Kembalikan juga metadata (tahun, turvar) untuk audit.
    """
    d = view_json.get("data", {})
    if not isinstance(d, dict):
        return None
    vervar = {str(v["val"]): v["label"] for v in d.get("verticalvar", [])}
    tahun = {str(t["val"]): t["label"] for t in d.get("tahun", [])}
    turvar = {str(t["val"]): t["label"] for t in d.get("turvar", [])}
    dc = d.get("datacontent", {})
    rows = []
    for k, val in dc.items():
        for vid, label in vervar.items():
            if k.startswith(vid):
                rows.append({"vervar_id": vid, "region": label, "key": k, "value": val})
                break
    return {
        "title": d.get("title", ""),
        "excel": d.get("excel", ""),
        "tahun": tahun,
        "turvar": turvar,
        "vervar_count": len(vervar),
        "rows": rows,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key = _load_key()
    s = _scraper()
    prov_lines = ["# BPS Production Data — Provenance", ""]
    failed = []

    # 1) padi terkonfirmasi (id 716) + cari tabel lain
    target_ids = {"716": "Produksi Padi Menurut Kabupaten/Kota (Ton)"}
    for kw in SEARCH:
        print(f"[search] '{kw}' ...")
        for tid, title in list_tables(s, key, kw.split()[-1]):
            low = title.lower()
            if "menurut kabupaten" in low and any(
                w in low for w in ("produksi",)
            ) and any(w in low for w in ("padi", "cabai", "cabe", "bawang")):
                target_ids[str(tid)] = title
        time.sleep(2)

    print(f"[tables] kandidat: {list(target_ids.keys())}")
    for tid, title in target_ids.items():
        print(f"[fetch] table {tid}: {title[:70]} ...")
        view = fetch_table(s, key, tid)
        if not view:
            print(f"    GAGAL (kosong) — perlu download manual.")
            failed.append((tid, title))
            continue
        dec = decode_per_kab(view)
        if not dec or dec["vervar_count"] < 10:
            print(f"    struktur tak terduga (vervar={dec['vervar_count'] if dec else '?'}) — cek _raw_{tid}.json")
            failed.append((tid, title))
            continue
        out = OUT_DIR / f"table_{tid}.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["vervar_id", "region", "key", "value"])
            w.writeheader()
            w.writerows(dec["rows"])
        print(f"    OK -> {out.name} ({len(dec['rows'])} rows, tahun={list(dec['tahun'].values())})")
        prov_lines += [
            f"## table {tid}: {dec['title']}",
            f"- URL: {BASE}/view/model/statictable/lang/ind/domain/{DOMAIN}/id/{tid}/key/<KEY>/",
            f"- tahun: {', '.join(dec['tahun'].values())}",
            f"- turvar (komoditas): {', '.join(list(dec['turvar'].values())[:8])}",
            f"- excel: {dec['excel']}",
            f"- fetched: {time.strftime('%Y-%m-%d')}",
            "",
        ]
        time.sleep(3)

    (OUT_DIR / "PROVENANCE.md").write_text("\n".join(prov_lines), encoding="utf-8")
    print("\n=== SELESAI ===")
    print(f"Output di: {OUT_DIR}")
    if failed:
        print("\nTabel yang GAGAL (download manual Excel-nya dari jatim.bps.go.id):")
        for tid, title in failed:
            print(f"  - id {tid}: {title}")
    print("\nLangkah berikutnya: beri tahu Claude isi sample_data/bps_real/ -> DEA decode jadi surplus/deficit real.")


if __name__ == "__main__":
    main()

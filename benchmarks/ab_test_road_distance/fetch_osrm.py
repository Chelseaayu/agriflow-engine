"""
One-shot OSRM /table fetch for 38 Jatim kabupaten.
Public demo endpoint router.project-osrm.org — rate-limited but
a single batch query of 38 coordinates is well within limits.

Output: osrm_distance_matrix.csv with rows (from_id, to_id, road_km, duration_hr).
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

KAB_CSV = ROOT / "sample_data" / "kabupaten_jatim.csv"
OUT_CSV = Path(__file__).parent / "osrm_distance_matrix.csv"
OUT_RAW = Path(__file__).parent / "osrm_raw_response.json"


def load_kabupaten():
    rows = []
    with open(KAB_CSV, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({
                "id": row["kab_id"],
                "nama": row["nama"],
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
            })
    return rows


def fetch_table(kabs, profile: str = "driving"):
    # OSRM expects lon,lat (NOT lat,lon)
    coord_str = ";".join(f"{k['lon']},{k['lat']}" for k in kabs)
    url = (
        f"http://router.project-osrm.org/table/v1/{profile}/"
        f"{urllib.parse.quote(coord_str, safe=',;')}"
        f"?annotations=distance,duration"
    )
    print(f"[osrm] requesting {len(kabs)} x {len(kabs)} table ({len(url)} char URL)")
    t = time.time()
    with urllib.request.urlopen(url, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    elapsed = time.time() - t
    print(f"[osrm] response {len(body)} bytes in {elapsed:.1f}s")
    data = json.loads(body)
    if data.get("code") != "Ok":
        print("[osrm] non-Ok response:", data)
        sys.exit(1)
    return data


def main():
    kabs = load_kabupaten()
    print(f"[osrm] loaded {len(kabs)} kabupaten")
    data = fetch_table(kabs)
    OUT_RAW.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[osrm] raw response cached -> {OUT_RAW.name}")

    distances = data["distances"]  # meters
    durations = data["durations"]  # seconds
    n = len(kabs)
    assert len(distances) == n and len(durations) == n

    n_missing = 0
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from_id", "from_nama", "to_id", "to_nama", "road_km", "duration_hr"])
        for i in range(n):
            for j in range(n):
                dist_m = distances[i][j]
                dur_s = durations[i][j]
                if dist_m is None or dur_s is None:
                    n_missing += 1
                    continue
                w.writerow([
                    kabs[i]["id"], kabs[i]["nama"],
                    kabs[j]["id"], kabs[j]["nama"],
                    f"{dist_m / 1000:.3f}",
                    f"{dur_s / 3600:.4f}",
                ])
    print(f"[osrm] wrote {n*n - n_missing} pairs -> {OUT_CSV.name}")
    if n_missing:
        print(f"[osrm] WARNING: {n_missing} pairs returned None (no route found)")


if __name__ == "__main__":
    main()

"""
Data Source: BMKG + Open-Meteo (fallback)
==========================================

Forecast cuaca untuk skenario D1 (banjir rute) di climate scoring.

Primary: BMKG Open Data
    URL: https://data.bmkg.go.id/prakiraan-cuaca
    Endpoint: https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={kode_desa}
    Format: JSON. Update 3-6 jam.

Fallback: Open-Meteo (free, no key required)
    URL: https://api.open-meteo.com/v1/forecast
    Lebih reliable untuk koordinat arbitrary.
    Rate limit: 10,000 req/day per IP.

Author: AgriFlow Team
"""
from __future__ import annotations
from typing import Dict, List, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class WeatherConnector:
    """
    Weather data dengan dual-source fallback.

    Usage:
        wc = WeatherConnector()
        forecasts = wc.fetch_route_forecast(
            origin_lat=-7.79, origin_lon=112.17,
            dest_lat=-7.25, dest_lon=112.75,
            days=2,
        )
    """

    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    BMKG_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
    DEFAULT_TIMEOUT = 10

    def __init__(
        self,
        prefer_bmkg: bool = False,
        adm4_lookup: Optional[dict] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Args:
            prefer_bmkg: Jika True, pakai BMKG (butuh `adm4_lookup` map koordinat→adm4
                kode desa). BMKG butuh kode desa per titik — koordinat bebas tidak
                cukup. Default False = pakai Open-Meteo (cukup lat/lon).
            adm4_lookup: Optional dict koordinat (lat,lon) → kode adm4 desa pusat.
                Tim production wajib generate ini dari data wilayah BPS.
            timeout: HTTP timeout dalam detik.
        """
        self.prefer_bmkg = prefer_bmkg
        self.adm4_lookup = adm4_lookup or {}
        self.timeout = timeout

    def fetch_route_forecast(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
        days: int = 2,
    ) -> Dict[str, float]:
        """
        Fetch max rain mm di sepanjang rute selama N hari ke depan.

        Strategy: cek 3 titik (origin, midpoint, dest), ambil max precipitation.
        Source seleksi: prefer_bmkg=True memerlukan adm4_lookup mapping titik→desa.
        Tanpa lookup, fallback ke Open-Meteo otomatis (lat/lon-based).

        Returns:
            {"max_rain_mm": float, "transit_window_days": days,
             "source": "BMKG" | "OPEN_METEO"}
        """
        # Sample 3 titik: origin, midpoint, dest
        midpoint_lat = (origin_lat + dest_lat) / 2
        midpoint_lon = (origin_lon + dest_lon) / 2
        points = [
            (origin_lat, origin_lon),
            (midpoint_lat, midpoint_lon),
            (dest_lat, dest_lon),
        ]

        max_rain = 0.0
        source_used = "OPEN_METEO"

        # BMKG path hanya aktif jika prefer_bmkg=True DAN adm4 mapping tersedia
        # untuk semua titik. Di luar itu fallback ke Open-Meteo.
        if self.prefer_bmkg and all((lat, lon) in self.adm4_lookup for lat, lon in points):
            for lat, lon in points:
                rain_mm = self._fetch_bmkg(self.adm4_lookup[(lat, lon)])
                if rain_mm > max_rain:
                    max_rain = rain_mm
            source_used = "BMKG"
        else:
            for lat, lon in points:
                rain_mm = self._fetch_open_meteo(lat, lon, days)
                if rain_mm > max_rain:
                    max_rain = rain_mm

        return {
            "max_rain_mm": max_rain,
            "transit_window_days": days,
            "source": source_used,
        }

    def _fetch_open_meteo(self, lat: float, lon: float, days: int) -> float:
        """
        Open-Meteo: free, no key needed.
        Return max precipitation_sum mm dalam window.
        """
        if not HAS_REQUESTS:
            return 0.0
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "precipitation_sum",
                "forecast_days": min(max(days, 1), 16),
                "timezone": "Asia/Jakarta",
            }
            r = requests.get(self.OPEN_METEO_URL, params=params,
                              timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            sums = data.get("daily", {}).get("precipitation_sum", [])
            return max(sums) if sums else 0.0
        except requests.RequestException as e:
            print(f"⚠ Open-Meteo error: {e}")
            return 0.0

    def _fetch_bmkg(self, adm4_kode: str) -> float:
        """
        BMKG butuh kode wilayah desa (adm4) — perlu mapping kabupaten → desa pusat.
        Implementasi production: pakai data wilayah BPS untuk pilih desa pusat per kab.
        """
        if not HAS_REQUESTS:
            return 0.0
        try:
            r = requests.get(
                f"{self.BMKG_URL}?adm4={adm4_kode}",
                timeout=self.timeout,
                headers={"User-Agent": "AgriFlow/1.0"},
            )
            r.raise_for_status()
            data = r.json()
            # Parse data — BMKG schema actual perlu reverse engineer
            # Ini placeholder skeleton
            cuaca = data.get("data", [])
            max_rain = 0.0
            for entry in cuaca:
                for hourly in entry.get("cuaca", [[]])[0]:
                    rain = hourly.get("tp", 0)  # total precipitation
                    if rain > max_rain:
                        max_rain = rain
            return max_rain
        except requests.RequestException as e:
            print(f"⚠ BMKG error: {e}")
            return 0.0


def get_route_weather(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    days: int = 2,
) -> dict:
    """Quick helper untuk dapat weather forecast satu rute."""
    return WeatherConnector().fetch_route_forecast(
        origin_lat, origin_lon, dest_lat, dest_lon, days
    )


if __name__ == "__main__":
    # Smoke test: Kediri → Surabaya
    forecast = get_route_weather(
        origin_lat=-7.796, origin_lon=112.170,
        dest_lat=-7.2575, dest_lon=112.7521,
        days=2,
    )
    print("Kediri → Surabaya forecast:", forecast)

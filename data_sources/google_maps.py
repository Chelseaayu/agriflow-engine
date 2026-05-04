"""
Data Source: Google Maps Routes API + OSRM (fallback)
======================================================

Routing untuk distance/duration antar kabupaten — lebih akurat dari haversine
yang dipakai default (geodesic distance, tidak tahu jalan/macet/ferry).

Primary: Google Maps Routes API
    URL: https://routes.googleapis.com/directions/v2:computeRoutes
    Authentication: API key required (paid setelah free tier).
    Free tier: $200/bulan credits.

Fallback: OSRM Demo Server
    URL: https://router.project-osrm.org/route/v1/driving/
    Free, public demo. Rate limit ~1000 req/day.
    Production: deploy OSRM sendiri di internal server.

Untuk hackathon: default ke OSRM (gratis), Google sebagai opsi.

Author: AgriFlow Team
"""
from __future__ import annotations
import os
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class RouteConnector:
    """
    Routing connector dengan Google → OSRM fallback.

    Usage:
        rc = RouteConnector()
        result = rc.get_distance_duration(
            origin_lat=-7.79, origin_lon=112.17,
            dest_lat=-7.25, dest_lon=112.75,
        )
        # → {"distance_km": 134.2, "duration_minutes": 168, "source": "OSRM"}
    """

    GOOGLE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
    DEFAULT_TIMEOUT = 10

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        prefer_google: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.google_api_key = google_api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
        self.prefer_google = prefer_google and bool(self.google_api_key)
        self.timeout = timeout

    def get_distance_duration(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
    ) -> dict:
        """
        Get driving distance & duration between 2 points.

        Returns:
            {
                "distance_km": float,
                "duration_minutes": float,
                "source": "GOOGLE" | "OSRM"
            }
        """
        if self.prefer_google:
            result = self._fetch_google(origin_lat, origin_lon, dest_lat, dest_lon)
            if result:
                return result
        # Fallback ke OSRM
        return self._fetch_osrm(origin_lat, origin_lon, dest_lat, dest_lon)

    def _fetch_google(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
    ) -> Optional[dict]:
        if not HAS_REQUESTS or not self.google_api_key:
            return None
        try:
            payload = {
                "origin": {"location": {"latLng": {
                    "latitude": origin_lat, "longitude": origin_lon
                }}},
                "destination": {"location": {"latLng": {
                    "latitude": dest_lat, "longitude": dest_lon
                }}},
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
            }
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.google_api_key,
                "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
            }
            r = requests.post(self.GOOGLE_URL, json=payload, headers=headers,
                               timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            routes = data.get("routes", [])
            if not routes:
                return None
            route = routes[0]
            distance_m = route.get("distanceMeters", 0)
            duration_str = route.get("duration", "0s")
            duration_s = int(duration_str.rstrip("s"))
            return {
                "distance_km": distance_m / 1000.0,
                "duration_minutes": duration_s / 60.0,
                "source": "GOOGLE",
            }
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"⚠ Google Maps error: {e}")
            return None

    def _fetch_osrm(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
    ) -> dict:
        """OSRM demo server. Format: /route/v1/driving/lon1,lat1;lon2,lat2"""
        if not HAS_REQUESTS:
            # Tanpa requests → return haversine estimate
            return self._fallback_haversine(
                origin_lat, origin_lon, dest_lat, dest_lon
            )
        try:
            url = (f"{self.OSRM_URL}/"
                   f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
                   f"?overview=false")
            r = requests.get(url, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return self._fallback_haversine(
                    origin_lat, origin_lon, dest_lat, dest_lon
                )
            route = data["routes"][0]
            return {
                "distance_km": route["distance"] / 1000.0,
                "duration_minutes": route["duration"] / 60.0,
                "source": "OSRM",
            }
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"⚠ OSRM error: {e}, fallback ke haversine")
            return self._fallback_haversine(
                origin_lat, origin_lon, dest_lat, dest_lon
            )

    def _fallback_haversine(
        self,
        origin_lat: float, origin_lon: float,
        dest_lat: float, dest_lon: float,
    ) -> dict:
        """Last-resort fallback: haversine + asumsi 60 km/h."""
        from math import asin, cos, radians, sin, sqrt
        R = 6371.0
        dlat = radians(dest_lat - origin_lat)
        dlon = radians(dest_lon - origin_lon)
        a = (sin(dlat / 2) ** 2 +
             cos(radians(origin_lat)) * cos(radians(dest_lat)) * sin(dlon / 2) ** 2)
        dist_km = 2 * R * asin(sqrt(a))
        return {
            "distance_km": dist_km,
            "duration_minutes": (dist_km / 60.0) * 60.0,  # 60 km/h
            "source": "HAVERSINE_FALLBACK",
        }


def get_route(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Helper helper."""
    return RouteConnector().get_distance_duration(lat1, lon1, lat2, lon2)


if __name__ == "__main__":
    # Smoke test: Kediri → Surabaya
    result = get_route(-7.796, 112.170, -7.2575, 112.7521)
    print("Kediri → Surabaya route:", result)

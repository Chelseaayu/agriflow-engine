"""
Data Source: Aladhan Hijri Calendar
====================================

Untuk skenario C1 (Ramadan/Idul Fitri spike) — deteksi H-14 secara otomatis.

URL: https://api.aladhan.com/v1/gToH/{date}
Format: GET, no auth needed.
Free, unlimited rate limit (within reason).

Idul Fitri = 1 Syawwal di kalender Hijriah.
H-14 spike window = 14 hari sebelum 1 Syawwal.

Author: AgriFlow Team
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class HijriCalendarConnector:
    """
    Aladhan API connector untuk konversi Gregorian ↔ Hijri.

    Usage:
        hc = HijriCalendarConnector()
        is_ramadan = hc.is_ramadan_period()
        next_idul_fitri = hc.next_idul_fitri()
    """

    BASE_URL = "https://api.aladhan.com/v1"
    TIMEOUT = 10

    def gregorian_to_hijri(self, gdate: date) -> dict:
        """
        Convert Gregorian → Hijri.
        Return: {"day": int, "month": {"number": int, "en": str},
                 "year": int}
        """
        if not HAS_REQUESTS:
            return {}
        try:
            date_str = gdate.strftime("%d-%m-%Y")
            r = requests.get(f"{self.BASE_URL}/gToH/{date_str}",
                              timeout=self.TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return data.get("data", {}).get("hijri", {})
        except requests.RequestException as e:
            print(f"⚠ Aladhan error: {e}")
            return {}

    def is_ramadan_proximity(
        self,
        reference: Optional[datetime] = None,
        days_before: int = 14,
    ) -> bool:
        """
        Apakah dalam window H-N sampai H-1 Idul Fitri?

        Strategy: convert reference date ke Hijri.
        - Jika bulan Ramadan (9) hari ≥ (30 - days_before) → True
        - Jika hari menjelang akhir Ramadan
        """
        reference = reference or datetime.now()
        hijri = self.gregorian_to_hijri(reference.date())
        if not hijri:
            return False
        month_num = hijri.get("month", {}).get("number", 0)
        day = hijri.get("day", 0)
        # Bulan 9 = Ramadan
        if month_num == 9 and day >= (30 - days_before):
            return True
        return False

    def next_idul_fitri(
        self,
        from_date: Optional[date] = None,
    ) -> Optional[date]:
        """
        Find next Idul Fitri (1 Syawwal) Gregorian date.
        Naive approach: scan forward 1 hari sampai ketemu 1 Syawwal.
        """
        if not HAS_REQUESTS:
            return None
        from_date = from_date or date.today()
        for offset in range(0, 400):  # Search 1 tahun ahead
            check = from_date + timedelta(days=offset)
            hijri = self.gregorian_to_hijri(check)
            if not hijri:
                continue
            month_num = hijri.get("month", {}).get("number", 0)
            day = hijri.get("day", 0)
            # Bulan 10 = Syawwal, hari 1 = Idul Fitri
            if month_num == 10 and day == 1:
                return check
        return None


# =============================================================================
# HARDCODED FALLBACK
# =============================================================================
# Idul Fitri future dates (sumber: kalender Hijriah Kemenag/almanak):
IDUL_FITRI_DATES = {
    2025: date(2025, 3, 31),
    2026: date(2026, 3, 20),
    2027: date(2027, 3, 9),
    2028: date(2028, 2, 26),
    2029: date(2029, 2, 14),
    2030: date(2030, 2, 4),
}


def is_ramadan_period(
    reference: Optional[datetime] = None,
    days_before: int = 14,
    use_api: bool = False,
) -> bool:
    """
    Default: pakai hardcoded dates (offline-friendly).
    Set use_api=True untuk live check via Aladhan.
    """
    reference = reference or datetime.now()
    if use_api:
        try:
            return HijriCalendarConnector().is_ramadan_proximity(
                reference, days_before=days_before
            )
        except Exception:
            pass

    # Hardcoded fallback
    year = reference.year
    target = IDUL_FITRI_DATES.get(year)
    if not target:
        return False
    spike_start = datetime.combine(target - timedelta(days=days_before + 7), datetime.min.time())
    spike_end = datetime.combine(target - timedelta(days=1), datetime.min.time())
    return spike_start <= reference <= spike_end


if __name__ == "__main__":
    print("Testing Hijri calendar...")
    print(f"Today: {datetime.now().date()}")
    print(f"Is Ramadan period (H-21 to H-1): {is_ramadan_period()}")
    # Test specific date
    test_date = datetime(2026, 3, 6)
    print(f"6 Mar 2026 is Ramadan period: {is_ramadan_period(test_date)}")

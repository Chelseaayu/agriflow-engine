# Respons API Produksi (live)

Diambil 22 July 2026 17:57 WIB dari `https://masteraaa123-agriflow-api.hf.space`.
Seluruh permintaan dijalankan terhadap API yang benar-benar melayani dashboard,
bukan terhadap salinan lokal. Perintahnya bisa diulang siapa pun dengan `curl`.

## `GET /health`

Liveness dan konfigurasi runtime

HTTP 200

```json
{
  "status": "ok",
  "version": "0.1.0",
  "mock_mode": true,
  "data_loaded": true,
  "kabupaten_count": 38,
  "komoditas_count": 6,
  "gemini_mock": true,
  "auth_configured": false,
  "require_auth": false,
  "quota_enabled": false,
  "free_daily_quota": 2,
  "quota_backend": "json",
  "billing_mock": true,
  "phone_hash_salted": false
}
```

## `GET /api/v1/commodities`

Daftar komoditas yang tercakup

HTTP 200

```json
[
  {
    "code": "bawang_merah",
    "nama": "Bawang Merah"
  },
  {
    "code": "bawang_putih",
    "nama": "Bawang Putih (Bonggol)"
  },
  {
    "code": "beras_medium",
    "nama": "Beras Medium"
  },
  {
    "code": "beras_premium",
    "nama": "Beras Premium"
  },
  {
    "code": "cabai_merah",
    "nama": "Cabai Merah Besar"
  },
  {
    "code": "cabai_rawit",
    "nama": "Cabai Rawit Merah"
  }
]
```

## `GET /api/v1/surplus-deficit?commodity=beras_premium`

Neraca surplus-defisit per kabupaten

HTTP 200

```json
{
  "commodity": {
    "code": "beras_premium",
    "nama": "Beras Premium"
  },
  "rows": [
    {
      "kab_id": "3524",
      "kab_nama": "Lamongan",
      "lat": -7.1155,
      "lng": 112.417,
      "tier": "TIER_2_MEDIUM",
      "role": "surplus",
      "volume_tons": 245413.62,
      "price_per_kg": 8625.0
    },
    {
      "kab_id": "3521",
      "kab_nama": "Ngawi",
      "lat": -7.408,
      "lng": 111.4458,
      "tier": "TIER_2_MEDIUM",
      "role": "surplus",
      "volume_tons": 219819.88,
      "price_per_kg": 8625.0
    },
    {
      "kab_id": "3522",
      "kab_nama": "Bojonegoro",
      "lat": -7.15,
      "lng": 111.88,
      "tier": "TIER_2_MEDIUM",
      "role": "surplus",
      "volume_tons": 177407.6,
      "price_per_kg": 8625.0
    },
    {
      "kab_id": "3523",
      "kab_nama": "Tuban",
      "lat": -6.897,
      "lng": 111.975,
      "tier": "TIER_2_MEDIUM",
      "role": "surplus",
      "volume_tons": 110704.25,
      "price_per_kg": 8625.0
    },
    {
      "kab_id": "3519",
      "kab_nama": "Madiun",
      "lat": -7.557,
      "lng": 111.689,
      "tier": "TIER_2_MEDIUM",
      "role": "surplus",
      "volume_tons": 105771.19,
      "price_per_kg": 8625.0
    },
    {
      "kab_id": "3525",
      "kab_nama": "Gresik",
      "lat": -7.1568,
      "lng": 112.651,
      "tier": "TIER_2_MEDIUM",
      "role": "surplus",
      "volume_tons": 82477.05,
      "price_per_kg": 8625.0
    },
    {
      "kab_id": "3502",
      "kab_nama": "Ponorogo",
      "lat": -7.8674,
      "lng": 111.4625,
      "tier": "TIER_2_MEDIUM",
      "role": "sur
  ... (dipotong)
```

## `GET /api/v1/matches?commodity=bawang_merah&limit=3`

Rekomendasi distribusi hasil matching engine 4 lapis

HTTP 200

```json
{
  "count": 3,
  "matches": [
    {
      "surplus": {
        "kab_id": "3527",
        "kab_nama": "Sampang",
        "lat": -7.1924,
        "lng": 113.2473,
        "price_per_kg": 24375.0
      },
      "deficit": {
        "kab_id": "3526",
        "kab_nama": "Bangkalan",
        "lat": -7.0317,
        "lng": 112.7491,
        "price_per_kg": 32500.0
      },
      "commodity_code": "bawang_merah",
      "commodity_nama": "Bawang Merah",
      "matched_volume_tons": 3282.74,
      "distance_km": 62.978,
      "final_score": 109.18051214666666,
      "confidence": "MEDIUM",
      "flags": [
        "EQUITY_BOOST_30",
        "MADURA_CLUSTER",
        "VOLUME_MISMATCH_DRASTIS"
      ]
    },
    {
      "surplus": {
        "kab_id": "3512",
        "kab_nama": "Situbondo",
        "lat": -7.7068,
        "lng": 114.0093,
        "price_per_kg": 24375.0
      },
      "deficit": {
        "kab_id": "3511",
        "kab_nama": "Bondowoso",
        "lat": -7.9134,
        "lng": 113.8217,
        "price_per_kg": 32500.0
      },
      "commodity_code": "bawang_merah",
      "commodity_nama": "Bawang Merah",
      "matched_volume_tons": 1955.81,
      "distance_km": 34.926,
      "final_score": 98.3861662825641,
      "confidence": "MEDIUM",
      "flags": [
        "EQUITY_BOOST_15"
      ]
    },
    {
      "surplus": {
        "kab_id": "3574",
        "kab_nama": "Kota Probolinggo",
        "lat": -7.7543,
        "lng": 113.2159,
        "price_per_kg": 24375.0
      },
      "deficit": {
        "kab_id": "3514",
        "kab_nama": "Pasuruan",
        "lat": -7.
  ... (dipotong)
```

## `GET /api/v1/forecast?commodity=cabai_rawit&city=Kota%20Surabaya`

Prakiraan harga, **sengaja dipanggil salah** dengan nama kota alih-alih kode IHK

HTTP 404

```json
{
  "detail": {
    "error": "No forecast for commodity='cabai_rawit' city='Kota Surabaya'",
    "available_pairs": [
      {
        "commodity": "bawang_merah",
        "city": "3509"
      },
      {
        "commodity": "bawang_merah",
        "city": "3510"
      },
      {
        "commodity": "bawang_merah",
        "city": "3529"
      },
      {
        "commodity": "bawang_merah",
        "city": "3571"
      },
      {
        "commodity": "bawang_merah",
        "city": "3573"
      },
      {
        "commodity": "bawang_merah",
        "city": "3574"
      },
      {
        "commodity": "bawang_merah",
        "city": "3577"
      },
      {
        "commodity": "bawang_merah",
        "city": "3578"
      },
      {
        "commodity": "bawang_putih",
        "city": "3509"
      },
      {
        "commodity": "bawang_putih",
        "city": "3510"
      },
      {
        "commodity": "bawang_putih",
        "city": "3529"
      },
      {
        "commodity": "bawang_putih",
        "city": "3571"
      },
      {
        "commodity": "bawang_putih",
        "city": "3573"
      },
      {
        "commodity": "bawang_putih",
        "city": "3574"
      },
      {
        "commodity": "bawang_putih",
        "city": "3577"
      },
      {
        "commodity": "bawang_putih",
        "city": "3578"
      },
      {
        "commodity": "beras_medium",
        "city": "3509"
      },
      {
        "commodity": "beras_medium",
        "city": "3510"
      },
      {
        "commodity": "beras_medium",
        "city": "3529"
      },
      {
        "co
  ... (dipotong)
```

## `GET /api/v1/forecast?commodity=cabai_rawit&city=3578`

Prakiraan harga 30 hari, pemanggilan benar (3578 = Kota Surabaya)

HTTP 200

```json
{
  "commodity_code": "cabai_rawit",
  "city_id": "3578",
  "city_name": "Kota Surabaya",
  "method": "seasonal_naive_baseline",
  "generated_at": "2026-05-31T15:55:31.738746Z",
  "horizon_days": 30,
  "history_end_date": "2025-12-31",
  "forecasts": [
    {
      "date": "2026-01-01",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-02",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-03",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-04",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-05",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-06",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-07",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-08",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-09",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-10",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-11",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-12",
      "point": 51250.0,
      "p10": 32717.5,
      "p90": 69782.5
    },
    {
      "date": "2026-01-13",
      "point": 51
  ... (dipotong)
```

## `GET /api/v1/anomalies?commodity=bawang_merah&limit=2`

Anomali harga terdeteksi

HTTP 200

```json
{
  "count": 2,
  "method": "shesd_v2",
  "anomalies": [
    {
      "date": "2023-05-02",
      "price": 45000.0,
      "rolling_median": 0.0,
      "deviation_pct": 32.35,
      "type": "SPIKE",
      "score": 105.333,
      "commodity_code": "bawang_merah",
      "city_id": "3509",
      "city_name": "Jember",
      "persistent": true
    },
    {
      "date": "2023-05-03",
      "price": 44650.0,
      "rolling_median": 0.0,
      "deviation_pct": 31.32,
      "type": "SPIKE",
      "score": 102.185,
      "commodity_code": "bawang_merah",
      "city_id": "3509",
      "city_name": "Jember",
      "persistent": true
    }
  ]
}
```


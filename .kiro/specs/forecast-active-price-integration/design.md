# Design Document: Active-Price Forecast Integration

## Overview
Migrate only `analysis/forecast_timesfm.py` from its private PIHPS-only anomaly loader to the public source-aware loader. A local adapter converts selected active records to forecast series, retaining provenance for artifact lineage. Anomaly, matching, database, dashboard, WhatsApp, raw data, and food-balance code remain untouched.

## Architecture
```text
*_cleaned.csv + *_jatim.csv
        │
load_source_price_history_csvs(price_dir)
        │ source records with data_source
select_active_prices(source_records)
        │ exact-key Siskaperbapo-first active records
forecast_timesfm._load_active_series()
        │ date-sorted series plus selected-source metadata
TimesFM / seasonal-naive fallback
        │
forecast_all.json (core fields + lineage + coverage)
```

## Components and Interfaces
### Active-series adapter in `analysis/forecast_timesfm.py`
Add a local helper that calls the two public `db.price_ingest` APIs in sequence. It groups selected rows by `(commodity_code, city_id)`, sorts each by date, and returns enough data to preserve the `date`, `price_per_kg`, and `data_source` of every active observation. It must not import `_load_all_rows` or `CITY_NAMES` from `analysis.price_anomaly`.

The numerical model input remains `list[(date, price)]`; its companion active rows supply provenance. The adapter does not impute missing dates, alter values, or write input files. The existing 30-observation eligibility check remains immediately before model execution.

### Regional label resolver
Add a forecast-local, cached reader for `sample_data/kabupaten_jatim.csv` that maps `kab_id` to `nama`. It provides all 38 Jawa Timur labels. `city_id` is the deterministic fallback label when a selected series is not in the reference file. `analysis.price_anomaly.CITY_NAMES` is not changed in this spec.

### Artifact lineage and coverage
For each eligible series, keep the existing core record fields and add:
```json
{
  "active_source_policy": "SISKAPERBAPO_EXACT_KEY_THEN_PIHPS",
  "history_start_date": "YYYY-MM-DD",
  "history_observation_count": 0,
  "active_history_source_counts": {"SISKAPERBAPO": 0, "PIHPS": 0},
  "latest_observation_source": "SISKAPERBAPO",
  "history_coverage_ratio": 0.0,
  "history_coverage_confidence": "HIGH"
}
```
`history_coverage_ratio` is `observation_count / ((end_date - start_date).days + 1)`, rounded deterministically for JSON. Its confidence thresholds are `HIGH >= 0.90`, `MEDIUM >= 0.70`, and `LOW < 0.70`. Counts include selected active history only; they are not raw-market counts. This accurately exposes incomplete Beras Premium series without inventing unavailable market-quality fields.

## Data Models
```python
ActiveObservation = {
    "date": datetime.date,
    "city_id": str,
    "commodity_code": str,
    "price_per_kg": float,
    "data_source": "SISKAPERBAPO" | "PIHPS",
}
ActiveSeries = {
    "series": list[tuple[datetime.date, float]],
    "observations": list[ActiveObservation],
}
```
`observations` and `series` have identical ascending-date order. Artifact lineage is derived only from `observations`.

## Correctness Properties
### Property 1: Precedence preservation
Forecast input values equal the active records selected by the public loader, so Siskaperbapo wins only for the same date/city/commodity and PIHPS remains exact-key fallback.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

### Property 2: Observed-history integrity
Each input series is date ordered, contains selected observed prices only, and its endpoint/source match the final active observation.

**Validates: Requirements 2.1, 2.2, 2.4, 2.5, 4.4**

### Property 3: Regional labelling
Every mapped Jawa Timur city ID uses `kabupaten_jatim.csv`; unmapped IDs retain a stable ID label.

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 4: Compatible explainability
Established core fields remain unchanged while the artifact truthfully distinguishes `timesfm_2.5` output from `seasonal_naive_baseline` and adds JSON-safe lineage and coverage fields.

**Validates: Requirements 4.1, 4.2, 4.3, 4.5**

## Error Handling
Loader failures propagate with their existing validation context. A malformed regional-reference CSV raises a clear error naming the file and missing required columns. An empty active history produces no forecast record. A short active history is skipped with the current diagnostic. No fallback substitutes a different date, city, commodity, or data source.

## Testing Strategy
Add focused forecast-adapter tests using temporary dual-source CSV fixtures. Assert exact-key priority/fallback, no cross-source mean, ordering, source-aware endpoint, eligibility, full regional-name lookup, unmapped label fallback, and coverage/provenance metadata including sparse Beras Premium history. Extend artifact compatibility assertions only for additive lineage fields; retain the existing API tests unchanged.

## Deferred Work
This spec does not migrate anomalies, expand WhatsApp resolution, persist source records to a database, add market-count quality data, overlay matching prices, or change food-balance/Tier decisions.

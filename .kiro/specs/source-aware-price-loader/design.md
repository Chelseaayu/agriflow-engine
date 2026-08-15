# Design Document: Source-Aware Price Loader

## Overview
Add an explicit, offline-safe price-loader API in `db/price_ingest.py`. It will retain normalised records from PIHPS and Siskaperbapo, then derive an active-price view using exact-key precedence: `SISKAPERBAPO` first, `PIHPS` fallback. This change does not modify food balance, matching nodes, raw files, scraping, forecasts, anomalies, or database schema.

## Architecture
```text
*_cleaned.csv (PIHPS) ───────┐
                              ├─ load_source_price_history_csvs() ─ source_records
*_jatim.csv (Siskaperbapo) ──┘                                      │
                                                                     └─ select_active_prices() ─ active_records
```

## Components and Interfaces
### `db.price_ingest.load_source_price_history_csvs(directory)`
Returns every normalised, source-labelled record as dictionaries with `date`, `city_id`, `commodity_code`, `price_per_kg`, and `data_source`.

- It discovers `*_cleaned.csv` as PIHPS and `*_jatim.csv` as Siskaperbapo.
- It validates the shared four-column CSV contract, ISO date, non-empty city ID, known commodity code, and a finite positive price.
- It labels files by discovery pattern, never by a column supplied in the CSV.
- PIHPS records are grouped by `(date, city_id, canonical_commodity, PIHPS)` and averaged only after PIHPS sub-grade normalisation.
- Siskaperbapo records are already district medians. Duplicate canonical keys within Siskaperbapo are rejected to avoid masking corrupt derived input.

### `db.price_ingest.select_active_prices(source_records)`
Returns one active record per `(date, city_id, commodity_code)` with the same five fields.

- It first selects PIHPS rows, then replaces only identical keys with Siskaperbapo rows.
- It does not calculate a cross-source aggregate.
- It sorts output by `(commodity_code, city_id, date)`.

### Compatibility
The existing `load_price_history_csvs()` remains PIHPS-only for existing callers and tests. It will reuse the PIHPS source-loading logic but continue returning the legacy four-field records. New callers must explicitly use the source-aware APIs, preventing silent source mixing.

## Data Models
```python
SourcePriceRecord = {
  "date": datetime.date,
  "city_id": str,
  "commodity_code": str,
  "price_per_kg": float,
  "data_source": "PIHPS" | "SISKAPERBAPO",
}
```
`source_records` may contain both sources for a key; `active_records` contains exactly one.

## Correctness Properties
### Property 1: Exact-key precedence
For any valid Siskaperbapo record, it wins only for the identical date, city, and canonical commodity key.

**Validates: Requirements 3.1, 3.3**

### Property 2: Exact-key fallback
A PIHPS record remains active whenever no Siskaperbapo record exists for its exact key.

**Validates: Requirements 3.2**

### Property 3: Source isolation
No active price is calculated from values belonging to different data sources.

**Validates: Requirements 2.1, 2.2, 3.4**

### Property 4: Determinism
Repeating a load over unchanged files returns equal, deterministically ordered records.

**Validates: Requirements 4.3, 6.2**

## Error Handling
A missing directory raises `FileNotFoundError`. Missing either source is allowed when at least one recognised source file exists. A recognised file with malformed headers, dates, commodity codes, city IDs, non-finite prices, or non-positive prices raises `ValueError` with file and line context. No loader code writes to input files.

## Testing Strategy
Extend `tests/test_price_ingest.py` with temporary fixtures covering: dual-source retention, Siskaperbapo priority, exact-key PIHPS fallback, no cross-source mean, PIHPS-only sub-grade averaging, deterministic order, valid single-source operation, and malformed Siskaperbapo input. Existing legacy-loader tests must continue to pass unchanged.

## Deferred Work
Source-specific database persistence, quality metadata, forecast/anomaly migration, 38-region labels, and matching-node price overlays remain later spec tasks after this loader is validated.

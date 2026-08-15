# Implementation Plan

## Overview
Implement the source-aware loader specified in `requirements.md` and `design.md`. The first delivery changes only `db/price_ingest.py` and verifies it without touching scraping, raw data, food balance, database persistence, forecast, anomaly, dashboard, or WhatsApp code.

## Task Dependency Graph
```json
{
  "waves": [
    {"wave": 1, "tasks": [1]},
    {"wave": 2, "tasks": [2], "dependsOn": [1]},
    {"wave": 3, "tasks": [3], "dependsOn": [2]},
    {"wave": 4, "tasks": [4], "dependsOn": [3]}
  ]
}
```

## Tasks
- [x] 1. Add source-aware record loading in `db/price_ingest.py`
  - Add source constants plus shared validation and normalisation helpers.
  - Discover PIHPS `*_cleaned.csv` and Siskaperbapo `*_jatim.csv` separately.
  - Return source-labelled records without modifying CSV input.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3, 2.4_

- [x] 2. Preserve source-local aggregation and select active records
  - Keep PIHPS-only sub-grade aggregation by canonical date/city/commodity key.
  - Reject duplicate Siskaperbapo canonical keys rather than hiding them.
  - Add deterministic Siskaperbapo-first, PIHPS-fallback active-price selection.
  - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3_

- [x] 3. Preserve the legacy PIHPS loader contract
  - Keep `load_price_history_csvs()` PIHPS-only and four-field compatible.
  - Update module documentation to direct new integrations to explicit source-aware APIs.
  - _Requirements: 6.1_

- [x] 4. Verify loader behaviour and regression safety
  - Exercise a temporary dual-source fixture to verify retention, precedence, fallback, source isolation, and deterministic ordering.
  - Run the existing targeted price-ingest test suite to confirm legacy behaviour remains intact.
  - _Requirements: 6.2_

## Notes
- Siskaperbapo quality metadata, database migration, and downstream consumption are explicitly deferred by the approved design.
- The loader must not modify raw data, determine food-balance roles/volumes, or change Tier classifications.

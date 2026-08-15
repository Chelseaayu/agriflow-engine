# Implementation Plan

## Overview
Implement offline forecasting from the approved active-price view. Tasks change forecast code and automated tests only; they do not touch source datasets, raw observations, artifacts, anomaly code, APIs, dashboard, WhatsApp, matching, database, food balance, or Tier policy.

## Task Dependency Graph
```json
{
  "waves": [
    {"wave": 1, "tasks": [1]},
    {"wave": 2, "tasks": [2], "dependsOn": [1]},
    {"wave": 3, "tasks": [3], "dependsOn": [2]},
    {"wave": 4, "tasks": [4], "dependsOn": [1, 2, 3]}
  ]
}
```

## Tasks
- [ ] 1. Add focused active-price forecast test fixtures and adapter tests in `tests/test_forecast_active_prices.py`.
  - Create temporary PIHPS/Siskaperbapo CSV fixtures that prove selected forecast inputs use Siskaperbapo for an exact shared key, retain PIHPS for a missing exact key, and never average cross-source values.
  - Assert active-series chronological/deterministic ordering, the existing 30-observation eligibility boundary, and source-aware final observation date/source.
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.5, 6.1, 6.2_

- [ ] 2. Replace the PIHPS-only forecast input path in `analysis/forecast_timesfm.py` with a local active-series adapter.
  - Import and call `load_source_price_history_csvs()` then `select_active_prices()`; remove the private `analysis.price_anomaly` loader dependency.
  - Group selected active records by canonical commodity/city, retain per-observation provenance, sort chronologically, and feed only `(date, price)` values to the existing forecasting methods.
  - Keep the 30-observation minimum, use the installed TimesFM 2.5 API with an honest `timesfm_2.5` label, and retain the explicit baseline fallback without imputing source observations.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 4.2_

- [ ] 3. Add forecast-local 38-region label resolution and source-aware lineage/coverage metadata in `analysis/forecast_timesfm.py`.
  - Read `sample_data/kabupaten_jatim.csv` into a cached `kab_id` to `nama` mapping, retaining `city_id` as the unmapped fallback label.
  - Preserve every existing artifact core field and append policy, history boundaries/counts, selected-source counts, latest selected source, coverage ratio, and coverage-confidence fields exactly as designed.
  - Calculate coverage strictly from active observation dates and never present forecast dates as observed history.
  - _Requirements: 2.4, 3.1, 3.2, 3.3, 4.1, 4.3, 4.4, 4.5_

- [ ] 4. Extend automated forecast tests for regional labels, metadata, sparse coverage, and artifact compatibility.
  - Test all 38 reference IDs resolve to their CSV names and unknown IDs resolve deterministically to the ID.
  - Test provenance counters, `history_end_date`, `latest_observation_source`, coverage ratio/confidence thresholds, and incomplete Beras Premium-style history.
  - Update forecast artifact-contract assertions to require additive lineage fields while retaining all existing core fields, forecast-point schema, method labels, and API compatibility expectations.
  - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 6.2, 6.3, 6.4_

## Implementation Constraints
- Use the existing loader's exact-key precedence; do not duplicate or weaken it.
- Do not create a forecast artifact record for a series with fewer than 30 active observations.
- Do not change surplus/deficit roles, volumes, Tier classifications, or Tier coverage. _Requirements: 5.1, 5.2_
- Do not read or modify raw Siskaperbapo observations. _Requirements: 1.5, 5.3_

## Notes
- Rebuild and delivery of the generated forecast artifact are intentionally outside this coding-only task plan.

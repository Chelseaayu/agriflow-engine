# Requirements Document

## Introduction
AgriFlow must precompute forecast time series from the validated active-price view: cleaned Siskaperbapo district medians win for an identical date, Kabupaten/Kota, and commodity; PIHPS is used only as an exact-key fallback. This migration is limited to offline forecasting and its forecast artifact.

## Glossary
- **Active observation:** one source-labelled price selected by `select_active_prices()` for `(date, city_id, commodity_code)`.
- **Active series:** active observations for one canonical `(commodity_code, city_id)`, ordered by observation date.
- **Coverage ratio:** active-observation count divided by inclusive calendar days from the first through last observed date.
- **Coverage confidence:** `HIGH` for coverage ratio >= 0.90, `MEDIUM` for >= 0.70, otherwise `LOW`.

## Requirements

### Requirement 1: Use the active-price contract
**User Story:** As an analyst, I want forecasts built from the same explicit source-precedence policy as the price loader.

#### Acceptance Criteria
1. The forecast precompute SHALL load records only with `load_source_price_history_csvs(price_dir)` followed by `select_active_prices(source_records)`.
2. The forecast precompute SHALL NOT import or call private PIHPS-only helpers from `analysis.price_anomaly`.
3. When valid Siskaperbapo and PIHPS records share an exact key, the forecast input SHALL use only the Siskaperbapo value.
4. When Siskaperbapo is absent for an exact key, the forecast input SHALL retain the PIHPS active fallback value.
5. The forecast precompute SHALL NOT calculate a cross-source mean or mutate source, derived, or raw price files.

### Requirement 2: Build valid, deterministic active series
**User Story:** As a user, I want each forecast to use its complete active observed-price history.

#### Acceptance Criteria
1. The system SHALL group active observations by canonical `(commodity_code, city_id)` and sort each series by ascending date.
2. The system SHALL preserve each selected observation's actual date, price, and `data_source` while adapting it for forecasting.
3. The system SHALL retain the existing minimum of 30 active observations per forecastable series.
4. The system SHALL NOT represent forecast output as an observed price or fill missing observations with synthetic source data.
5. Repeated precomputes over unchanged inputs SHALL emit the same series ordering and history endpoint, except for `generated_at`.

### Requirement 3: Cover all valid Jawa Timur regional series
**User Story:** As a regional user, I want correctly labelled forecasts wherever a supported regional series has sufficient history.

#### Acceptance Criteria
1. The precompute SHALL support every valid active series for the 38 Kabupaten/Kota IDs in `sample_data/kabupaten_jatim.csv`.
2. The forecast artifact SHALL resolve `city_name` from that reference file without changing the anomaly module's existing label map.
3. A valid series with an unmapped city ID SHALL remain forecastable with its city ID used as the label.

### Requirement 4: Preserve forecast behaviour and artifact compatibility
**User Story:** As an API and WhatsApp consumer, I want source-aware forecasts without breaking existing forecast output.

#### Acceptance Criteria
1. The existing core fields (`commodity_code`, `city_id`, `city_name`, `method`, `generated_at`, `horizon_days`, `history_end_date`, and `forecasts`) SHALL remain present and retain their current meanings.
2. The forecast SHALL use the installed TimesFM 2.5 PyTorch API when available and label successful model output as `timesfm_2.5`; the clearly labelled `seasonal_naive_baseline` fallback SHALL remain available.
3. Each artifact record SHALL add `active_source_policy`, `history_start_date`, `history_observation_count`, `active_history_source_counts`, `latest_observation_source`, `history_coverage_ratio`, and `history_coverage_confidence`.
4. `history_end_date` and `latest_observation_source` SHALL describe the final active observed input, not a forecast date or a non-selected source record.
5. The artifact SHALL serialize provenance and quality metadata as JSON-safe values.

### Requirement 5: Keep domain boundaries intact
**User Story:** As a policymaker, I want richer forecasts without changing food-balance policy.

#### Acceptance Criteria
1. The forecast integration SHALL NOT modify food-balance surplus/deficit roles or volumes.
2. The forecast integration SHALL NOT modify Tier classifications, Tier 1 coverage, matching eligibility, database persistence, anomaly processing, dashboard code, or WhatsApp code.
3. The forecast integration SHALL NOT read, alter, delete, or regenerate immutable Siskaperbapo raw observations.

### Requirement 6: Verify source-aware forecasting
**User Story:** As a developer, I want durable tests for the forecasting migration.

#### Acceptance Criteria
1. Automated tests SHALL cover Siskaperbapo exact-key priority, PIHPS exact-key fallback, and the absence of cross-source averaging in forecast input.
2. Automated tests SHALL cover deterministic series order, source-aware history endpoint, 30-observation eligibility, 38-region name resolution, and unmapped-city fallback labels.
3. Automated tests SHALL cover provenance and coverage metadata, including incomplete Beras Premium coverage.
4. Existing forecast artifact/API compatibility tests SHALL continue to accept the preserved core forecast contract.

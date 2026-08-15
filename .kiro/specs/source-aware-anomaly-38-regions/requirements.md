# Requirements Document

## Introduction

Expand offline price-anomaly detection from the eight legacy IHK cities to every Jawa Timur Kabupaten/Kota in the authoritative 38-region reference. The feature uses source-aware, Siskaperbapo-preferred active prices for seven supported commodities, preserves the current interpretable S-H-ESD-style protections, and presents availability, provenance, freshness, and history confidence honestly through artifacts, API, dashboard, and WhatsApp. The feature excludes database-ingestion changes and any changes to food-balance, Tier, or matching decisions.

## Glossary

- **Source_Aware_Anomaly_Pipeline**: The offline process that selects active price observations, evaluates eligible price series, and writes the anomaly artifact.
- **Source_Aware_Price_Loader**: The existing price-history interface formed by `load_source_price_history_csvs()` followed by `select_active_prices()`.
- **Active_Price**: The selected positive, finite price for one exact `(date, city_id, commodity_code)` key, including its `data_source` provenance.
- **Siskaperbapo_Observation**: An immutable raw market-level observation from Siskaperbapo.
- **Derived_District_Price**: The median of valid, non-excluded Siskaperbapo market prices for one `(date, city_id, commodity_code)` key.
- **Exclusion_Audit**: The record in `sample_data/price_history/siskaperbapo_excluded_records.csv` identifying a manually confirmed source-input error and its reason.
- **Region_Registry**: The `kab_id` and `nama` rows in `sample_data/kabupaten_jatim.csv`.
- **Supported_Anomaly_Commodity**: One of `beras_premium`, `beras_medium`, `daging_ayam`, `telur_ayam`, `bawang_merah`, `bawang_putih`, or `cabai_rawit`.
- **Eligible_Series**: An Active_Price series for one Region_Registry `city_id` and Supported_Anomaly_Commodity containing at least 30 observations.
- **History_Coverage_Ratio**: The observation count divided by the inclusive calendar-day count from the first to the latest Active_Price observation in a series.
- **History_Confidence**: `HIGH` for a History_Coverage_Ratio of at least 0.90, `MEDIUM` for at least 0.70 and below 0.90, and `LOW` for below 0.70.
- **Observation_Freshness**: The latest Active_Price date and the whole-day difference between that date and the artifact generation date.
- **Series_Status**: `DETECTABLE` for an Eligible_Series, `INSUFFICIENT_HISTORY` for a series with 1–29 observations, `NO_ACTIVE_HISTORY` for zero observations, or `OUT_OF_COVERAGE` for an unsupported commodity.
- **Anomaly_Artifact**: The offline-precomputed, versioned data package containing series-status metadata and detected anomaly records.
- **Anomaly_API**: The backend endpoint that reads the Anomaly_Artifact.
- **Dashboard_Anomaly_View**: The dashboard interface that displays anomaly results and status.
- **WhatsApp_Anomaly_Responder**: The WhatsApp response path for anomaly requests.

## Requirements

### Requirement 1: Select Source-Aware Active Prices

**User Story:** As a market analyst, I want anomaly detection to use the authoritative price for each region-date-commodity key, so that Siskaperbapo coverage expands analysis without blending incompatible sources.

#### Acceptance Criteria

1. WHEN Anomaly_Artifact precomputation begins, THE Source_Aware_Anomaly_Pipeline SHALL obtain source records by calling `load_source_price_history_csvs()` and SHALL obtain Active_Price records by passing those records to `select_active_prices()`.
2. WHEN both a valid Siskaperbapo price and a PIHPS price exist for the same `(date, city_id, commodity_code)` key, THE Source_Aware_Price_Loader SHALL select the Siskaperbapo price and its `SISKAPERBAPO` provenance for the Active_Price.
3. WHEN no valid Siskaperbapo price exists for a `(date, city_id, commodity_code)` key and a PIHPS price exists for that key, THE Source_Aware_Price_Loader SHALL select the PIHPS price and its `PIHPS` provenance for the Active_Price.
4. IF no Active_Price exists for a requested `(date, city_id, commodity_code)` key, THEN THE Source_Aware_Anomaly_Pipeline SHALL record no synthetic price for that key.
5. THE Source_Aware_Anomaly_Pipeline SHALL retain the selected `data_source` for every Active_Price used in an Anomaly_Artifact.

### Requirement 2: Preserve Siskaperbapo Evidence and District Derivation

**User Story:** As a data steward, I want district prices to remain traceable to auditable market observations, so that anomaly results can be trusted and reviewed.

#### Acceptance Criteria

1. WHEN valid non-excluded Siskaperbapo_Observations share a `(date, city_id, commodity_code)` key, THE Source_Aware_Anomaly_Pipeline SHALL use the median of the market prices as the Derived_District_Price.
2. WHEN a Siskaperbapo_Observation is excluded from a Derived_District_Price, THE Source_Aware_Anomaly_Pipeline SHALL retain an Exclusion_Audit entry identifying the observation and the manually confirmed input-error reason.
3. WHEN a Siskaperbapo_Observation has no Exclusion_Audit entry, THE Source_Aware_Anomaly_Pipeline SHALL retain the Siskaperbapo_Observation in the derived-price calculation.
4. WHEN an anomaly precomputation run completes, THE Source_Aware_Anomaly_Pipeline SHALL preserve every Siskaperbapo_Observation value and identifier unchanged from the precomputation input.

### Requirement 3: Resolve All Authoritative Jawa Timur Regions

**User Story:** As a Jawa Timur user, I want anomaly results for my Kabupaten/Kota, so that price signals are available beyond the eight IHK cities.

#### Acceptance Criteria

1. THE Region_Registry SHALL define the supported anomaly regions exclusively from the 38 `kab_id` and `nama` rows in `sample_data/kabupaten_jatim.csv`.
2. WHEN an Anomaly_Artifact is generated, THE Source_Aware_Anomaly_Pipeline SHALL create a Series_Status entry for every Region_Registry region and every Supported_Anomaly_Commodity.
3. WHEN a user supplies an exact Region_Registry `kab_id`, THE Dashboard_Anomaly_View and WhatsApp_Anomaly_Responder SHALL use that `kab_id` without name-based substitution.
4. IF a user supplies the unqualified name `Kediri`, `Malang`, `Probolinggo`, or `Madiun`, THEN THE WhatsApp_Anomaly_Responder SHALL return an ambiguity status.
5. WHEN the WhatsApp_Anomaly_Responder returns an ambiguity status for an unqualified name, THE WhatsApp_Anomaly_Responder SHALL list the corresponding `Kabupaten` and `Kota` Region_Registry names as selectable alternatives.


### Requirement 4: Declare Commodity Coverage Without Substitution

**User Story:** As a commodity user, I want coverage limits stated explicitly, so that I can distinguish unavailable analysis from analysis for a different commodity.

#### Acceptance Criteria

1. THE Source_Aware_Anomaly_Pipeline SHALL treat exactly the seven Supported_Anomaly_Commodity codes as Siskaperbapo-derived anomaly commodities.
2. WHEN a user requests anomaly information for an engine commodity outside the Supported_Anomaly_Commodity set, THE Anomaly_API SHALL return Series_Status `OUT_OF_COVERAGE` and the requested commodity code.
3. WHEN a user requests anomaly information for an engine commodity outside the Supported_Anomaly_Commodity set, THE Dashboard_Anomaly_View and WhatsApp_Anomaly_Responder SHALL display `OUT_OF_COVERAGE` without presenting a substituted commodity result.

### Requirement 5: Detect Only Eligible Series with Protected S-H-ESD Behavior

**User Story:** As a policy analyst, I want anomalies to be based on sufficient evidence and an interpretable detector, so that short histories and nominal variation do not become misleading alerts.

#### Acceptance Criteria

1. WHEN an Active_Price series contains at least 30 observations, THE Source_Aware_Anomaly_Pipeline SHALL assign Series_Status `DETECTABLE` before invoking the S-H-ESD-style anomaly detector.
2. WHEN an Active_Price series contains from 1 through 29 observations, THE Source_Aware_Anomaly_Pipeline SHALL assign Series_Status `INSUFFICIENT_HISTORY` and SHALL store the exact observation count.
3. WHEN an Active_Price series contains zero observations, THE Source_Aware_Anomaly_Pipeline SHALL assign Series_Status `NO_ACTIVE_HISTORY`.
4. WHILE a series has Series_Status `INSUFFICIENT_HISTORY` or `NO_ACTIVE_HISTORY`, THE Source_Aware_Anomaly_Pipeline SHALL emit no anomaly event for that series.
5. WHEN the S-H-ESD-style anomaly detector evaluates an Eligible_Series, THE Source_Aware_Anomaly_Pipeline SHALL retain seasonal adjustment, robust residual-deviation scoring, the persistence threshold, the low-volatility MAD-floor protection, and the minimum-relative-change protection.
6. WHEN an Eligible_Series has no detector event, THE Source_Aware_Anomaly_Pipeline SHALL retain Series_Status `DETECTABLE` rather than reporting the series as unavailable.

### Requirement 6: Produce an Offline, Auditable Anomaly Artifact

**User Story:** As an operations user, I want precomputed anomaly data with evidence metadata, so that runtime results are fast and interpretable.

#### Acceptance Criteria

1. WHEN Anomaly_Artifact generation completes, THE Source_Aware_Anomaly_Pipeline SHALL write the Anomaly_Artifact without requiring Anomaly_API runtime anomaly calculation.
2. THE Anomaly_Artifact SHALL identify the artifact generation timestamp and the active-source policy `SISKAPERBAPO_EXACT_KEY_THEN_PIHPS`.
3. THE Anomaly_Artifact SHALL store, for each Series_Status entry, the Region_Registry `city_id` and name, commodity code, Series_Status, history start date when observations exist, latest observation date when observations exist, observation count, History_Coverage_Ratio, History_Confidence, Active_Price source counts, latest observation source when observations exist, and Observation_Freshness.
4. WHEN the Anomaly_Artifact stores a detected anomaly event, THE Anomaly_Artifact SHALL store the event date, observed price, signed deviation percentage, event type, score, persistence result, Region_Registry `city_id` and name, commodity code, and selected Active_Price provenance.
5. WHEN the Anomaly_Artifact contains an Eligible_Series whose selected Active_Prices come from multiple sources, THE Anomaly_Artifact SHALL report the count for each selected source without replacing the series provenance with a blended source label.
6. THE Anomaly_Artifact SHALL contain no derived anomaly event whose price equals an average of PIHPS and Siskaperbapo prices for the same `(date, city_id, commodity_code)` key.

### Requirement 7: Serve Refreshed Artifact Data Without Runtime Detection

**User Story:** As an API consumer, I want a refreshed artifact to become visible through a defined backend operation, so that I do not receive stale anomaly information.

#### Acceptance Criteria

1. WHEN an Anomaly_API request is processed, THE Anomaly_API SHALL read Anomaly_Artifact content and SHALL not execute S-H-ESD-style anomaly calculations.
2. WHEN an Anomaly_API request specifies a region and commodity, THE Anomaly_API SHALL return the matching Series_Status metadata even when the matching series contains zero anomaly events.
3. WHEN an Anomaly_API request specifies a region and commodity with Series_Status `INSUFFICIENT_HISTORY`, `NO_ACTIVE_HISTORY`, or `OUT_OF_COVERAGE`, THE Anomaly_API SHALL return that Series_Status and SHALL return zero anomaly events for that region-commodity request.
4. WHEN a rebuilt Anomaly_Artifact replaces the currently served artifact and the documented backend reload or restart operation completes, THE Anomaly_API SHALL evict the previously cached Anomaly_Artifact and SHALL serve the replacement artifact on the next request.
5. THE Anomaly_API SHALL expose the served artifact generation timestamp in every anomaly response.

### Requirement 8: Present Honest Anomaly Availability in Dashboard and WhatsApp

**User Story:** As a dashboard or WhatsApp user, I want availability and data quality shown with anomaly results, so that I do not mistake missing data for no anomaly.

#### Acceptance Criteria

1. WHEN the Dashboard_Anomaly_View displays a `DETECTABLE` series, THE Dashboard_Anomaly_View SHALL display the Region_Registry name, commodity, active-source information, latest observation date, Observation_Freshness, observation count, History_Coverage_Ratio, History_Confidence, and anomaly-event count.
2. WHEN the Dashboard_Anomaly_View displays `INSUFFICIENT_HISTORY`, `NO_ACTIVE_HISTORY`, or `OUT_OF_COVERAGE`, THE Dashboard_Anomaly_View SHALL display the returned Series_Status and available coverage metadata without displaying a mock anomaly record.
3. IF an Anomaly_API request fails, THEN THE Dashboard_Anomaly_View SHALL display an anomaly-data-unavailable error state without generating a mock anomaly record or mock availability claim.
4. WHEN the WhatsApp_Anomaly_Responder returns results for a `DETECTABLE` series, THE WhatsApp_Anomaly_Responder SHALL state the Region_Registry name, commodity, latest observation date, active-source information, History_Confidence, and whether the artifact contains anomaly events.
5. WHEN the WhatsApp_Anomaly_Responder returns `INSUFFICIENT_HISTORY`, `NO_ACTIVE_HISTORY`, or `OUT_OF_COVERAGE`, THE WhatsApp_Anomaly_Responder SHALL state the Series_Status and SHALL not describe the request as `no anomaly` or `full coverage`.

### Requirement 9: Preserve Food-Balance and Matching Behavior

**User Story:** As a distribution planner, I want price-anomaly expansion to remain informational, so that supply allocation decisions retain their approved food-balance basis.

#### Acceptance Criteria

1. THE Source_Aware_Anomaly_Pipeline SHALL leave food-balance regional surplus and deficit roles unchanged.
2. THE Source_Aware_Anomaly_Pipeline SHALL leave food-balance regional surplus and deficit volumes unchanged.
3. THE Source_Aware_Anomaly_Pipeline SHALL leave Tier classifications and Tier coverage unchanged.
4. THE Source_Aware_Anomaly_Pipeline SHALL leave matching eligibility unchanged.
5. THE Source_Aware_Anomaly_Pipeline SHALL complete without database-ingestion changes.

## Executable Correctness Properties

The following properties define automated checks for the feature. Property-based checks use generated valid in-memory records and do not invoke external services.

### Property 1: Exact-Key Source Precedence and No Cross-Source Averaging

For every generated collection of valid PIHPS and Siskaperbapo source records with at most one selected record per source and exact key, applying `select_active_prices(load_source_price_history_csvs(...))` or its equivalent input fixture SHALL produce exactly one Active_Price per exact key. A key containing Siskaperbapo SHALL retain the Siskaperbapo value and provenance; a key without Siskaperbapo but with PIHPS SHALL retain the PIHPS value and provenance; and no selected value SHALL equal a cross-source arithmetic mean unless one original source value independently equals that number.

### Property 2: Derived District Median Retains Non-Excluded Evidence

For every generated non-empty set of positive Siskaperbapo market prices and every generated subset marked by Exclusion_Audit entries, the Derived_District_Price SHALL equal the mathematical median of exactly the unexcluded prices. A generated statistical extreme lacking an Exclusion_Audit entry SHALL remain in the median input set, and the raw input records SHALL be byte-for-byte unchanged after derivation.

### Property 3: Detection-Eligibility Boundary Is Honest

For every generated Active_Price series length from 0 through 60, a length below 30 SHALL yield `NO_ACTIVE_HISTORY` at zero or `INSUFFICIENT_HISTORY` otherwise and no anomaly events; a length of at least 30 SHALL yield `DETECTABLE` before detector evaluation. An eligible series with no emitted events SHALL remain `DETECTABLE`.

### Property 4: Artifact Coverage and Provenance Are Complete

For every generated active-price fixture and a Region_Registry fixture containing 38 unique region IDs, the Anomaly_Artifact status collection SHALL contain exactly one Series_Status entry for each of the 38 region IDs crossed with the seven Supported_Anomaly_Commodity codes. Each entry with observations SHALL report a latest observation source that occurs in its active-source counts, and the counts SHALL sum to the entry observation count.

### Property 5: Unsupported Commodity Responses Cannot Masquerade as Supported Results

For every generated engine commodity code outside the seven-code Supported_Anomaly_Commodity set, the Anomaly_API response, Dashboard_Anomaly_View state, and WhatsApp_Anomaly_Responder message SHALL identify `OUT_OF_COVERAGE`, preserve the requested code, and contain no anomaly event or replacement commodity code.

## Representative Integration Checks

1. Rebuild an Anomaly_Artifact from fixture data containing both sources for the same exact key and verify that the served price and provenance are Siskaperbapo.
2. Replace a temporary Anomaly_Artifact, perform the documented reload or restart operation, and verify that the next Anomaly_API response contains the replacement generation timestamp and no data from the superseded artifact.
3. Request `Kabupaten Kediri` and `Kota Kediri` by their respective IDs and verify distinct results; request unqualified `Kediri` and verify the WhatsApp_Anomaly_Responder asks the user to choose.
4. Compare food-balance roles, volumes, Tier classifications, Tier coverage, and matching eligibility snapshots before and after anomaly artifact generation and verify equality.
5. Simulate an Anomaly_API failure and each unavailable Series_Status in the Dashboard_Anomaly_View and verify that no mock anomaly record or `no anomaly` claim is rendered.

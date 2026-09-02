# Requirements Document

## Introduction
The Forecast Dashboard Feature expands the AgriFlow dashboard forecast city selector from eight legacy IHK cities to the 38 Kabupaten/Kota with forecast artifact coverage. The feature must obtain and render real forecast data for the selected commodity and city through the existing Local Forecast API, show explicit request failures, and preserve all non-forecast behavior and source data.

## Glossary
- **Dashboard:** The AgriFlow web interface that presents forecast and anomaly analysis.
- **Dashboard Test Suite:** The automated verification for Dashboard behavior.
- **Forecast Dashboard Feature:** The Dashboard behavior that selects, requests, and renders forecasts.
- **Forecast City Selector:** The Dashboard control used to choose a forecast region.
- **Forecast Commodity Selector:** The Dashboard control used to choose a forecast commodity.
- **Forecast Region:** One Kabupaten/Kota represented by an identifier and display name in forecast artifact coverage metadata.
- **Forecast Pair:** One exact combination of a forecast commodity code and a Forecast Region identifier.
- **Forecast Artifact:** The source-aware, precomputed forecast dataset with 266 covered Forecast Pairs across seven forecast commodities and 38 Forecast Regions.
- **Local Forecast API:** The existing locally configured API endpoint that returns the Forecast Artifact record for one Forecast Pair.
- **API Failure:** A network failure, unsuccessful Local Forecast API response, or unusable Local Forecast API response.
- **Usable Forecast Response:** A successful Local Forecast API response containing the requested commodity code, requested region identifier, and at least one forecast point.
- **Forecast Rendering Contract:** The established Dashboard rendering of `commodity_code`, `city_id`, `city_name`, `method`, `generated_at`, `horizon_days`, `history_end_date`, and forecast-point `date`, `point`, `p10`, and `p90` values.
- **Anomaly Feature:** The existing Dashboard anomaly selector, request behavior, and anomaly artifact rendering.
- **Protected Domain Behavior:** The existing food-balance roles and volumes, Tier classifications, matching behavior, database behavior, WhatsApp city resolution, `price_anomaly` `CITY_NAMES`, anomaly artifact, raw source files, and derived source files.

## Requirements

### Requirement 1: Provide all forecast-covered regions
**User Story:** As a Dashboard user, I want to select every forecast-covered Kabupaten/Kota, so that I can inspect forecasts outside the legacy IHK-city set.

#### Acceptance Criteria
1. WHEN the Dashboard initializes the Forecast City Selector, THE Dashboard SHALL present exactly 38 Forecast Regions from the Forecast Artifact coverage metadata, with each of the eight legacy IHK cities counted within the 38 Forecast Regions.
2. WHEN the Dashboard presents a Forecast Region, THE Dashboard SHALL display the Forecast Region display name and retain the Forecast Region identifier as the selectable value.
3. WHEN a Dashboard user selects a Forecast Region, THE Dashboard SHALL use the selected Forecast Region identifier for the Forecast Pair.
4. WHEN the Dashboard receives a Forecast Region selection before presenting the Forecast City Selector, THE Dashboard SHALL accept the selection and use the Forecast Region identifier for the Forecast Pair.
5. THE Dashboard SHALL retain support for each of the eight legacy IHK cities as Forecast Regions when the cities are represented by the Forecast Artifact coverage metadata.

### Requirement 2: Request and render the exact Forecast Pair
**User Story:** As a Dashboard user, I want the forecast panel to show the forecast for my exact commodity and region selection, so that I can rely on the displayed analysis.

#### Acceptance Criteria
1. WHEN a Dashboard user changes the Forecast Commodity Selector or Forecast City Selector, THE Dashboard SHALL request the Local Forecast API with the selected forecast commodity code and selected Forecast Region identifier without waiting for a subsequent selector change.
2. WHEN the Local Forecast API returns a Usable Forecast Response, THE Dashboard SHALL render that Usable Forecast Response according to the Forecast Rendering Contract.
3. WHEN the Dashboard begins a Local Forecast API request for a new Forecast Pair, THE Dashboard SHALL mark the Forecast Pair as loading and remove forecast values associated with a different Forecast Pair from the forecast display, including when a Forecast Pair is already loaded.
4. THE Dashboard SHALL use the Local Forecast API response for the requested Forecast Pair as the sole source of forecast values displayed for that Forecast Pair.

### Requirement 3: Surface Local Forecast API failures
**User Story:** As a Dashboard user, I want clear forecast failures rather than invented values, so that I can distinguish unavailable data from a genuine forecast.

#### Acceptance Criteria
1. IF the Local Forecast API returns a not-found response for a Forecast Pair, THEN THE Dashboard SHALL display a forecast-unavailable message identifying the selected forecast commodity and Forecast Region.
2. IF the Local Forecast API returns an unsuccessful response other than a not-found response, THEN THE Dashboard SHALL display a forecast-request-error message for the selected Forecast Pair.
3. IF the Dashboard cannot receive a Local Forecast API response because of a local connection or request failure, THEN THE Dashboard SHALL display a local-forecast-service-unavailable message for the selected Forecast Pair.
4. IF the Local Forecast API returns a response that is not a Usable Forecast Response, THEN THE Dashboard SHALL display a forecast-data-unavailable message for the selected Forecast Pair.
5. WHILE an API Failure applies to a Forecast Pair, THE Dashboard SHALL display the applicable error state in place of forecast values for that Forecast Pair.

### Requirement 4: Preserve forecast rendering compatibility
**User Story:** As an existing Dashboard user, I want valid forecasts to retain their current presentation, so that the city-selector expansion does not disrupt forecast interpretation.

#### Acceptance Criteria
1. WHEN the Local Forecast API returns a Usable Forecast Response, THE Dashboard SHALL preserve the Forecast Rendering Contract.
2. WHERE a Usable Forecast Response contains source provenance or coverage metadata, THE Dashboard SHALL accept the metadata without presenting the metadata or changing any visual element of the Forecast Rendering Contract.
3. WHEN a Dashboard user selects one of the eight legacy IHK cities, THE Dashboard SHALL request and render the corresponding Forecast Pair using the same Local Forecast API behavior used for every Forecast Region.

### Requirement 5: Preserve protected non-forecast behavior and data
**User Story:** As a project stakeholder, I want this forecast-only expansion to leave established operational behavior and data intact, so that wider forecast coverage does not change unrelated decisions or evidence.

#### Acceptance Criteria
1. THE Forecast Dashboard Feature SHALL retain the Anomaly Feature without expanding its city selector, modifying its artifact, or changing `price_anomaly` `CITY_NAMES`.
2. THE Forecast Dashboard Feature SHALL retain existing WhatsApp city resolution.
3. THE Forecast Dashboard Feature SHALL retain food-balance roles and volumes as the source of truth for regional surplus and deficit behavior.
4. THE Forecast Dashboard Feature SHALL retain existing Tier classifications and matching behavior.
5. THE Forecast Dashboard Feature SHALL retain existing database behavior.
6. THE Forecast Dashboard Feature SHALL retain raw source files and derived source files without modification.

### Requirement 6: Verify the forecast-region expansion
**User Story:** As a maintainer, I want automated verification of forecast selection and failure behavior, so that future changes cannot silently regress data integrity or compatibility.

#### Acceptance Criteria
1. WHEN automated Dashboard tests run with Forecast Artifact coverage metadata, THE Dashboard SHALL verify that the Forecast City Selector contains the 38 Forecast Regions and includes the eight legacy IHK cities.
2. WHEN automated Dashboard tests run with a Usable Forecast Response, THE Dashboard SHALL verify that the Local Forecast API receives the exact selected Forecast Pair and that the Forecast Rendering Contract is rendered.
3. WHEN automated Dashboard tests run with each API Failure type, THE Dashboard SHALL verify that the applicable error state is displayed without forecast values for the selected Forecast Pair.
4. WHEN Dashboard regression tests detect an Anomaly Feature behavior change, THE Dashboard Test Suite SHALL record the change for manual review and complete the regression tests.

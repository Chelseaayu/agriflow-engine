# Requirements Document

## Introduction
AgriFlow needs one source-aware historical-price loader. It must load PIHPS and cleaned Siskaperbapo district prices separately, then select Siskaperbapo as the active price whenever a valid observation exists for the same date, Kabupaten/Kota, and commodity. PIHPS remains a fallback and comparison source.

## Glossary
- **Active price:** the selected record for a `(date, city_id, canonical_commodity)` key after source precedence is applied.
- **Source record:** a normalised observation retained with its originating source, `PIHPS` or `SISKAPERBAPO`.
- **Canonical commodity:** the commodity code used by AgriFlow after source-specific normalisation.
- **Valid Siskaperbapo record:** a positive, schema-valid district median already produced by the cleaner and subject only to its confirmed-error audit rules.

## Requirements

### Requirement 1: Load both price sources separately
**User Story:** As a system, I want to load PIHPS and Siskaperbapo records independently so that each observation retains its origin.

#### Acceptance Criteria
1. WHEN price history is loaded, THE system SHALL read legacy PIHPS `*_cleaned.csv` files and cleaned Siskaperbapo `*_jatim.csv` files.
2. THE system SHALL normalise each source's commodity codes into AgriFlow canonical commodity codes.
3. THE system SHALL retain `data_source` as `PIHPS` or `SISKAPERBAPO` on every loaded record.
4. THE system SHALL validate required fields, ISO dates, non-empty city IDs, recognised commodity codes, and positive prices.

### Requirement 2: Preserve source-local aggregation
**User Story:** As a data steward, I want source values to remain auditable and statistically correct.

#### Acceptance Criteria
1. THE system SHALL average only PIHPS sub-grades that normalise to the same canonical commodity on the same date and city.
2. THE system SHALL treat each cleaned Siskaperbapo district median as one source record and SHALL NOT average it with PIHPS.
3. THE system SHALL retain all valid source records for comparison and audit.
4. THE system SHALL NOT read, alter, or delete immutable Siskaperbapo raw data.

### Requirement 3: Select an active price deterministically
**User Story:** As an AgriFlow consumer, I want the best available regional price automatically selected.

#### Acceptance Criteria
1. WHEN a valid Siskaperbapo record exists for `(date, city_id, canonical_commodity)`, THE system SHALL select it as the active record.
2. WHEN no valid Siskaperbapo record exists for that exact key and PIHPS exists, THE system SHALL select PIHPS as the active record.
3. THE system SHALL NOT use a Siskaperbapo observation from a different date, city, or commodity to suppress a PIHPS record.
4. THE system SHALL NOT calculate a cross-source mean.

### Requirement 4: Expose provenance and price selection
**User Story:** As an analyst, I want selected prices to state their source so that outputs are explainable.

#### Acceptance Criteria
1. THE active-price result SHALL include date, city ID, canonical commodity, price, and data source.
2. THE source-record result SHALL support access to both source records for the same key when both exist.
3. THE loader output SHALL be deterministically ordered.

### Requirement 5: Maintain domain boundaries
**User Story:** As a policymaker, I want price improvements not to change food-balance decisions.

#### Acceptance Criteria
1. THE loader SHALL NOT determine or modify surplus/deficit role or volume.
2. THE loader SHALL NOT modify Tier classifications or expand Tier 1 coverage.
3. Active prices MAY later support display, price scoring, forecasts, anomalies, and quality indicators only.

### Requirement 6: Protect existing callers during migration
**User Story:** As a developer, I want a safe path to migrate existing price consumers.

#### Acceptance Criteria
1. THE implementation SHALL provide explicit source-aware APIs rather than silently mixing files in legacy PIHPS-only calls.
2. THE implementation SHALL include tests for priority, fallback, source-local aggregation, validation, provenance, and ordering.
3. Forecast and anomaly consumers SHALL be migrated only after they can use the same active-source selection contract.

# Implementation Plan

## Overview
Implement the approved source-aware anomaly design as an offline artifact pipeline and artifact-only API, WhatsApp, and dashboard consumers. Forecast work is limited to the separately cited artifact refresh, interval ordering, selector, and tests.

## Task Dependency Graph
```json
{
  "waves": [
    {"wave": 1, "tasks": [1, 2, 3]},
    {"wave": 2, "tasks": [4, 5], "dependsOn": [1, 2, 3]},
    {"wave": 3, "tasks": [6, 7, 8], "dependsOn": [4, 5]},
    {"wave": 4, "tasks": [9], "dependsOn": [6, 7, 8]},
    {"wave": 5, "tasks": [10, 11, 12], "dependsOn": [1]},
    {"wave": 6, "tasks": [13], "dependsOn": [9, 12]}
  ]
}
```

## Tasks
- [ ] 1. Add deterministic dual-source fixtures and loader-contract tests
  - Create temporary PIHPS/Siskaperbapo CSV fixtures and a valid 38-row registry fixture; assert the precompute path calls `load_source_price_history_csvs()` then `select_active_prices()`, exact-key Siskaperbapo priority, PIHPS fallback, one selected row per key, retained provenance, ascending dates, no synthetic dates, and no cross-source mean.
  - Byte-compare raw observations and exclusion audit inputs before/after, and retain unexcluded statistical extremes in derived inputs.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 6.5, 6.6, 9.5_

- [ ] 2. Implement source-aware active-series, registry, and status helpers in `analysis/price_anomaly.py`
  - Read and validate exactly 38 unique `kab_id`/`nama` entries from `sample_data/kabupaten_jatim.csv`; replace the legacy eight-city reporting map only in this anomaly path. Group selected records by city/commodity while preserving date, price, and source; support exactly the seven approved commodity codes; emit one status for every 38×7 pair.
  - Calculate bounds, counts, inclusive-day coverage, confidence, source counts, latest source, and artifact-time freshness. Assign `NO_ACTIVE_HISTORY`, `INSUFFICIENT_HISTORY`, or `DETECTABLE` before detection; call the unchanged protected detector only at 30+ observations and retain `DETECTABLE` with zero events.
  - _Requirements: 1.1, 1.4, 1.5, 3.1, 3.2, 4.1, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.3, 6.4, 6.5, 6.6, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 3. Add status, detector-boundary, and protected-domain regression tests
  - Cover 0, 1–29, and 30+ observations, detectable zero-event series, confidence thresholds, freshness from one timestamp, 266 unique ordered keys, source-count totals, latest-source membership, and invalid registries.
  - Snapshot food-balance roles/volumes, Tier data, matching eligibility, database inputs, scraper/cleaner files, and source evidence before/after precompute to prove no mutation.
  - _Requirements: 3.1, 3.2, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.3, 6.4, 6.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 4. Implement atomic versioned artifact generation in `analysis/precompute_anomalies.py`
  - Consume only the public loader sequence and write a temporary sibling then atomically replace `sample_data/anomalies/anomalies_all.json`. Emit `schema_version`, artifact type, one UTC timestamp, method, `SISKAPERBAPO_EXACT_KEY_THEN_PIHPS`, deterministic 266 statuses, and deterministic events.
  - Serialize honest null/zero unavailable fields, event-level selected-observation provenance, and per-source counts without a blended source label; do not write raw, cleaner, exclusion, or derived inputs.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 5. Validate artifact schema and regenerate `sample_data/anomalies/anomalies_all.json`
  - Test version/policy/timestamp fields, deterministic serialization, all required status metadata, no-history nulls, source-count consistency, event provenance, and no averaged price; then regenerate the committed artifact using approved current inputs.
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.5_

- [ ] 6. Upgrade `whatsapp_bot/server.py` to serve and reload the artifact object
  - Add a schema-validated cached artifact reader with no runtime detector import/call; preserve aggregate `count`, `method`, and `anomalies`; return a one-series status envelope with zero events when both filters are supplied; synthesize `OUT_OF_COVERAGE` only for the requested unsupported code.
  - Include generation timestamp/policy/status summary, return explicit `503` for missing or invalid artifacts, and add `reload_anomaly_artifact()` to clear cache after atomic replacement.
  - _Requirements: 4.2, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 7.5, 9.5_

- [ ] 7. Implement strict anomaly-region resolution and status-aware replies in `whatsapp_bot/handlers.py`
  - Resolve valid IDs exactly, then exact normalized full registry names; return both Kabupaten and Kota alternatives for bare Kediri, Malang, Probolinggo, and Madiun; reject all other partial/nearest substitutions. Keep forecast resolution unchanged.
  - Render detectable source/date/confidence/event information and event sources; render unavailable statuses without “no anomaly” or “full coverage”; preserve unsupported requested commodity codes.
  - _Requirements: 3.3, 3.4, 3.5, 4.2, 4.3, 7.1, 7.2, 7.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 8. Add FastAPI and WhatsApp artifact contracts
  - Test zero-event detectable, insufficient/no-history, unsupported, aggregate compatibility, malformed/missing artifact `503`, no runtime detector invocation, replacement-plus-reload generation timestamp, exact Kabupaten/Kota IDs, all four ambiguity replies, and provenance/status wording.
  - _Requirements: 3.3, 3.4, 3.5, 4.2, 4.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 7.5, 8.4, 8.5, 9.5_

- [ ] 9. Update anomaly dashboard client, page, panel, and tests
  - In `dashboard/app/lib/api.ts`, `dashboard/app/page.tsx`, and `dashboard/app/components/AnomalyPanel.tsx`, type the artifact envelope/provenance; separate anomaly selectors/state from forecast; populate all 38 API regions and seven anomaly codes; query the exact pair; clear stale state; retain valid empty detectable events; and show only anomaly-data-unavailable on failure.
  - Render detectable lineage/quality/event provenance and unavailable metadata/status only. Remove fabricated fallback anomaly rows and availability claims. Test all 38 selector values, exact requests, empty detectable, every unavailable status, API failure, and absence of mocks.
  - _Requirements: 3.2, 3.3, 4.2, 4.3, 7.2, 7.3, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 10. Refresh the active-price forecast artifact and safely normalize TimesFM intervals
  - Regenerate the committed latest active-price forecast artifact. In `analysis/forecast_timesfm.py`, enforce `p10 <= point <= p90` by correcting only inverted intervals while preserving valid output and the existing forecast fields/coverage metadata.
  - _Forecast Dashboard Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.2, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 11. Make the forecast selector consume actual forecast coverage/API values, not mock lists
  - Retain coverage-region ID as the selector value, request immediately after either forecast selector changes, clear old-pair values while loading, render only the usable exact-pair API response, preserve the rendering contract, and display each defined API failure state.
  - _Forecast Dashboard Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 12. Add forecast artifact, interval, selector, and failure-contract tests
  - Assert 38 coverage regions including legacy IHK cities, ordered bounds for every point, selector options from real mocked coverage API data rather than constants, exact-pair calls, stale-value removal, rendering compatibility, and every failure state without forecast values.
  - _Forecast Dashboard Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4_

- [ ] 13. Run focused post-change validation suites
  - Run the Python loader/status/artifact tests, FastAPI reload contracts, WhatsApp resolver tests, dashboard anomaly states, forecast interval/selector contracts, and protected-domain snapshots after the regenerated artifacts are in place.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5. Forecast Dashboard Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4_

## Notes
- Food balance, Tier, matching, database, scraper, cleaner, raw source evidence, exclusion audit, and derived source files are protected throughout; no task permits their modification.
- Tasks are coding, data-artifact, and automated-test work only; no discovery, manual review, git, or commit tasks are included.

# Design Document: Source-Aware Anomalies for 38 Jawa Timur Regions

## Overview
This design expands only offline price-anomaly analysis from the legacy eight IHK cities to the authoritative 38-region Jawa Timur registry. It consumes the approved source-aware active-price view, retains S-H-ESD-style detection unchanged for eligible series, and publishes an auditable, versioned artifact for FastAPI, dashboard, and WhatsApp. It deliberately does not modify source cleaning, database ingestion, forecasting, food balance, Tier, matching, roles, or volumes.

**Requirement mapping:** active-price selection and immutable evidence implement R1–R2; registry and unsupported coverage implement R3–R4; detector eligibility implements R5; the artifact implements R6; serving/reload implements R7; consumers implement R8; preserved boundaries implement R9.

## Architecture
```text
PIHPS *_cleaned.csv + Siskaperbapo *_jatim.csv
        │ immutable four-column derived inputs
        ▼
db.price_ingest.load_source_price_history_csvs(price_dir)
        │ all normalized records, each with data_source
        ▼
db.price_ingest.select_active_prices(records)
        │ one observed price per (date, city_id, commodity_code)
        │ SISKAPERBAPO exact-key precedence; PIHPS exact-key fallback
        ▼
analysis.price_anomaly source-aware series adapter
        │ 38-region × seven-commodity status matrix; eligible numerical series
        ▼
existing detect_anomalies() S-H-ESD-style path
        ▼
sample_data/anomalies/anomalies_all.json (versioned artifact object)
        ├── whatsapp_bot.server /api/v1/anomalies (cached reader)
        ├── dashboard API client and AnomalyPanel
        └── whatsapp_bot.handlers.handle_anomali
```

The offline precompute entry point in `analysis/precompute_anomalies.py` calls the two public loader functions in that order; it must not call `price_anomaly._load_all_rows`, reconstruct precedence, or use a cross-source average. The local adapter added in `analysis/price_anomaly.py` groups selected records by `(commodity_code, city_id)`, sorts observations by ascending `date`, and retains every row's `date`, `price_per_kg`, and `data_source`. Its numerical companion series is only `list[(date, price)]`; it never fills dates, changes prices, or writes inputs. **R1.1–R1.5, R6.5–R6.6.**

Siskaperbapo raw market observations, their identifiers, and `siskaperbapo_excluded_records.csv` remain cleaner-owned inputs. The loader consumes only current four-column `*_jatim.csv` district-derived files. Therefore this feature neither recalculates a market median nor alters exclusions; it preserves raw evidence by never opening for write, deleting, synthesizing, or statistically discarding raw records. Valid ordinary outliers remain in the already-derived observation path. **R2.1–R2.4.**

## Region and commodity resolution
`analysis.price_anomaly.py` gains a cached registry reader for `sample_data/kabupaten_jatim.csv`. It requires `kab_id` and `nama`, validates exactly 38 unique nonempty IDs/names, and exposes `city_id -> city_name`; it replaces the eight-entry `CITY_NAMES` reporting map for this feature. It uses neither `tier` nor a hand-maintained fallback list. The resolver's complete authoritative mapping is:

| ID | Name | ID | Name |
|---|---|---|---|
|3578|Kota Surabaya|3573|Kota Malang|
|3571|Kota Kediri|3577|Kota Madiun|
|3574|Kota Probolinggo|3510|Banyuwangi|
|3529|Sumenep|3509|Jember|
|3501|Pacitan|3502|Ponorogo|
|3503|Trenggalek|3504|Tulungagung|
|3505|Blitar|3506|Kediri|
|3507|Malang|3508|Lumajang|
|3511|Bondowoso|3512|Situbondo|
|3513|Probolinggo|3514|Pasuruan|
|3515|Sidoarjo|3516|Mojokerto|
|3517|Jombang|3518|Nganjuk|
|3519|Madiun|3520|Magetan|
|3521|Ngawi|3522|Bojonegoro|
|3523|Tuban|3524|Lamongan|
|3525|Gresik|3526|Bangkalan|
|3527|Sampang|3528|Pamekasan|
|3572|Kota Blitar|3575|Kota Pasuruan|
|3576|Kota Mojokerto|3579|Kota Batu|

The fixed supported set is `{beras_premium, beras_medium, daging_ayam, telur_ayam, bawang_merah, bawang_putih, cabai_rawit}`. Precompute always emits exactly 38 × 7 = 266 statuses in registry order then supported-commodity order, whether or not data exists. A requested engine commodity outside that set is not remapped (including no `cabai_merah -> cabai_rawit` substitution): it receives an `OUT_OF_COVERAGE` series envelope with its requested code. **R3.1–R3.2, R4.1–R4.3.**

## Detection and status generation
For each supported `(city_id, commodity_code)`, the adapter derives metadata solely from selected active observations. With observations sorted by date, `history_coverage_ratio = observation_count / ((latest_date - history_start_date).days + 1)`, rounded to six decimals; confidence is `HIGH` at `>= 0.90`, `MEDIUM` at `>= 0.70` and `< 0.90`, otherwise `LOW`. Freshness is `generation_date_utc.date() - latest_observation_date` in whole days. The generation timestamp is captured once per artifact so every status has the same freshness reference. There is no generated record for an unobserved date. **R1.4, R6.3.**

Status selection precedes detection:

| Active observation count | `series_status` | Detection/event behavior |
|---:|---|---|
| 0 | `NO_ACTIVE_HISTORY` | no detector call; no events |
| 1–29 | `INSUFFICIENT_HISTORY` | no detector call; exact count retained; no events |
| >=30 | `DETECTABLE` | call existing `detect_anomalies()`; retain status even if no event |

For eligible series, the existing S-H-ESD-style detector remains the sole numerical implementation: monthly seasonal adjustment, rolling-median trend/residual calculation, robust MAD scoring, persistence filter, low-volatility MAD-floor protection, and minimum-relative-change gate keep their defaults and semantics. The adapter only supplies different observed source-aware history; it does not weaken protections or turn no-event `DETECTABLE` series into unavailable series. **R5.1–R5.6.**

## Versioned anomaly artifact
`analysis/precompute_anomalies.py` changes the output from the current ambiguous bare JSON list to one JSON object at the existing `sample_data/anomalies/anomalies_all.json` location. The filename is preserved for deployment compatibility, while `schema_version` makes content compatibility explicit.

```json
{
  "schema_version": "source-aware-anomaly/v1",
  "artifact_type": "source_aware_anomaly",
  "generated_at": "2026-08-10T12:00:00Z",
  "method": "shesd_v2",
  "active_source_policy": "SISKAPERBAPO_EXACT_KEY_THEN_PIHPS",
  "series_statuses": ["exactly 266 status objects"],
  "events": ["zero or more anomaly event objects"]
}
```

Each `series_statuses` member has this JSON-safe schema (all counts are selected active observations, not raw-market counts):

```json
{
  "city_id": "3506",
  "city_name": "Kediri",
  "commodity_code": "bawang_merah",
  "series_status": "DETECTABLE",
  "history_start_date": "2025-01-01",
  "latest_observation_date": "2026-08-09",
  "observation_count": 221,
  "history_coverage_ratio": 0.994595,
  "history_confidence": "HIGH",
  "active_history_source_counts": {"SISKAPERBAPO": 220, "PIHPS": 1},
  "latest_observation_source": "SISKAPERBAPO",
  "observation_freshness_days": 1,
  "market_quality": null,
  "market_quality_availability": "UNAVAILABLE_DERIVED_FILE_HAS_FOUR_COLUMNS"
}
```

For no observations, `history_start_date`, `latest_observation_date`, `latest_observation_source`, `observation_freshness_days`, and `history_coverage_ratio` are `null`; `history_confidence` is `null`; both source-count keys are present with zero. `OUT_OF_COVERAGE` is an API-created response status for a requested code and is not one of the fixed 266 supported-series entries. This makes unavailable history distinct from a detectable series with no events. **R3.2, R4.2, R5.2–R5.4, R6.3.**

`market_quality: null` is intentional and is accompanied by the stated unavailable reason. Current derived files expose only date, city ID, commodity code, and price; the artifact must not invent `market_count`, mean, minimum, maximum, median, coverage, or confidence. A future cleaner/loader contract may supply a structured `market_quality` object in this same nullable field without changing the artifact envelope. This design does not change cleaner or loader data files. **R2, R6.3, R8.1.**

Each event is an individual detected selected observation, never a source blend:

```json
{
  "date": "2026-08-09",
  "price": 41000.0,
  "rolling_median": 31800.0,
  "deviation_pct": 28.93,
  "type": "SPIKE",
  "score": 4.81,
  "persistent": true,
  "city_id": "3506",
  "city_name": "Kediri",
  "commodity_code": "bawang_merah",
  "observation_provenance": {
    "data_source": "SISKAPERBAPO",
    "observation_date": "2026-08-09",
    "price_per_kg": 41000.0
  }
}
```

The event provenance is obtained by indexing the selected active row by exact `(date, city_id, commodity_code)`. Per-series lineage remains the counts, endpoint source, active-source policy, history bounds, coverage, and freshness in its status object. A multi-source series is never labelled as a fictitious mixed source. Serialization uses deterministic status ordering and deterministic event order (score descending, then commodity, city, date) for reproducible artifacts. **R1.5, R6.2, R6.4–R6.6.**

## FastAPI serving, compatibility, and cache reload
`whatsapp_bot/server.py` replaces `_load_anomalies() -> list` with a cached artifact-object loader that validates `schema_version` and required top-level keys before serving. It remains an artifact reader only: it never imports or invokes `analysis.price_anomaly.detect_anomalies` at request time. Missing, malformed, or incompatible artifacts yield the existing explicit `503` path rather than silently treating an error as no anomaly. **R6.1, R7.1.**

`GET /api/v1/anomalies` retains `commodity`, `city`, `limit`, and `since`. Existing top-level `count`, `method`, and `anomalies` stay present, so aggregate consumers remain compatible. Every successful response additionally includes `schema_version`, `artifact_generated_at`, `active_source_policy`, and status data:

* With both `city` and `commodity`, return one **series envelope**: `series` is the matching status object (or a synthesized `OUT_OF_COVERAGE` status retaining the requested code); `anomalies` contains only that series' filtered events; `count` is its event count. Thus zero events still carries its metadata.
* With neither, or only one, filter, retain aggregate event-list behavior: `anomalies` contains filtered events, `count` reflects it, `series` is `null`, and `status_summary` reports the total/filter-matching counts by `DETECTABLE`, `INSUFFICIENT_HISTORY`, and `NO_ACTIVE_HISTORY`; it may expose `matching_series_statuses` when a single filter is supplied. This avoids falsely representing multiple series as one.
* `since` and `limit` filter/slice events only, never the selected status or its event count metadata. `OUT_OF_COVERAGE` always has `anomalies: []` and `count: 0`.

The endpoint receives an explicit `reload_anomaly_artifact()` maintenance operation in `whatsapp_bot/server.py`: after atomic replacement of the completed JSON file, deployment automation/admin invokes it (or restarts the process). It calls the loader cache's `cache_clear()`; the next request reads the replacement and exposes its `artifact_generated_at`. Writers must produce a temporary sibling then atomically replace the final artifact, so readers see either the old complete artifact or the new complete artifact, never partial JSON. **R7.2–R7.5.**

## Dashboard type, UI, and data flow
`dashboard/app/lib/api.ts` replaces the list-only anomaly types with `AnomalySeriesStatus`, `AnomalyObservationProvenance`, extended `AnomalyRecord`, `AnomalyStatusSummary`, and `AnomaliesResponse` containing the compatibility event fields plus `artifact_generated_at`, `series`, and `status_summary`. `api.anomalies()` keeps its query builder but typed callers use `series` whenever both filters are supplied.

`dashboard/app/page.tsx` separates anomaly state (`anomalyCommodity`, `anomalyCity`, envelope, loading, error) from the existing forecast selectors. The anomaly city selector uses the full `/api/v1/kabupaten` 38-name result and all seven supported anomaly commodity codes; it must not use `kabupaten.slice(0, 8)`. Forecast may retain its existing selectors and behavior, because this change does not silently promise new forecast coverage. Separate labelled selectors are required if the page keeps forecast and anomaly panels together. The anomaly fetch accepts an empty event array as a valid response, stores the supplied series metadata, and on failure stores no event data plus an explicit anomaly-data-unavailable error. It removes the current fabricated fallback anomaly records and availability claims. **R3.3, R4.3, R7.2–R7.3, R8.1–R8.3.**

`dashboard/app/components/AnomalyPanel.tsx` accepts a series envelope rather than inferring availability from `events.length`. For `DETECTABLE`, it renders region, commodity, event count, source counts/latest source, latest date, freshness, observation count, coverage ratio/confidence, and nullable market-quality unavailable indicator; a zero event list says “no detector event in this detectable history.” For `INSUFFICIENT_HISTORY`, `NO_ACTIVE_HISTORY`, and `OUT_OF_COVERAGE`, it renders the status and returned metadata only, no mock row and no “no anomaly” conclusion. Event rows display their individual `observation_provenance.data_source`. **R6.4, R8.1–R8.3.**

## WhatsApp resolution and responses
`whatsapp_bot/handlers.py` reads the same versioned artifact through a strict artifact loader. It adds a cached 38-region resolver sourced from `kabupaten_jatim.csv` for anomaly requests only; forecast resolution remains unchanged. Resolution order is: (1) use supplied `intent.kabupaten_id` exactly when it is a registry ID; (2) exact full-name match after whitespace/case normalization; (3) for the bare names `Kediri`, `Malang`, `Probolinggo`, and `Madiun`, return an ambiguity reply listing `Kabupaten <name>` and `Kota <name>` alternatives; (4) otherwise request a valid full region name/ID. It must not perform partial or nearest-name substitution. **R3.3–R3.5.**

For a resolved `DETECTABLE` series, the reply states the registry region name, commodity, latest observation date, active-source counts/latest source, history confidence, and whether the artifact has events; event output includes each event's own source. For `INSUFFICIENT_HISTORY`, `NO_ACTIVE_HISTORY`, and `OUT_OF_COVERAGE`, it states the status and available metadata and does not call it “tidak ada anomali” or “cakupan penuh.” Unsupported commodities retain the user-requested code/name and are never substituted. **R4.2–R4.3, R8.4–R8.5.**

## File-level component boundaries

| File | Design change |
|---|---|
| `analysis/price_anomaly.py` | Add source-aware active-series adapter, 38-region resolver, status/history/freshness/lineage helpers; retain `detect_anomalies()` behavior. Stop relying on the eight-city map for source-aware output. |
| `analysis/precompute_anomalies.py` | Generate the versioned object artifact, the exact 266 statuses, and provenance-bearing events using the public loader contract. |
| `whatsapp_bot/server.py` | Cache/validate artifact object, serve the compatible enriched endpoint, and expose cache-clear reload operation; no runtime detector. |
| `whatsapp_bot/handlers.py` | Resolve anomaly regions through exact IDs/full registry names, handle ambiguity and status-aware messaging, and consume artifact object. |
| `dashboard/app/lib/api.ts` | Define the enriched artifact/API TypeScript types and typed response. |
| `dashboard/app/page.tsx` | Use independent anomaly selectors/state, all 38 API regions, and error/empty responses without fabricated anomaly data. |
| `dashboard/app/components/AnomalyPanel.tsx` | Render series availability/lineage and provenance-bearing events. |
| `sample_data/anomalies/anomalies_all.json` | Regenerated offline as the versioned artifact; it is output data, not an application-code schema source. |

## Testing Strategy
Use normal pytest unit tests and FastAPI/TestClient integration tests, plus dashboard component/API-client tests supported by the existing dashboard toolchain. `requirements.txt` contains pytest but no property-based test framework; therefore this feature does not introduce property-test infrastructure or implementation.

Focused Python fixtures create dual-source temporary CSVs and a 38-row registry fixture. Verify the precompute adapter calls `load_source_price_history_csvs()` then `select_active_prices()`, exact-key Siskaperbapo priority, PIHPS fallback, no cross-source mean, date order, no synthetic gaps, raw input byte invariance, 0/1–29/30 eligibility boundaries, detector regression behavior, and a detectable zero-event series. Validate the artifact's version, timestamp/policy, deterministic encoding, exactly 266 unique supported status keys, source-count sum, endpoint source membership, coverage/freshness calculations, null market quality, and event-level source provenance.

Endpoint integration tests cover filtered single-series envelopes (including zero events and all unavailable statuses), unsupported-code envelopes, aggregate backward-compatible event lists/status summary, malformed/missing artifacts, absence of detector calls, and atomic artifact replacement followed by `reload_anomaly_artifact()` returning the new generation timestamp. WhatsApp tests cover exact IDs, all-name lookup, the four ambiguous bare names and listed alternatives, source/confidence wording, and no false “no anomaly” wording. Dashboard tests cover all-38 selector data, separate forecast/anomaly selection, metadata rendering, empty detectable history event display, unavailable states, and API failure with no mock anomaly rows. Finally, snapshot food-balance roles/volumes, Tier classifications/coverage, matching eligibility, and forecast artifacts before/after anomaly precompute to prove they are unchanged. **R1–R9.**

## Explicitly out of scope
Database schema/ingestion; scraping; cleaner logic or derived-file schema; raw-market derivation/exclusion policy; forecasting code, artifacts, model, or coverage; food-balance roles and volumes; Tier values/coverage; matching eligibility/scoring; and price overlays into matching nodes. No source is averaged across PIHPS and Siskaperbapo, no missing history is synthesized, and raw source evidence remains immutable.

## Components and Interfaces
The public integration seam is `load_source_price_history_csvs(price_dir)` followed only by `select_active_prices(source_records)`. The anomaly adapter accepts those active dictionaries and returns date-sorted `ActiveSeries` values plus their unmodified provenance. The precompute module accepts a price directory and output directory and writes one completed artifact. The FastAPI interface remains `GET /api/v1/anomalies`; its filtered form has the single-series envelope described above, while its aggregate form preserves `count`, `method`, and `anomalies`. Dashboard and WhatsApp consume only that artifact/API contract, never detector internals.

## Data Models
`ActiveObservation` is `{date: date, city_id: str, commodity_code: str, price_per_kg: float, data_source: "PIHPS" | "SISKAPERBAPO"}`. `ActiveSeries` is `{observations: list[ActiveObservation], numerical_series: list[tuple[date, float]]}` in identical date order. `SeriesStatus` and `AnomalyEvent` are the JSON objects defined in the artifact schema; `AnomalyArtifact` is the versioned top-level object containing exactly the fixed supported status collection and flattened events. Nullable fields represent unavailable source data, not guessed values.

## Correctness Properties
### Property 1: Exact-key active-source selection
Public-loader selection yields one selected observation per exact key, with Siskaperbapo priority, PIHPS fallback, provenance retention, and no cross-source average.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 6.5, 6.6**

### Property 2: Eligibility boundary and protected detection
For every active-series length, zero is `NO_ACTIVE_HISTORY`, 1–29 is `INSUFFICIENT_HISTORY` with no events, and 30+ is `DETECTABLE` before unchanged detector evaluation.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6**

### Property 3: Complete status coverage and lineage
A valid 38-region registry crossed with the seven supported codes produces exactly 266 unique status entries; source counts sum to observation count and endpoint source occurs in those counts.

**Validates: Requirements 3.1, 3.2, 6.3, 6.4, 6.5**

### Property 4: Unsupported requests remain unsupported
Any unsupported requested code produces `OUT_OF_COVERAGE` with the same requested code and zero events in API, dashboard state, and WhatsApp wording.

**Validates: Requirements 4.2, 4.3, 8.2, 8.3, 8.5**

## Error Handling
The adapter propagates loader validation errors with their file/line context. A malformed registry or artifact fails loudly with the named path and missing/invalid field; the server returns `503` for missing or invalid artifact data and the dashboard displays an error state rather than an empty-result claim. An unknown registry ID/full name is resolved only by an explicit user correction; ambiguous bare names receive the prescribed alternatives. Artifact replacement uses temporary-write then atomic replace, and cache clearing is explicit. **R3.3–R3.5, R7.3–R7.4, R8.3.**

# Siskaperbapo integration — approved project baseline

## Status and scope
This is an approved architectural baseline, not an instruction to implement the integration now. When a later task asks to integrate Siskaperbapo, review or establish the guiding spec before changing application code.

## Immutable business rules
- Food balance (`production − consumption`) is the sole source of truth for regional surplus/deficit role and volume.
- Market prices must never replace food balance, alter its role/volume, or automatically change Tier classifications.
- Price data may support price display, price spread, matching score, forecasting, anomaly detection, dashboard/WhatsApp information, and data-quality indicators.
- Do not automatically expand Tier 1 coverage merely because Siskaperbapo covers all 38 Jawa Timur regions.

## Siskaperbapo data contract
- Keep market-level source observations immutable in `sample_data/raw_data/siskaperbapo_*_raw.csv`; never overwrite, synthesize, or delete raw evidence during cleaning.
- Use `data_sources/siskaperbapo.py` to scrape per commodity with its progress checkpoints.
- Use `sample_data/cleaning_siskaperbapo.py` to derive one district price per `(date, city_id, commodity)`.
- The official derived price is the median of valid market prices in that Kabupaten/Kota on that date.
- Only manually confirmed source-input errors may be excluded from derived output. Keep every exclusion in `sample_data/price_history/siskaperbapo_excluded_records.csv` with its reason.
- Do not discard ordinary statistical outliers automatically; raw market values and their later quality review remain auditable.
- Current derived files use the `*_jatim.csv` suffix intentionally, separate from legacy PIHPS `*_cleaned.csv` files.

## Multi-source policy
- Never blindly average PIHPS and Siskaperbapo observations for the same date, region, and commodity.
- For Jawa Timur district/date/commodity coverage, prefer Siskaperbapo when a valid derived observation exists.
- Retain PIHPS as a fallback and comparison source when Siskaperbapo is unavailable.
- A future source-aware model must preserve provenance and apply explicit active-source precedence; it must not rely on the legacy uniqueness/conflict behaviour that collapses sources.

## Required implementation sequence
1. Create or review a spec for the source-aware price-history integration before direct code changes.
2. Implement and validate a source-aware loader that reads both sources, normalises commodity codes, preserves source metadata, and applies the precedence rule above.
3. Add derived quality metadata where available: market count, mean, min, max, median, coverage/confidence, source, and observation date.
4. Update database schema/ingestion deliberately so `data_source` and source-specific records are retained or an explicit active-source layer is used.
5. Rebuild forecast and anomaly artifacts from the source-aware loader for all supported 38 Jawa Timur regions; include coverage/confidence, particularly for incomplete Beras Premium coverage.
6. Expand city identifiers/names and WhatsApp resolution beyond the current 8 IHK cities.
7. Overlay approved current prices into matching nodes only after the loader is validated. Keep food-balance volumes and roles unchanged; `matching_engine.scoring.price_score()` may then use the updated node prices.
8. Expose source, freshness, and confidence transparently in dashboard/API/WhatsApp outputs.

## Current integration boundaries
- `db/price_ingest.py`, `analysis/price_anomaly.py`, and `analysis/forecast_timesfm.py` currently discover only legacy `*_cleaned.csv` PIHPS data.
- `whatsapp_bot/handlers.py` and `analysis/price_anomaly.py` currently use 8 IHK city mappings.
- Do not rename Siskaperbapo output files simply to make legacy loaders consume them; build the source-aware path instead.

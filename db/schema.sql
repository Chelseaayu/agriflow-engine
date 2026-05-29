-- =============================================================================
-- AgriFlow — Supabase / Postgres Schema
-- Apply with: psql $SUPABASE_DB_URL -f db/schema.sql
-- =============================================================================
--
-- TABLE INVENTORY
--   1. kabupaten             — mirror of sample_data/kabupaten_jatim.csv
--   2. commodity             — mirror of sample_data/komoditas_constraints.csv
--   3. surplus_deficit       — mirror of sample_data/surplus_deficit.csv
--   4. weather_forecast      — mirror of sample_data/weather_forecast.csv
--   5. historical_prices     — mirror of sample_data/historical_price_stats.csv
--   6. commodity_code_map    — Bapanas integer ID ↔ canonical code mapping
--   7. policy_docs           — RAG document store (pgvector embeddings)
--   8. price_history         — TimesFM INPUT  (daily price time series per city)
--   9. forecasts             — TimesFM OUTPUT (per-commodity per-city forecasts)
-- =============================================================================

-- Required extension for pgvector (RAG embeddings)
CREATE EXTENSION IF NOT EXISTS vector;


-- =============================================================================
-- 1. KABUPATEN
-- =============================================================================
CREATE TABLE IF NOT EXISTS kabupaten (
    kab_id          VARCHAR(10)     PRIMARY KEY,    -- BPS wilayah code, e.g. "3578"
    nama            VARCHAR(100)    NOT NULL,        -- e.g. "Kota Surabaya"
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    ipm_2024        DOUBLE PRECISION NOT NULL,       -- IPM BPS 2024
    population_2024 INTEGER         NOT NULL DEFAULT 0,
    tier            VARCHAR(20)     NOT NULL         -- 'TIER_1_HIGH' | 'TIER_2_MEDIUM'
                    CHECK (tier IN ('TIER_1_HIGH', 'TIER_2_MEDIUM')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kabupaten_tier ON kabupaten(tier);


-- =============================================================================
-- 2. COMMODITY
-- =============================================================================
CREATE TABLE IF NOT EXISTS commodity (
    code                VARCHAR(50)     PRIMARY KEY,    -- canonical code, e.g. "cabai_merah"
    nama                VARCHAR(100)    NOT NULL,
    max_distance_km     DOUBLE PRECISION NOT NULL,
    min_viable_tons     DOUBLE PRECISION NOT NULL,
    max_fresh_age_days  INTEGER         NOT NULL,
    bulog_priority      BOOLEAN         NOT NULL DEFAULT FALSE,
    is_imported         BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- 3. SURPLUS_DEFICIT
-- =============================================================================
CREATE TABLE IF NOT EXISTS surplus_deficit (
    id                  BIGSERIAL       PRIMARY KEY,
    kab_id              VARCHAR(10)     NOT NULL REFERENCES kabupaten(kab_id),
    commodity_code      VARCHAR(50)     NOT NULL REFERENCES commodity(code),
    role                VARCHAR(10)     NOT NULL
                        CHECK (role IN ('SURPLUS', 'DEFICIT')),
    volume_tons         DOUBLE PRECISION NOT NULL,
    price_idr_per_kg    DOUBLE PRECISION NOT NULL,
    harvest_age_days    INTEGER         NOT NULL DEFAULT 0,
    data_source         VARCHAR(20)     NOT NULL DEFAULT 'PIHPS',
    recorded_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_surdef_kab         ON surplus_deficit(kab_id);
CREATE INDEX IF NOT EXISTS idx_surdef_commodity   ON surplus_deficit(commodity_code);
CREATE INDEX IF NOT EXISTS idx_surdef_role        ON surplus_deficit(role);
CREATE INDEX IF NOT EXISTS idx_surdef_recorded_at ON surplus_deficit(recorded_at DESC);


-- =============================================================================
-- 4. WEATHER_FORECAST
-- =============================================================================
CREATE TABLE IF NOT EXISTS weather_forecast (
    id                  BIGSERIAL       PRIMARY KEY,
    origin_kab_id       VARCHAR(10)     NOT NULL REFERENCES kabupaten(kab_id),
    dest_kab_id         VARCHAR(10)     NOT NULL REFERENCES kabupaten(kab_id),
    max_rain_mm         DOUBLE PRECISION NOT NULL,
    transit_window_days INTEGER         NOT NULL DEFAULT 1,
    source              VARCHAR(20)     NOT NULL DEFAULT 'BMKG',
    valid_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (origin_kab_id, dest_kab_id, valid_at)
);

CREATE INDEX IF NOT EXISTS idx_weather_origin ON weather_forecast(origin_kab_id);
CREATE INDEX IF NOT EXISTS idx_weather_dest   ON weather_forecast(dest_kab_id);


-- =============================================================================
-- 5. HISTORICAL_PRICES
-- (aggregate stats per commodity — used by engine for fairness scoring)
-- =============================================================================
CREATE TABLE IF NOT EXISTS historical_prices (
    commodity_code      VARCHAR(50)     PRIMARY KEY REFERENCES commodity(code),
    median_idr_per_kg   DOUBLE PRECISION NOT NULL,
    std_idr_per_kg      DOUBLE PRECISION NOT NULL,
    sample_size         INTEGER         NOT NULL DEFAULT 0,
    period_start        DATE,
    period_end          DATE,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- 6. COMMODITY_CODE_MAP
-- Maps Bapanas integer IDs ↔ AgriFlow canonical codes.
-- Explicit in DB — NOT hardcoded in application logic.
-- Mitigates risk if Bapanas API changes its numbering scheme.
-- =============================================================================
CREATE TABLE IF NOT EXISTS commodity_code_map (
    mapping_id          INTEGER         PRIMARY KEY,    -- Bapanas integer commodity ID
    canonical_code      VARCHAR(50)     NOT NULL REFERENCES commodity(code),
    bapanas_name        VARCHAR(100)    NOT NULL,       -- name as returned by Bapanas API
    pihps_code          VARCHAR(50),                    -- PIHPS code if different
    notes               TEXT,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ccmap_canonical ON commodity_code_map(canonical_code);
CREATE INDEX IF NOT EXISTS idx_ccmap_active    ON commodity_code_map(is_active);

-- Seed: known Bapanas commodity IDs at time of AgriFlow v9 build (2026-05)
-- Update this table when Bapanas changes their numbering — never change canonical_code.
INSERT INTO commodity_code_map (mapping_id, canonical_code, bapanas_name) VALUES
    (1,  'beras_premium',  'Beras Premium'),
    (2,  'beras_medium',   'Beras Medium'),
    (3,  'beras_ir64',     'Beras IR 64'),
    (4,  'jagung',         'Jagung Pipilan Kering'),
    (5,  'kedelai',        'Kedelai Biji Kering (Impor)'),
    (6,  'cabai_merah',    'Cabai Merah Besar'),
    (7,  'cabai_rawit',    'Cabai Rawit Merah'),
    (8,  'bawang_merah',   'Bawang Merah'),
    (9,  'bawang_putih',   'Bawang Putih (Bonggol)'),
    (10, 'daging_sapi',    'Daging Sapi Murni'),
    (11, 'daging_ayam',    'Daging Ayam Ras'),
    (12, 'telur_ayam',     'Telur Ayam Ras'),
    (13, 'minyak_goreng',  'Minyak Goreng Curah'),
    (14, 'gula_pasir',     'Gula Pasir Lokal'),
    (15, 'tepung_terigu',  'Tepung Terigu (Curah)'),
    (16, 'tomat',          'Tomat Sayur'),
    (17, 'kentang',        'Kentang'),
    (18, 'wortel',         'Wortel'),
    (19, 'kacang_tanah',   'Kacang Tanah Kupas')
ON CONFLICT (mapping_id) DO NOTHING;


-- =============================================================================
-- 7. POLICY_DOCS
-- Supabase pgvector store for RAG (Gemini embeddings, 768 dims).
-- =============================================================================
CREATE TABLE IF NOT EXISTS policy_docs (
    id              BIGSERIAL       PRIMARY KEY,
    title           TEXT            NOT NULL,
    source          VARCHAR(100),                   -- e.g. 'Permendag 2024', 'BPOM No.5/2024'
    content         TEXT            NOT NULL,       -- full text chunk
    embedding       vector(768),                    -- text-embedding-004 output
    metadata        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- IVFFlat index — good enough for < 1M rows; tune lists param at scale.
-- Build AFTER initial bulk insert for speed.
CREATE INDEX IF NOT EXISTS idx_policy_docs_embedding
    ON policy_docs
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_policy_docs_source ON policy_docs(source);


-- =============================================================================
-- 8. PRICE_HISTORY  —  TimesFM INPUT
--
-- One row per (date, city_id, commodity_code).
-- Fed into google/timesfm-2.0-500m-pytorch for forecasting.
--
-- DATA CONTRACT (shared with TimesFM repo):
--   date            DATE        — observation date (YYYY-MM-DD), no time zone
--   city_id         VARCHAR(10) — matches kabupaten.kab_id (BPS wilayah code)
--   commodity_code  VARCHAR(50) — matches commodity.code (AgriFlow canonical)
--   price_per_kg    NUMERIC(12,2) — observed price in IDR per kg
-- =============================================================================
CREATE TABLE IF NOT EXISTS price_history (
    id              BIGSERIAL       PRIMARY KEY,
    date            DATE            NOT NULL,
    city_id         VARCHAR(10)     NOT NULL REFERENCES kabupaten(kab_id),
    commodity_code  VARCHAR(50)     NOT NULL REFERENCES commodity(code),
    price_per_kg    NUMERIC(12, 2)  NOT NULL,
    data_source     VARCHAR(30)     NOT NULL DEFAULT 'PIHPS',  -- 'PIHPS'|'BAPANAS'|'MANUAL'
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (date, city_id, commodity_code)
);

CREATE INDEX IF NOT EXISTS idx_ph_date          ON price_history(date DESC);
CREATE INDEX IF NOT EXISTS idx_ph_city          ON price_history(city_id);
CREATE INDEX IF NOT EXISTS idx_ph_commodity     ON price_history(commodity_code);
-- Composite for the primary TimesFM query pattern: time series per city+commodity
CREATE INDEX IF NOT EXISTS idx_ph_city_commodity_date
    ON price_history(city_id, commodity_code, date DESC);


-- =============================================================================
-- 9. FORECASTS  —  TimesFM OUTPUT
--
-- One row per (commodity, city_id, date) per model run.
-- Written by the TimesFM inference pipeline; read by the AgriFlow dashboard.
--
-- DATA CONTRACT (shared with TimesFM repo):
--   commodity       VARCHAR(50)    — matches commodity.code
--   city_id         VARCHAR(10)    — matches kabupaten.kab_id
--   city_name       VARCHAR(100)   — denormalized for dashboard convenience
--   date            DATE           — forecast date (YYYY-MM-DD)
--   price_forecast  NUMERIC(12,2)  — point forecast, IDR per kg
--   price_lower     NUMERIC(12,2)  — lower bound (e.g. 10th percentile)
--   price_upper     NUMERIC(12,2)  — upper bound (e.g. 90th percentile)
--   model           VARCHAR(100)   — model identifier, e.g. 'google/timesfm-2.0-500m-pytorch'
--   generated_at    TIMESTAMPTZ    — when this forecast was produced
-- =============================================================================
CREATE TABLE IF NOT EXISTS forecasts (
    id              BIGSERIAL       PRIMARY KEY,
    commodity       VARCHAR(50)     NOT NULL REFERENCES commodity(code),
    city_id         VARCHAR(10)     NOT NULL REFERENCES kabupaten(kab_id),
    city_name       VARCHAR(100)    NOT NULL,
    date            DATE            NOT NULL,
    price_forecast  NUMERIC(12, 2)  NOT NULL,
    price_lower     NUMERIC(12, 2),
    price_upper     NUMERIC(12, 2),
    model           VARCHAR(100)    NOT NULL DEFAULT 'google/timesfm-2.0-500m-pytorch',
    generated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (commodity, city_id, date, model)
);

CREATE INDEX IF NOT EXISTS idx_forecasts_commodity    ON forecasts(commodity);
CREATE INDEX IF NOT EXISTS idx_forecasts_city         ON forecasts(city_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_date         ON forecasts(date DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_generated_at ON forecasts(generated_at DESC);
-- Composite for the primary dashboard query: latest forecast per city+commodity
CREATE INDEX IF NOT EXISTS idx_forecasts_city_commodity_date
    ON forecasts(city_id, commodity, date DESC);

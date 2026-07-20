// Typed thin wrapper around the FastAPI dashboard endpoints.

import { getSupabase } from "./supabase";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type Commodity = { code: string; nama: string };

export type BillingStatus = {
  plan: "FREE" | "PRO";
  is_pro: boolean;
  expires_at: string | null;
  used_today: number;
  limit: number;
  remaining: number; // -1 means unlimited (PRO)
};

export type Kabupaten = {
  id: string;
  nama: string;
  lat: number;
  lng: number;
  tier: string;
  ipm: number;
  population: number;
};

export type SurplusDeficitRow = {
  kab_id: string;
  kab_nama: string;
  lat: number;
  lng: number;
  tier: string;
  role: "surplus" | "deficit";
  volume_tons: number;
  price_per_kg: number;
};

export type SurplusDeficitResponse = {
  commodity: { code: string; nama: string };
  rows: SurplusDeficitRow[];
  totals: { surplus_tons: number; deficit_tons: number; balance_tons: number };
};

export type Match = {
  surplus: {
    kab_id: string;
    kab_nama: string;
    lat: number;
    lng: number;
    price_per_kg: number;
  };
  deficit: {
    kab_id: string;
    kab_nama: string;
    lat: number;
    lng: number;
    price_per_kg: number;
  };
  commodity_code: string;
  commodity_nama: string;
  matched_volume_tons: number;
  distance_km: number;
  final_score: number;
  confidence: string;
  flags: string[];
};

export type MatchesResponse = { count: number; matches: Match[] };

// ---------------------------------------------------------------------------
// Forecast types
// ---------------------------------------------------------------------------

export type ForecastPoint = {
  date: string;   // ISO 8601
  point: number;  // IDR/kg
  p10: number;
  p90: number;
};

export type ForecastResponse = {
  commodity_code:   string;
  city_id:          string;
  city_name:        string;
  method:           string;  // "timesfm_2.0" | "seasonal_naive_baseline"
  generated_at:     string;
  horizon_days:     number;
  history_end_date: string;
  forecasts:        ForecastPoint[];
};

// ---------------------------------------------------------------------------
// Anomaly types
// ---------------------------------------------------------------------------

export type AnomalyRecord = {
  date:           string;   // ISO 8601
  price:          number;   // IDR/kg
  rolling_median: number;
  deviation_pct:  number;   // signed; positive = spike
  type:           "SPIKE" | "DROP";
  score:          number;
  commodity_code: string;
  city_id:        string;
  city_name:      string;
  persistent:     boolean;
};

export type AnomaliesResponse = {
  count:     number;
  method:    string;
  anomalies: AnomalyRecord[];
};

// ---------------------------------------------------------------------------
// Fetch helper + API object
// ---------------------------------------------------------------------------

// Thrown when the API rejects our token. Callers can catch this specifically
// to send the user back to /login instead of showing a generic error.
export class UnauthorizedError extends Error {
  constructor(path: string) {
    super(`${path} requires sign-in`);
    this.name = "UnauthorizedError";
  }
}

async function fetchJson<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};

  // Attach the Supabase access token when there is a session. getSession()
  // refreshes it if it is close to expiry, so a tab left open overnight sends
  // a live token rather than a stale one.
  const supabase = getSupabase();
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store", headers });
  if (r.status === 401) throw new UnauthorizedError(path);
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  commodities: () => fetchJson<Commodity[]>("/api/v1/commodities"),
  kabupaten: () => fetchJson<Kabupaten[]>("/api/v1/kabupaten"),
  surplusDeficit: (commodity: string) =>
    fetchJson<SurplusDeficitResponse>(
      `/api/v1/surplus-deficit?commodity=${encodeURIComponent(commodity)}`,
    ),
  matches: (params: { commodity?: string; kab_id?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params.commodity) q.set("commodity", params.commodity);
    if (params.kab_id) q.set("kab_id", params.kab_id);
    if (params.limit) q.set("limit", String(params.limit));
    return fetchJson<MatchesResponse>(`/api/v1/matches?${q.toString()}`);
  },
  forecast: (params: { commodity: string; city: string }) =>
    fetchJson<ForecastResponse>(
      `/api/v1/forecast?commodity=${encodeURIComponent(params.commodity)}&city=${encodeURIComponent(params.city)}`,
    ),
  anomalies: (params: {
    commodity?: string;
    city?: string;
    limit?: number;
    since?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.commodity) q.set("commodity", params.commodity);
    if (params.city) q.set("city", params.city);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.since) q.set("since", params.since);
    return fetchJson<AnomaliesResponse>(`/api/v1/anomalies?${q.toString()}`);
  },
  // Plan + remaining free-tier quota for a WhatsApp number. The API hashes the
  // number server-side; it is never stored in raw form.
  billingStatus: (phone: string) =>
    fetchJson<BillingStatus>(
      `/billing/status?phone=${encodeURIComponent(phone)}`,
    ),
};

// Typed thin wrapper around the FastAPI dashboard endpoints.

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type Commodity = { code: string; nama: string };

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

async function fetchJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
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
};

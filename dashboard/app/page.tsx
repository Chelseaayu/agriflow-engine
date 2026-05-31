"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  api,
  type AnomalyRecord,
  type Commodity,
  type ForecastResponse,
  type Kabupaten,
  type Match,
  type SurplusDeficitResponse,
} from "./lib/api";
import AnomalyPanel from "./components/AnomalyPanel";
import ForecastPanel from "./components/ForecastPanel";

// Leaflet touches window — must be client-only.
const MapView = dynamic(() => import("./components/MapView"), { ssr: false });

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function fmtIdr(n: number): string {
  return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}

// ---------------------------------------------------------------------------
// IHK city list — cities for which price_history data exists
// ---------------------------------------------------------------------------

const IHK_CITIES = [
  { id: "3509", name: "Jember" },
  { id: "3510", name: "Banyuwangi" },
  { id: "3529", name: "Sumenep" },
  { id: "3571", name: "Kota Kediri" },
  { id: "3573", name: "Kota Malang" },
  { id: "3574", name: "Kota Probolinggo" },
  { id: "3577", name: "Kota Madiun" },
  { id: "3578", name: "Kota Surabaya" },
];

// Commodities available in price_history (anomaly + forecast dataset)
const ANALYSIS_COMMODITIES = [
  { code: "cabai_rawit",   nama: "Cabai Rawit" },
  { code: "bawang_merah",  nama: "Bawang Merah" },
  { code: "bawang_putih",  nama: "Bawang Putih" },
  { code: "beras_medium",  nama: "Beras Medium" },
  { code: "beras_premium", nama: "Beras Premium" },
  { code: "daging_ayam",   nama: "Daging Ayam" },
  { code: "telur_ayam",    nama: "Telur Ayam" },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Home() {
  // --- Distribution state ---
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [kabupaten, setKabupaten]     = useState<Kabupaten[]>([]);
  const [commodity, setCommodity]     = useState<string>("cabai_merah");
  const [sd, setSd]                   = useState<SurplusDeficitResponse | null>(null);
  const [matches, setMatches]         = useState<Match[]>([]);
  const [selectedKabId, setSelectedKabId] = useState<string | null>(null);
  const [loading, setLoading]         = useState(false);
  const [err, setErr]                 = useState<string | null>(null);

  // --- Analysis state ---
  const [analysisCommodity, setAnalysisCommodity] = useState("cabai_rawit");
  const [analysisCity, setAnalysisCity]           = useState("3578"); // Surabaya default
  const [forecast, setForecast]                   = useState<ForecastResponse | null>(null);
  const [forecastLoading, setForecastLoading]     = useState(false);
  const [forecastErr, setForecastErr]             = useState<string | null>(null);
  const [anomalies, setAnomalies]                 = useState<AnomalyRecord[]>([]);
  const [anomalyTotal, setAnomalyTotal]           = useState(0);
  const [anomalyLoading, setAnomalyLoading]       = useState(false);
  const [anomalyErr, setAnomalyErr]               = useState<string | null>(null);

  // Bootstrap: commodities + kabupaten
  useEffect(() => {
    Promise.all([api.commodities(), api.kabupaten()])
      .then(([c, k]) => {
        setCommodities(c);
        setKabupaten(k);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  // Refresh distribution when commodity OR selected kab changes
  useEffect(() => {
    if (!commodity) return;
    setLoading(true);
    setErr(null);
    Promise.all([
      api.surplusDeficit(commodity),
      api.matches({ commodity, kab_id: selectedKabId ?? undefined, limit: 20 }),
    ])
      .then(([sdRes, mRes]) => {
        setSd(sdRes);
        setMatches(mRes.matches);
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [commodity, selectedKabId]);

  // Refresh forecast when analysis selectors change
  useEffect(() => {
    setForecastLoading(true);
    setForecastErr(null);
    api.forecast({ commodity: analysisCommodity, city: analysisCity })
      .then(setForecast)
      .catch((e) => {
        setForecastErr(String(e));
        setForecast(null);
      })
      .finally(() => setForecastLoading(false));
  }, [analysisCommodity, analysisCity]);

  // Refresh anomalies when analysis selectors change
  useEffect(() => {
    setAnomalyLoading(true);
    setAnomalyErr(null);
    api.anomalies({
      commodity: analysisCommodity,
      city:      analysisCity,
      limit:     20,
      since:     "2023-01-01",
    })
      .then((res) => {
        setAnomalies(res.anomalies);
        setAnomalyTotal(res.count);
      })
      .catch((e) => {
        setAnomalyErr(String(e));
        setAnomalies([]);
      })
      .finally(() => setAnomalyLoading(false));
  }, [analysisCommodity, analysisCity]);

  const selectedKab = useMemo(
    () => kabupaten.find((k) => k.id === selectedKabId) ?? null,
    [kabupaten, selectedKabId],
  );

  return (
    <div className="min-h-screen flex flex-col bg-zinc-50 text-zinc-900">
      {/* ================================================================ */}
      {/* Header                                                           */}
      {/* ================================================================ */}
      <header className="border-b border-zinc-200 bg-white px-6 py-3 flex items-center justify-between sticky top-0 z-50">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            AgriFlow <span className="text-emerald-600">·</span> Dashboard
          </h1>
          <p className="text-xs text-zinc-500">
            Surplus-defisit pangan Jawa Timur · matching engine live
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-zinc-600">Komoditas:</label>
          <select
            className="border border-zinc-300 rounded px-3 py-1.5 text-sm bg-white"
            value={commodity}
            onChange={(e) => {
              setCommodity(e.target.value);
              setSelectedKabId(null);
            }}
          >
            {commodities.map((c) => (
              <option key={c.code} value={c.code}>{c.nama}</option>
            ))}
          </select>
        </div>
      </header>

      {/* ================================================================ */}
      {/* Stats strip                                                      */}
      {/* ================================================================ */}
      <div className="border-b border-zinc-200 bg-white px-6 py-2 flex gap-6 text-sm">
        <Stat label="Kabupaten/Kota" value={`${kabupaten.length}`} />
        <Stat
          label="Surplus total"
          value={sd ? `${sd.totals.surplus_tons.toFixed(0)} ton` : "—"}
          color="text-emerald-600"
        />
        <Stat
          label="Defisit total"
          value={sd ? `${sd.totals.deficit_tons.toFixed(0)} ton` : "—"}
          color="text-rose-600"
        />
        <Stat
          label="Balance"
          value={sd ? `${sd.totals.balance_tons.toFixed(0)} ton` : "—"}
          color={sd && sd.totals.balance_tons >= 0 ? "text-emerald-600" : "text-rose-600"}
        />
        <Stat label="Top matches" value={`${matches.length}`} />
        {loading && <span className="text-zinc-400 text-xs self-center">memuat...</span>}
        {err && <span className="text-rose-600 text-xs self-center">{err}</span>}
      </div>

      {/* ================================================================ */}
      {/* PILAR 1 — Distribusi (map + sidebar)                            */}
      {/* ================================================================ */}
      <div className="h-[420px] flex overflow-hidden border-b border-zinc-200">
        <div className="flex-1 relative">
          <MapView
            kabupaten={kabupaten}
            surplusDeficit={sd?.rows ?? []}
            matches={matches}
            onSelectKab={setSelectedKabId}
            selectedKabId={selectedKabId}
          />
          {/* Legend overlay */}
          <div className="absolute bottom-3 left-3 bg-white/95 border border-zinc-200 rounded-lg px-3 py-2 text-xs shadow-sm space-y-1 z-[1000]">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-emerald-600 inline-block" />
              Surplus (siap kirim)
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-rose-600 inline-block" />
              Defisit (butuh supply)
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-slate-400 inline-block" />
              Tidak ada data
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-0.5 bg-indigo-400 inline-block" />
              Match flow
            </div>
          </div>
        </div>

        {/* Sidebar — top matches */}
        <aside className="w-80 border-l border-zinc-200 bg-white overflow-y-auto">
          <div className="px-4 py-3 border-b border-zinc-200">
            {selectedKab ? (
              <>
                <h2 className="font-semibold text-sm">{selectedKab.nama}</h2>
                <p className="text-xs text-zinc-500">
                  Tier {selectedKab.tier} · IPM {selectedKab.ipm.toFixed(1)} ·{" "}
                  {selectedKab.population.toLocaleString("id-ID")} jiwa
                </p>
                <button
                  className="text-xs text-indigo-600 hover:underline mt-1"
                  onClick={() => setSelectedKabId(null)}
                >
                  ← lihat semua match
                </button>
              </>
            ) : (
              <>
                <h2 className="font-semibold text-sm">
                  Top {matches.length} match · {sd?.commodity.nama ?? ""}
                </h2>
                <p className="text-xs text-zinc-500">
                  Klik salah satu kabupaten di peta untuk filter
                </p>
              </>
            )}
          </div>

          <ul className="divide-y divide-zinc-100">
            {matches.length === 0 && !loading && (
              <li className="px-4 py-6 text-sm text-zinc-500">Belum ada match.</li>
            )}
            {matches.map((m, idx) => (
              <li key={idx} className="px-4 py-3 hover:bg-zinc-50">
                <div className="flex items-baseline justify-between">
                  <div className="font-medium text-sm">
                    {m.surplus.kab_nama}
                    <span className="text-zinc-400 px-1">→</span>
                    {m.deficit.kab_nama}
                  </div>
                  <div className="text-xs font-mono text-indigo-600">
                    {m.final_score.toFixed(1)}
                  </div>
                </div>
                <div className="text-xs text-zinc-600 mt-0.5">
                  {m.matched_volume_tons.toFixed(0)} ton ·{" "}
                  {m.distance_km.toFixed(0)} km · {m.confidence}
                </div>
                <div className="text-xs text-zinc-500 mt-0.5">
                  Beli {fmtIdr(m.surplus.price_per_kg)}/kg →
                  Jual {fmtIdr(m.deficit.price_per_kg)}/kg
                  <span className="text-emerald-600 ml-1">
                    (Δ {fmtIdr(m.deficit.price_per_kg - m.surplus.price_per_kg)})
                  </span>
                </div>
                {m.flags.length > 0 && (
                  <div className="text-xs mt-1 flex flex-wrap gap-1">
                    {m.flags.map((f) => (
                      <span
                        key={f}
                        className="bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded text-[10px] font-medium"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </aside>
      </div>

      {/* ================================================================ */}
      {/* PILAR 2 & 3 — Forecast + Anomaly (section below the map)       */}
      {/* ================================================================ */}
      <section className="bg-zinc-50 px-6 py-4">
        {/* Section header + selectors */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-800">
              Analisis Harga · Forecast & Anomali
            </h2>
            <p className="text-xs text-zinc-500">
              Data IHK 8 kota Jawa Timur · 2021–2025
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-600">Komoditas:</label>
            <select
              className="border border-zinc-300 rounded px-2 py-1 text-xs bg-white"
              value={analysisCommodity}
              onChange={(e) => setAnalysisCommodity(e.target.value)}
            >
              {ANALYSIS_COMMODITIES.map((c) => (
                <option key={c.code} value={c.code}>{c.nama}</option>
              ))}
            </select>
            <label className="text-xs text-zinc-600">Kota:</label>
            <select
              className="border border-zinc-300 rounded px-2 py-1 text-xs bg-white"
              value={analysisCity}
              onChange={(e) => setAnalysisCity(e.target.value)}
            >
              {IHK_CITIES.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Two-column grid: Forecast (left) + Anomaly (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Forecast panel */}
          <div>
            <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider mb-1.5">
              Prediksi 30 Hari
            </p>
            <ForecastPanel
              forecast={forecast}
              loading={forecastLoading}
              error={forecastErr}
            />
          </div>

          {/* Anomaly panel */}
          <div>
            <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider mb-1.5">
              Anomali Harga (sejak Jan 2023)
            </p>
            <AnomalyPanel
              anomalies={anomalies}
              loading={anomalyLoading}
              error={anomalyErr}
              totalCount={anomalyTotal}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat component (unchanged)
// ---------------------------------------------------------------------------

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
      <span className={`font-semibold tabular-nums ${color ?? "text-zinc-900"}`}>{value}</span>
    </div>
  );
}

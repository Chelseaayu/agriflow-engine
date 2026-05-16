"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  api, type Commodity, type Kabupaten, type Match, type SurplusDeficitResponse,
} from "./lib/api";

// Leaflet touches window — must be client-only.
const MapView = dynamic(() => import("./components/MapView"), { ssr: false });

function fmtIdr(n: number): string {
  return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}

export default function Home() {
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [kabupaten, setKabupaten] = useState<Kabupaten[]>([]);
  const [commodity, setCommodity] = useState<string>("cabai_merah");
  const [sd, setSd] = useState<SurplusDeficitResponse | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedKabId, setSelectedKabId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Bootstrap: commodities + kabupaten (static across the session)
  useEffect(() => {
    Promise.all([api.commodities(), api.kabupaten()])
      .then(([c, k]) => {
        setCommodities(c);
        setKabupaten(k);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  // Refresh when commodity OR selected kab changes
  useEffect(() => {
    if (!commodity) return;
    setLoading(true);
    setErr(null);
    Promise.all([
      api.surplusDeficit(commodity),
      api.matches({
        commodity,
        kab_id: selectedKabId ?? undefined,
        limit: 20,
      }),
    ])
      .then(([sdRes, mRes]) => {
        setSd(sdRes);
        setMatches(mRes.matches);
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [commodity, selectedKabId]);

  const selectedKab = useMemo(
    () => kabupaten.find((k) => k.id === selectedKabId) ?? null,
    [kabupaten, selectedKabId],
  );

  return (
    <div className="h-screen flex flex-col bg-zinc-50 text-zinc-900">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white px-6 py-3 flex items-center justify-between">
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

      {/* Stats strip */}
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

      {/* Main split — map + sidebar */}
      <div className="flex-1 flex overflow-hidden">
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

        {/* Sidebar */}
        <aside className="w-96 border-l border-zinc-200 bg-white overflow-y-auto">
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
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
      <span className={`font-semibold tabular-nums ${color ?? "text-zinc-900"}`}>{value}</span>
    </div>
  );
}

"use client";

/**
 * AnomalyPanel — displays recent price anomalies (S-H-ESD detections).
 *
 * Shows a scrollable list of anomalies with SPIKE/DROP badges,
 * deviation percentage, and city/commodity labels.
 *
 * Props:
 *   anomalies   AnomalyRecord[]
 *   loading     boolean
 *   error       string | null
 *   totalCount  number
 */

import type { AnomalyRecord } from "../lib/api";

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function fmtIdr(n: number): string {
  if (n >= 1_000_000) return "Rp " + (n / 1_000_000).toFixed(2) + "jt";
  if (n >= 1_000)     return "Rp " + (n / 1_000).toFixed(1) + "k";
  return "Rp " + n.toFixed(0);
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

const COMMODITY_NAMES: Record<string, string> = {
  cabai_rawit:   "Cabai Rawit",
  bawang_merah:  "Bawang Merah",
  bawang_putih:  "Bawang Putih",
  beras_medium:  "Beras Medium",
  beras_premium: "Beras Premium",
  daging_ayam:   "Daging Ayam",
  telur_ayam:    "Telur Ayam",
};

// ---------------------------------------------------------------------------
// Single anomaly row
// ---------------------------------------------------------------------------

function AnomalyRow({ a }: { a: AnomalyRecord }) {
  const isSpike = a.type === "SPIKE";
  const sign    = a.deviation_pct >= 0 ? "+" : "";
  const comName = COMMODITY_NAMES[a.commodity_code] ?? a.commodity_code;

  return (
    <li className="px-3 py-2 hover:bg-zinc-50 flex items-start gap-2.5">
      {/* Badge */}
      <span
        className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap mt-0.5 ${
          isSpike
            ? "bg-rose-100 text-rose-700"
            : "bg-sky-100 text-sky-700"
        }`}
      >
        {a.type}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-1">
          <span className="text-xs font-medium text-zinc-800 truncate">{comName}</span>
          <span className={`text-xs font-mono ${isSpike ? "text-rose-600" : "text-sky-600"}`}>
            {sign}{a.deviation_pct.toFixed(1)}%
          </span>
        </div>
        <div className="text-[11px] text-zinc-500 mt-0.5">
          {fmtDate(a.date)} · {a.city_name} · {fmtIdr(a.price)}/kg
        </div>
        <div className="text-[10px] text-zinc-400 mt-0.5">
          score {a.score.toFixed(2)}
          {a.persistent && (
            <span className="ml-1.5 text-indigo-500">persisten</span>
          )}
        </div>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

type Props = {
  anomalies:  AnomalyRecord[];
  loading:    boolean;
  error:      string | null;
  totalCount: number;
};

export default function AnomalyPanel({ anomalies, loading, error, totalCount }: Props) {
  if (error) {
    return (
      <div className="border border-rose-200 rounded-lg p-3 bg-rose-50 text-xs text-rose-700">
        {error}
      </div>
    );
  }

  return (
    <div className="border border-zinc-200 rounded-lg bg-white overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-zinc-800">
          Anomali Harga Terbaru
        </span>
        <span className="text-[10px] text-zinc-400">
          {loading ? "memuat..." : `${totalCount.toLocaleString("id-ID")} total`}
        </span>
      </div>

      {loading && (
        <div className="px-3 py-4 text-xs text-zinc-400 animate-pulse">
          Memuat anomali...
        </div>
      )}

      {!loading && anomalies.length === 0 && (
        <div className="px-3 py-4 text-xs text-zinc-400">
          Tidak ada anomali untuk filter ini.
        </div>
      )}

      {!loading && anomalies.length > 0 && (
        <>
          <ul className="divide-y divide-zinc-100 max-h-64 overflow-y-auto">
            {anomalies.map((a, i) => (
              <AnomalyRow key={`${a.date}-${a.commodity_code}-${a.city_id}-${i}`} a={a} />
            ))}
          </ul>

          {/* Legend */}
          <div className="px-3 py-1.5 border-t border-zinc-100 flex gap-3 text-[10px] text-zinc-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-rose-200 inline-block" />
              SPIKE (harga naik)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-sky-200 inline-block" />
              DROP (harga turun)
            </span>
            <span className="ml-1 text-indigo-400">persisten = ≥2 hari beruntun</span>
          </div>
        </>
      )}
    </div>
  );
}

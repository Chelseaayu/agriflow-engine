"use client";

import type {
  AnomaliesResponse,
  AnomalyRecord,
  AnomalySeries,
} from "../lib/api";

function fmtIdr(n: number): string {
  if (n >= 1_000_000) return "Rp " + (n / 1_000_000).toFixed(2) + "jt";
  if (n >= 1_000) return "Rp " + (n / 1_000).toFixed(1) + "k";
  return "Rp " + n.toFixed(0);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

const COMMODITY_NAMES: Record<string, string> = {
  cabai_rawit: "Cabai Rawit",
  bawang_merah: "Bawang Merah",
  bawang_putih: "Bawang Putih",
  beras_medium: "Beras Medium",
  beras_premium: "Beras Premium",
  daging_ayam: "Daging Ayam",
  telur_ayam: "Telur Ayam",
};

function sourceLabel(source: string | null): string {
  return source === "SISKAPERBAPO" ? "Siskaperbapo" : source === "PIHPS" ? "PIHPS" : "—";
}

function AnomalyRow({ anomaly }: { anomaly: AnomalyRecord }) {
  const isSpike = anomaly.type === "SPIKE";
  const sign = anomaly.deviation_pct >= 0 ? "+" : "";
  const commodity = COMMODITY_NAMES[anomaly.commodity_code] ?? anomaly.commodity_code;

  return (
    <li className="px-3 py-2 hover:bg-zinc-50 flex items-start gap-2.5">
      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap mt-0.5 ${isSpike ? "bg-rose-100 text-rose-700" : "bg-sky-100 text-sky-700"}`}>
        {anomaly.type}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-1">
          <span className="text-xs font-medium text-zinc-800 truncate">{commodity}</span>
          <span className={`text-xs font-mono ${isSpike ? "text-rose-600" : "text-sky-600"}`}>
            {sign}{anomaly.deviation_pct.toFixed(1)}%
          </span>
        </div>
        <div className="text-[11px] text-zinc-500 mt-0.5">
          {fmtDate(anomaly.date)} · {anomaly.city_name} · {fmtIdr(anomaly.price)}/kg
        </div>
        <div className="text-[10px] text-zinc-400 mt-0.5">
          score {anomaly.score.toFixed(2)} · sumber observasi {sourceLabel(anomaly.observation_provenance.data_source)}
          {anomaly.persistent && <span className="ml-1.5 text-indigo-500">persisten</span>}
        </div>
      </div>
    </li>
  );
}

type Props = {
  response: AnomaliesResponse | null;
  loading: boolean;
  error: string | null;
};

export default function AnomalyPanel({ response, loading, error }: Props) {
  if (error) {
    return <div className="border border-rose-200 rounded-lg p-3 bg-rose-50 text-xs text-rose-700">{error}</div>;
  }

  if (loading) {
    return <div className="border border-zinc-200 rounded-lg p-3 text-xs text-zinc-400 animate-pulse">Memuat anomali...</div>;
  }

  if (!response?.series) {
    return <div className="border border-zinc-200 rounded-lg p-3 text-xs text-zinc-400">Pilih komoditas dan wilayah untuk melihat status anomali.</div>;
  }

  const { series, anomalies } = response;
  const detectable = series.series_status === "DETECTABLE";

  return (
    <div className="border border-zinc-200 rounded-lg bg-white overflow-hidden">
      <div className="px-3 py-2 border-b border-zinc-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-zinc-800">Anomali Harga</span>
        <span className="text-[10px] text-zinc-400">{response.count.toLocaleString("id-ID")} event</span>
      </div>
      {detectable && anomalies.length === 0 && (
        <div className="px-3 py-4 text-xs text-zinc-500">Tidak ada event detector dalam riwayat yang dapat dideteksi.</div>
      )}

      {!detectable && (
        <div className="px-3 py-4 text-xs text-zinc-500">
          Status {series.series_status}; data anomali belum dapat dideteksi untuk kombinasi ini.
        </div>
      )}

      {detectable && anomalies.length > 0 && (
        <>
          <ul className="divide-y divide-zinc-100 max-h-64 overflow-y-auto">
            {anomalies.map((anomaly, index) => (
              <AnomalyRow key={`${anomaly.date}-${anomaly.commodity_code}-${anomaly.city_id}-${index}`} anomaly={anomaly} />
            ))}
          </ul>
          <div className="px-3 py-1.5 border-t border-zinc-100 flex gap-3 text-[10px] text-zinc-500">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-rose-200 inline-block" />SPIKE (harga naik)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-sky-200 inline-block" />DROP (harga turun)</span>
            <span className="ml-1 text-indigo-400">persisten = ≥2 hari beruntun</span>
          </div>
        </>
      )}
    </div>
  );
}

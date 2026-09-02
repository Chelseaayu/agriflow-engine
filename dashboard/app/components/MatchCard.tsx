"use client";

// One recommendation, explained. Everything on the card is a field the
// engine returned: score decomposition, equity multiplier, flags, road
// distance, arbitrage. "Mengapa" opens the ranking of every viable supplier
// for the same deficit (/api/v1/matches/explain).

import { useState } from "react";
import type { Match } from "../lib/api";
import { fmtIdr, fmtTon, shortKab } from "../lib/format";
import { Icons } from "./Icons";

const DIMS: { key: keyof Match["breakdown"]; label: string; weight: string }[] = [
  { key: "distance", label: "Jarak", weight: "22%" },
  { key: "volume", label: "Volume", weight: "22%" },
  { key: "price", label: "Harga", weight: "22%" },
  { key: "perishability", label: "Masa simpan", weight: "18%" },
  { key: "climate", label: "Iklim rute", weight: "16%" },
];

const FLAG_LABEL: Record<string, string> = {
  EQUITY_BOOST_30: "Equity +30%",
  EQUITY_BOOST_15: "Equity +15%",
  EQUITY_BOOST_05: "Equity +5%",
  MADURA_CLUSTER: "Klaster Madura",
  VOLUME_MISMATCH_DRASTIS: "Volume kecil vs kebutuhan",
  STALE_DATA_24H: "Data >24 jam",
  RAMADAN_SPIKE: "Mode Ramadan",
  IMPORT_POLICY_ACTIVE: "Kebijakan impor",
  HUMANITARIAN_PRIORITY: "Prioritas kemanusiaan",
  GRADE_SUBSTITUTION: "Substitusi grade",
};

export function priorityOf(m: Match): { label: string; cls: string } {
  if (m.equity_multiplier >= 1.3) return { label: "Prioritas equity", cls: "bg-[#fce9e9] text-[#b33c3c]" };
  if (m.equity_multiplier >= 1.15) return { label: "Daerah tertinggal", cls: "bg-[#fef4e2] text-[#b27218]" };
  if (m.final_score >= 90) return { label: "Skor tinggi", cls: "bg-[#e2edd8] text-[#44602c]" };
  return { label: "Layak", cls: "bg-zinc-100 text-zinc-600" };
}

export default function MatchCard({
  m, compact = false, onExplain, onFocus, highlight = false,
}: {
  m: Match;
  compact?: boolean;
  onExplain?: (m: Match) => void;
  onFocus?: (m: Match) => void;
  highlight?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const pr = priorityOf(m);
  const flags = m.flags.filter((f) => FLAG_LABEL[f]);

  return (
    <div className={`bg-white rounded-2xl p-3.5 shadow-sm flex flex-col gap-2 border ${highlight ? "border-yellow-400 ring-2 ring-yellow-300" : "border-transparent"}`}>
      <div className="flex justify-between items-center gap-2">
        <span className={`text-[9px] font-extrabold px-2 py-0.5 rounded uppercase tracking-wider ${pr.cls}`}>{pr.label}</span>
        <span className="text-xs font-extrabold text-[#44602c] truncate">{m.commodity_nama}</span>
      </div>

      <button onClick={() => onFocus?.(m)} className="text-left flex items-center justify-between gap-2 text-sm font-bold text-zinc-900">
        <span className="truncate">{shortKab(m.surplus.kab_nama)}</span>
        <span className="flex-1 flex flex-col items-center px-2 min-w-[64px]">
          <span className="text-[10px] font-bold text-zinc-500">{m.distance_km.toFixed(0)} km jalan</span>
          <span className="w-full border-t border-dashed border-[#4e643c]/50" />
        </span>
        <span className="truncate text-right">{shortKab(m.deficit.kab_nama)}</span>
      </button>

      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <Stat label="Volume" value={fmtTon(m.matched_volume_tons)} />
        <Stat label="Skor" value={m.final_score.toFixed(0)} sub={`base ${m.base_score.toFixed(0)} × ${m.equity_multiplier.toFixed(2)}`} />
        <Stat label="Selisih harga" value={fmtIdr(m.price_spread_idr_per_kg) + "/kg"} />
      </div>

      {!compact && (
        <div className="space-y-1">
          {DIMS.map((d) => {
            const v = m.breakdown[d.key];
            return (
              <div key={d.key} className="flex items-center gap-2 text-[10px]">
                <span className="w-20 text-zinc-500 shrink-0">{d.label} <span className="text-zinc-300">{d.weight}</span></span>
                <span className="flex-1 h-1.5 bg-zinc-100 rounded overflow-hidden">
                  <span className="block h-full bg-[#5b7245]" style={{ width: `${Math.round(v * 100)}%` }} />
                </span>
                <span className="w-8 text-right tabular-nums text-zinc-600">{v.toFixed(2)}</span>
              </div>
            );
          })}
        </div>
      )}

      {flags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {flags.map((f) => (
            <span key={f} className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600">{FLAG_LABEL[f]}</span>
          ))}
          <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-zinc-50 text-zinc-500">confidence {m.confidence}</span>
        </div>
      )}

      <div className="flex items-center justify-between gap-2 pt-1 border-t border-zinc-100">
        <button onClick={() => setOpen((v) => !v)} className="text-[11px] font-bold text-[#5b7245] hover:underline flex items-center gap-1">
          <Icons.ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
          {open ? "Sembunyikan alasan" : "Mengapa match ini"}
        </button>
        {onExplain && (
          <button onClick={() => onExplain(m)} className="text-[11px] font-bold text-white bg-[#4e643c] hover:bg-[#3d5030] px-3 py-1 rounded-lg">
            Bandingkan pemasok
          </button>
        )}
      </div>
      {open && (
        <ul className="text-[11px] text-zinc-700 space-y-1 list-disc pl-4">
          {m.why.map((w, i) => <li key={i}>{w}</li>)}
          {m.gross_arbitrage_idr > 0 && (
            <li>Potensi selisih nilai (harga tujuan dikurangi asal × volume): {fmtIdr(m.gross_arbitrage_idr, { compact: true })}</li>
          )}
          {m.notes && <li className="text-amber-700">{m.notes}</li>}
        </ul>
      )}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-[#f4f7f2] rounded-lg px-2 py-1.5 min-w-0">
      <span className="text-[9px] font-bold text-zinc-400 uppercase tracking-wider block">{label}</span>
      <span className="text-xs font-extrabold text-zinc-800 block truncate tabular-nums">{value}</span>
      {sub && <span className="text-[9px] text-zinc-500 block truncate">{sub}</span>}
    </div>
  );
}

"use client";

import dynamic from "next/dynamic";
import type { Kabupaten, Match, SurplusDeficitResponse } from "../../lib/api";
import { fmtIdr, fmtTon } from "../../lib/format";

const MapView = dynamic(() => import("../MapView"), { ssr: false });

export default function PetaPasokan({
  name, sd, matches, kabupaten, selectedKabId, onSelectKab,
}: {
  name: string;
  sd: SurplusDeficitResponse | null;
  matches: Match[];
  kabupaten: Kabupaten[];
  selectedKabId: string | null;
  onSelectKab: (id: string | null) => void;
}) {
  const rows = sd?.rows ?? [];
  const surplus = rows.filter((r) => r.role === "surplus").sort((a, b) => b.volume_tons - a.volume_tons);
  const deficit = rows.filter((r) => r.role === "deficit").sort((a, b) => b.volume_tons - a.volume_tons);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between gap-2">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">Peta pasokan: {name}</h2>
          <p className="text-xs text-emerald-100/80 mt-0.5">Ukuran lingkaran sebanding akar volume. Klik kabupaten untuk memfilter rekomendasi.</p>
        </div>
        {selectedKabId && <button onClick={() => onSelectKab(null)} className="bg-white text-[#5b7245] px-3 py-1.5 rounded-xl text-xs font-bold shadow-sm">Hapus filter</button>}
      </div>
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden h-[55vh] min-h-[320px] relative">
        <MapView kabupaten={kabupaten} surplusDeficit={rows} matches={matches} onSelectKab={(id) => onSelectKab(id)} selectedKabId={selectedKabId} flowLimit={25} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ListCard title={`Wilayah surplus (${surplus.length})`} tone="bg-[#e2edd8] text-[#44602c]" rowTone="bg-[#708b5e]" rows={surplus} selected={selectedKabId} onSelect={onSelectKab} />
        <ListCard title={`Wilayah defisit (${deficit.length})`} tone="bg-[#fce6e6] text-[#aa3a3a]" rowTone="bg-[#d78a8a]" rows={deficit} selected={selectedKabId} onSelect={onSelectKab} />
      </div>
      {sd && (
        <p className="text-[11px] text-emerald-100/80">
          Total surplus {fmtTon(sd.totals.surplus_tons)}, defisit {fmtTon(sd.totals.deficit_tons)}, neraca {sd.totals.balance_tons >= 0 ? "+" : ""}{fmtTon(sd.totals.balance_tons)}. Sumber: BPS produksi dan konsumsi 2022 per kabupaten, dikonversi ke ton.
        </p>
      )}
    </div>
  );
}

function ListCard({ title, tone, rowTone, rows, selected, onSelect }: {
  title: string; tone: string; rowTone: string;
  rows: SurplusDeficitResponse["rows"]; selected: string | null; onSelect: (id: string | null) => void;
}) {
  return (
    <div className="bg-white rounded-2xl shadow-sm overflow-hidden flex flex-col max-h-[320px]">
      <div className={`px-4 py-2 font-bold text-xs ${tone}`}>{title}</div>
      <ul className="flex-1 overflow-y-auto px-3 py-2.5 space-y-1.5 text-xs">
        {rows.length === 0 && <li className="px-4 py-6 text-center text-zinc-400 bg-zinc-50 rounded-xl">Tidak ada.</li>}
        {rows.map((r) => (
          <li key={r.kab_id}>
            <button
              onClick={() => onSelect(selected === r.kab_id ? null : r.kab_id)}
              className={`w-full px-3 py-2 rounded-lg flex justify-between items-center font-bold text-xs text-white ${rowTone} hover:opacity-90 ${selected === r.kab_id ? "ring-2 ring-yellow-400" : ""}`}
            >
              <span className="truncate text-left">{r.kab_nama}</span>
              <span className="text-[10px] opacity-90 font-medium">{fmtIdr(r.price_per_kg)}/kg</span>
              <span className="tabular-nums">{fmtTon(r.volume_tons)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import type { Kabupaten, Match, SurplusDeficitResponse } from "../../lib/api";
import MatchCard from "../MatchCard";
import SimulatorPanel from "../SimulatorPanel";

const MapView = dynamic(() => import("../MapView"), { ssr: false });

export default function Simulasi({
  commodity, name, sd, baselineMatches, kabupaten, onExplain,
}: {
  commodity: string;
  name: string;
  sd: SurplusDeficitResponse | null;
  baselineMatches: Match[];
  kabupaten: Kabupaten[];
  onExplain: (m: Match) => void;
}) {
  const [scenario, setScenario] = useState<Match[] | null>(null);
  const [down, setDown] = useState<string[]>([]);
  const shown = scenario ?? baselineMatches;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">Simulasi what-if: {name}</h2>
        <p className="text-xs text-emerald-100/80 mt-0.5">Peta menampilkan {scenario ? "hasil skenario" : "baseline hari ini"}. Kabupaten abu-abu putus-putus berarti tidak terjangkau dalam skenario.</p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm overflow-hidden h-[320px] sm:h-[420px]">
          <MapView kabupaten={kabupaten} surplusDeficit={sd?.rows ?? []} matches={shown} onSelectKab={() => {}} selectedKabId={null} unreachable={down} flowLimit={40} />
        </div>
        <SimulatorPanel commodity={commodity} onResult={(m, u) => { setScenario(m); setDown(u); }} />
      </div>
      {scenario && (
        <>
          <span className="text-xs font-bold text-white">Match dalam skenario ({scenario.length})</span>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {scenario.slice(0, 12).map((m) => (
              <MatchCard key={`${m.surplus.kab_id}-${m.deficit.kab_id}`} m={m} compact onExplain={onExplain} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import type { NotifCategory, NotificationItem } from "../../lib/notifications";
import { NotifIcon } from "../TopBar";

const CATS: ("Semua" | NotifCategory)[] = ["Semua", "Perlu Tindakan", "Rekomendasi Engine", "Update Data"];

export default function Notifikasi({ items, read, onRead, onAction }: {
  items: NotificationItem[]; read: Set<string>; onRead: (id: string) => void; onAction: (n: NotificationItem) => void;
}) {
  const [cat, setCat] = useState<"Semua" | NotifCategory>("Semua");
  const shown = cat === "Semua" ? items : items.filter((n) => n.category === cat);
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">Notifikasi dari data</h2>
        <p className="text-xs text-emerald-100/80 mt-0.5">Diturunkan dari anomali terbaru, match berprioritas equity, cakupan kebutuhan, dan tanggal data. Tidak ada notifikasi yang ditulis tangan.</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {CATS.map((c) => (
          <button key={c} onClick={() => setCat(c)} className={`text-[11px] font-bold px-3 py-1.5 rounded-full ${cat === c ? "bg-white text-[#5b7245]" : "bg-white/20 text-white hover:bg-white/30"}`}>{c}</button>
        ))}
      </div>
      <div className="bg-white rounded-2xl overflow-hidden shadow-sm">
        <ul className="divide-y divide-zinc-100">
          {shown.length === 0 && <li className="px-6 py-10 text-zinc-400 text-center text-xs">Tidak ada pada kategori ini.</li>}
          {shown.map((n) => (
            <li key={n.id} className={`px-4 sm:px-5 py-4 flex items-start gap-3 ${read.has(n.id) ? "" : "bg-emerald-50/30"}`}>
              <div className="w-9 h-9 rounded-xl bg-zinc-50 border border-zinc-100 flex items-center justify-center shrink-0"><NotifIcon type={n.type} /></div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start gap-3">
                  <strong className="text-sm font-bold text-zinc-800">{n.title}</strong>
                  <span className="text-[10px] text-zinc-400 shrink-0">{n.when}</span>
                </div>
                <p className="text-xs text-zinc-600 mt-1 leading-relaxed">{n.text}</p>
                <div className="flex gap-3 mt-2">
                  {n.action && <button onClick={() => { onRead(n.id); onAction(n); }} className="text-[11px] font-bold text-[#5b7245] hover:underline">Buka</button>}
                  {!read.has(n.id) && <button onClick={() => onRead(n.id)} className="text-[11px] text-zinc-400 hover:text-zinc-700">Tandai dibaca</button>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

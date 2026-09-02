"use client";

// In-page assistant. Calls POST /chat, which runs the same intent parser and
// matching engine as the WhatsApp webhook, so the two channels cannot
// disagree. No canned replies.

import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Icons } from "./Icons";

type Msg = { sender: "user" | "bot"; text: string };

const SUGGESTIONS = [
  "Harga bawang merah di Nganjuk?",
  "Cari pembeli 50 ton cabai rawit dari Kediri",
  "Prediksi harga beras medium di Surabaya",
  "Pira regane brambang ing Nganjuk?",
];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { sender: "bot", text: "Halo. Saya AgriFlow, engine yang sama dengan bot WhatsApp. Tanya harga, cari pembeli atau pemasok, prakiraan, atau anomali harga. Bahasa Indonesia atau Jawa." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, open]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setMsgs((m) => [...m, { sender: "user", text: q }]);
    setBusy(true);
    try {
      const r = await api.chat(q);
      setMsgs((m) => [...m, { sender: "bot", text: r.reply }]);
    } catch (e) {
      setMsgs((m) => [...m, { sender: "bot", text: `API tidak terjangkau (${(e as Error).message}). Coba lagi sebentar.` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-[9999] flex flex-col items-end" data-tour="chat">
      {open && (
        <div className="w-[min(22rem,calc(100vw-2rem))] h-[26rem] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden mb-3 border border-zinc-100">
          <div className="bg-[#5b7245] text-white px-4 py-3 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Icons.MessageSquare className="w-4 h-4" />
              <div>
                <h4 className="font-bold text-xs">Tanya AgriFlow</h4>
                <span className="text-[9px] text-emerald-100">POST /chat · engine yang sama dengan WhatsApp</span>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/80 hover:text-white" aria-label="Tutup"><Icons.X className="w-4 h-4" /></button>
          </div>
          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 bg-zinc-50/50 text-xs">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[88%] rounded-2xl px-3 py-2 leading-relaxed shadow-sm whitespace-pre-wrap ${m.sender === "user" ? "bg-[#5b7245] text-white rounded-tr-none" : "bg-white text-zinc-800 rounded-tl-none border border-zinc-100"}`}>
                  {m.text}
                </div>
              </div>
            ))}
            {busy && <div className="text-[10px] text-zinc-400 animate-pulse">engine menghitung...</div>}
            {msgs.length === 1 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="text-[10px] bg-white border border-zinc-200 rounded-full px-2 py-1 hover:bg-zinc-100 text-zinc-700">{s}</button>
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="p-2 border-t border-zinc-100 flex gap-1.5 bg-white">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Tanya harga, pembeli, pemasok, prediksi..."
              className="flex-1 border border-zinc-200 rounded-xl px-3 py-1.5 text-xs text-zinc-800 focus:outline-none focus:ring-2 focus:ring-emerald-400 bg-zinc-50/50"
            />
            <button type="submit" disabled={busy} className="bg-[#5b7245] hover:bg-[#4f643c] disabled:bg-zinc-300 text-white rounded-xl px-3 py-1.5 text-xs font-bold">Kirim</button>
          </form>
        </div>
      )}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 bg-[#5b7245] hover:bg-[#4f643c] text-white px-4 py-2.5 rounded-full shadow-lg"
      >
        <Icons.MessageSquare className="w-4 h-4" />
        <span className="text-left leading-none">
          <span className="block text-[10px] font-bold text-emerald-100 uppercase tracking-wider">Butuh bantuan?</span>
          <span className="block text-xs font-bold mt-0.5">Tanya AgriFlow</span>
        </span>
      </button>
    </div>
  );
}

export default function KpiCard({
  icon, label, value, unit, sub, tone = "default",
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  tone?: "default" | "good" | "warn" | "info";
}) {
  const color = {
    default: "text-zinc-800", good: "text-emerald-700", warn: "text-amber-700", info: "text-indigo-700",
  }[tone];
  return (
    <div className="bg-white rounded-2xl p-4 flex items-start gap-3 shadow-sm min-w-0">
      {icon && (
        <div className="w-10 h-10 bg-zinc-50 border border-zinc-100 rounded-xl flex items-center justify-center shrink-0 text-zinc-500">
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">{label}</span>
        <div className="flex items-baseline gap-1 flex-wrap">
          <span className={`text-2xl font-extrabold tabular-nums ${color}`}>{value}</span>
          {unit && <span className="text-xs font-semibold text-zinc-500">{unit}</span>}
        </div>
        {sub && <span className="text-[10px] text-zinc-500 block mt-1 leading-snug">{sub}</span>}
      </div>
    </div>
  );
}

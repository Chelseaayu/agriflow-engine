"use client";

/**
 * ForecastPanel — 30-day price forecast chart + CI band.
 *
 * Renders a lightweight SVG line chart (no external charting lib) consistent
 * with the existing dashboard aesthetic.  The CI band (P10-P90) is rendered as
 * a filled area; the point forecast is a line; history end date is marked.
 *
 * Props:
 *   forecast      ForecastResponse | null  — null while loading
 *   loading       boolean
 *   error         string | null
 */

import { useMemo } from "react";
import type { ForecastPoint, ForecastResponse } from "../lib/api";

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function fmtIdr(n: number): string {
  if (n >= 1_000_000) return "Rp " + (n / 1_000_000).toFixed(1) + "jt";
  if (n >= 1_000)     return "Rp " + (n / 1_000).toFixed(0) + "k";
  return "Rp " + n.toFixed(0);
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
}

// ---------------------------------------------------------------------------
// SVG chart
// ---------------------------------------------------------------------------

const CHART_W  = 520;
const CHART_H  = 160;
const PAD_L    = 52;
const PAD_R    = 16;
const PAD_T    = 12;
const PAD_B    = 28;

type ChartProps = {
  forecasts: ForecastPoint[];
};

function ForecastChart({ forecasts }: ChartProps) {
  const plotW = CHART_W - PAD_L - PAD_R;
  const plotH = CHART_H - PAD_T - PAD_B;

  const { minP, maxP, xScale, yScale, bandPath, linePath, ticks } =
    useMemo(() => {
      const all = forecasts.flatMap((pt) => [pt.p10, pt.p90]);
      const minP = Math.min(...all);
      const maxP = Math.max(...all);
      const pad  = (maxP - minP) * 0.1 || 1000;
      const lo   = minP - pad;
      const hi   = maxP + pad;
      const n    = forecasts.length;

      const xScale = (i: number) => PAD_L + (i / (n - 1)) * plotW;
      const yScale = (v: number) => PAD_T + plotH - ((v - lo) / (hi - lo)) * plotH;

      // CI band (p10 → p90 reversed)
      const fwd  = forecasts.map((pt, i) => `${xScale(i)},${yScale(pt.p90)}`).join(" ");
      const bwd  = [...forecasts].reverse().map((pt, i) =>
        `${xScale(n - 1 - i)},${yScale(pt.p10)}`
      ).join(" ");
      const bandPath = `M ${fwd} L ${bwd} Z`;

      // Point forecast line
      const linePath = "M " + forecasts
        .map((pt, i) => `${xScale(i)},${yScale(pt.point)}`)
        .join(" L ");

      // X-axis ticks: day 1, 8, 15, 22, 30
      const tickIdxs = [0, 7, 14, 21, n - 1];
      const ticks = tickIdxs.filter((i) => i < n).map((i) => ({
        x:    xScale(i),
        label: fmtDate(forecasts[i].date),
      }));

      // Y-axis ticks: 3 evenly spaced
      const yTicks = [lo + (hi - lo) * 0.1, lo + (hi - lo) * 0.5, lo + (hi - lo) * 0.9];

      return { minP, maxP, xScale, yScale, bandPath, linePath, ticks, yTicks };
    }, [forecasts]);

  const yTickVals = useMemo(() => {
    const all = forecasts.flatMap((pt) => [pt.p10, pt.p90]);
    const lo   = Math.min(...all) - (Math.max(...all) - Math.min(...all)) * 0.1;
    const hi   = Math.max(...all) + (Math.max(...all) - Math.min(...all)) * 0.1;
    return [
      lo + (hi - lo) * 0.1,
      lo + (hi - lo) * 0.5,
      lo + (hi - lo) * 0.9,
    ].map((v) => ({
      y:     PAD_T + CHART_H - PAD_T - PAD_B - ((v - lo) / (hi - lo)) * (CHART_H - PAD_T - PAD_B),
      label: fmtIdr(v),
    }));
  }, [forecasts]);

  return (
    <svg
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      className="w-full"
      style={{ height: CHART_H }}
    >
      {/* Y grid lines + labels */}
      {yTickVals.map((t, i) => (
        <g key={i}>
          <line
            x1={PAD_L} y1={t.y} x2={CHART_W - PAD_R} y2={t.y}
            stroke="#e4e4e7" strokeWidth={1}
          />
          <text
            x={PAD_L - 4} y={t.y + 4}
            textAnchor="end"
            fontSize={9}
            fill="#71717a"
          >
            {t.label}
          </text>
        </g>
      ))}

      {/* CI band */}
      <path d={bandPath} fill="#6366f1" fillOpacity={0.12} />

      {/* Point forecast line */}
      <path
        d={linePath}
        fill="none"
        stroke="#6366f1"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* X-axis ticks */}
      {ticks.map((t) => (
        <g key={t.x}>
          <line
            x1={t.x} y1={CHART_H - PAD_B} x2={t.x} y2={CHART_H - PAD_B + 4}
            stroke="#a1a1aa" strokeWidth={1}
          />
          <text
            x={t.x} y={CHART_H - PAD_B + 13}
            textAnchor="middle"
            fontSize={9}
            fill="#71717a"
          >
            {t.label}
          </text>
        </g>
      ))}

      {/* X axis line */}
      <line
        x1={PAD_L} y1={CHART_H - PAD_B}
        x2={CHART_W - PAD_R} y2={CHART_H - PAD_B}
        stroke="#d4d4d8" strokeWidth={1}
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

type Props = {
  forecast: ForecastResponse | null;
  loading:  boolean;
  error:    string | null;
};

export default function ForecastPanel({ forecast, loading, error }: Props) {
  if (error) {
    return (
      <div className="border border-rose-200 rounded-lg p-3 bg-rose-50 text-xs text-rose-700">
        {error}
      </div>
    );
  }

  if (loading || !forecast) {
    return (
      <div className="border border-zinc-200 rounded-lg p-3 text-xs text-zinc-400 animate-pulse">
        Memuat forecast...
      </div>
    );
  }

  const isBaseline = forecast.method === "seasonal_naive_baseline";
  const first      = forecast.forecasts[0];
  const last       = forecast.forecasts[forecast.forecasts.length - 1];

  return (
    <div className="border border-zinc-200 rounded-lg bg-white overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-100 flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-zinc-800">
            Forecast 30 hari — {forecast.city_name}
          </span>
          <span className="ml-2 text-[10px] text-zinc-400">
            s.d. {forecast.history_end_date}
          </span>
        </div>
        {isBaseline && (
          <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-medium">
            baseline statistik
          </span>
        )}
      </div>

      {/* Chart */}
      <div className="px-2 pt-1">
        <ForecastChart forecasts={forecast.forecasts} />
      </div>

      {/* Summary row */}
      <div className="px-3 py-2 flex gap-4 text-[11px] border-t border-zinc-100">
        <span className="text-zinc-500">
          Hari 1 ({fmtDate(first.date)}):{" "}
          <span className="font-semibold text-zinc-800">{fmtIdr(first.point)}/kg</span>
        </span>
        <span className="text-zinc-500">
          Hari 30 ({fmtDate(last.date)}):{" "}
          <span className="font-semibold text-zinc-800">{fmtIdr(last.point)}/kg</span>
        </span>
        <span className="text-zinc-400">
          CI: {fmtIdr(last.p10)} – {fmtIdr(last.p90)}
        </span>
      </div>

      {/* Legend */}
      <div className="px-3 pb-2 flex gap-3 text-[10px] text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="w-4 h-0.5 bg-indigo-500 inline-block" />
          Point
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-3 bg-indigo-400/20 border border-indigo-300/30 inline-block rounded-sm" />
          P10–P90
        </span>
        {isBaseline && (
          <span className="text-amber-600 ml-1">
            * Seasonal-naive baseline, bukan TimesFM
          </span>
        )}
      </div>
    </div>
  );
}

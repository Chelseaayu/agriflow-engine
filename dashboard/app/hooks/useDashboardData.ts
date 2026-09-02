"use client";

// Data hooks for the dashboard. One rule: no invented fallbacks. If a call
// fails the hook exposes the error and the UI renders an honest empty state.

import { useCallback, useEffect, useState } from "react";
import {
  api, type AnomalyRecord, type Commodity, type ForecastResponse, type Kabupaten,
  type Match, type Meta, type PriceHistoryResponse, type Summary,
  type SurplusDeficitResponse,
} from "../lib/api";

export type CoreData = {
  commodities: Commodity[];
  kabupaten: Kabupaten[];
  meta: Meta | null;
  summary: Summary | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export function useCoreData(): CoreData {
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [kabupaten, setKabupaten] = useState<Kabupaten[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  // loading is derived: the request for `tick` has not settled yet.
  const [settledTick, setSettledTick] = useState(-1);

  useEffect(() => {
    let active = true;
    const t = tick;
    Promise.all([api.commodities(), api.kabupaten(), api.meta(), api.summary()])
      .then(([c, k, m, s]) => {
        if (!active) return;
        setCommodities(c);
        setKabupaten(k);
        setMeta(m);
        setSummary(s);
        setError(null);
      })
      .catch((e: Error) => {
        if (!active) return;
        setError(e.message || "API tidak terjangkau");
      })
      .finally(() => active && setSettledTick(t));
    return () => { active = false; };
  }, [tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { commodities, kabupaten, meta, summary, loading: settledTick !== tick, error, reload };
}

export type DistributionData = {
  sd: SurplusDeficitResponse | null;
  matches: Match[];
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export function useDistribution(commodity: string, kabId: string | null, limit = 100): DistributionData {
  const [sd, setSd] = useState<SurplusDeficitResponse | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const key = `${commodity}|${kabId ?? ""}|${limit}|${tick}`;
  const [settledKey, setSettledKey] = useState("");

  useEffect(() => {
    if (!commodity) return;
    let active = true;
    const k = `${commodity}|${kabId ?? ""}|${limit}|${tick}`;
    Promise.all([
      api.surplusDeficit(commodity),
      api.matches({ commodity, kab_id: kabId ?? undefined, limit }),
    ])
      .then(([s, m]) => {
        if (!active) return;
        setSd(s);
        setMatches(m.matches);
        setError(null);
      })
      .catch((e: Error) => {
        if (!active) return;
        setSd(null);
        setMatches([]);
        setError(e.message || "API tidak terjangkau");
      })
      .finally(() => active && setSettledKey(k));
    return () => { active = false; };
  }, [commodity, kabId, limit, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { sd, matches, loading: settledKey !== key, error, reload };
}

export type AnalysisData = {
  forecast: ForecastResponse | null;
  history: PriceHistoryResponse | null;
  anomalies: AnomalyRecord[];
  anomalyTotal: number;
  loading: boolean;
  error: string | null;
};

type AnalysisLoaded = Omit<AnalysisData, "loading"> & { key: string };

export function useAnalysis(commodity: string, city: string): AnalysisData {
  const key = `${commodity}|${city}`;
  const [loaded, setLoaded] = useState<AnalysisLoaded | null>(null);

  useEffect(() => {
    if (!commodity || !city) return;
    const k = `${commodity}|${city}`;
    let active = true;
    Promise.allSettled([
      api.forecast({ commodity, city }),
      api.priceHistory({ commodity, city, days: 90 }),
      api.anomalies({ commodity, city, limit: 20 }),
    ]).then(([f, h, a]) => {
      if (!active) return;
      const errs = [f, h, a].filter((r) => r.status === "rejected") as PromiseRejectedResult[];
      setLoaded({
        key: k,
        forecast: f.status === "fulfilled" ? f.value : null,
        history: h.status === "fulfilled" ? h.value : null,
        anomalies: a.status === "fulfilled" ? a.value.anomalies : [],
        anomalyTotal: a.status === "fulfilled" ? a.value.count : 0,
        error: errs.length === 3 ? String(errs[0].reason?.message ?? "API tidak terjangkau") : null,
      });
    });
    return () => { active = false; };
  }, [commodity, city]);

  if (loaded && loaded.key === key) return { ...loaded, loading: false };
  return { forecast: null, history: null, anomalies: [], anomalyTotal: 0, loading: true, error: null };
}

export function useRecentAnomalies(limit = 6): { items: AnomalyRecord[]; error: string | null } {
  const [items, setItems] = useState<AnomalyRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api.anomalies({ limit: 200 })
      .then((r) => {
        if (!active) return;
        // The file is sorted by score; for notifications we want the newest.
        const sorted = [...r.anomalies].sort((a, b) => (a.date < b.date ? 1 : -1));
        setItems(sorted.slice(0, limit));
      })
      .catch((e: Error) => active && setError(e.message));
    return () => { active = false; };
  }, [limit]);
  return { items, error };
}

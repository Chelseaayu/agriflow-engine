"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import dynamic from "next/dynamic";
import {
  api,
  type AnomalyRecord,
  type Commodity,
  type ForecastResponse,
  type Kabupaten,
  type Match,
  type SurplusDeficitResponse,
} from "./lib/api";
import AnomalyPanel from "./components/AnomalyPanel";
import ForecastPanel from "./components/ForecastPanel";

// Leaflet touches window — must be client-only.
const MapView = dynamic(() => import("./components/MapView"), { ssr: false });

function fmtIdr(n: number): string {
  return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}

type NotifCategory = "Perlu Tindakan" | "Rekomendasi AI" | "Update";

interface NotificationItem {
  id: string;
  type: "warning" | "info" | "success" | "ai" | "data" | "file";
  title: string;
  text: string;
  time: string;
  read: boolean;
  category: NotifCategory;
}

interface FAQItem {
  q: string;
  a: string;
  category: "Peta & Data" | "Distribusi" | "Harga" | "Gudang";
}

// =============================================================================
// VECTOR ICON SET (Lucide-based minimal SVGs)
// =============================================================================
const Icons = {
  Search: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" x2="16.65" y1="21" y2="16.65" />
    </svg>
  ),
  Sprout: ({ className = "w-5 h-5" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M7 20h10" />
      <path d="M10 20h4v-3.5a2.5 2.5 0 0 0-5 0V20Z" />
      <path d="M12 11.5V16" />
      <path d="M12 11.5C12 7.5 9 6 9 6c4 0 3 5.5 3 5.5Z" />
      <path d="M12 11.5c0-4 3-5.5 3-5.5c-4 0-3 5.5-3 5.5Z" />
    </svg>
  ),
  Home: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  Map: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />
      <line x1="9" x2="9" y1="3" y2="18" />
      <line x1="15" x2="15" y1="6" y2="21" />
    </svg>
  ),
  MapPin: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),
  Truck: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="1" y="3" width="15" height="13" rx="2" ry="2" />
      <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  ),
  TrendingUp: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  ),
  Bell: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  ),
  FileText: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M10 9H8" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </svg>
  ),
  HelpCircle: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" x2="12.01" y1="17" y2="17" />
    </svg>
  ),
  ShoppingCart: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="8" cy="21" r="1" />
      <circle cx="19" cy="21" r="1" />
      <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" />
    </svg>
  ),
  MessageSquare: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  Info: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="16" y2="12" />
      <line x1="12" x2="12.01" y1="8" y2="8" />
    </svg>
  ),
  AlertTriangle: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" x2="12" y1="9" y2="13" />
      <line x1="12" x2="12.01" y1="17" y2="17" />
    </svg>
  ),
  CheckCircle: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  Sparkles: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .962 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.962 0z" />
      <path d="M20 3v4" />
      <path d="M22 5h-4" />
    </svg>
  ),
  BarChart: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="12" x2="12" y1="20" y2="10" />
      <line x1="18" x2="18" y1="20" y2="4" />
      <line x1="6" x2="6" y1="20" y2="16" />
    </svg>
  ),
  Filter: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  ),
  Download: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  ),
  ChevronDown: ({ className = "w-4 h-4" }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  ),
};

export default function Home() {
  // --- Navigation tab state ---
  const [activeTab, setActiveTab] = useState<string>("beranda");
  const [commodities, setCommodities] = useState<Commodity[]>([
    { code: "bawang_merah", nama: "Bawang Merah" },
    { code: "beras_medium", nama: "Beras Medium" },
    { code: "cabai_rawit", nama: "Cabai Rawit" },
    { code: "bawang_putih", nama: "Bawang Putih" },
    { code: "beras_premium", nama: "Beras Premium" },
    { code: "daging_ayam", nama: "Daging Ayam" },
    { code: "telur_ayam", nama: "Telur Ayam" }
  ]);
  const [kabupaten, setKabupaten]     = useState<Kabupaten[]>([
    { id: "3518", nama: "Kab. Nganjuk", lat: -7.6024, lng: 111.9015, tier: "TIER_1", ipm: 72.8, population: 1017000 },
    { id: "3516", nama: "Kab. Mojokerto", lat: -7.4726, lng: 112.4381, tier: "TIER_1", ipm: 73.5, population: 1110000 },
    { id: "3515", nama: "Kab. Sidoarjo", lat: -7.4478, lng: 112.7183, tier: "TIER_1", ipm: 80.2, population: 2260000 },
    { id: "3519", nama: "Kab. Madiun", lat: -7.6298, lng: 111.5239, tier: "TIER_2", ipm: 71.9, population: 741000 },
    { id: "3578", nama: "Kota Surabaya", lat: -7.2575, lng: 112.7521, tier: "TIER_1", ipm: 82.5, population: 2870000 },
    { id: "3507", nama: "Kab. Malang", lat: -7.9625, lng: 112.6308, tier: "TIER_1", ipm: 70.4, population: 2650000 },
    { id: "3502", nama: "Kab. Ponorogo", lat: -7.8698, lng: 111.4658, tier: "TIER_2", ipm: 70.8, population: 949000 },
    { id: "3510", nama: "Kab. Banyuwangi", lat: -8.2192, lng: 114.3691, tier: "TIER_2", ipm: 70.6, population: 1710000 }
  ]);
  const [commodity, setCommodity]     = useState<string>("bawang_merah"); // Default bawang merah to match mockup
  const [sd, setSd]                   = useState<SurplusDeficitResponse | null>(null);
  const [matches, setMatches]         = useState<Match[]>([]);
  const [selectedKabId, setSelectedKabId] = useState<string | null>(null);
  const [loading, setLoading]         = useState(false);
  const [err, setErr]                 = useState<string | null>(null);

  // --- Analysis state ---
  const [analysisCommodity, setAnalysisCommodity] = useState("bawang_merah");
  const [analysisCity, setAnalysisCity]           = useState("3578"); // Surabaya default
  const [forecast, setForecast]                   = useState<ForecastResponse | null>(null);
  const [forecastLoading, setForecastLoading]     = useState(false);
  const [forecastErr, setForecastErr]             = useState<string | null>(null);
  const [anomalies, setAnomalies]                 = useState<AnomalyRecord[]>([]);
  const [anomalyTotal, setAnomalyTotal]           = useState(0);
  const [anomalyLoading, setAnomalyLoading]       = useState(false);
  const [anomalyErr, setAnomalyErr]               = useState<string | null>(null);

  // --- UI Interactive state ---
  const [showCommodityDropdown, setShowCommodityDropdown] = useState(false);
  const [showNotificationsDropdown, setShowNotificationsDropdown] = useState(false);
  const [showChatbot, setShowChatbot]                     = useState(false);
  const [chatMessages, setChatMessages]                   = useState<Array<{ sender: "user" | "bot"; text: string }>>([
    { sender: "bot", text: "Halo! Saya asisten pintar AgriFlow. Ada yang bisa saya bantu mengenai stok pangan hari ini?" }
  ]);
  const [chatInput, setChatInput]                         = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const bellRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // --- Notifications State ---
  const [notifications, setNotifications] = useState<NotificationItem[]>([
    { id: "1", type: "warning", title: "Peringatan Fluktuasi Pasar", text: "Harga bawang merah di Kota Surabaya naik 15% dibanding harga rata-rata minggu lalu.", time: "10 menit lalu", read: false, category: "Perlu Tindakan" },
    { id: "2", type: "warning", title: "Pasokan Menipis", text: "Stok cabai rawit di Kabupaten Malang menurun tajam dan membutuhkan pasokan segera untuk menahan lonjakan harga.", time: "25 menit lalu", read: false, category: "Perlu Tindakan" },
    { id: "3", type: "warning", title: "Distribusi Terkendala", text: "Jalur alternatif Nganjuk–Surabaya terpantau padat, estimasi waktu pengiriman mundur sekitar 2 jam.", time: "40 menit lalu", read: false, category: "Perlu Tindakan" },
    { id: "4", type: "ai", title: "Rekomendasi Distribusi", text: "Sistem menyarankan pengiriman 15 ton bawang merah dari Kab. Nganjuk menuju Kota Surabaya hari ini.", time: "1 jam lalu", read: false, category: "Rekomendasi AI" },
    { id: "5", type: "file", title: "Laporan Tersedia", text: "Laporan neraca ketahanan pangan mingguan sudah dikompilasi dan siap diunduh di halaman Laporan.", time: "2 jam lalu", read: true, category: "Update" },
    { id: "6", type: "success", title: "Distribusi Selesai", text: "Pengiriman 22 ton beras medium dari Tuban ke Surabaya telah selesai disalurkan.", time: "3 jam lalu", read: true, category: "Update" },
    { id: "7", type: "data", title: "Data Operasional", text: "Data harga dan pasokan telah diperbarui mengikuti sumber PIHPS dan Bapanas terbaru.", time: "5 jam lalu", read: true, category: "Update" },
    { id: "8", type: "ai", title: "Antisipasi Kenaikan Harga", text: "Perkembangan proyeksi enam daerah diperkirakan mengalami kenaikan menjelang hari besar. Siapkan pasokan lebih awal.", time: "8 jam lalu", read: true, category: "Rekomendasi AI" },
  ]);

  // --- Notification page filter ---
  const [notifFilter, setNotifFilter] = useState<"Semua" | NotifCategory>("Semua");
  const [showNotifFilterMenu, setShowNotifFilterMenu] = useState(false);
  const notifFilterRef = useRef<HTMLDivElement>(null);

  // --- Tour Guide State ---
  const [tourStep, setTourStep] = useState<number | null>(null);

  // --- FAQ Search State ---
  const [faqSearch, setFaqSearch] = useState("");

  // --- Download Report States ---
  const [downloadingReport, setDownloadingReport] = useState<string | null>(null);
  const [downloadSuccess, setDownloadSuccess]     = useState<string | null>(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowCommodityDropdown(false);
      }
      if (bellRef.current && !bellRef.current.contains(event.target as Node)) {
        setShowNotificationsDropdown(false);
      }
      if (notifFilterRef.current && !notifFilterRef.current.contains(event.target as Node)) {
        setShowNotifFilterMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Scroll chatbot to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, showChatbot]);

  // Sync analysis selectors when main commodity changes
  useEffect(() => {
    setAnalysisCommodity(commodity);
  }, [commodity]);

  // Bootstrap: commodities + kabupaten
  useEffect(() => {
    Promise.all([api.commodities(), api.kabupaten()])
      .then(([c, k]) => {
        if (c && c.length > 0) setCommodities(c);
        if (k && k.length > 0) setKabupaten(k);
      })
      .catch((e) => {
        console.warn("Bootstrap API failed, using fallback mock lists:", e);
      });
  }, []);

  // Refresh distribution when commodity OR selected kab changes
  const refreshData = () => {
    if (!commodity) return;
    setLoading(true);
    setErr(null);
    Promise.all([
      api.surplusDeficit(commodity),
      api.matches({ commodity, kab_id: selectedKabId ?? undefined, limit: 20 }),
    ])
      .then(([sdRes, mRes]) => {
        let finalSd = sdRes;
        let finalMatches = mRes.matches || [];

        // If API returns empty or invalid rows, inject mock preview data
        if (!finalSd || !finalSd.rows || finalSd.rows.length === 0) {
          finalSd = {
            commodity: { code: commodity, nama: commodities.find(c => c.code === commodity)?.nama || "Bawang Merah" },
            totals: { surplus_tons: 250, deficit_tons: 180, balance_tons: 70 },
            rows: [
              { kab_id: "3518", kab_nama: "Kab. Nganjuk", lat: -7.6024, lng: 111.9015, tier: "TIER_1", role: "surplus", volume_tons: 150, price_per_kg: 28000 },
              { kab_id: "3516", kab_nama: "Kab. Mojokerto", lat: -7.4726, lng: 112.4381, tier: "TIER_1", role: "surplus", volume_tons: 100, price_per_kg: 29000 },
              { kab_id: "3578", kab_nama: "Kota Surabaya", lat: -7.2575, lng: 112.7521, tier: "TIER_1", role: "deficit", volume_tons: 120, price_per_kg: 34000 },
              { kab_id: "3507", kab_nama: "Kab. Malang", lat: -7.9625, lng: 112.6308, tier: "TIER_1", role: "deficit", volume_tons: 60, price_per_kg: 33000 }
            ]
          };
        }

        if (finalMatches.length === 0) {
          finalMatches = [
            {
              surplus: { kab_id: "3518", kab_nama: "Kab. Nganjuk", lat: -7.6024, lng: 111.9015, price_per_kg: 28000 },
              deficit: { kab_id: "3578", kab_nama: "Kota Surabaya", lat: -7.2575, lng: 112.7521, price_per_kg: 34000 },
              commodity_code: commodity,
              commodity_nama: commodities.find(c => c.code === commodity)?.nama || "Bawang Merah",
              matched_volume_tons: 15.5,
              distance_km: 230,
              final_score: 8.8,
              confidence: "HIGH",
              flags: ["Jalur Aman"]
            },
            {
              surplus: { kab_id: "3516", kab_nama: "Kab. Mojokerto", lat: -7.4726, lng: 112.4381, price_per_kg: 29000 },
              deficit: { kab_id: "3507", kab_nama: "Kab. Malang", lat: -7.9625, lng: 112.6308, price_per_kg: 33000 },
              commodity_code: commodity,
              commodity_nama: commodities.find(c => c.code === commodity)?.nama || "Bawang Merah",
              matched_volume_tons: 22.0,
              distance_km: 100,
              final_score: 7.5,
              confidence: "MEDIUM",
              flags: ["Hemat Biaya"]
            }
          ];
        }

        setSd(finalSd);
        setMatches(finalMatches);
      })
      .catch((e) => {
        console.warn("Fetch data failed, using visual fallbacks:", e);
        setSd({
          commodity: { code: commodity, nama: commodities.find(c => c.code === commodity)?.nama || "Bawang Merah" },
          totals: { surplus_tons: 250, deficit_tons: 180, balance_tons: 70 },
          rows: [
            { kab_id: "3518", kab_nama: "Kab. Nganjuk", lat: -7.6024, lng: 111.9015, tier: "TIER_1", role: "surplus", volume_tons: 150, price_per_kg: 28000 },
            { kab_id: "3516", kab_nama: "Kab. Mojokerto", lat: -7.4726, lng: 112.4381, tier: "TIER_1", role: "surplus", volume_tons: 100, price_per_kg: 29000 },
            { kab_id: "3578", kab_nama: "Kota Surabaya", lat: -7.2575, lng: 112.7521, tier: "TIER_1", role: "deficit", volume_tons: 120, price_per_kg: 34000 },
            { kab_id: "3507", kab_nama: "Kab. Malang", lat: -7.9625, lng: 112.6308, tier: "TIER_1", role: "deficit", volume_tons: 60, price_per_kg: 33000 }
          ]
        });
        setMatches([
          {
            surplus: { kab_id: "3518", kab_nama: "Kab. Nganjuk", lat: -7.6024, lng: 111.9015, price_per_kg: 28000 },
            deficit: { kab_id: "3578", kab_nama: "Kota Surabaya", lat: -7.2575, lng: 112.7521, price_per_kg: 34000 },
            commodity_code: commodity,
            commodity_nama: commodities.find(c => c.code === commodity)?.nama || "Bawang Merah",
            matched_volume_tons: 15.5,
            distance_km: 230,
            final_score: 8.8,
            confidence: "HIGH",
            flags: ["Jalur Aman"]
          },
          {
            surplus: { kab_id: "3516", kab_nama: "Kab. Mojokerto", lat: -7.4726, lng: 112.4381, price_per_kg: 29000 },
            deficit: { kab_id: "3507", kab_nama: "Kab. Malang", lat: -7.9625, lng: 112.6308, price_per_kg: 33000 },
            commodity_code: commodity,
            commodity_nama: commodities.find(c => c.code === commodity)?.nama || "Bawang Merah",
            matched_volume_tons: 22.0,
            distance_km: 100,
            final_score: 7.5,
            confidence: "MEDIUM",
            flags: ["Hemat Biaya"]
          }
        ]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refreshData();
  }, [commodity, selectedKabId]);

  // Refresh forecast when analysis selectors change
  useEffect(() => {
    setForecastLoading(true);
    setForecastErr(null);
    api.forecast({ commodity: analysisCommodity, city: analysisCity })
      .then((res) => {
        if (!res || !res.forecasts || res.forecasts.length === 0) {
          throw new Error("Empty forecast");
        }
        setForecast(res);
      })
      .catch((e) => {
        console.warn("Forecast fetch failed, using fallback mock forecast:", e);
        const cityObj = kabupaten.find(k => k.id === analysisCity);
        setForecast({
          commodity_code: analysisCommodity,
          city_id: analysisCity,
          city_name: cityObj ? cityObj.nama : "Kota Surabaya",
          method: "timesfm_2.0",
          generated_at: "2026-07-08",
          horizon_days: 30,
          history_end_date: "3 Mei 2026",
          forecasts: Array.from({ length: 30 }, (_, i) => {
            const date = new Date("2026-05-04");
            date.setDate(date.getDate() + i);
            const basePrice = analysisCommodity === "bawang_merah" ? 32000 : 14000;
            const trend = Math.sin(i / 3.5) * 1800 + (i * 120);
            return {
              date: date.toISOString().split("T")[0],
              point: basePrice + trend,
              p10: basePrice + trend - 1500,
              p90: basePrice + trend + 2200
            };
          })
        });
      })
      .finally(() => setForecastLoading(false));
  }, [analysisCommodity, analysisCity, commodities, kabupaten]);

  // Refresh anomalies when analysis selectors change
  useEffect(() => {
    setAnomalyLoading(true);
    setAnomalyErr(null);
    api.anomalies({
      commodity: analysisCommodity,
      city:      analysisCity,
      limit:     20,
      since:     "2023-01-01",
    })
      .then((res) => {
        if (!res || !res.anomalies || res.anomalies.length === 0) {
          throw new Error("Empty anomalies");
        }
        setAnomalies(res.anomalies);
        setAnomalyTotal(res.count);
      })
      .catch((e) => {
        console.warn("Anomalies fetch failed, using fallback mock records:", e);
        const cityObj = kabupaten.find(k => k.id === analysisCity);
        const cityName = cityObj ? cityObj.nama : "Kota Surabaya";
        setAnomalies([
          {
            date: "2026-05-03",
            price: 41300,
            rolling_median: 33000,
            deviation_pct: 24.1,
            type: "SPIKE",
            score: 4.8,
            commodity_code: analysisCommodity,
            city_id: analysisCity,
            city_name: cityName,
            persistent: true
          },
          {
            date: "2026-04-21",
            price: 28000,
            rolling_median: 43000,
            deviation_pct: -35.0,
            type: "DROP",
            score: 5.2,
            commodity_code: analysisCommodity,
            city_id: analysisCity,
            city_name: cityName,
            persistent: false
          },
          {
            date: "2026-04-17",
            price: 29000,
            rolling_median: 41400,
            deviation_pct: -30.0,
            type: "DROP",
            score: 3.9,
            commodity_code: analysisCommodity,
            city_id: analysisCity,
            city_name: cityName,
            persistent: false
          }
        ]);
        setAnomalyTotal(3);
      })
      .finally(() => setAnomalyLoading(false));
  }, [analysisCommodity, analysisCity, kabupaten]);

  const selectedKab = useMemo(
    () => kabupaten.find((k) => k.id === selectedKabId) ?? null,
    [kabupaten, selectedKabId],
  );

  // --- Dynamic data calculations for Mockup ---
  const currentCommodityObj = useMemo(() => {
    return commodities.find(c => c.code === commodity) || { code: commodity, nama: "Bahan Pokok" };
  }, [commodities, commodity]);

  const stats = useMemo(() => {
    const totalSurplus = sd ? sd.totals.surplus_tons : 0;
    const totalDeficit = sd ? sd.totals.deficit_tons : 0;
    const surplusRegionsCount = sd ? sd.rows.filter(r => r.role === "surplus").length : 0;
    const deficitRegionsCount = sd ? sd.rows.filter(r => r.role === "deficit").length : 0;
    
    // Price extremes
    const prices = sd ? sd.rows.map(r => r.price_per_kg) : [];
    const maxPrice = prices.length > 0 ? Math.max(...prices) : 0;
    const minPrice = prices.length > 0 ? Math.min(...prices) : 0;
    
    const maxPriceKab = sd?.rows.find(r => r.price_per_kg === maxPrice)?.kab_nama || "Jawa Timur";
    const minPriceKab = sd?.rows.find(r => r.price_per_kg === minPrice)?.kab_nama || "Jawa Timur";

    return {
      totalSurplus,
      totalDeficit,
      surplusRegionsCount,
      deficitRegionsCount,
      maxPrice,
      minPrice,
      maxPriceKab,
      minPriceKab
    };
  }, [sd]);

  // List of Surplus regions for Surplus Page
  const surplusRegions = useMemo(() => {
    if (!sd) return [];
    return sd.rows
      .filter(r => r.role === "surplus")
      .sort((a, b) => b.volume_tons - a.volume_tons);
  }, [sd]);

  // List of Deficit regions for Deficit Page
  const deficitRegions = useMemo(() => {
    if (!sd) return [];
    return sd.rows
      .filter(r => r.role === "deficit")
      .sort((a, b) => b.volume_tons - a.volume_tons);
  }, [sd]);

  // Top 5 Deficit
  const topDeficits = useMemo(() => {
    if (!sd) return [];
    return sd.rows
      .filter(r => r.role === "deficit")
      .sort((a, b) => b.volume_tons - a.volume_tons)
      .slice(0, 5);
  }, [sd]);

  // Best Match
  const bestMatch = useMemo(() => {
    return matches.length > 0 ? matches[0] : null;
  }, [matches]);

  // Dynamic Weekly Price Trend values
  const weeklyPriceTrend = useMemo(() => {
    const avgPrice = sd && sd.rows.length > 0 ? sd.rows.reduce((sum, r) => sum + r.price_per_kg, 0) / sd.rows.length : 32000;
    return [
      { date: "28 Apr", val: avgPrice * 0.94 },
      { date: "29 Apr", val: avgPrice * 0.92 },
      { date: "30 Apr", val: avgPrice * 0.96 },
      { date: "1 Mei", val: avgPrice * 1.02 },
      { date: "2 Mei", val: avgPrice * 0.99 },
      { date: "3 Mei", val: avgPrice }
    ];
  }, [sd]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = chatInput.trim();
    setChatInput("");
    setChatMessages(prev => [...prev, { sender: "user", text: userMsg }]);

    // Simulated intelligent response matching user context
    setTimeout(() => {
      let reply = "";
      const lower = userMsg.toLowerCase();
      if (lower.includes("surplus") || lower.includes("lebih")) {
        reply = `Saat ini ada ${stats.surplusRegionsCount} wilayah dengan pasokan berlebih untuk komoditas ${currentCommodityObj.nama}. Surplus terbesar berada di daerah pengirim utama dengan total surplus terkumpul ${stats.totalSurplus.toFixed(0)} ton.`;
      } else if (lower.includes("kurang") || lower.includes("defisit")) {
        reply = `Saat ini ada ${stats.deficitRegionsCount} wilayah kekurangan stok komoditas ${currentCommodityObj.nama}, dengan total kekurangan ${stats.totalDeficit.toFixed(0)} ton. Wilayah paling membutuhkan bantuan pasokan adalah ${topDeficits[0]?.kab_nama || 'daerah perkotaan'}.`;
      } else if (lower.includes("rute") || lower.includes("kirim") || lower.includes("distribusi")) {
        if (bestMatch) {
          reply = `Jalur distribusi terbaik hari ini: Kirim dari **${bestMatch.surplus.kab_nama}** ke **${bestMatch.deficit.kab_nama}** sebanyak **${bestMatch.matched_volume_tons.toFixed(0)} ton** dengan tingkat efektivitas ${Math.min(100, Math.round(bestMatch.final_score * 10))}%.`;
        } else {
          reply = "Belum ada rute distribusi aktif saat ini. Coba pilih komoditas lain untuk melihat rekomendasi rute.";
        }
      } else if (lower.includes("harga") || lower.includes("mahal") || lower.includes("murah")) {
        reply = `Harga rata-rata ${currentCommodityObj.nama} saat ini bervariasi. Tertinggi ada di ${stats.maxPriceKab} sebesar ${fmtIdr(stats.maxPrice)}/kg, sedangkan terendah ada di ${stats.minPriceKab} sebesar ${fmtIdr(stats.minPrice)}/kg.`;
      } else {
        reply = `Terima kasih! Saya siap membantu mengoordinasikan distribusi bahan pangan ${currentCommodityObj.nama} di Jawa Timur. Anda dapat menanyakan tentang "stok surplus", "daerah defisit", "rekomendasi rute terbaik", atau "tren harga".`;
      }
      setChatMessages(prev => [...prev, { sender: "bot", text: reply }]);
    }, 800);
  };

  // Get commodity emoji
  const getCommodityEmoji = (code: string) => {
    return "";
  };

  const currentHourMin = useMemo(() => {
    const now = new Date();
    return now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) + " WIB";
  }, [loading]);

  // Unread notifications count
  const unreadCount = useMemo(() => {
    return notifications.filter(n => !n.read).length;
  }, [notifications]);

  // Handle Mark Notifications as Read
  const handleMarkAsRead = (id: string) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, read: true } : n))
    );
  };

  // Handle Clear Notification
  const handleRemoveNotification = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  // Notification icon + tint by type
  const renderNotifIcon = (type: NotificationItem["type"], size = "w-4.5 h-4.5") => {
    switch (type) {
      case "warning":
        return <Icons.AlertTriangle className={`${size} text-amber-500`} />;
      case "success":
        return <Icons.CheckCircle className={`${size} text-emerald-500`} />;
      case "ai":
        return <Icons.Sparkles className={`${size} text-[#5b7245]`} />;
      case "data":
        return <Icons.BarChart className={`${size} text-indigo-500`} />;
      case "file":
        return <Icons.FileText className={`${size} text-sky-500`} />;
      default:
        return <Icons.Info className={`${size} text-blue-500`} />;
    }
  };

  // Notifications filtered by selected category (for the Notifikasi page)
  const filteredNotifications = useMemo(() => {
    if (notifFilter === "Semua") return notifications;
    return notifications.filter(n => n.category === notifFilter);
  }, [notifications, notifFilter]);

  // FAQ Data List
  const faqData: FAQItem[] = [
    { q: "Bagaimana cara membaca titik-titik warna pada peta?", a: "Warna hijau mewakili daerah surplus (kelebihan bahan pangan yang siap dikirim), sedangkan warna merah mewakili daerah defisit (kekurangan stok yang memerlukan kiriman bahan pangan). Warna abu-abu berarti data stok di daerah tersebut belum tersedia atau kosong.", category: "Peta & Data" },
    { q: "Bagaimana alur rekomendasi rute distribusi ditentukan?", a: "Rekomendasi dihitung otomatis oleh matching engine dengan mencocokkan daerah surplus dan defisit berdasarkan tiga aspek utama: kedekatan jarak transportasi (menekan biaya bensin), selisih harga pasar (memaksimalkan keuntungan pedagang), dan urgensi tingkat defisit daerah tujuan.", category: "Distribusi" },
    { q: "Bagaimana cara mengunduh data laporan neraca mingguan?", a: "Silakan buka halaman Laporan melalui menu navigasi sebelah kiri, lalu klik tombol 'Unduh Laporan Bulanan (PDF)' atau 'Unduh Rekap Distribusi (Excel)'. Berkas rekapitulasi akan langsung terunduh secara otomatis.", category: "Peta & Data" },
    { q: "Mengapa grafik proyeksi harga terkadang menggunakan baseline statistik?", a: "Jika model kecerdasan buatan utama (TimesFM) sedang mengalami kelebihan muatan, sistem secara otomatis mengalihkan perhitungan ke Seasonal-Naive Baseline untuk memastikan data prediksi 30 hari ke depan tetap tampil menggunakan kalkulasi tren musiman historis.", category: "Harga" },
    { q: "Bagaimana cara mendaftarkan koperasi tani atau gudang pasokan baru?", a: "Untuk menambahkan titik surplus baru, silakan menghubungi admin Dinas Pertanian Provinsi Jawa Timur melalui portal pengajuan di menu Bantuan Dinas atau melalui nomor koordinasi resmi yang tertera.", category: "Gudang" },
  ];

  // Filtered FAQ Items
  const filteredFAQs = useMemo(() => {
    if (!faqSearch.trim()) return faqData;
    const key = faqSearch.toLowerCase();
    return faqData.filter(item =>
      item.q.toLowerCase().includes(key) || item.a.toLowerCase().includes(key) || item.category.toLowerCase().includes(key)
    );
  }, [faqSearch]);

  // Handle Report Downloads Simulation
  const handleDownload = (fileName: string) => {
    setDownloadingReport(fileName);
    setTimeout(() => {
      setDownloadingReport(null);
      setDownloadSuccess(fileName);
      setTimeout(() => setDownloadSuccess(null), 3000);
    }, 1500);
  };

  // Onboarding Tour Steps definition
  const tourSteps = [
    {
      title: "Filter Komoditas Bahan Pangan",
      desc: "Pilih jenis komoditas utama (seperti bawang merah, beras, dll.) di sudut kanan atas ini. Semua data peta, harga, dan alur rute pengiriman akan diperbarui secara otomatis sesuai komoditas pilihan Anda.",
    },
    {
      title: "Kartu Ringkasan Pasokan Regional",
      desc: "Di baris ini, Anda dapat memantau akumulasi total volume surplus (kelebihan) dan defisit (kekurangan) bahan pangan di Jawa Timur secara cepat beserta jumlah kabupaten/kota yang terdampak.",
    },
    {
      title: "Peta Distribusi Interaktif",
      desc: "Gunakan peta Leaflet ini untuk memantau sebaran pasokan. Klik marker wilayah hijau (surplus) atau merah (defisit) untuk memfilter detail rute distribusi logistik pangan.",
    },
    {
      title: "Proyeksi Tren & Rute Cerdas Terbaik",
      desc: "Lihat ringkasan grafik fluktuasi harga 6 hari terakhir, serta rute pengiriman logistik terbaik hari ini yang direkomendasikan sistem agar menghemat ongkos pengiriman.",
    },
    {
      title: "Tanya Asisten AgriFlow",
      desc: "Butuh bantuan instan terkait data neraca pangan? Klik asisten petani melayang di sudut kanan bawah ini untuk berkonsultasi mengenai rekomendasi stok langsung dari asisten pintar.",
    }
  ];

  // Tour rings application helper
  const getTourRingClass = (stepIndex: number) => {
    return tourStep === stepIndex ? "ring-4 ring-emerald-500 ring-offset-2 animate-pulse relative z-50 bg-white" : "";
  };

  return (
    <div className="min-h-screen flex bg-[#5b7245] text-zinc-900 font-sans antialiased p-6 gap-6 relative">
      {/* ================================================================ */}
      {/* SIDEBAR COLUMNS (LEFT column vertical stack of cards)             */}
      {/* ================================================================ */}
      <aside className="w-64 flex flex-col gap-4 shrink-0 h-[calc(100vh-3rem)] overflow-y-auto">
        {/* Card 1: Sidebar Navigation */}
        <div className="bg-white rounded-2xl p-5 shadow-md border-none flex flex-col gap-4">
          {/* Logo Brand Header */}
          <div className="pb-3 border-b border-zinc-100 flex items-center justify-center">
            <img src="/logo.png" alt="AGRIFLOW" className="h-20 w-auto object-contain" />
          </div>

          {/* Menu Navigasi */}
          <nav className="space-y-1">
            <SidebarButton
              active={activeTab === "beranda"}
              icon={<Icons.Home />}
              label="Beranda"
              onClick={() => setActiveTab("beranda")}
            />
            <SidebarButton
              active={activeTab === "peta-pasokan"}
              icon={<Icons.Map />}
              label="Peta Pasokan"
              onClick={() => setActiveTab("peta-pasokan")}
            />
            <SidebarButton
              active={activeTab === "distribusi"}
              icon={<Icons.Truck />}
              label="Rekomendasi Distribusi"
              onClick={() => setActiveTab("distribusi")}
            />
            <SidebarButton
              active={activeTab === "harga"}
              icon={<Icons.TrendingUp />}
              label="Harga & Tren"
              onClick={() => setActiveTab("harga")}
            />
            <SidebarButton
              active={activeTab === "notifikasi-page"}
              icon={<Icons.Bell />}
              label="Notifikasi"
              badge={unreadCount}
              onClick={() => setActiveTab("notifikasi-page")}
            />
            <SidebarButton
              active={activeTab === "laporan"}
              icon={<Icons.FileText />}
              label="Laporan"
              onClick={() => setActiveTab("laporan")}
            />
            <SidebarButton
              active={activeTab === "bantuan"}
              icon={<Icons.HelpCircle />}
              label="Bantuan FAQ"
              onClick={() => setActiveTab("bantuan")}
            />
          </nav>
        </div>

        {/* Card 2: Sidebar Info Ringkasan Hari Ini */}
        <div className="bg-white rounded-2xl p-5 shadow-md border-none flex flex-col">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs font-bold text-zinc-800">Ringkasan Hari Ini</span>
            <span className="text-[10px] text-zinc-400 font-medium font-mono">2 Juli 2026</span>
          </div>
          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                Surplus Total
              </span>
              <strong className="text-zinc-800 font-semibold">{stats.totalSurplus.toFixed(0)} ton</strong>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" />
                Defisit Total
              </span>
              <strong className="text-zinc-800 font-semibold">{stats.totalDeficit.toFixed(0)} ton</strong>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" />
                Wilayah Surplus
              </span>
              <strong className="text-zinc-800 font-semibold">{stats.surplusRegionsCount}</strong>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                Wilayah Defisit
              </span>
              <strong className="text-zinc-800 font-semibold">{stats.deficitRegionsCount}</strong>
            </div>
          </div>
          
          <button
            onClick={refreshData}
            disabled={loading}
            className="w-full mt-4 bg-[#5b7245] hover:bg-[#4f643c] disabled:bg-zinc-200 disabled:text-zinc-400 text-white rounded-xl py-2 text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
          >
            {loading ? (
              <span className="flex items-center gap-1.5">
                <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Memproses...
              </span>
            ) : (
              "Perbarui Data"
            )}
          </button>
        </div>

        {/* Card 3: Tips */}
        <div className="bg-[#dbe6d3] text-[#4e643c] rounded-2xl p-5 text-xs font-medium leading-relaxed shadow-sm flex items-start gap-2.5 border-none">
          <Icons.Info className="w-4 h-4 text-[#4e643c] shrink-0 mt-0.5" />
          <span>
            <strong>Tips:</strong> Gunakan navigasi di bagian kiri untuk menelusuri detail peta stok kabupaten, analisis rekomendasi kecocokan rute, dan grafik prediksi tren harga bahan pokok secara rinci.
          </span>
        </div>
      </aside>

      {/* ================================================================ */}
      {/* MAIN CONTAINER CONTENT (Right column)                            */}
      {/* ================================================================ */}
      <main className="flex-1 flex flex-col min-w-0 gap-6 overflow-y-auto h-[calc(100vh-3rem)]">
        {/* ================================================================ */}
        {/* TOP FLOATING HEADER                                              */}
        {/* ================================================================ */}
        <div className="flex items-center justify-between gap-4 shrink-0 select-none">
          {/* Info Banner Alert */}
          <div className="flex-1 max-w-xl bg-white rounded-full px-5 py-2.5 shadow-sm text-xs text-zinc-700 flex items-center gap-2 border-none">
            <Icons.Bell className="w-3.5 h-3.5 text-[#5b7245] shrink-0" />
            <span className="truncate">
              <strong>Info hari ini:</strong> Ketersediaan {currentCommodityObj.nama} terpantau surplus di {stats.surplusRegionsCount} wilayah. <span className="underline font-semibold cursor-pointer text-[#5b7245]" onClick={() => setActiveTab("distribusi")}>Lihat rekomendasi distribusi</span>
            </span>
          </div>

          {/* Right Controls Area */}
          <div className="flex items-center gap-3">
            {/* Tour Button */}
            <button
              onClick={() => setTourStep(0)}
              className="bg-white hover:bg-zinc-50 px-4 py-2.5 rounded-full text-xs font-semibold text-zinc-700 flex items-center gap-1.5 transition-all cursor-pointer shadow-sm border-none"
            >
              <Icons.HelpCircle className="w-3.5 h-3.5 text-zinc-500" />
              Panduan
            </button>

            {/* Notification Bell Icon & Dropdown */}
            <div className="relative" ref={bellRef}>
              <div
                onClick={() => setShowNotificationsDropdown(!showNotificationsDropdown)}
                className="relative w-9 h-9 bg-white rounded-full flex items-center justify-center cursor-pointer hover:bg-zinc-50 transition-all shadow-sm border-none"
              >
                <Icons.Bell className="w-4 h-4 text-zinc-500" />
                {unreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-rose-600 text-white text-[9px] font-bold w-4.5 h-4.5 rounded-full flex items-center justify-center animate-pulse">
                    {unreadCount}
                  </span>
                )}
              </div>

              {showNotificationsDropdown && (
                <div className="absolute right-0 mt-2 w-80 bg-white border border-zinc-100 rounded-2xl shadow-xl py-2 z-50 animate-in fade-in slide-in-from-top-1 duration-100">
                  <div className="px-4 py-2.5 border-b border-zinc-100 flex justify-between items-center bg-zinc-50/50">
                    <span className="text-xs font-bold text-zinc-800">Notifikasi Terbaru</span>
                    <button
                      onClick={() => setNotifications(prev => prev.map(n => ({ ...n, read: true })))}
                      className="text-[10px] text-[#5b7245] font-bold hover:underline cursor-pointer"
                    >
                      Tandai semua dibaca
                    </button>
                  </div>
                  <ul className="max-h-64 overflow-y-auto divide-y divide-zinc-100">
                    {notifications.length === 0 ? (
                      <li className="px-4 py-6 text-xs text-zinc-400 text-center">Tidak ada notifikasi.</li>
                    ) : (
                      notifications.map(n => (
                        <li
                          key={n.id}
                          onClick={() => handleMarkAsRead(n.id)}
                          className={`p-3 text-xs hover:bg-zinc-50 flex items-start gap-2.5 transition-colors cursor-pointer ${
                            !n.read ? "bg-emerald-50/20 font-medium" : ""
                          }`}
                        >
                          <span className="shrink-0 mt-0.5">
                            {renderNotifIcon(n.type, "w-3.5 h-3.5")}
                          </span>
                          <div className="flex-1 min-w-0">
                            <strong className="text-zinc-800 font-bold block leading-normal">{n.title}</strong>
                            <p className="text-zinc-600 leading-normal mt-0.5 line-clamp-2">{n.text}</p>
                            <span className="text-[10px] text-zinc-400 block mt-1">{n.time}</span>
                          </div>
                          <button
                            onClick={(e) => handleRemoveNotification(n.id, e)}
                            className="text-zinc-400 hover:text-zinc-600 text-[10px] pl-1"
                          >
                            ✕
                          </button>
                        </li>
                      ))
                    )}
                  </ul>
                  <div className="px-4 py-2 border-t border-zinc-100 text-center bg-zinc-50/30">
                    <button
                      onClick={() => {
                        setActiveTab("notifikasi-page");
                        setShowNotificationsDropdown(false);
                      }}
                      className="text-[10px] text-zinc-500 font-semibold hover:text-zinc-800"
                    >
                      Lihat seluruh notifikasi
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Commodity Selector (Styled as custom floating pill) */}
            <div className="relative" ref={dropdownRef}>
              <div
                onClick={() => setShowCommodityDropdown(!showCommodityDropdown)}
                className={`flex items-center gap-2 px-4 py-2 bg-white rounded-full hover:bg-zinc-50 transition-all cursor-pointer select-none shadow-sm border-none ${getTourRingClass(0)}`}
              >
                <div className="text-left shrink-0 flex items-center gap-1.5">
                  <span className="text-xs font-bold text-zinc-850">Bahan Pokok</span>
                  <span className="text-xs font-semibold text-[#5b7245]">{currentCommodityObj.nama}</span>
                </div>
                <span className="text-zinc-400 text-[9px] pl-0.5">▼</span>
              </div>

              {showCommodityDropdown && (
                <div className="absolute right-0 mt-2 w-52 bg-white border border-zinc-100 rounded-2xl shadow-xl py-1.5 z-50 animate-in fade-in slide-in-from-top-1 duration-100">
                  <div className="px-3.5 py-2 text-[9px] font-bold text-zinc-400 border-b border-zinc-100 uppercase tracking-wider">
                    Pilih Komoditas Pantauan
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    {commodities.map((c) => (
                      <button
                        key={c.code}
                        onClick={() => {
                          setCommodity(c.code);
                          setShowCommodityDropdown(false);
                        }}
                        className={`w-full text-left px-4 py-2.5 text-xs flex items-center gap-2 hover:bg-zinc-50 transition-colors ${
                          commodity === c.code ? "bg-emerald-50 text-[#5b7245] font-bold" : "text-zinc-700"
                        }`}
                      >
                        <span>{c.nama}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ================================================================ */}
        {/* TAB 1: BERANDA                                                   */}
        {/* ================================================================ */}
        {activeTab === "beranda" && (
          <div className="flex flex-col gap-4">
            {/* Title Section */}
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Pantauan Real-time Jawa Timur
              </h2>
              <p className="text-xs text-emerald-100/80 mt-0.5">
                Visualisasi neraca ketahanan pangan dan alur distribusi di tingkat kabupaten/kota
              </p>
            </div>

            {/* STATUS CARDS ROW */}
            <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 ${getTourRingClass(1)}`}>
              {/* Card 1: Surplus (Siap Kirim) */}
              <div className="bg-white rounded-2xl p-4 flex items-start gap-4 shadow-sm border-none">
                <div className="w-10 h-10 bg-zinc-50 border border-zinc-100 rounded-xl flex items-center justify-center shrink-0">
                  <Icons.Truck className="w-5 h-5 text-zinc-500" />
                </div>
                <div className="space-y-0.5">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Surplus (Siap Kirim)</span>
                  <div className="flex items-baseline">
                    <span className="text-2xl font-extrabold text-zinc-800">{stats.totalSurplus.toFixed(0)}</span>
                    <span className="text-xs font-semibold text-zinc-450 ml-1">ton</span>
                  </div>
                  <span className="inline-flex items-center text-[9px] text-[#c93b3b] bg-[#fce6e6] px-2 py-0.5 rounded font-bold mt-1">
                    12% dari kemarin
                  </span>
                </div>
              </div>

              {/* Card 2: Defisit (Butuh Pasokan) */}
              <div className="bg-white rounded-2xl p-4 flex items-start gap-4 shadow-sm border-none">
                <div className="w-10 h-10 bg-zinc-50 border border-zinc-100 rounded-xl flex items-center justify-center shrink-0">
                  <Icons.ShoppingCart className="w-5 h-5 text-zinc-500" />
                </div>
                <div className="space-y-0.5">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Defisit (Butuh Pasokan)</span>
                  <div className="flex items-baseline">
                    <span className="text-2xl font-extrabold text-zinc-800">{stats.totalDeficit.toFixed(0)}</span>
                    <span className="text-xs font-semibold text-zinc-450 ml-1">ton</span>
                  </div>
                  <span className="inline-flex items-center text-[9px] text-[#44602c] bg-[#e2edd8] px-2 py-0.5 rounded font-bold mt-1">
                    12% dari kemarin
                  </span>
                </div>
              </div>

              {/* Card 3: Wilayah Surplus */}
              <div className="bg-white rounded-2xl p-4 flex items-start gap-4 shadow-sm border-none">
                <div className="w-10 h-10 bg-zinc-50 border border-zinc-100 rounded-xl flex items-center justify-center shrink-0">
                  <Icons.Map className="w-5 h-5 text-zinc-500" />
                </div>
                <div className="space-y-0.5">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Wilayah Surplus</span>
                  <div className="flex items-baseline">
                    <span className="text-2xl font-extrabold text-zinc-800">{stats.surplusRegionsCount}</span>
                    <span className="text-xs font-semibold text-zinc-455 ml-1">wilayah</span>
                  </div>
                  <span className="text-[9px] text-zinc-400 block mt-1">
                    dari {kabupaten.length || 38} kabupaten/kota
                  </span>
                </div>
              </div>

              {/* Card 4: Wilayah Defisit */}
              <div className="bg-white rounded-2xl p-4 flex items-start gap-4 shadow-sm border-none">
                <div className="w-10 h-10 bg-zinc-50 border border-zinc-100 rounded-xl flex items-center justify-center shrink-0">
                  <Icons.MapPin className="w-5 h-5 text-zinc-500" />
                </div>
                <div className="space-y-0.5">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">Wilayah Defisit</span>
                  <div className="flex items-baseline">
                    <span className="text-2xl font-extrabold text-zinc-800">{stats.deficitRegionsCount}</span>
                    <span className="text-xs font-semibold text-zinc-455 ml-1">wilayah</span>
                  </div>
                  <span className="text-[9px] text-zinc-400 block mt-1">
                    dari {kabupaten.length || 38} kabupaten/kota
                  </span>
                </div>
              </div>
            </div>

            {/* MAIN CONTENT GRID (2 COLUMNS) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* LEFT & CENTER COLUMN (Span 2) */}
              <div className="lg:col-span-2 flex flex-col gap-4">
                {/* 1. Map Panel */}
                <div className={`bg-white rounded-2xl shadow-sm border-none overflow-hidden flex flex-col ${getTourRingClass(2)}`}>
                  <div className="px-4 py-2.5 border-b border-zinc-100 flex justify-between items-center bg-zinc-50/30">
                    <span className="text-xs font-bold text-zinc-800">Peta Pasokan & Kebutuhan Wilayah</span>
                    <button
                      onClick={() => setActiveTab("peta-pasokan")}
                      className="text-xs text-[#5b7245] hover:text-[#4f643c] font-bold flex items-center gap-1.5 cursor-pointer transition-colors border-none bg-transparent"
                    >
                      <Icons.Search className="w-3.5 h-3.5" /> Lihat Full Map
                    </button>
                  </div>
                  <div className="h-[250px] w-full relative">
                    <MapView
                      kabupaten={kabupaten}
                      surplusDeficit={sd?.rows ?? []}
                      matches={matches}
                      onSelectKab={(id) => {
                        setSelectedKabId(id);
                        setActiveTab("distribusi");
                      }}
                      selectedKabId={selectedKabId}
                    />
                    
                    {/* Inline Map Legend */}
                    <div className="absolute bottom-4 left-4 bg-white/95 border border-zinc-150 rounded-xl p-3 text-[10px] shadow-lg space-y-1.5 z-[1000] leading-none">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block" />
                        <span className="text-zinc-650 font-semibold">Surplus (Siap Kirim)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-rose-600 inline-block" />
                        <span className="text-zinc-650 font-semibold">Defisit (Butuh Pasokan)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-slate-400 inline-block" />
                        <span className="text-zinc-650 font-semibold">Tidak ada data</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 2. Sub Grid: Price average */}
                <div className={`grid grid-cols-1 gap-4 ${getTourRingClass(3)}`}>
                  {/* Harga Rata-rata Hari Ini */}
                  <div className="bg-white rounded-2xl p-4 shadow-sm border-none flex flex-col gap-2.5">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-zinc-800">Harga rata-rata hari ini</span>
                      <button onClick={() => setActiveTab("harga")} className="text-[10px] text-[#5b7245] font-bold hover:underline cursor-pointer border-none bg-transparent">Lihat detail</button>
                    </div>

                    {/* 3-Column Split Body (1/3 for cards, 2/3 for chart) */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                      {/* Left Column: Highest & Lowest price cards */}
                      <div className="flex flex-col gap-2 md:col-span-1">
                        <div className="bg-[#f4f7f2] border border-[#e4ebd3] p-2.5 rounded-xl relative overflow-hidden flex flex-col gap-0.5 animate-in fade-in slide-in-from-left-2 duration-200">
                          <span className="text-[9px] font-bold text-zinc-400 uppercase tracking-wider block leading-tight">Harga Tertinggi</span>
                          <strong className="text-sm font-extrabold text-zinc-800 block">{fmtIdr(stats.maxPrice)}</strong>
                          <span className="text-[10px] text-rose-650 font-semibold truncate flex items-center gap-1">
                            <Icons.TrendingUp className="w-3.5 h-3.5 stroke-[2.5] text-rose-500 inline-block" /> {stats.maxPriceKab}
                          </span>
                        </div>
                        <div className="bg-[#f4f7f2] border border-[#e4ebd3] p-2.5 rounded-xl relative overflow-hidden flex flex-col gap-0.5 animate-in fade-in slide-in-from-left-2 duration-200 delay-75">
                          <span className="text-[9px] font-bold text-zinc-400 uppercase tracking-wider block leading-tight">Harga Terendah</span>
                          <strong className="text-sm font-extrabold text-zinc-800 block">{fmtIdr(stats.minPrice)}</strong>
                          <span className="text-[10px] text-emerald-700 font-semibold truncate flex items-center gap-1">
                            <svg className="w-3.5 h-3.5 text-emerald-600 inline-block animate-pulse" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                              <polyline points="22 17 13.5 8.5 8.5 13.5 2 7"></polyline>
                              <polyline points="16 17 22 17 22 11"></polyline>
                            </svg>
                            {stats.minPriceKab}
                          </span>
                        </div>
                      </div>

                      {/* Right Column: Weekly Price Trend SVG Chart (Spans 2 columns) */}
                      <div className="bg-[#f4f7f2]/40 border border-dashed border-[#e4ebd3] p-2 rounded-xl flex flex-col justify-between h-[116px] md:col-span-2 animate-in fade-in slide-in-from-right-2 duration-200">
                        <div className="text-[9px] font-bold text-zinc-400 uppercase tracking-wider mb-1 block">Tren Harga Mingguan</div>
                        <div className="flex-1 flex items-center justify-center">
                          <svg viewBox="0 0 200 65" className="w-full h-[70px]">
                            <defs>
                              <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#5b7245" stopOpacity="0.25" />
                                <stop offset="100%" stopColor="#5b7245" stopOpacity="0.0" />
                              </linearGradient>
                            </defs>
                            
                            {/* Grid lines */}
                            <line x1="0" y1="10" x2="200" y2="10" stroke="#e4e4e7" strokeWidth="0.5" />
                            <line x1="0" y1="30" x2="200" y2="30" stroke="#e4e4e7" strokeWidth="0.5" />
                            <line x1="0" y1="50" x2="200" y2="50" stroke="#e4e4e7" strokeWidth="0.5" />

                            {/* Chart Line Path */}
                            <path
                              d={`M 10,48 L 45,51 L 80,44 L 115,22 L 150,28 L 185,35`}
                              fill="none"
                              stroke="#5b7245"
                              strokeWidth="2.5"
                              strokeLinecap="round"
                            />
                            
                            {/* Gradient Area under line */}
                            <path
                              d={`M 10,48 L 45,51 L 80,44 L 115,22 L 150,28 L 185,35 L 185,60 L 10,60 Z`}
                              fill="url(#chartGrad)"
                            />

                            {/* Chart dots */}
                            <circle cx="10" cy="48" r="2.5" fill="#5b7245" />
                            <circle cx="45" cy="51" r="2.5" fill="#5b7245" />
                            <circle cx="80" cy="44" r="2.5" fill="#5b7245" />
                            <circle cx="115" cy="22" r="3.5" fill="#4e643c" />
                            <circle cx="150" cy="28" r="2.5" fill="#5b7245" />
                            <circle cx="185" cy="35" r="2.5" fill="#5b7245" />

                            {/* Labels */}
                            <text x="10" y="62" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#71717a">2021</text>
                            <text x="45" y="62" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#71717a">2022</text>
                            <text x="80" y="62" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#71717a">2023</text>
                            <text x="115" y="62" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#71717a">2024</text>
                            <text x="150" y="62" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#71717a">2025</text>
                            <text x="185" y="62" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#71717a">2026</text>
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT COLUMN (Span 1) */}
              <div className="space-y-4">
                {/* Rekomendasi Distribusi Cerdas List */}
                <div className="bg-white rounded-2xl p-4 shadow-sm border-none flex flex-col gap-3">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-zinc-800">Rekomendasi Distribusi Cerdas</span>
                    <button onClick={() => setActiveTab("distribusi")} className="text-[10px] text-[#5b7245] font-bold hover:underline cursor-pointer border-none bg-transparent">Lihat semua</button>
                  </div>

                  <div className="flex flex-col gap-2">
                    {/* CARD 1: High Priority (Bawang Merah) */}
                    <div className="bg-[#fce9e9] border border-[#f5c6c6] rounded-xl p-2.5 flex flex-col gap-1.5">
                      <div className="flex justify-between items-center">
                        <span className="text-[9px] font-extrabold bg-[#f5c6c6] text-[#b33c3c] px-2 py-0.5 rounded uppercase tracking-wider">
                          HIGH PRIORITY
                        </span>
                        <span className="text-xs font-extrabold text-[#b33c3c]">Bawang Merah</span>
                      </div>
                      <div className="flex items-center justify-between text-xs font-bold text-zinc-800">
                        <span>Nganjuk</span>
                        <div className="flex-1 flex flex-col items-center mx-2 relative">
                          <span className="text-[9px] font-bold text-[#b33c3c] absolute -top-3.5">230 Km</span>
                          <div className="w-full border-t border-dashed border-[#b33c3c]/50 h-0.5"></div>
                          <span className="text-[8px] text-zinc-450 mt-1">🚚 Rute Aman</span>
                        </div>
                        <span>Surabaya</span>
                      </div>
                      <div className="flex justify-between items-center pt-1 border-t border-[#f5c6c6]/45">
                        <span className="text-[10px] text-zinc-500 font-medium">Matched Volume:</span>
                        <span className="text-xs font-bold text-zinc-800">15.5 Ton</span>
                      </div>
                      <button 
                        onClick={() => { setSelectedKabId("3518"); setActiveTab("distribusi"); }}
                        className="w-full bg-white hover:bg-zinc-55 text-zinc-800 rounded-lg py-1 text-[10px] font-bold transition-all border border-[#f5c6c6] cursor-pointer shadow-sm text-center mt-1 border-none"
                      >
                        MORE INFO
                      </button>
                    </div>

                    {/* CARD 2: Medium Priority (Beras) */}
                    <div className="bg-[#fef4e2] border border-[#fbe3ba] rounded-xl p-2.5 flex flex-col gap-1.5">
                      <div className="flex justify-between items-center">
                        <span className="text-[9px] font-extrabold bg-[#fbe3ba] text-[#b27218] px-2 py-0.5 rounded uppercase tracking-wider">
                          MEDIUM PRIORITY
                        </span>
                        <span className="text-xs font-extrabold text-[#b27218]">Beras</span>
                      </div>
                      <div className="flex items-center justify-between text-xs font-bold text-zinc-800">
                        <span>Mojokerto</span>
                        <div className="flex-1 flex flex-col items-center mx-2 relative">
                          <span className="text-[9px] font-bold text-[#b27218] absolute -top-3.5">100 Km</span>
                          <div className="w-full border-t border-dashed border-[#b27218]/50 h-0.5"></div>
                          <span className="text-[8px] text-zinc-455 mt-1">🚚 Hemat Biaya</span>
                        </div>
                        <span>Malang</span>
                      </div>
                      <div className="flex justify-between items-center pt-1 border-t border-[#fbe3ba]/45">
                        <span className="text-[10px] text-zinc-500 font-medium">Matched Volume:</span>
                        <span className="text-xs font-bold text-zinc-800">22.0 Ton</span>
                      </div>
                      <button 
                        onClick={() => { setSelectedKabId("3516"); setActiveTab("distribusi"); }}
                        className="w-full bg-white hover:bg-zinc-55 text-zinc-800 rounded-lg py-1 text-[10px] font-bold transition-all border border-[#fbe3ba] cursor-pointer shadow-sm text-center mt-1 border-none"
                      >
                        MORE INFO
                      </button>
                    </div>

                    {/* CARD 3: Low Priority (Kentang) */}
                    <div className="bg-[#f4f7f2] border border-[#e4ebd3] rounded-xl p-2.5 flex flex-col gap-1.5">
                      <div className="flex justify-between items-center">
                        <span className="text-[9px] font-extrabold bg-[#e4ebd3] text-[#556943] px-2 py-0.5 rounded uppercase tracking-wider">
                          LOW PRIORITY
                        </span>
                        <span className="text-xs font-extrabold text-[#556943]">Kentang</span>
                      </div>
                      <div className="flex items-center justify-between text-xs font-bold text-zinc-800">
                        <span>Nganjuk</span>
                        <div className="flex-1 flex flex-col items-center mx-2 relative">
                          <span className="text-[9px] font-bold text-[#556943] absolute -top-3.5">100 Km</span>
                          <div className="w-full border-t border-dashed border-[#e4ebd3] h-0.5"></div>
                          <span className="text-[8px] text-zinc-455 mt-1">🚚 Distribusi Rutin</span>
                        </div>
                        <span>Ponorogo</span>
                      </div>
                      <div className="flex justify-between items-center pt-1 border-t border-[#e4ebd3]/45">
                        <span className="text-[10px] text-zinc-500 font-medium">Matched Volume:</span>
                        <span className="text-xs font-bold text-zinc-800">8.0 Ton</span>
                      </div>
                      <button 
                        onClick={() => { setSelectedKabId("3518"); setActiveTab("distribusi"); }}
                        className="w-full bg-white hover:bg-zinc-55 text-zinc-800 rounded-lg py-1 text-[10px] font-bold transition-all border border-[#e4ebd3] cursor-pointer shadow-sm text-center mt-1 border-none"
                      >
                        MORE INFO
                      </button>
                    </div>
                  </div>

                  <button
                    onClick={() => setActiveTab("distribusi")}
                    className="w-full mt-1 bg-[#5b7245] hover:bg-[#4f643c] text-white rounded-xl py-2 text-xs font-bold transition-all cursor-pointer shadow-sm text-center border-none"
                  >
                    Lihat lebih banyak
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 2: PETA PASOKAN                                              */}
        {/* ================================================================ */}
        {activeTab === "peta-pasokan" && (
          <div className="flex flex-col gap-6 flex-1 min-h-0">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Peta Pasokan Jawa Timur
              </h2>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-3 content-start">
              {/* Map block */}
              <div className="lg:col-span-4 bg-white rounded-2xl shadow-sm overflow-hidden h-[380px] relative border-none">
                <MapView
                  kabupaten={kabupaten}
                  surplusDeficit={sd?.rows ?? []}
                  matches={matches}
                  onSelectKab={setSelectedKabId}
                  selectedKabId={selectedKabId}
                />
                
                {/* Inline Map Legend */}
                <div className="absolute bottom-4 left-4 bg-white/95 border border-zinc-150 rounded-xl p-3 text-[10px] shadow-lg space-y-1.5 z-[1000] leading-none">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block" />
                    <span className="text-zinc-650 font-semibold">Surplus (Siap Kirim)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-600 inline-block" />
                    <span className="text-zinc-650 font-semibold">Defisit (Butuh Pasokan)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-400 inline-block" />
                    <span className="text-zinc-650 font-semibold">Tidak ada data</span>
                  </div>
                </div>
              </div>

              {/* Left Sidebar List of Surplus */}
              <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm overflow-hidden flex flex-col h-[220px] border-none">
                <div className="px-4 py-2 bg-[#e2edd8] font-bold text-xs text-[#44602c] border-none select-none">
                  Daftar Wilayah Surplus ({surplusRegions.length})
                </div>
                <ul className="flex-1 overflow-y-auto px-3 py-2.5 space-y-1.5 text-xs">
                  {surplusRegions.length === 0 ? (
                    <li className="px-4 py-6 text-center text-zinc-400 bg-zinc-50 rounded-xl">Tidak ada wilayah surplus saat ini.</li>
                  ) : (
                    surplusRegions.map(r => (
                      <li
                        key={r.kab_id}
                        onClick={() => setSelectedKabId(r.kab_id)}
                        className={`px-3 py-2 rounded-lg flex justify-between items-center cursor-pointer font-bold text-xs bg-[#708b5e] text-white transition-all hover:opacity-90 shadow-sm ${
                          selectedKabId === r.kab_id ? "ring-2 ring-yellow-400 shadow-md scale-[1.01]" : ""
                        }`}
                      >
                        <span className="w-1/3 text-left truncate">{r.kab_nama}</span>
                        <span className="w-1/3 text-center font-medium opacity-90 truncate">{currentCommodityObj.nama}</span>
                        <span className="w-1/3 text-right">{(r.volume_tons * 6.6).toFixed(0)}kg</span>
                      </li>
                    ))
                  )}
                </ul>
                <div className="px-3 py-2 border-t border-zinc-100 bg-zinc-50/50">
                  <button onClick={() => setActiveTab("distribusi")} className="w-full bg-[#5b7245] hover:bg-[#4f643c] text-white rounded-lg py-1.5 text-xs font-bold transition-all text-center cursor-pointer shadow-sm">
                    Lihat lebih banyak
                  </button>
                </div>
              </div>

              {/* Right Sidebar List of Deficit */}
              <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm overflow-hidden flex flex-col h-[220px] border-none">
                <div className="px-4 py-2 bg-[#fce6e6] font-bold text-xs text-[#aa3a3a] border-none select-none">
                  Daftar Wilayah Defisit ({deficitRegions.length})
                </div>
                <ul className="flex-1 overflow-y-auto px-3 py-2.5 space-y-1.5 text-xs">
                  {deficitRegions.length === 0 ? (
                    <li className="px-4 py-6 text-center text-zinc-400 bg-zinc-50 rounded-xl">Tidak ada wilayah kekurangan stok saat ini.</li>
                  ) : (
                    deficitRegions.map(r => (
                      <li
                        key={r.kab_id}
                        onClick={() => setSelectedKabId(r.kab_id)}
                        className={`px-3 py-2 rounded-lg flex justify-between items-center cursor-pointer font-bold text-xs bg-[#d78a8a] text-white transition-all hover:opacity-90 shadow-sm ${
                          selectedKabId === r.kab_id ? "ring-2 ring-yellow-400 shadow-md scale-[1.01]" : ""
                        }`}
                      >
                        <span className="w-1/3 text-left truncate">{r.kab_nama}</span>
                        <span className="w-1/3 text-center font-medium opacity-90 truncate">{currentCommodityObj.nama}</span>
                        <span className="w-1/3 text-right">{(r.volume_tons * 0.41).toFixed(0)}kg</span>
                      </li>
                    ))
                  )}
                </ul>
                <div className="px-3 py-2 border-t border-zinc-100 bg-zinc-50/50">
                  <button onClick={() => setActiveTab("distribusi")} className="w-full bg-[#5b7245] hover:bg-[#4f643c] text-white rounded-lg py-1.5 text-xs font-bold transition-all text-center cursor-pointer shadow-sm">
                    Lihat lebih banyak
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 3: KEBUTUHAN DAERAH                                          */}
        {/* ================================================================ */}
        {activeTab === "kebutuhan-daerah" && (
          <div className="flex flex-col gap-6 flex-1 min-h-0">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Pemantauan Wilayah Defisit (Kekurangan Stok)
              </h2>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
              {/* Left Sidebar List of Deficits */}
              <div className="bg-white rounded-2xl shadow-sm overflow-hidden flex flex-col h-[480px] border-none">
                <div className="px-4 py-3 border-b border-zinc-100 bg-zinc-50/50 font-bold text-xs text-zinc-800">
                  Daftar Wilayah Defisit ({deficitRegions.length})
                </div>
                <ul className="flex-1 overflow-y-auto divide-y divide-zinc-100 text-xs">
                  {deficitRegions.length === 0 ? (
                    <li className="px-4 py-8 text-center text-zinc-400">Tidak ada wilayah kekurangan stok saat ini.</li>
                  ) : (
                    deficitRegions.map(r => (
                      <li
                        key={r.kab_id}
                        onClick={() => setSelectedKabId(r.kab_id)}
                        className={`p-3 hover:bg-zinc-50 transition-colors cursor-pointer flex justify-between items-center ${
                          selectedKabId === r.kab_id ? "bg-rose-50/40 border-l-4 border-rose-500" : ""
                        }`}
                      >
                        <div>
                          <strong className="text-zinc-800 block font-bold">{r.kab_nama}</strong>
                          <span className="text-[10px] text-zinc-400 block mt-0.5">Harga: {fmtIdr(r.price_per_kg)}/kg</span>
                        </div>
                        <span className="bg-rose-100 text-rose-800 px-2 py-0.5 rounded-full font-bold text-[10px]">
                          -{r.volume_tons.toFixed(0)} ton
                        </span>
                      </li>
                    ))
                  )}
                </ul>
              </div>

              {/* Map block */}
              <div className="lg:col-span-3 bg-white rounded-2xl shadow-sm overflow-hidden h-[480px] relative border-none">
                <MapView
                  kabupaten={kabupaten}
                  surplusDeficit={sd?.rows ?? []}
                  matches={matches}
                  onSelectKab={setSelectedKabId}
                  selectedKabId={selectedKabId}
                />
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 4: REKOMENDASI DISTRIBUSI FULL                               */}
        {/* ================================================================ */}
        {activeTab === "distribusi" && (
          <div className="flex flex-col gap-6 flex-1 min-h-0">
            {/* Title Section */}
            <div className="flex justify-between items-end">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Peta Pasokan Jawa Timur
                </h2>
              </div>
              {selectedKabId && (
                <button
                  onClick={() => setSelectedKabId(null)}
                  className="bg-white hover:bg-zinc-50 text-[#5b7245] px-4 py-2 rounded-xl text-xs font-bold cursor-pointer shadow-sm transition-all border-none animate-in fade-in zoom-in-95 duration-100"
                >
                  Clear Filter Kabupaten
                </button>
              )}
            </div>

            {/* Top Map view (Full Width) */}
            <div className="bg-white rounded-2xl shadow-sm overflow-hidden h-[380px] w-full border-none relative">
              <MapView
                kabupaten={kabupaten}
                surplusDeficit={sd?.rows ?? []}
                matches={matches}
                onSelectKab={setSelectedKabId}
                selectedKabId={selectedKabId}
              />
            </div>

            {/* Bottom Rekomendasi Distribusi Cerdas (Full Width) */}
            <div className="bg-white rounded-2xl p-5 shadow-sm border-none flex flex-col gap-4">
              <div className="flex justify-between items-center">
                <span className="text-xs font-bold text-zinc-800">Rekomendasi Distribusi Cerdas</span>
                <span className="text-[10px] text-zinc-450 font-medium">Urut berdasarkan tingkat kecocokan rute tertinggi</span>
              </div>

              <div className="flex flex-col gap-3">
                {matches.length === 0 ? (
                  <div className="p-8 text-center text-xs text-zinc-400 bg-zinc-50 rounded-xl">
                    Belum ada rekomendasi rute distribusi aktif untuk filter ini.
                  </div>
                ) : (
                  matches.map((m, idx) => {
                    // Assign Priority tier based on index
                    const isHigh = idx === 0;
                    const isMed = idx === 1;
                    const badgeText = isHigh ? "HIGH PRIORITY" : isMed ? "MEDIUM PRIORITY" : "LOW PRIORITY";
                    const badgeClass = isHigh
                      ? "text-[#b33c3c] bg-[#fce9e9] border border-[#f5c6c6]/50"
                      : isMed
                      ? "text-[#b27218] bg-[#fef4e2] border border-[#fbe3ba]/50"
                      : "text-[#44602c] bg-[#f4f7f2] border border-[#e4ebd3]/50";
                    const commColor = isHigh ? "text-[#b33c3c]" : isMed ? "text-[#b27218]" : "text-[#44602c]";

                    return (
                      <div
                        key={idx}
                        className="bg-[#b2c2a9]/50 hover:bg-[#b2c2a9]/70 border-none rounded-2xl p-4 flex items-center justify-between gap-6 transition-all text-xs text-zinc-800 shadow-sm"
                      >
                        {/* Priority Badge */}
                        <div className="w-36 shrink-0">
                          <span className={`text-[9px] font-extrabold px-3 py-1 rounded-full uppercase tracking-wider block text-center ${badgeClass}`}>
                            {badgeText}
                          </span>
                        </div>

                        {/* Surplus City */}
                        <div className="w-24 shrink-0 font-bold text-zinc-900 text-sm">
                          {m.surplus.kab_nama.replace("Kab. ", "").replace("Kota ", "")}
                        </div>

                        {/* Distance & Route line graphic */}
                        <div className="flex-1 flex items-center gap-2 relative">
                          <span className="text-[10px] text-zinc-500 font-bold shrink-0">{m.distance_km.toFixed(0)} Km</span>
                          <span className="text-base shrink-0">📦</span>
                          <div className="flex-1 border-t-2 border-dashed border-[#4e643c]/40 h-0.5"></div>
                          <span className="text-base shrink-0">📍</span>
                        </div>

                        {/* Deficit City */}
                        <div className="w-28 shrink-0 font-bold text-zinc-900 text-sm text-left">
                          {m.deficit.kab_nama.replace("Kab. ", "").replace("Kota ", "")}
                        </div>

                        {/* Commodity name */}
                        <div className={`w-32 shrink-0 font-extrabold text-sm ${commColor}`}>
                          {m.commodity_nama}
                        </div>

                        {/* Action Button */}
                        <div className="shrink-0">
                          <button
                            onClick={() => {
                              setSelectedKabId(m.surplus.kab_id);
                              alert(`Rencana Distribusi:\nRute: ${m.surplus.kab_nama} -> ${m.deficit.kab_nama}\nKomoditas: ${m.commodity_nama}\nVolume: ${m.matched_volume_tons.toFixed(0)} Ton\nEstimasi Jarak: ${m.distance_km.toFixed(0)} km\n\nJalur aman terpantau bebas hambatan.`);
                            }}
                            className="bg-[#4e643c] hover:bg-[#3d5030] text-white px-5 py-2.5 rounded-xl text-[10px] font-bold transition-all shadow-sm cursor-pointer border-none"
                          >
                            MORE INFO
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <button
                onClick={() => alert("Semua rekomendasi rute distribusi sudah ditampilkan.")}
                className="w-full mt-2 bg-[#5b7245] hover:bg-[#4f643c] text-white rounded-xl py-3 text-xs font-bold transition-all cursor-pointer shadow-sm text-center border-none"
              >
                Lihat lebih banyak
              </button>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 5: HARGA & TREN (Forecast + Anomaly Panel)                    */}
        {/* ================================================================ */}
        {activeTab === "harga" && (
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Proyeksi Harga Pangan & Deteksi Tren Pasar
                </h2>
                <p className="text-xs text-emerald-100/80 mt-0.5">
                  Pantau perkiraan pergerakan harga pangan komoditas 30 hari ke depan serta deteksi lonjakan/penurunan tidak wajar.
                </p>
              </div>

              {/* Selectors inside styled elements */}
              <div className="flex items-center gap-2">
                <div className="bg-white rounded-full px-4 py-2 shadow-sm flex items-center gap-2">
                  <label className="text-[10px] font-bold text-zinc-400 uppercase">Komoditas</label>
                  <select
                    className="border-none text-xs bg-white text-[#5b7245] font-extrabold focus:outline-none cursor-pointer"
                    value={analysisCommodity}
                    onChange={(e) => setAnalysisCommodity(e.target.value)}
                  >
                    {commodities.map((c) => (
                      <option key={c.code} value={c.code}>{c.nama}</option>
                    ))}
                  </select>
                </div>
                <div className="bg-white rounded-full px-4 py-2 shadow-sm flex items-center gap-2">
                  <label className="text-[10px] font-bold text-zinc-400 uppercase">Kota Pantauan</label>
                  <select
                    className="border-none text-xs bg-white text-[#5b7245] font-extrabold focus:outline-none cursor-pointer"
                    value={analysisCity}
                    onChange={(e) => setAnalysisCity(e.target.value)}
                  >
                    {kabupaten.slice(0, 8).map((c) => (
                      <option key={c.id} value={c.id}>{c.nama}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-6">
              {/* Forecast graph panel */}
              <div className="bg-white rounded-2xl shadow-sm overflow-hidden p-2 border-none">
                <ForecastPanel
                  forecast={forecast}
                  loading={forecastLoading}
                  error={forecastErr}
                />
              </div>

              {/* Anomaly scan panel */}
              <div className="bg-white rounded-2xl shadow-sm overflow-hidden border-none p-2">
                <AnomalyPanel
                  anomalies={anomalies}
                  loading={anomalyLoading}
                  error={anomalyErr}
                  totalCount={anomalyTotal}
                />
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 6: NOTIFIKASI PAGE                                           */}
        {/* ================================================================ */}
        {activeTab === "notifikasi-page" && (
          <div className="flex flex-col gap-5">
            <div className="flex justify-between items-start gap-4">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">Pusat Informasi Pemantauan & Rekomendasi</h2>
                <p className="text-xs text-emerald-100/80 mt-0.5">Kumpulan peringatan fluktuasi harga, rekomendasi distribusi, dan pembaruan aktivitas logistik pangan hari ini.</p>
              </div>

              {/* Filter dropdown */}
              <div className="relative shrink-0" ref={notifFilterRef}>
                <button
                  onClick={() => setShowNotifFilterMenu((v) => !v)}
                  className="bg-white rounded-full px-4 py-2 shadow-sm flex items-center gap-2 text-xs font-bold text-[#5b7245] cursor-pointer hover:bg-zinc-50 transition-colors border-none"
                >
                  <Icons.Filter className="w-3.5 h-3.5" />
                  <span>{notifFilter === "Semua" ? "Semua Notifikasi" : notifFilter}</span>
                  <Icons.ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
                </button>

                {showNotifFilterMenu && (
                  <div className="absolute right-0 mt-2 w-52 bg-white border border-zinc-100 rounded-2xl shadow-xl py-2 z-50 animate-in fade-in slide-in-from-top-1 duration-100">
                    <div className="px-4 py-1.5 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Filter Kategori</div>
                    {([
                      { key: "Semua", label: "Semua Notifikasi", icon: <Icons.Bell className="w-3.5 h-3.5 text-zinc-500" /> },
                      { key: "Perlu Tindakan", label: "Perlu Tindakan", icon: <Icons.AlertTriangle className="w-3.5 h-3.5 text-amber-500" /> },
                      { key: "Rekomendasi AI", label: "Rekomendasi AI", icon: <Icons.Sparkles className="w-3.5 h-3.5 text-[#5b7245]" /> },
                      { key: "Update", label: "Update", icon: <Icons.BarChart className="w-3.5 h-3.5 text-indigo-500" /> },
                    ] as const).map((opt) => (
                      <button
                        key={opt.key}
                        onClick={() => { setNotifFilter(opt.key); setShowNotifFilterMenu(false); }}
                        className={`w-full flex items-center gap-2.5 px-4 py-2 text-xs font-semibold text-left transition-colors cursor-pointer hover:bg-zinc-50 ${
                          notifFilter === opt.key ? "text-[#5b7245] bg-emerald-50/40" : "text-zinc-600"
                        }`}
                      >
                        {opt.icon}
                        <span>{opt.label}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="bg-white rounded-2xl overflow-hidden shadow-sm border-none">
              <ul className="divide-y divide-zinc-100">
                {filteredNotifications.length === 0 ? (
                  <li className="px-6 py-12 text-zinc-400 text-center text-xs">
                    Tidak ada notifikasi pada kategori ini.
                  </li>
                ) : (
                  filteredNotifications.map(n => (
                    <li
                      key={n.id}
                      onClick={() => handleMarkAsRead(n.id)}
                      className={`group px-5 py-4 hover:bg-zinc-50 flex items-start gap-4 transition-colors cursor-pointer ${
                        !n.read ? "bg-emerald-50/20" : ""
                      }`}
                    >
                      <div className="w-10 h-10 rounded-xl bg-zinc-50 border border-zinc-100 flex items-center justify-center shrink-0">
                        {renderNotifIcon(n.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-start gap-3">
                          <strong className="text-sm font-bold text-zinc-800 flex items-center gap-2">
                            {n.title}
                            {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />}
                          </strong>
                          <span className="text-[10px] text-zinc-400 font-medium shrink-0 whitespace-nowrap">{n.time}</span>
                        </div>
                        <p className="text-xs text-zinc-600 mt-1 leading-relaxed">{n.text}</p>
                      </div>
                      <button
                        onClick={(e) => handleRemoveNotification(n.id, e)}
                        className="text-zinc-300 hover:text-rose-500 text-xs shrink-0 opacity-0 group-hover:opacity-100 transition-opacity pl-1"
                        title="Hapus notifikasi"
                      >
                        ✕
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 7: LAPORAN (Report Downloads)                                */}
        {/* ================================================================ */}
        {activeTab === "laporan" && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">Laporan Ketahanan Pangan</h2>
              <p className="text-xs text-emerald-100/80 mt-0.5">Rekapitulasi dampak koordinasi distribusi serta dokumen neraca pangan Jawa Timur yang siap diunduh.</p>
            </div>

            {/* Simulated success or download toasts */}
            {downloadingReport && (
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-xs text-blue-800 animate-pulse flex items-center gap-2">
                🔄 Sedang memproses dan mengompilasi berkas <strong>{downloadingReport}</strong>. Silakan tunggu...
              </div>
            )}
            {downloadSuccess && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-800 flex items-center gap-2 animate-bounce">
                ✅ Berkas <strong>{downloadSuccess}</strong> sukses diunduh ke komputer Anda!
              </div>
            )}

            {/* Summary Stat Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Efektivitas Bantuan", value: "24", unit: "penyaluran", sub: "Tersalurkan bulan ini", color: "text-[#5b7245]" },
                { label: "Kebutuhan Pangan Terpenuhi", value: "94", unit: "%", sub: "Dari total kebutuhan wilayah", color: "text-emerald-600" },
                { label: "Daerah Terdampak", value: "16", unit: "wilayah", sub: "Kabupaten/kota terbantu", color: "text-indigo-600" },
                { label: "Estimasi Penghematan Biaya", value: "Rp 219", unit: "juta", sub: "Efisiensi biaya distribusi", color: "text-amber-600" },
              ].map((c) => (
                <div key={c.label} className="bg-white rounded-2xl p-5 shadow-sm border-none relative overflow-hidden">
                  <div className="absolute top-0 left-0 h-1 w-full bg-[#5b7245]/70" />
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block leading-tight">{c.label}</span>
                  <div className="mt-2 flex items-baseline gap-1">
                    <strong className={`text-2xl font-extrabold ${c.color}`}>{c.value}</strong>
                    <span className="text-xs font-bold text-zinc-500">{c.unit}</span>
                  </div>
                  <p className="text-[9px] text-zinc-400 mt-1.5">{c.sub}</p>
                </div>
              ))}
            </div>

            {/* Report Documents Table */}
            <div className="bg-white rounded-2xl shadow-sm overflow-hidden border-none">
              <div className="px-5 py-3.5 border-b border-zinc-100 font-bold text-sm text-zinc-800">
                Dokumen Laporan Siap Download
              </div>

              {/* Table header */}
              <div className="hidden md:grid grid-cols-[1.4fr_1.6fr_0.7fr_1fr] gap-4 px-5 py-2.5 bg-zinc-50/60 border-b border-zinc-100 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                <span>Nama Laporan</span>
                <span>Deskripsi File</span>
                <span>Periode</span>
                <span className="text-right">Unduh</span>
              </div>

              <div className="divide-y divide-zinc-100">
                {[
                  { icon: <Icons.FileText className="w-4 h-4 text-[#5b7245]" />, name: "Neraca Ketahanan Pangan Jawa Timur", desc: "Ringkasan neraca surplus-defisit seluruh kabupaten/kota.", period: "Mei 2026", formats: [{ ext: "PDF", tone: "rose", file: "Neraca_Pangan_Jatim_Mei2026.pdf" }, { ext: "Excel", tone: "green", file: "Neraca_Pangan_Jatim_Mei2026.xlsx" }] },
                  { icon: <Icons.Truck className="w-4 h-4 text-indigo-500" />, name: "Laporan Distribusi Komoditas", desc: "Realisasi penyaluran pangan antar wilayah.", period: "Apr 2026", formats: [{ ext: "PDF", tone: "rose", file: "Distribusi_Komoditas_Apr2026.pdf" }, { ext: "Excel", tone: "green", file: "Distribusi_Komoditas_Apr2026.xlsx" }] },
                  { icon: <Icons.TrendingUp className="w-4 h-4 text-amber-500" />, name: "Laporan Analitika Harga Pangan", desc: "Tren dan volatilitas harga pasar bulanan.", period: "Mei 2026", formats: [{ ext: "PDF", tone: "rose", file: "Analitika_Harga_Mei2026.pdf" }, { ext: "CSV", tone: "sky", file: "Analitika_Harga_Mei2026.csv" }] },
                  { icon: <Icons.MapPin className="w-4 h-4 text-rose-500" />, name: "Rekap Wilayah Rentan & Prioritas", desc: "Daftar daerah defisit prioritas intervensi.", period: "Mei 2026", formats: [{ ext: "PDF", tone: "rose", file: "Wilayah_Prioritas_Mei2026.pdf" }, { ext: "Excel", tone: "green", file: "Wilayah_Prioritas_Mei2026.xlsx" }] },
                  { icon: <Icons.BarChart className="w-4 h-4 text-sky-500" />, name: "Peramalan Harga 30 Hari", desc: "Proyeksi pergerakan harga komoditas ke depan.", period: "Mei 2026", formats: [{ ext: "PDF", tone: "rose", file: "Peramalan_Harga_30Hari.pdf" }, { ext: "Excel", tone: "green", file: "Peramalan_Harga_30Hari.xlsx" }] },
                  { icon: <Icons.AlertTriangle className="w-4 h-4 text-amber-500" />, name: "Statistik Anomali Harga", desc: "Deteksi lonjakan dan penurunan harga tak wajar.", period: "Mei 2026", formats: [{ ext: "PDF", tone: "rose", file: "Statistik_Anomali_Mei2026.pdf" }, { ext: "Excel", tone: "green", file: "Statistik_Anomali_Mei2026.xlsx" }] },
                ].map((row) => (
                  <div key={row.name} className="grid grid-cols-1 md:grid-cols-[1.4fr_1.6fr_0.7fr_1fr] gap-2 md:gap-4 px-5 py-3.5 items-center hover:bg-zinc-50/60 transition-colors">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="w-8 h-8 rounded-lg bg-zinc-50 border border-zinc-100 flex items-center justify-center shrink-0">{row.icon}</span>
                      <strong className="text-xs font-bold text-zinc-800 leading-tight">{row.name}</strong>
                    </div>
                    <span className="text-[11px] text-zinc-500 leading-snug">{row.desc}</span>
                    <span className="text-[11px] text-zinc-500 font-semibold">{row.period}</span>
                    <div className="flex items-center gap-2 md:justify-end flex-wrap">
                      {row.formats.map((f) => {
                        const tones: Record<string, string> = {
                          rose: "text-rose-600 bg-rose-50 border-rose-100 hover:bg-rose-100",
                          green: "text-[#5b7245] bg-emerald-50 border-emerald-100 hover:bg-emerald-100",
                          sky: "text-sky-600 bg-sky-50 border-sky-100 hover:bg-sky-100",
                        };
                        return (
                          <button
                            key={f.ext}
                            disabled={!!downloadingReport}
                            onClick={() => handleDownload(f.file)}
                            className={`flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${tones[f.tone]}`}
                          >
                            <Icons.Download className="w-3 h-3" />
                            {f.ext}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Download full summary */}
            <div className="flex justify-end">
              <button
                disabled={!!downloadingReport}
                onClick={() => handleDownload("Ringkasan_Laporan_Ketahanan_Pangan.pdf")}
                className="bg-[#5b7245] hover:bg-[#4f643c] disabled:bg-zinc-300 text-white rounded-xl px-5 py-2.5 font-bold cursor-pointer shadow-sm flex items-center gap-2 transition-colors border-none text-xs"
              >
                <Icons.Download className="w-4 h-4" />
                Unduh Ringkasan (PDF)
              </button>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* TAB 8: BANTUAN FAQ INTERAKTIF                                    */}
        {/* ================================================================ */}
        {activeTab === "bantuan" && (
          <div className="flex flex-col gap-6 max-w-4xl">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">Pusat Bantuan FAQ & Panduan</h2>
              <p className="text-xs text-emerald-100/80 mt-0.5">Temukan solusi cepat dan tutorial penggunaan dashboard pemantauan stok pangan Jawa Timur di bawah ini.</p>
            </div>

            {/* FAQ Search bar */}
            <div className="bg-white rounded-2xl p-4.5 shadow-sm flex items-center gap-3 border-none">
              <Icons.Search className="w-4.5 h-4.5 text-[#5b7245] shrink-0" />
              <input
                type="text"
                value={faqSearch}
                onChange={(e) => setFaqSearch(e.target.value)}
                placeholder="Ketik kata kunci pertanyaan bantuan Anda di sini (misal: peta, surplus, rute)"
                className="flex-1 bg-transparent text-xs text-zinc-850 focus:outline-none placeholder-zinc-400 font-medium"
              />
              {faqSearch && (
                <button
                  onClick={() => setFaqSearch("")}
                  className="text-zinc-450 hover:text-zinc-700 text-xs font-bold"
                >
                  Clear
                </button>
              )}
            </div>

            {/* FAQ List Content */}
            <div className="flex flex-col gap-4">
              {filteredFAQs.length === 0 ? (
                <div className="bg-white rounded-2xl p-8 text-center text-zinc-400 text-xs shadow-sm">
                  Pertanyaan tidak ditemukan. Coba ketik kata kunci lainnya.
                </div>
              ) : (
                filteredFAQs.map((faq, idx) => (
                  <div key={idx} className="bg-[#f1f6ef] border border-[#e4eedf] rounded-2xl p-5 shadow-sm space-y-2.5">
                    <div className="flex items-center gap-2">
                      <span className="bg-[#e4eedf] text-[#4e643c] text-[9px] font-extrabold px-2.5 py-0.8 rounded uppercase tracking-wider">
                        {faq.category}
                      </span>
                      <h3 className="font-bold text-xs text-zinc-800 leading-tight">
                        {faq.q}
                      </h3>
                    </div>
                    <p className="text-xs text-zinc-650 leading-relaxed">
                      {faq.a}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </main>

      {/* ================================================================ */}
      {/* FLOATING CHATBOT HELPER                                          */}
      {/* ================================================================ */}
      <div className={`fixed bottom-5 right-5 z-[9999] flex flex-col items-end ${getTourRingClass(4)}`}>
        {showChatbot && (
          <div className="w-80 h-96 bg-white border border-zinc-150 rounded-2xl shadow-2xl flex flex-col overflow-hidden mb-3 animate-in fade-in slide-in-from-bottom-2 duration-150 relative z-[99999]">
            {/* Chatbot Header */}
            <div className="bg-[#5b7245] text-white px-4 py-3 flex justify-between items-center shadow-md">
              <div className="flex items-center gap-2">
                <Icons.MessageSquare className="w-4 h-4 text-white animate-pulse" />
                <div>
                  <h4 className="font-bold text-xs">Tanya AgriFlow</h4>
                  <span className="text-[9px] text-emerald-100 font-medium">Asisten Cerdas Stok Pangan</span>
                </div>
              </div>
              <button
                onClick={() => setShowChatbot(false)}
                className="text-white/80 hover:text-white text-xs cursor-pointer focus:outline-none"
              >
                ✕
              </button>
            </div>

            {/* Chat Messages Area */}
            <div className="flex-1 p-3 overflow-y-auto space-y-2.5 bg-zinc-50/50 text-xs">
              {chatMessages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 leading-relaxed shadow-sm ${
                      m.sender === "user"
                        ? "bg-[#5b7245] text-white rounded-tr-none"
                        : "bg-white text-zinc-800 rounded-tl-none border border-zinc-150"
                    }`}
                  >
                    {m.text}
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input Area */}
            <form onSubmit={handleSendMessage} className="p-2 border-t border-zinc-150 flex gap-1.5 bg-white">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Tanyakan stok, harga, rute..."
                className="flex-1 border border-zinc-200 rounded-xl px-3 py-1.5 text-xs text-zinc-800 focus:outline-none focus:ring-1.5 focus:ring-emerald-500 bg-zinc-50/50 font-medium"
              />
              <button
                type="submit"
                className="bg-[#5b7245] hover:bg-[#4f643c] text-white rounded-xl px-3 py-1.5 text-xs font-bold transition-all cursor-pointer shadow-sm border-none"
              >
                Kirim
              </button>
            </form>
          </div>
        )}

        {/* Floating Chatbot Bubble Trigger */}
        <div
          onClick={() => setShowChatbot(!showChatbot)}
          className="flex items-center gap-2.5 bg-[#5b7245] hover:bg-[#4f643c] text-white px-4 py-2.5 rounded-full shadow-lg hover:shadow-xl transition-all cursor-pointer scale-100 hover:scale-105 active:scale-95 duration-100 border border-[#5b7245]/50"
        >
          <Icons.MessageSquare className="w-4 h-4 text-white" />
          <div className="text-left leading-none">
            <div className="text-[10px] font-bold text-emerald-100 uppercase tracking-wider">Butuh Bantuan?</div>
            <div className="text-xs font-bold mt-0.5">Tanya AgriFlow</div>
          </div>
        </div>
      </div>

      {/* ================================================================ */}
      {/* INTERACTIVE TOUR GUIDE OVERLAY                                    */}
      {/* ================================================================ */}
      {tourStep !== null && (
        <div className="fixed inset-0 bg-black/60 z-[99998] flex items-center justify-center p-4">
          <div className="w-96 bg-white rounded-2xl border border-zinc-200 shadow-2xl p-5 space-y-4 animate-in zoom-in-95 duration-150 text-left">
            {/* Tour steps progression */}
            <div className="flex justify-between items-center text-[10px] text-[#5b7245] font-bold uppercase tracking-wider">
              <span className="flex items-center gap-1">
                <Icons.HelpCircle className="w-3 h-3" />
                Panduan Interaktif
              </span>
              <span>Langkah {tourStep + 1} dari {tourSteps.length}</span>
            </div>

            {/* Tour Body */}
            <div className="space-y-1.5">
              <h3 className="font-bold text-sm text-zinc-950 flex items-center gap-1.5">
                {tourSteps[tourStep].title}
              </h3>
              <p className="text-xs text-zinc-500 leading-relaxed">
                {tourSteps[tourStep].desc}
              </p>
            </div>

            {/* Tour Navigation Controls */}
            <div className="flex justify-between items-center pt-3 border-t border-zinc-100">
              <button
                onClick={() => setTourStep(null)}
                className="text-xs text-zinc-400 hover:text-zinc-650 font-semibold cursor-pointer"
              >
                Lewati Tour
              </button>
              
              <div className="flex gap-2">
                {tourStep > 0 && (
                  <button
                    onClick={() => setTourStep(prev => (prev !== null ? prev - 1 : null))}
                    className="border border-zinc-200 text-zinc-700 rounded-lg px-3 py-1.5 text-xs font-semibold hover:bg-zinc-50 cursor-pointer animate-none"
                  >
                    Kembali
                  </button>
                )}
                
                {tourStep < tourSteps.length - 1 ? (
                  <button
                    onClick={() => setTourStep(prev => (prev !== null ? prev + 1 : null))}
                    className="bg-[#5b7245] text-white rounded-lg px-4 py-1.5 text-xs font-bold hover:bg-[#4f643c] cursor-pointer shadow-sm"
                  >
                    Lanjut
                  </button>
                ) : (
                  <button
                    onClick={() => setTourStep(null)}
                    className="bg-[#5b7245] text-white rounded-lg px-4 py-1.5 text-xs font-bold hover:bg-[#4f643c] cursor-pointer shadow-sm"
                  >
                    Selesai
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// HELPER SUB-COMPONENTS
// =============================================================================

function SidebarButton({
  active,
  icon,
  label,
  badge,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs transition-all cursor-pointer group ${
        active
          ? "bg-[#5b7245] text-white font-semibold shadow-sm"
          : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800 font-medium"
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span className={`w-4.5 h-4.5 flex items-center justify-center ${active ? "text-white" : "text-zinc-400 group-hover:text-zinc-650"}`}>{icon}</span>
        <span>{label}</span>
      </div>
      {badge !== undefined && badge > 0 && (
        <span className={`text-[9px] font-extrabold w-4.5 h-4.5 rounded-full flex items-center justify-center ${
          active ? "bg-white text-[#5b7245]" : "bg-rose-600 text-white"
        }`}>
          {badge}
        </span>
      )}
    </button>
  );
}

function ActivityItem({
  icon,
  title,
  desc,
  time,
}: {
  icon: string;
  title: string;
  desc: string;
  time: string;
}) {
  return (
    <div className="flex items-start gap-3 text-xs leading-normal">
      <span className="text-base leading-none mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <strong className="text-zinc-850 font-bold block">{title}</strong>
        <span className="text-zinc-500 block mt-0.5 truncate">{desc}</span>
        <span className="text-[9px] text-zinc-400 block mt-0.5">{time}</span>
      </div>
    </div>
  );
}

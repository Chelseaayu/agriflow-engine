"use client";

import { MapContainer, TileLayer, CircleMarker, Tooltip, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { Kabupaten, SurplusDeficitRow, Match } from "../lib/api";

const CENTER: [number, number] = [-7.7, 112.5]; // Jawa Timur centroid-ish
const ZOOM = 8;

type Props = {
  kabupaten: Kabupaten[];
  surplusDeficit: SurplusDeficitRow[];
  matches: Match[];
  onSelectKab: (kabId: string) => void;
  selectedKabId: string | null;
};

// Radius proportional to sqrt(volume) so visual area ~ volume.
function bubbleRadius(tons: number): number {
  if (tons <= 0) return 4;
  return Math.max(6, Math.min(28, Math.sqrt(tons) * 1.8));
}

export default function MapView({
  kabupaten, surplusDeficit, matches, onSelectKab, selectedKabId,
}: Props) {
  const rowByKab = new Map<string, SurplusDeficitRow>();
  for (const r of surplusDeficit) rowByKab.set(r.kab_id, r);

  return (
    <MapContainer
      center={CENTER}
      zoom={ZOOM}
      scrollWheelZoom
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Flow lines for top matches */}
      {matches.slice(0, 10).map((m, idx) => (
        <Polyline
          key={`flow-${idx}`}
          positions={[
            [m.surplus.lat, m.surplus.lng],
            [m.deficit.lat, m.deficit.lng],
          ]}
          pathOptions={{
            color: "#6366f1",
            weight: 1.5,
            opacity: 0.45,
            dashArray: "4 4",
          }}
        />
      ))}

      {/* Kabupaten bubbles */}
      {kabupaten.map((k) => {
        const row = rowByKab.get(k.id);
        const role = row?.role;
        const tons = row?.volume_tons ?? 0;
        const color =
          role === "surplus" ? "#16a34a"
          : role === "deficit" ? "#dc2626"
          : "#94a3b8";
        const radius = row ? bubbleRadius(tons) : 4;
        const isSelected = selectedKabId === k.id;
        return (
          <CircleMarker
            key={k.id}
            center={[k.lat, k.lng]}
            radius={radius}
            pathOptions={{
              color: isSelected ? "#facc15" : color,
              weight: isSelected ? 3 : 1.5,
              fillColor: color,
              fillOpacity: row ? 0.55 : 0.25,
            }}
            eventHandlers={{ click: () => onSelectKab(k.id) }}
          >
            <Tooltip direction="top" offset={[0, -4]}>
              <div style={{ fontSize: 12, lineHeight: 1.35 }}>
                <strong>{k.nama}</strong>
                <br />
                Tier {k.tier.replace("TIER_", "").replace("_HIGH", " HIGH").replace("_MEDIUM", " MED")}
                <br />
                IPM {k.ipm.toFixed(1)} · {(k.population / 1000).toFixed(0)}k jiwa
                {row && (
                  <>
                    <br />
                    <span style={{ color }}>
                      {role === "surplus" ? "Surplus" : "Defisit"}: {tons.toFixed(0)} ton
                    </span>
                  </>
                )}
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}

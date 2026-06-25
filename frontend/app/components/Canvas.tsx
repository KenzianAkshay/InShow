"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { LayoutDashboard } from "lucide-react";
import { Artifact } from "@/lib/api";
import BoothLayout from "@/app/components/booth/BoothLayout";

const AXIS = "var(--muted-foreground)";
const GRID = "var(--border)";

const tooltipStyle: React.CSSProperties = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  color: "var(--popover-foreground)",
  fontSize: 12,
  boxShadow: "0 12px 30px -16px rgba(0,0,0,0.5)",
};

function BarArtifact({ data }: { data: { label: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
        <defs>
          <linearGradient id="barFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff9678" />
            <stop offset="100%" stopColor="#ef5f3d" />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: AXIS, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: GRID }}
        />
        <YAxis
          tick={{ fill: AXIS, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          cursor={{ fill: "var(--secondary)" }}
        />
        <Bar dataKey="value" fill="url(#barFill)" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function LineArtifact({ data }: { data: { label: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: AXIS, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: GRID }}
        />
        <YAxis
          tick={{ fill: AXIS, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip contentStyle={tooltipStyle} />
        <Area
          type="monotone"
          dataKey="value"
          stroke="var(--accent)"
          strokeWidth={2.5}
          fill="url(#areaFill)"
          dot={{ fill: "var(--accent)", r: 3 }}
          activeDot={{ r: 5 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function MapScatter({
  points,
}: {
  points: { lat: number; lng: number; label?: string }[];
}) {
  if (points.length === 0) return null;
  const W = 420;
  const H = 220;
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
  const [minLng, maxLng] = [Math.min(...lngs), Math.max(...lngs)];
  const sx = (lng: number) =>
    20 + ((lng - minLng) / (maxLng - minLng || 1)) * (W - 40);
  const sy = (lat: number) =>
    H - 20 - ((lat - minLat) / (maxLat - minLat || 1)) * (H - 40);
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="block w-full rounded-[var(--radius-md)]"
      style={{ background: "var(--secondary)" }}
    >
      {points.map((p, i) => (
        <g key={i}>
          <circle
            cx={sx(p.lng)}
            cy={sy(p.lat)}
            r={6}
            fill="var(--accent)"
            stroke="var(--background)"
            strokeWidth={2}
          />
          {p.label && (
            <text
              x={sx(p.lng) + 9}
              y={sy(p.lat) + 3}
              fontSize={10}
              fill="var(--muted-foreground)"
            >
              {p.label}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

export default function Canvas({ artifact }: { artifact: Artifact | null }) {
  // Recharts measures the DOM, so defer chart render until after mount to avoid
  // a zero-size first paint / hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="glass overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border/70 px-4 py-2.5 text-sm font-semibold">
        <LayoutDashboard className="size-4 text-muted-foreground" />
        Canvas
        {artifact?.title && (
          <span className="font-normal text-muted-foreground">
            · {artifact.title}
          </span>
        )}
      </div>
      <div className="p-4">
        {!artifact && (
          <p className="m-0 text-sm text-muted-foreground">
            Agent-generated charts, tables, and maps appear here.
          </p>
        )}
        {artifact?.type === "booth_layout" && <BoothLayout artifact={artifact} />}
        {mounted && artifact?.type === "bar" && (
          <BarArtifact data={artifact.data} />
        )}
        {mounted && artifact?.type === "line" && (
          <LineArtifact data={artifact.data} />
        )}
        {artifact?.type === "map" && <MapScatter points={artifact.points} />}
        {artifact?.type === "metrics" && (
          <div className="flex flex-wrap gap-3">
            {artifact.items.map((m, i) => (
              <div
                key={i}
                className="metal min-w-[120px] flex-1 p-3.5"
              >
                <div className="text-2xl font-bold tabular-nums">{m.value}</div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  {m.label}
                </div>
              </div>
            ))}
          </div>
        )}
        {artifact?.type === "table" && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  {artifact.columns.map((c, i) => (
                    <th
                      key={i}
                      className="border-b-2 border-border px-2.5 py-2 text-left font-semibold text-muted-foreground"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {artifact.rows.map((row, i) => (
                  <tr key={i} className="transition-colors hover:bg-secondary/60">
                    {row.map((cell, j) => (
                      <td
                        key={j}
                        className="border-b border-border/70 px-2.5 py-2"
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

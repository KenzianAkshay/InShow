"use client";

import { Artifact } from "@/lib/api";

type Booth = Extract<Artifact, { type: "booth_layout" }>;

const S = 42; // pixels per metre
const M = { left: 38, right: 16, top: 16, bottom: 30 };

export default function BoothLayout2D({ artifact }: { artifact: Booth }) {
  const { booth, zones, aisles = [] } = artifact;
  const W = booth.width;
  const D = booth.depth;
  const open = new Set(booth.open_sides);

  // Booth front (y=0) is drawn at the bottom; flip the y axis for SVG.
  const px = (m: number) => m * S;
  const flipY = (y: number, h: number) => (D - y - h) * S;

  const vw = px(W) + M.left + M.right;
  const vh = px(D) + M.top + M.bottom;

  // Edge endpoints in booth space → svg (within the translated group).
  const edges: Record<string, { x1: number; y1: number; x2: number; y2: number }> = {
    front: { x1: 0, y1: px(D), x2: px(W), y2: px(D) },
    back: { x1: 0, y1: 0, x2: px(W), y2: 0 },
    left: { x1: 0, y1: 0, x2: 0, y2: px(D) },
    right: { x1: px(W), y1: 0, x2: px(W), y2: px(D) },
  };

  return (
    <svg
      viewBox={`0 0 ${vw} ${vh}`}
      className="block w-full"
      style={{ maxHeight: 420 }}
      role="img"
      aria-label={`Booth floor plan, ${W} by ${D} metres`}
    >
      <defs>
        <pattern id="aisle-hatch" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="7" stroke="var(--muted-foreground)" strokeWidth="1" opacity="0.28" />
        </pattern>
      </defs>

      <g transform={`translate(${M.left} ${M.top})`}>
        {/* booth floor */}
        <rect x={0} y={0} width={px(W)} height={px(D)} rx={4} fill="var(--secondary)" opacity={0.4} />

        {/* aisles (entrance strip) */}
        {aisles.map((a, i) => (
          <rect
            key={i}
            x={px(a.x)}
            y={flipY(a.y, a.h)}
            width={px(a.w)}
            height={px(a.h)}
            fill="url(#aisle-hatch)"
            stroke="var(--border)"
            strokeDasharray="4 3"
          />
        ))}

        {/* booth edges: solid wall when closed, accent when open to an aisle */}
        {Object.entries(edges).map(([side, e]) => (
          <line
            key={side}
            x1={e.x1}
            y1={e.y1}
            x2={e.x2}
            y2={e.y2}
            stroke={open.has(side) ? "var(--accent)" : "var(--foreground)"}
            strokeWidth={open.has(side) ? 3 : 2.5}
            strokeDasharray={open.has(side) ? "6 4" : undefined}
            strokeLinecap="round"
            opacity={open.has(side) ? 0.9 : 0.55}
          />
        ))}

        {/* zones */}
        {zones.map((z) => {
          const x = px(z.x);
          const y = flipY(z.y, z.h);
          const w = px(z.w);
          const h = px(z.h);
          const small = w < 58 || h < 34;
          return (
            <g key={z.id}>
              <rect
                x={x}
                y={y}
                width={w}
                height={h}
                rx={5}
                fill={z.color ?? "#7c93c9"}
                fillOpacity={0.82}
                stroke="#ffffff"
                strokeOpacity={0.5}
                strokeWidth={1}
              />
              <text
                x={x + w / 2}
                y={y + h / 2 - (small ? 0 : 5)}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={small ? 8.5 : 11}
                fontWeight={600}
                fill="#ffffff"
                style={{ pointerEvents: "none" }}
              >
                {z.name}
              </text>
              {!small && (
                <text
                  x={x + w / 2}
                  y={y + h / 2 + 9}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize={8.5}
                  fill="#ffffff"
                  fillOpacity={0.85}
                  style={{ pointerEvents: "none" }}
                >
                  {z.w}×{z.h} m
                </text>
              )}
            </g>
          );
        })}
      </g>

      {/* overall dimensions */}
      <text
        x={M.left + px(W) / 2}
        y={vh - 8}
        textAnchor="middle"
        fontSize={10}
        fontWeight={600}
        fill="var(--muted-foreground)"
      >
        {W} m {open.has("front") ? "· open front ▾" : ""}
      </text>
      <text
        x={11}
        y={M.top + px(D) / 2}
        textAnchor="middle"
        fontSize={10}
        fontWeight={600}
        fill="var(--muted-foreground)"
        transform={`rotate(-90 11 ${M.top + px(D) / 2})`}
      >
        {D} m
      </text>
    </svg>
  );
}

"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Maximize2, Tag, ZoomIn, ZoomOut } from "lucide-react";
import { compute2DLayout } from "@/lib/ontology3d";
import type { GEdge, GNode } from "@/app/components/Ontology3D";

const W = 1000;
const H = 600;
const PAD = 70;

function radiusFor(count: number | undefined): number {
  return 7 + Math.min(20, 3.2 * Math.sqrt(count ?? 1));
}

function ControlButton({
  label,
  active,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
      className="ring-focus grid size-8 place-items-center rounded-lg border border-border bg-[var(--glass-bg)] text-muted-foreground backdrop-blur-md transition-colors hover:text-foreground"
      style={active ? { color: "#ff7a59", borderColor: "#ff7a59" } : undefined}
    >
      {children}
    </button>
  );
}

/** Readable 2D class map: nodes spread on a plane via a collision-aware force
 *  layout, labels sit beside each node (no depth stacking), with pan/zoom and
 *  hover highlighting. Click a class to drill into its instances. */
export default function OntologySchema2D({
  nodes,
  edges,
  onDrill,
}: {
  nodes: GNode[];
  edges: GEdge[];
  onDrill?: (id: string) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [showAllLabels, setShowAllLabels] = useState(false);
  const [t, setT] = useState({ k: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(
    null,
  );

  // Lay out, then frame the result to fit the 1000x600 canvas.
  const pos = useMemo(() => {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const labelWidth = (id: string) => {
      const n = byId.get(id);
      const r = radiusFor(n?.count);
      // Half the label's pixel width (+ node radius headroom) so neighbours keep
      // enough distance for labels not to collide.
      return Math.max(r + 16, (n?.label.length ?? 4) * 4.4 + 22);
    };
    const raw = compute2DLayout(
      nodes.map((n) => n.id),
      edges,
      labelWidth,
    );
    const xs = Object.values(raw).map((p) => p[0]);
    const ys = Object.values(raw).map((p) => p[1]);
    const minX = Math.min(...xs, 0);
    const maxX = Math.max(...xs, 0);
    const minY = Math.min(...ys, 0);
    const maxY = Math.max(...ys, 0);
    const scale = Math.min(
      (W - PAD * 2) / Math.max(1, maxX - minX),
      (H - PAD * 2) / Math.max(1, maxY - minY),
    );
    const out: Record<string, { x: number; y: number }> = {};
    for (const [id, p] of Object.entries(raw)) {
      out[id] = {
        x: PAD + (p[0] - minX) * scale,
        y: PAD + (p[1] - minY) * scale,
      };
    }
    return out;
  }, [nodes, edges]);

  const neighbours = useMemo(() => {
    if (!hovered) return null;
    const s = new Set<string>([hovered]);
    for (const e of edges) {
      if (e.from === hovered) s.add(e.to);
      if (e.to === hovered) s.add(e.from);
    }
    return s;
  }, [hovered, edges]);

  const toSvg = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = svg.createSVGPoint();
    p.x = clientX;
    p.y = clientY;
    const v = p.matrixTransform(ctm.inverse());
    return { x: v.x, y: v.y };
  }, []);

  const zoom = useCallback(
    (factor: number, cx = W / 2, cy = H / 2) => {
      setT((prev) => {
        const k = Math.max(0.3, Math.min(6, prev.k * factor));
        return {
          k,
          x: cx - ((cx - prev.x) * k) / prev.k,
          y: cy - ((cy - prev.y) * k) / prev.k,
        };
      });
    },
    [],
  );

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const v = toSvg(e.clientX, e.clientY);
    zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, v.x, v.y);
  };

  const onPointerDownBg = (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, tx: t.x, ty: t.y };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const svg = svgRef.current;
    const scaleX = svg ? W / svg.getBoundingClientRect().width : 1;
    const scaleY = svg ? H / svg.getBoundingClientRect().height : 1;
    setT((prev) => ({
      ...prev,
      x: drag.current!.tx + (e.clientX - drag.current!.x) * scaleX,
      y: drag.current!.ty + (e.clientY - drag.current!.y) * scaleY,
    }));
  };
  const onPointerUp = () => {
    drag.current = null;
  };

  return (
    <div className="relative h-full w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full touch-none"
        style={{ cursor: drag.current ? "grabbing" : "grab" }}
        onWheel={onWheel}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="#8aa0d6" />
          </marker>
          <marker
            id="arrow-lit"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="#ff7a59" />
          </marker>
        </defs>

        {/* background pan surface */}
        <rect
          x={0}
          y={0}
          width={W}
          height={H}
          fill="transparent"
          onPointerDown={onPointerDownBg}
        />

        <g transform={`translate(${t.x} ${t.y}) scale(${t.k})`}>
          {edges.map((e, i) => {
            const a = pos[e.from];
            const b = pos[e.to];
            if (!a || !b) return null;
            const lit =
              !!hovered && (e.from === hovered || e.to === hovered);
            const dim = !!hovered && !lit;
            const rb = radiusFor(nodes.find((n) => n.id === e.to)?.count);
            const ra = radiusFor(nodes.find((n) => n.id === e.from)?.count);
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const len = Math.hypot(dx, dy) || 1;
            const ux = dx / len;
            const uy = dy / len;
            const x1 = a.x + ux * ra;
            const y1 = a.y + uy * ra;
            const x2 = b.x - ux * (rb + 6);
            const y2 = b.y - uy * (rb + 6);
            const mx = (x1 + x2) / 2;
            const my = (y1 + y2) / 2;
            return (
              <g key={i} opacity={dim ? 0.12 : 1}>
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={lit ? "#ff7a59" : "#8aa0d6"}
                  strokeWidth={lit ? 2 : 1}
                  strokeOpacity={lit ? 1 : 0.5}
                  markerEnd={`url(#${lit ? "arrow-lit" : "arrow"})`}
                />
                {(showAllLabels || lit) && (
                  <text
                    x={mx}
                    y={my - 2}
                    textAnchor="middle"
                    className="fill-muted-foreground"
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      letterSpacing: 0.3,
                      paintOrder: "stroke",
                      stroke: "var(--background)",
                      strokeWidth: 3,
                    }}
                  >
                    {e.type}
                    {e.count != null && e.count > 1 ? ` ×${e.count}` : ""}
                  </text>
                )}
              </g>
            );
          })}

          {nodes.map((n) => {
            const p = pos[n.id];
            if (!p) return null;
            const r = radiusFor(n.count);
            const isHover = n.id === hovered;
            const dim = !!neighbours && !neighbours.has(n.id);
            return (
              <g
                key={n.id}
                opacity={dim ? 0.25 : 1}
                style={{ cursor: onDrill ? "pointer" : "default" }}
                onPointerEnter={() => setHovered(n.id)}
                onPointerLeave={() => setHovered((h) => (h === n.id ? null : h))}
                onClick={(e) => {
                  e.stopPropagation();
                  onDrill?.(n.id);
                }}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={r}
                  fill={n.color}
                  stroke={isHover ? "#ff7a59" : "var(--background)"}
                  strokeWidth={isHover ? 3 : 1.5}
                />
                <text
                  x={p.x}
                  y={p.y + r + 11}
                  textAnchor="middle"
                  className="fill-foreground"
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    paintOrder: "stroke",
                    stroke: "var(--background)",
                    strokeWidth: 3.5,
                  }}
                >
                  {n.label}
                  {n.count != null ? `  ${n.count}` : ""}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      <div className="absolute right-2 top-2 flex flex-col gap-1.5">
        <ControlButton label="Zoom in" onClick={() => zoom(1.2)}>
          <ZoomIn className="size-4" />
        </ControlButton>
        <ControlButton label="Zoom out" onClick={() => zoom(1 / 1.2)}>
          <ZoomOut className="size-4" />
        </ControlButton>
        <ControlButton
          label="Reset view"
          onClick={() => setT({ k: 1, x: 0, y: 0 })}
        >
          <Maximize2 className="size-4" />
        </ControlButton>
        <ControlButton
          label="Show all relationship labels"
          active={showAllLabels}
          onClick={() => setShowAllLabels((v) => !v)}
        >
          <Tag className="size-4" />
        </ControlButton>
      </div>
    </div>
  );
}

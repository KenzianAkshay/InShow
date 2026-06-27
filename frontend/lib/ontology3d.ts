import {
  forceSimulation,
  forceManyBody,
  forceLink,
  forceCenter,
  forceCollide,
  type SimNode,
} from "d3-force-3d";
import * as d3force from "d3-force-3d";

// forceX / forceY exist at runtime but are missing from the package's type
// declarations; reach them through the module namespace with a typed cast.
const axisForce = (axis: "forceX" | "forceY", strength: number) => {
  const f = (
    d3force as unknown as Record<
      string,
      (v: number) => { strength: (s: number) => unknown }
    >
  )[axis](0);
  (f as { strength: (s: number) => unknown }).strength(strength);
  return f;
};

export type Vec3 = [number, number, number];
export type Edge = { from: string; to: string };

// Deterministic seeded RNG (mulberry32) fed to d3 so the same ontology always
// lays out identically — important for a stable, testable visualization.
function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Compute deterministic 3D positions for an ontology graph using a 3D
 * force-directed simulation (d3-force-3d). Positions are normalized to roughly
 * fit a sphere of the given radius so the camera framing stays consistent
 * regardless of graph size.
 */
export function compute3DLayout(
  nodeIds: string[],
  edges: Edge[],
  radius = 6,
): Record<string, Vec3> {
  const out: Record<string, Vec3> = {};
  const n = nodeIds.length;
  if (n === 0) return out;
  if (n === 1) {
    out[nodeIds[0]] = [0, 0, 0];
    return out;
  }

  const index = new Set(nodeIds);
  const nodes: (SimNode & { id: string })[] = nodeIds.map((id) => ({ id }));
  const links = edges
    .filter((e) => index.has(e.from) && index.has(e.to))
    .map((e) => ({ source: e.from, target: e.to }));

  const sim = forceSimulation(nodes, 3)
    .randomSource(seededRandom(1337))
    .force("charge", forceManyBody().strength(-55))
    .force(
      "link",
      forceLink(links)
        .id((d: SimNode) => (d as { id: string }).id)
        .distance(26)
        .strength(0.65),
    )
    .force("center", forceCenter(0, 0, 0))
    .stop();

  // Run a fixed number of cooling ticks (no animation; we only need final coords).
  sim.tick(320);

  // Normalize so the furthest node sits near `radius`.
  let max = 0;
  for (const node of nodes) {
    const d = Math.hypot(node.x ?? 0, node.y ?? 0, node.z ?? 0);
    if (d > max) max = d;
  }
  const scale = max > 0 ? radius / max : 1;
  for (const node of nodes) {
    out[node.id] = [
      (node.x ?? 0) * scale,
      (node.y ?? 0) * scale,
      (node.z ?? 0) * scale,
    ];
  }
  return out;
}

export type Vec2 = [number, number];

/**
 * Deterministic 2D force-directed layout for the schema (class) map. Uses a
 * collision force sized to each node's label so classes spread out on a plane
 * and labels don't pile up — the readable alternative to the 3D ball at 40+
 * nodes. Returns raw simulation coordinates; the caller frames them to fit.
 */
export function compute2DLayout(
  nodeIds: string[],
  edges: Edge[],
  labelWidth: (id: string) => number,
): Record<string, Vec2> {
  const out: Record<string, Vec2> = {};
  const n = nodeIds.length;
  if (n === 0) return out;
  if (n === 1) {
    out[nodeIds[0]] = [0, 0];
    return out;
  }

  const index = new Set(nodeIds);
  const nodes: (SimNode & { id: string })[] = nodeIds.map((id) => ({ id }));
  const links = edges
    .filter((e) => index.has(e.from) && index.has(e.to))
    .map((e) => ({ source: e.from, target: e.to }));

  const spacing = 70 + Math.sqrt(n) * 12;

  // Collision (sized to each node's label) does the spacing so no two nodes or
  // labels overlap; weak gravity toward the centre gathers disconnected tabs so
  // the map fills the frame instead of flying apart into tiny far clusters.
  const collide = forceCollide();
  (collide as unknown as {
    radius: (fn: (d: SimNode) => number) => unknown;
    strength: (s: number) => unknown;
    iterations: (i: number) => unknown;
  }).radius((d: SimNode) => labelWidth((d as { id: string }).id));
  (collide as unknown as { strength: (s: number) => unknown }).strength(0.9);
  (collide as unknown as { iterations: (i: number) => unknown }).iterations(3);

  const sim = forceSimulation(nodes, 2)
    .randomSource(seededRandom(1337))
    .force("charge", forceManyBody().strength(-40))
    .force(
      "link",
      forceLink(links)
        .id((d: SimNode) => (d as { id: string }).id)
        .distance(spacing)
        .strength(0.12),
    )
    .force("center", forceCenter(0, 0))
    .force("x", axisForce("forceX", 0.045) as never)
    .force("y", axisForce("forceY", 0.045) as never)
    .force("collide", collide)
    .stop();

  sim.tick(420);

  for (const node of nodes) {
    out[node.id] = [node.x ?? 0, node.y ?? 0];
  }
  return out;
}

// A calm, cohesive palette for ontology classes. Deliberately avoids reds and
// oranges so the coral "active/traversed" highlight always reads as distinct.
const PALETTE = [
  "#4f8cff", // blue
  "#2bd4a8", // green
  "#a78bfa", // violet
  "#2bc6df", // cyan
  "#f0c419", // amber
  "#7c93c9", // slate blue
  "#e86fae", // berry
  "#46c79a", // sea green
];

export function colorForLabel(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

// Turn a uid ("City:Berlin", "Booth:03828faa69c8f961") into a readable label.
// Record nodes are keyed by an opaque hash, so show their class name instead.
export function displayName(uid: string): string {
  const idx = uid.indexOf(":");
  if (idx === -1) return uid;
  const label = uid.slice(0, idx);
  const value = uid.slice(idx + 1);
  const name = /^[0-9a-f]{10,}$/i.test(value) ? label : value;
  return name.length > 18 ? name.slice(0, 17) + "…" : name;
}

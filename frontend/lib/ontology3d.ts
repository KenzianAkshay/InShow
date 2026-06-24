import {
  forceSimulation,
  forceManyBody,
  forceLink,
  forceCenter,
  type SimNode,
} from "d3-force-3d";

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

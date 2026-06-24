// Minimal type surface for d3-force-3d (no official @types package). Covers only
// the 3D-aware simulation pieces we use in lib/ontology3d.ts.
declare module "d3-force-3d" {
  export interface SimNode {
    index?: number;
    x?: number;
    y?: number;
    z?: number;
    vx?: number;
    vy?: number;
    vz?: number;
    fx?: number | null;
    fy?: number | null;
    fz?: number | null;
    [key: string]: unknown;
  }

  export interface SimLink<N = SimNode> {
    source: N | string | number;
    target: N | string | number;
    index?: number;
    [key: string]: unknown;
  }

  export interface Force {
    (alpha: number): void;
    initialize?: (nodes: SimNode[], ...args: unknown[]) => void;
  }

  export interface Simulation<N extends SimNode = SimNode> {
    nodes(): N[];
    nodes(nodes: N[]): this;
    force(name: string): Force | undefined;
    force(name: string, force: Force | null): this;
    alpha(alpha: number): this;
    alphaDecay(decay: number): this;
    alphaMin(min: number): this;
    tick(iterations?: number): this;
    stop(): this;
    restart(): this;
    randomSource(source: () => number): this;
  }

  export interface ManyBodyForce extends Force {
    strength(strength: number): this;
  }

  export interface LinkForce<N = SimNode> extends Force {
    links(links: SimLink<N>[]): this;
    id(id: (node: N) => string): this;
    distance(distance: number): this;
    strength(strength: number): this;
  }

  export interface CenterForce extends Force {
    strength(strength: number): this;
  }

  export function forceSimulation<N extends SimNode = SimNode>(
    nodes?: N[],
    numDimensions?: number,
  ): Simulation<N>;
  export function forceManyBody(): ManyBodyForce;
  export function forceLink<N extends SimNode = SimNode>(
    links?: SimLink<N>[],
  ): LinkForce<N>;
  export function forceCenter(x?: number, y?: number, z?: number): CenterForce;
  export function forceCollide(radius?: number | ((node: SimNode) => number)): Force;
}

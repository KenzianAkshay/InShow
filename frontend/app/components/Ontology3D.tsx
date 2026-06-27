"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  Environment,
  Html,
  Lightformer,
  Line,
  OrbitControls,
} from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";
import {
  Layers,
  Maximize2,
  Rotate3d,
  Tag,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { compute3DLayout, type Vec3 } from "@/lib/ontology3d";

export type GNode = {
  id: string;
  label: string;
  color: string;
  size: number; // sphere radius
  count?: number; // instance count (schema nodes)
};
export type GEdge = { from: string; to: string; type: string; count?: number };

type Rel = { dir: "in" | "out"; type: string; count?: number; other: string };

function Node({
  position,
  radius,
  color,
  active,
  focus,
  dim,
  label,
  showLabel,
  onSelect,
  onHover,
}: {
  position: Vec3;
  radius: number;
  color: string;
  active: boolean;
  focus: boolean;
  dim: boolean;
  label: string;
  showLabel: boolean;
  onSelect: () => void;
  onHover: (hovering: boolean) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const target = useMemo(() => new THREE.Vector3(), []);

  useFrame((state) => {
    const mesh = ref.current;
    if (!mesh) return;
    const t = state.clock.elapsedTime;
    const base = focus ? 1.3 : 1;
    const s = active ? 1.4 + Math.sin(t * 4) * 0.12 : base;
    target.set(s, s, s);
    mesh.scale.lerp(target, 0.15);
    const mat = mesh.material as THREE.MeshStandardMaterial;
    mat.emissiveIntensity = THREE.MathUtils.lerp(
      mat.emissiveIntensity,
      active ? 2.8 : focus ? 1.4 : 0.18,
      0.1,
    );
    mat.opacity = THREE.MathUtils.lerp(mat.opacity, dim ? 0.16 : 1, 0.12);
  });

  const highlight = active || focus;

  return (
    <group position={position}>
      <mesh
        ref={ref}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          onHover(false);
          document.body.style.cursor = "auto";
        }}
      >
        <sphereGeometry args={[radius, 32, 32]} />
        <meshStandardMaterial
          color={highlight ? "#ff7a59" : color}
          emissive={highlight ? "#ff7a59" : color}
          emissiveIntensity={0.18}
          metalness={0.85}
          roughness={0.26}
          transparent
          opacity={1}
        />
      </mesh>
      {showLabel && (
        <Html
          center
          distanceFactor={11}
          position={[0, radius + 0.4, 0]}
          style={{ pointerEvents: "none" }}
          zIndexRange={[10, 0]}
        >
          <div
            className="whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
            style={{
              color: highlight ? "#fff" : "var(--foreground)",
              background: highlight
                ? "#ef5f3d"
                : "color-mix(in oklab, var(--popover) 80%, transparent)",
              border: "1px solid var(--border)",
              backdropFilter: "blur(4px)",
            }}
          >
            {label}
          </div>
        </Html>
      )}
    </group>
  );
}

function Edge({
  a,
  b,
  type,
  count,
  lit,
  dim,
  showLabel,
}: {
  a: Vec3;
  b: Vec3;
  type: string;
  count?: number;
  lit: boolean;
  dim: boolean;
  showLabel: boolean;
}) {
  const { conePos, quat, mid } = useMemo(() => {
    const av = new THREE.Vector3(...a);
    const bv = new THREE.Vector3(...b);
    const dir = bv.clone().sub(av);
    const len = dir.length() || 1;
    const ndir = dir.clone().normalize();
    const cone = av.clone().add(ndir.clone().multiplyScalar(Math.max(0, len - 0.55)));
    const q = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      ndir,
    );
    return {
      conePos: cone.toArray() as Vec3,
      quat: q.toArray() as [number, number, number, number],
      mid: av.clone().lerp(bv, 0.5).toArray() as Vec3,
    };
  }, [a, b]);

  const color = lit ? "#ff7a59" : "#8aa0d6";
  const opacity = dim ? 0.05 : lit ? 1 : 0.38;

  return (
    <>
      <Line
        points={[a, b]}
        color={color}
        lineWidth={lit ? 2.6 : 1}
        transparent
        opacity={opacity}
      />
      <mesh position={conePos} quaternion={quat}>
        <coneGeometry args={[0.12, 0.3, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={lit ? 1.4 : 0.15}
          transparent
          opacity={dim ? 0.07 : opacity}
        />
      </mesh>
      {showLabel && type && (
        <Html
          center
          distanceFactor={10}
          position={mid}
          style={{ pointerEvents: "none" }}
          zIndexRange={[6, 0]}
        >
          <div
            className="whitespace-nowrap rounded px-1 py-0.5 text-[9.5px] font-bold uppercase tracking-wide"
            style={{
              color: lit ? "#fff" : "var(--muted-foreground)",
              background: lit
                ? "#ef5f3d"
                : "color-mix(in oklab, var(--popover) 72%, transparent)",
              border: "1px solid var(--border)",
              backdropFilter: "blur(4px)",
            }}
          >
            {type}
            {count != null && count > 1 ? ` ×${count}` : ""}
          </div>
        </Html>
      )}
    </>
  );
}

function Scene({
  nodes,
  edges,
  activeNodes,
  selected,
  hovered,
  onSelect,
  onHover,
  controlsRef,
  autoRotate,
  alwaysLabels,
  showAllLabels,
}: {
  nodes: GNode[];
  edges: GEdge[];
  activeNodes: Set<string>;
  selected: string | null;
  hovered: string | null;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  controlsRef: React.MutableRefObject<THREE.EventDispatcher | null>;
  autoRotate: boolean;
  alwaysLabels: boolean;
  showAllLabels: boolean;
}) {
  const radius = nodes.length > 80 ? 9 : 6;
  const positions = useMemo(
    () =>
      compute3DLayout(
        nodes.map((n) => n.id),
        edges,
        radius,
      ),
    [nodes, edges, radius],
  );

  const neighbourhood = useMemo(() => {
    if (!selected) return null;
    const s = new Set<string>([selected]);
    for (const e of edges) {
      if (e.from === selected) s.add(e.to);
      if (e.to === selected) s.add(e.from);
    }
    return s;
  }, [selected, edges]);

  const focusRef = useRef<THREE.Vector3 | null>(null);
  useEffect(() => {
    focusRef.current =
      selected && positions[selected]
        ? new THREE.Vector3(...positions[selected])
        : null;
  }, [selected, positions]);

  useFrame(() => {
    const c = controlsRef.current as unknown as {
      target: THREE.Vector3;
      object: THREE.Camera;
      update: () => void;
    } | null;
    if (!c || !focusRef.current) return;
    const goal = focusRef.current;
    c.target.lerp(goal, 0.1);
    const offset = c.object.position.clone().sub(c.target);
    offset.setLength(THREE.MathUtils.lerp(offset.length(), 7, 0.06));
    c.object.position.copy(c.target.clone().add(offset));
    c.update();
    if (c.target.distanceTo(goal) < 0.04) focusRef.current = null;
  });

  return (
    <>
      <ambientLight intensity={0.45} />
      <directionalLight position={[6, 8, 5]} intensity={1.1} />
      <pointLight position={[-8, -4, -6]} intensity={0.6} color="#ff7a59" />

      <Suspense fallback={null}>
        <Environment resolution={256} frames={1}>
          <Lightformer intensity={2} position={[0, 5, -5]} scale={12} />
          <Lightformer
            intensity={1.1}
            position={[-6, 2, 5]}
            scale={9}
            color="#bcd4ff"
          />
          <Lightformer
            intensity={1.1}
            position={[6, -3, 3]}
            scale={9}
            color="#ffd9c2"
          />
        </Environment>
      </Suspense>

      {edges.map((e, i) => {
        const a = positions[e.from];
        const b = positions[e.to];
        if (!a || !b) return null;
        const activeEdge = activeNodes.has(e.from) && activeNodes.has(e.to);
        const incidentSel =
          !!selected && (e.from === selected || e.to === selected);
        const incidentHover =
          !!hovered && (e.from === hovered || e.to === hovered);
        const lit = activeEdge || incidentSel || incidentHover;
        const dim = !!selected && !incidentSel;
        return (
          <Edge
            key={i}
            a={a}
            b={b}
            type={e.type}
            count={e.count}
            lit={lit}
            dim={dim}
            showLabel={showAllLabels || alwaysLabels || lit}
          />
        );
      })}

      {nodes.map((n) => {
        const p = positions[n.id];
        if (!p) return null;
        const active = activeNodes.has(n.id);
        const inFocus = neighbourhood?.has(n.id) ?? false;
        const dim = !!neighbourhood && !inFocus;
        const showLabel =
          alwaysLabels ||
          active ||
          n.id === selected ||
          n.id === hovered ||
          inFocus;
        return (
          <Node
            key={n.id}
            position={p}
            radius={n.size}
            color={n.color}
            active={active}
            focus={!!selected && n.id === selected}
            dim={dim}
            label={n.label}
            showLabel={showLabel}
            onSelect={() => onSelect(n.id)}
            onHover={(h) => onHover(h ? n.id : null)}
          />
        );
      })}

      <OrbitControls
        ref={controlsRef as never}
        makeDefault
        enableDamping
        dampingFactor={0.1}
        enablePan
        autoRotate={autoRotate}
        autoRotateSpeed={0.6}
        minDistance={3}
        maxDistance={70}
      />

      <EffectComposer>
        <Bloom
          intensity={0.9}
          luminanceThreshold={0.5}
          luminanceSmoothing={0.2}
          mipmapBlur
        />
      </EffectComposer>
    </>
  );
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

export default function Ontology3D({
  nodes,
  edges,
  activeNodes,
  alwaysLabels,
  onDrill,
}: {
  nodes: GNode[];
  edges: GEdge[];
  activeNodes: Set<string>;
  alwaysLabels: boolean;
  onDrill?: (id: string) => void;
}) {
  const controlsRef = useRef<THREE.EventDispatcher | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [autoRotate, setAutoRotate] = useState(true);
  const [showAllLabels, setShowAllLabels] = useState(false);

  // Reset interaction state when the underlying graph changes (e.g. drill-down).
  useEffect(() => {
    setSelected(null);
    setHovered(null);
  }, [nodes, edges]);

  const select = useCallback((id: string | null) => {
    setSelected(id);
    if (id) setAutoRotate(false);
  }, []);

  const dolly = useCallback((scale: number) => {
    const c = controlsRef.current as unknown as {
      target: THREE.Vector3;
      object: THREE.Camera;
      update: () => void;
      minDistance: number;
      maxDistance: number;
    } | null;
    if (!c) return;
    const offset = c.object.position.clone().sub(c.target);
    const dist = THREE.MathUtils.clamp(
      offset.length() * scale,
      c.minDistance,
      c.maxDistance,
    );
    offset.setLength(dist);
    c.object.position.copy(c.target.clone().add(offset));
    c.update();
  }, []);

  const reset = useCallback(() => {
    setSelected(null);
    const c = controlsRef.current as unknown as { reset?: () => void } | null;
    c?.reset?.();
  }, []);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selected) ?? null,
    [nodes, selected],
  );
  const labelOf = useMemo(() => {
    const m = new Map(nodes.map((n) => [n.id, n.label]));
    return (id: string) => m.get(id) ?? id;
  }, [nodes]);

  const rels = useMemo<Rel[]>(() => {
    if (!selected) return [];
    return edges.flatMap((e): Rel[] => {
      if (e.from === selected)
        return [{ dir: "out", type: e.type, count: e.count, other: e.to }];
      if (e.to === selected)
        return [{ dir: "in", type: e.type, count: e.count, other: e.from }];
      return [];
    });
  }, [selected, edges]);

  return (
    <div className="relative h-full w-full">
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [0, 2, 18], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
        onPointerMissed={() => setSelected(null)}
      >
        <Scene
          nodes={nodes}
          edges={edges}
          activeNodes={activeNodes}
          selected={selected}
          hovered={hovered}
          onSelect={select}
          onHover={setHovered}
          controlsRef={controlsRef}
          autoRotate={autoRotate}
          alwaysLabels={alwaysLabels}
          showAllLabels={showAllLabels}
        />
      </Canvas>

      <div className="absolute right-2 top-2 flex flex-col gap-1.5">
        <ControlButton label="Zoom in" onClick={() => dolly(0.8)}>
          <ZoomIn className="size-4" />
        </ControlButton>
        <ControlButton label="Zoom out" onClick={() => dolly(1.25)}>
          <ZoomOut className="size-4" />
        </ControlButton>
        <ControlButton label="Reset view" onClick={reset}>
          <Maximize2 className="size-4" />
        </ControlButton>
        <ControlButton
          label="Auto-rotate"
          active={autoRotate}
          onClick={() => setAutoRotate((v) => !v)}
        >
          <Rotate3d className="size-4" />
        </ControlButton>
        <ControlButton
          label="Show all relationship labels"
          active={showAllLabels}
          onClick={() => setShowAllLabels((v) => !v)}
        >
          <Tag className="size-4" />
        </ControlButton>
      </div>

      {selectedNode && (
        <div className="absolute bottom-2 left-2 max-h-[64%] w-60 overflow-y-auto rounded-xl border border-border bg-[var(--glass-bg)] p-3 backdrop-blur-md">
          <div className="truncate text-sm font-bold" title={selectedNode.id}>
            {selectedNode.label}
          </div>
          {selectedNode.count != null && (
            <div className="text-xs text-muted-foreground">
              {selectedNode.count} instance{selectedNode.count === 1 ? "" : "s"}
            </div>
          )}
          {onDrill && selectedNode.count != null && (
            <button
              type="button"
              onClick={() => onDrill(selectedNode.id)}
              className="ring-focus mt-2 flex w-full items-center justify-center gap-1.5 rounded-md bg-[linear-gradient(180deg,#ff9678,#ff7a59_55%,#ef5f3d)] px-2 py-1.5 text-xs font-semibold text-white"
            >
              <Layers className="size-3.5" />
              Explore instances
            </button>
          )}
          <div className="mt-2 text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground">
            {rels.length} relationship{rels.length === 1 ? "" : "s"}
          </div>
          <div className="mt-1 space-y-1">
            {rels.map((r, i) => (
              <button
                key={i}
                type="button"
                onClick={() => select(r.other)}
                className="ring-focus flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-xs transition-colors hover:bg-secondary"
              >
                <span className="shrink-0 text-[0.62rem] font-bold uppercase tracking-wide text-accent">
                  {r.dir === "out" ? "→" : "←"} {r.type}
                  {r.count != null && r.count > 1 ? ` ×${r.count}` : ""}
                </span>
                <span className="truncate text-muted-foreground">
                  {labelOf(r.other)}
                </span>
              </button>
            ))}
            {rels.length === 0 && (
              <p className="text-xs text-muted-foreground">No relationships.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

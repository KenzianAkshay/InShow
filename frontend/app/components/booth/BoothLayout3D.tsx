"use client";

import { Canvas } from "@react-three/fiber";
import { Environment, Html, Lightformer, Line, OrbitControls } from "@react-three/drei";
import { Artifact } from "@/lib/api";

type Booth = Extract<Artifact, { type: "booth_layout" }>;

export default function BoothLayout3D({ artifact }: { artifact: Booth }) {
  const { booth, zones } = artifact;
  const W = booth.width;
  const D = booth.depth;
  const open = new Set(booth.open_sides);

  // Booth coords → centred 3D space. Front (y=0) faces +Z (toward the camera).
  const toX = (x: number, w: number) => x + w / 2 - W / 2;
  const toZ = (y: number, h: number) => D / 2 - (y + h / 2);
  const span = Math.max(W, D);

  const corners = {
    front: [
      [-W / 2, 0.02, D / 2],
      [W / 2, 0.02, D / 2],
    ],
    back: [
      [-W / 2, 0.02, -D / 2],
      [W / 2, 0.02, -D / 2],
    ],
    left: [
      [-W / 2, 0.02, D / 2],
      [-W / 2, 0.02, -D / 2],
    ],
    right: [
      [W / 2, 0.02, D / 2],
      [W / 2, 0.02, -D / 2],
    ],
  } as const;

  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [W * 0.25, span * 1.05, D * 0.85 + span * 0.5], fov: 45 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[span, span * 1.4, span]} intensity={1.1} castShadow />
      <Environment resolution={128} frames={1}>
        <Lightformer intensity={1.6} position={[0, 6, 2]} scale={12} />
        <Lightformer intensity={0.9} position={[-6, 3, -4]} scale={8} color="#bcd4ff" />
      </Environment>

      {/* booth floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[W, D]} />
        <meshStandardMaterial color="#8895a7" roughness={0.95} metalness={0.05} opacity={0.5} transparent />
      </mesh>

      {/* booth perimeter: accent dashed on open sides, solid otherwise */}
      {Object.entries(corners).map(([side, pts]) => (
        <Line
          key={side}
          points={pts as unknown as [number, number, number][]}
          color={open.has(side) ? "#2bc6df" : "#8895a7"}
          lineWidth={open.has(side) ? 2.5 : 1.5}
          dashed={open.has(side)}
          dashSize={0.3}
          gapSize={0.2}
        />
      ))}

      {/* zones as extruded volumes */}
      {zones.map((z) => {
        const height = Math.max(0.1, z.height ?? 1.2);
        return (
          <group key={z.id} position={[toX(z.x, z.w), 0, toZ(z.y, z.h)]}>
            <mesh position={[0, height / 2, 0]} castShadow>
              <boxGeometry args={[z.w, height, z.h]} />
              <meshStandardMaterial color={z.color ?? "#7c93c9"} roughness={0.45} metalness={0.15} />
            </mesh>
            <Html
              position={[0, height + 0.35, 0]}
              center
              distanceFactor={span * 1.2}
              style={{ pointerEvents: "none" }}
              zIndexRange={[10, 0]}
            >
              <div
                className="whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold"
                style={{
                  color: "var(--foreground)",
                  background: "color-mix(in oklab, var(--popover) 80%, transparent)",
                  border: "1px solid var(--border)",
                }}
              >
                {z.name}
              </div>
            </Html>
          </group>
        );
      })}

      <OrbitControls
        enableDamping
        dampingFactor={0.1}
        target={[0, 0.5, 0]}
        minDistance={span * 0.4}
        maxDistance={span * 4}
        maxPolarAngle={Math.PI / 2.05}
      />
    </Canvas>
  );
}

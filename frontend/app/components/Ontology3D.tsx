"use client";

import { Suspense, useMemo, useRef } from "react";
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
import { Ontology } from "@/lib/api";
import {
  colorForLabel,
  compute3DLayout,
  displayName,
  type Vec3,
} from "@/lib/ontology3d";

function Node({
  position,
  color,
  active,
  label,
  showLabel,
}: {
  position: Vec3;
  color: string;
  active: boolean;
  label: string;
  showLabel: boolean;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const target = useMemo(() => new THREE.Vector3(), []);

  useFrame((state) => {
    const mesh = ref.current;
    if (!mesh) return;
    const t = state.clock.elapsedTime;
    const s = active ? 1.4 + Math.sin(t * 4) * 0.12 : 1;
    target.set(s, s, s);
    mesh.scale.lerp(target, 0.15);
    const mat = mesh.material as THREE.MeshStandardMaterial;
    mat.emissiveIntensity = THREE.MathUtils.lerp(
      mat.emissiveIntensity,
      active ? 2.8 : 0.18,
      0.1,
    );
  });

  return (
    <group position={position}>
      <mesh ref={ref}>
        <sphereGeometry args={[0.4, 32, 32]} />
        <meshStandardMaterial
          color={active ? "#ff7a59" : color}
          emissive={active ? "#ff7a59" : color}
          emissiveIntensity={0.18}
          metalness={0.85}
          roughness={0.26}
        />
      </mesh>
      {showLabel && (
        <Html
          center
          distanceFactor={11}
          position={[0, 0.75, 0]}
          style={{ pointerEvents: "none" }}
          zIndexRange={[10, 0]}
        >
          <div
            className="whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
            style={{
              color: active ? "#fff" : "var(--foreground)",
              background: active
                ? "#ef5f3d"
                : "color-mix(in oklab, var(--popover) 78%, transparent)",
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

function Scene({
  ontology,
  activeNodes,
}: {
  ontology: Ontology;
  activeNodes: Set<string>;
}) {
  const positions = useMemo(
    () =>
      compute3DLayout(
        ontology.nodes.map((n) => n.uid),
        ontology.edges,
      ),
    [ontology],
  );

  const labelFor = useMemo(() => {
    const m = new Map(ontology.nodes.map((n) => [n.uid, n.label]));
    return (uid: string) => m.get(uid) ?? "Entity";
  }, [ontology]);

  const showAllLabels = ontology.nodes.length <= 28;

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

      {/* Edges */}
      {ontology.edges.map((e, i) => {
        const a = positions[e.from];
        const b = positions[e.to];
        if (!a || !b) return null;
        const active = activeNodes.has(e.from) && activeNodes.has(e.to);
        return (
          <Line
            key={i}
            points={[a, b]}
            color={active ? "#ff7a59" : "#7c93c9"}
            lineWidth={active ? 2.6 : 1}
            transparent
            opacity={active ? 1 : 0.34}
          />
        );
      })}

      {/* Nodes */}
      {ontology.nodes.map((n) => {
        const p = positions[n.uid];
        if (!p) return null;
        const active = activeNodes.has(n.uid);
        return (
          <Node
            key={n.uid}
            position={p}
            color={colorForLabel(labelFor(n.uid))}
            active={active}
            label={displayName(n.uid)}
            showLabel={showAllLabels || active}
          />
        );
      })}

      <OrbitControls
        enableDamping
        dampingFactor={0.1}
        autoRotate
        autoRotateSpeed={0.6}
        minDistance={4}
        maxDistance={40}
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

export default function Ontology3D({
  ontology,
  activeNodes,
}: {
  ontology: Ontology;
  activeNodes: Set<string>;
}) {
  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 2, 16], fov: 50 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: "transparent" }}
    >
      <Scene ontology={ontology} activeNodes={activeNodes} />
    </Canvas>
  );
}

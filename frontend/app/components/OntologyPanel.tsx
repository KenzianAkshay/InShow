"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Network } from "lucide-react";
import { api, Ontology, Traversal } from "@/lib/api";
import { colorForLabel } from "@/lib/ontology3d";
import { Skeleton } from "@/app/components/ui/skeleton";

// Three.js needs `window`, so the WebGL scene is loaded client-side only.
const Ontology3D = dynamic(() => import("@/app/components/Ontology3D"), {
  ssr: false,
  loading: () => <Skeleton className="h-[380px] w-full rounded-none" />,
});

export default function OntologyPanel({
  traversal,
  projectId,
}: {
  traversal: Traversal | null;
  projectId: number | null;
}) {
  const [ontology, setOntology] = useState<Ontology | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (projectId === null) return;
    api
      .getOntology(projectId)
      .then(setOntology)
      .catch(() => setOntology(null));
  }, [projectId]);

  // Reveal the traversal path one hop at a time, lighting up nodes in sequence.
  const pathNodes = useMemo(() => traversal?.nodes ?? [], [traversal]);
  const traversalKey = JSON.stringify(pathNodes);
  useEffect(() => {
    if (pathNodes.length === 0) return;
    setStep(0);
    const timer = setInterval(() => {
      setStep((s) => {
        if (s >= pathNodes.length) {
          clearInterval(timer);
          return s;
        }
        return s + 1;
      });
    }, 400);
    return () => clearInterval(timer);
  }, [traversalKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeNodes = useMemo(
    () => new Set(pathNodes.slice(0, step)),
    [pathNodes, step],
  );

  const hasGraph = ontology && ontology.nodes.length > 0;

  return (
    <div className="glass overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border/70 px-4 py-2.5 text-sm font-semibold">
        <Network className="size-4 text-muted-foreground" />
        Ontology layer
        {hasGraph && (
          <span className="font-normal text-muted-foreground">
            · {ontology!.nodes.length} nodes · {ontology!.classes.length} classes
          </span>
        )}
      </div>

      {!hasGraph ? (
        <p className="px-4 py-8 text-sm text-muted-foreground">
          No ontology yet. Ingest a dataset and build the ontology from an
          agent&apos;s setup page.
        </p>
      ) : (
        <>
          <div className="relative h-[380px] w-full">
            <Ontology3D ontology={ontology!} activeNodes={activeNodes} />
            <span className="pointer-events-none absolute bottom-2 left-3 text-[0.68rem] text-muted-foreground">
              Drag to orbit · scroll to zoom
            </span>
          </div>

          <div className="flex flex-wrap gap-x-3.5 gap-y-1.5 border-t border-border/70 px-4 py-3">
            {ontology!.classes.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
              >
                <span
                  className="inline-block size-2.5 rounded-full"
                  style={{ background: colorForLabel(c) }}
                />
                {c}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

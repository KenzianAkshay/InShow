"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { ChevronLeft, Network } from "lucide-react";
import {
  api,
  OntologyInstances,
  OntologySchema,
  Traversal,
} from "@/lib/api";
import { colorForLabel, displayName } from "@/lib/ontology3d";
import type { GEdge, GNode } from "@/app/components/Ontology3D";
import { Skeleton } from "@/app/components/ui/skeleton";

// Three.js needs `window`, so the WebGL scene is loaded client-side only.
const Ontology3D = dynamic(() => import("@/app/components/Ontology3D"), {
  ssr: false,
  loading: () => <Skeleton className="h-[380px] w-full rounded-none" />,
});

// The schema map is a lightweight SVG view (no WebGL).
const OntologySchema2D = dynamic(
  () => import("@/app/components/OntologySchema2D"),
  { ssr: false, loading: () => <Skeleton className="h-[380px] w-full rounded-none" /> },
);

type View =
  | { kind: "schema" }
  | { kind: "class"; label: string; data: OntologyInstances }
  | { kind: "traversal" };

function classOf(uid: string): string {
  const i = uid.indexOf(":");
  return i === -1 ? uid : uid.slice(0, i);
}

// Schema node radius scales gently with instance count so big classes read as
// hubs without dwarfing the rest.
function radiusForCount(count: number): number {
  return Math.min(1.4, 0.36 + 0.16 * Math.log2(1 + count));
}

export default function OntologyPanel({
  traversal,
  projectId,
}: {
  traversal: Traversal | null;
  projectId: number | null;
}) {
  const [schema, setSchema] = useState<OntologySchema | null>(null);
  const [view, setView] = useState<View>({ kind: "schema" });
  const [drillLoading, setDrillLoading] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (projectId === null) return;
    api
      .getOntologySchema(projectId)
      .then(setSchema)
      .catch(() => setSchema(null));
  }, [projectId]);

  // A new chat traversal switches to the traversal view and reveals the path
  // one hop at a time.
  const pathNodes = useMemo(() => traversal?.nodes ?? [], [traversal]);
  const traversalKey = JSON.stringify(pathNodes);
  useEffect(() => {
    if (pathNodes.length === 0) return;
    setView({ kind: "traversal" });
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

  function openClass(label: string) {
    if (projectId === null) return;
    setDrillLoading(true);
    api
      .getClassInstances(projectId, label)
      .then((data) => setView({ kind: "class", label, data }))
      .catch(() => {})
      .finally(() => setDrillLoading(false));
  }

  const { gnodes, gedges, alwaysLabels, onDrill } = useMemo<{
    gnodes: GNode[];
    gedges: GEdge[];
    alwaysLabels: boolean;
    onDrill?: (id: string) => void;
  }>(() => {
    if (view.kind === "traversal") {
      const gnodes = pathNodes.map((uid) => ({
        id: uid,
        label: displayName(uid),
        color: colorForLabel(classOf(uid)),
        size: 0.42,
      }));
      return {
        gnodes,
        gedges: traversal?.edges ?? [],
        alwaysLabels: gnodes.length <= 25,
      };
    }
    if (view.kind === "class") {
      const gnodes = view.data.nodes.map((n) => ({
        id: n.uid,
        label: displayName(n.uid),
        color: colorForLabel(n.label),
        size: 0.42,
      }));
      return {
        gnodes,
        gedges: view.data.edges,
        alwaysLabels: view.data.nodes.length <= 25,
      };
    }
    const gnodes = (schema?.classes ?? []).map((c) => ({
      id: c.name,
      label: c.name,
      color: colorForLabel(c.name),
      size: radiusForCount(c.count),
      count: c.count,
    }));
    return {
      gnodes,
      gedges: schema?.edges ?? [],
      alwaysLabels: true,
      onDrill: openClass,
    };
  }, [view, schema, traversalKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeNodes = useMemo(
    () =>
      view.kind === "traversal"
        ? new Set(pathNodes.slice(0, step))
        : new Set<string>(),
    [view, pathNodes, step],
  );

  const classCount = schema?.classes.length ?? 0;
  const relCount = schema?.edges.length ?? 0;
  const hasSchema = classCount > 0;

  const header =
    view.kind === "class"
      ? `${view.label} · ${gnodes.length} shown`
      : view.kind === "traversal"
        ? `Chat traversal · ${pathNodes.length} nodes`
        : `${classCount} classes · ${relCount} relationship types`;

  return (
    <div className="glass flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center gap-2 border-b border-border/70 px-3 py-2.5 text-sm font-semibold">
        {view.kind !== "schema" ? (
          <button
            type="button"
            onClick={() => setView({ kind: "schema" })}
            className="ring-focus inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <ChevronLeft className="size-3.5" />
            Schema
          </button>
        ) : (
          <Network className="size-4 text-muted-foreground" />
        )}
        <span className="truncate">
          {view.kind === "schema" ? "Ontology layer" : "Ontology"}
        </span>
        {hasSchema && (
          <span className="truncate font-normal text-muted-foreground">
            · {header}
          </span>
        )}
        {drillLoading && (
          <span className="ml-auto text-xs font-normal text-muted-foreground">
            Loading…
          </span>
        )}
      </div>

      {!hasSchema ? (
        <p className="px-4 py-8 text-sm text-muted-foreground">
          No ontology yet. Ingest a dataset and build the ontology from an
          agent&apos;s setup page.
        </p>
      ) : (
        <>
          <div className="relative min-h-[180px] w-full flex-1">
            {view.kind === "schema" ? (
              <OntologySchema2D
                nodes={gnodes}
                edges={gedges}
                onDrill={onDrill}
              />
            ) : (
              <Ontology3D
                nodes={gnodes}
                edges={gedges}
                activeNodes={activeNodes}
                alwaysLabels={alwaysLabels}
                onDrill={onDrill}
              />
            )}
            <span className="pointer-events-none absolute bottom-2 left-3 text-[0.68rem] text-muted-foreground">
              {view.kind === "schema"
                ? "Class map · drag to pan · scroll to zoom · click a class to explore"
                : "Click a node to navigate · scroll to zoom"}
            </span>
          </div>

          {view.kind === "schema" && (
            <div className="flex shrink-0 flex-wrap gap-x-3.5 gap-y-1.5 border-t border-border/70 px-4 py-3">
              {schema!.classes.slice(0, 12).map((c) => (
                <span
                  key={c.name}
                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
                >
                  <span
                    className="inline-block size-2.5 rounded-full"
                    style={{ background: colorForLabel(c.name) }}
                  />
                  {c.name}
                  <span className="tabular-nums opacity-60">{c.count}</span>
                </span>
              ))}
              {classCount > 12 && (
                <span className="text-xs text-muted-foreground">
                  +{classCount - 12} more
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

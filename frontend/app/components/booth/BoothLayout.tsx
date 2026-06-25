"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { Box, Check, Grid2x2, TriangleAlert } from "lucide-react";
import { Artifact } from "@/lib/api";
import { cn } from "@/lib/utils";
import BoothLayout2D from "./BoothLayout2D";
import { Skeleton } from "@/app/components/ui/skeleton";

type Booth = Extract<Artifact, { type: "booth_layout" }>;

// Three.js is client-only; load the 3D view lazily.
const BoothLayout3D = dynamic(() => import("./BoothLayout3D"), {
  ssr: false,
  loading: () => <Skeleton className="h-[360px] w-full" />,
});

export default function BoothLayout({ artifact }: { artifact: Booth }) {
  const [view, setView] = useState<"2d" | "3d">("2d");
  const checks = artifact.validation?.checks ?? [];
  const repaired = artifact.validation?.repaired ?? 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          {artifact.booth.type} · {artifact.booth.width}×{artifact.booth.depth}{" "}
          {artifact.units ?? "m"}
        </span>
        <div className="glass flex rounded-full p-0.5">
          {(
            [
              ["2d", "2D", Grid2x2],
              ["3d", "3D", Box],
            ] as const
          ).map(([v, label, Icon]) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors",
                view === v
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-[var(--radius-md)] border border-border/70 bg-[var(--secondary)]/30">
        {view === "2d" ? (
          <div className="p-2">
            <BoothLayout2D artifact={artifact} />
          </div>
        ) : (
          <div className="h-[360px] w-full">
            <BoothLayout3D artifact={artifact} />
          </div>
        )}
      </div>

      {checks.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {repaired > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              repaired ×{repaired}
            </span>
          )}
          {checks.map((c) => (
            <span
              key={c.name}
              title={c.detail || c.name}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                c.ok
                  ? "border-transparent bg-success/15 text-success"
                  : "border-transparent bg-destructive/15 text-destructive",
              )}
            >
              {c.ok ? <Check className="size-3" /> : <TriangleAlert className="size-3" />}
              {c.name.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
